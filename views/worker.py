# views/worker.py
import streamlit as st
import base64
import os
from datetime import datetime
from io import BytesIO
import pandas as pd

from core.database import UnitOfWork
from core.session import session_manager
from core.enums import ActionType, ItemStatus
from services.ocr_service import ocr_service
from services.ai_service import ai_service
from services.notification_service import notification_service

def save_image(image_bytes: bytes) -> str:
    """حفظ الصورة مع ضغط وتحسين"""
    from PIL import Image
    from core.config import settings
    
    # تأكيد إنشاء مجلد uploads
    upload_dir = settings.BASE_DIR / "uploads"
    upload_dir.mkdir(exist_ok=True)
    
    filename = f"item_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{abs(hash(image_bytes)) % 10000}.jpg"
    filepath = os.path.join(upload_dir, filename)
    
    img = Image.open(BytesIO(image_bytes))
    max_size = settings.MAX_IMAGE_SIZE
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # تحويل لـ RGB لو الصورة فيها شفافية عشان نقدر نحفظها كـ JPG
    if img.mode != 'RGB':
        img = img.convert('RGB')
        
    img.save(filepath, settings.IMAGE_FORMAT, quality=settings.IMAGE_QUALITY, optimize=True)
    return filepath

def worker_view():
    """عرض العامل الرئيسي"""
    worker_input_view()

def worker_input_view():
    """عرض إدخال القطع"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### إدخال قطع جديدة")
    
    if 'worker_session' not in st.session_state:
        st.session_state.worker_session = []
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_file = st.file_uploader("رفع صورة القطعة", type=['jpg', 'png', 'jpeg', 'webp'])
    
    with col2:
        item_categories = ["بوردة", "أنبوبة", "كابل", "محول", "أخرى"]
        selected_cat = st.selectbox("التصنيف العام", item_categories)
    
    if selected_cat == "أخرى":
        item_type = st.text_input("نوع القطعة")
    else:
        item_type = selected_cat
    
    image_path = None
    image_bytes = None
    
    if uploaded_file:
        image_bytes = uploaded_file.getvalue()
        quality_ok, quality_msg = ocr_service.check_quality(image_bytes)
        if not quality_ok:
            st.warning(quality_msg)
        else:
            image_path = save_image(image_bytes)
            st.image(uploaded_file, width=150)
            
            # نتأكد إن نتيجة الذكاء الاصطناعي المخزنة (لو موجودة) بتاعة نفس الصورة دي، وإلا نمسحها
            current_hash = hash(image_bytes)
            if st.session_state.get("worker_ai_image_hash") != current_hash:
                st.session_state.worker_ai_result = None
                st.session_state.worker_ai_image_hash = current_hash
            
            if st.button("تحليل الصورة بالذكاء الاصطناعي"):
                image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                ai_input = item_type if item_type else "غير معروف - يرجى التعرف على القطعة من الصورة مباشرة"
                
                with st.spinner("جاري تحليل الصورة بالذكاء الاصطناعي..."):
                    brand, category, ai_part, comp, add, val, insight = ai_service.analyze_part(
                        ai_input, image_base64
                    )
                    
                    if insight == "Pending_AI_Quota":
                        st.warning("باقة الذكاء الاصطناعي مستنفذة حالياً. جاري محاولة استخراج تقريبي محلياً (أقل دقة)...")
                        fallback_text, fallback_part = ocr_service.extract_text(image_bytes)
                        if fallback_text and "خطأ" not in fallback_text:
                            st.info(f"نص تقريبي مستخرج محلياً: {fallback_text[:150]}")
                            st.session_state.worker_ai_result = {
                                "brand": "غير معروف", "category": item_type, "part_number": fallback_part or "PENDING",
                                "compatible_model": "", "additional_compatibility": "",
                                "market_value": "", "insight": "تم الاستخراج محلياً بسبب استنفاذ باقة الذكاء الاصطناعي - يحتاج مراجعة يدوية"
                            }
                        else:
                            st.error("تعذر استخراج أي نص من الصورة محلياً أيضاً.")
                    elif insight and not insight.startswith(("خطأ", "Pending", "تحذير")):
                        st.session_state.worker_ai_result = {
                            "brand": brand, "category": category, "part_number": ai_part,
                            "compatible_model": comp, "additional_compatibility": add,
                            "market_value": val, "insight": insight
                        }
                    else:
                        st.error(insight or "تعذر تحليل الصورة.")
    
    ai_result = st.session_state.get("worker_ai_result")
    if ai_result:
        st.markdown("#### نتائج تحليل الذكاء الاصطناعي")
        st.info(f"**الماركة:** {ai_result['brand']}")
        st.info(f"**اسم/نوع القطعة:** {ai_result['category']}")
        st.info(f"**رقم القطعة:** {ai_result['part_number']}")
        st.info(f"**الجهاز المتوافق:** {ai_result['compatible_model'] or 'غير محدد'}")
        st.info(f"**توافقية إضافية:** {ai_result['additional_compatibility'] or 'لا يوجد'}")
        st.info(f"**القيمة السوقية التقديرية:** {ai_result['market_value'] or 'غير محددة'}")
        st.caption(f"**ملاحظات فنية:** {ai_result['insight']}")
    
    # الموقع
    with UnitOfWork() as uow:
        repo = uow.get_repository(ItemRepository)
        locations = repo.session.query(InventoryItem.location).distinct().filter(
            InventoryItem.location.isnot(None)
        ).all()
        existing_locs = [loc[0] for loc in locations if loc[0]]
    
    loc_options = existing_locs + ["إضافة جديد"]
    chosen_loc = st.selectbox("الموقع", loc_options)
    loc = st.text_input("كود الرف", value=chosen_loc if chosen_loc != "إضافة جديد" else "")
    
    condition = st.selectbox("الحالة", ["جديدة", "مستعملة"])
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("إضافة"):
            if loc and item_type and image_path:
                item_id = len(st.session_state.worker_session) + 1
                st.session_state.worker_session.append({
                    "id": item_id,
                    "type": item_type,
                    "part_number": (ai_result["part_number"] if ai_result else None) or "PENDING",
                    "location": loc,
                    "condition": condition,
                    "image_path": image_path,
                    "ai_data": ai_result
                })
                st.session_state.worker_ai_result = None
                st.success("تمت الإضافة")
                st.rerun()
            else:
                st.error("أدخل جميع البيانات وارفع صورة")
    
    with col_btn2:
        if st.button("مسح الكل"):
            st.session_state.worker_session = []
            st.rerun()
    
    # عرض الجلسة
    if st.session_state.worker_session:
        st.markdown("---")
        st.markdown("### القطع المضافة")
        
        for item in st.session_state.worker_session:
            cols = st.columns([1, 4, 1])
            with cols[0]:
                if item.get('image_path') and os.path.exists(item['image_path']):
                    st.image(item['image_path'], width=80)
            with cols[1]:
                st.write(f"**{item['type']}** - {item['location']}")
                st.caption(f"Part: {item.get('part_number', 'PENDING')}")
                if item.get('ai_data'):
                    st.caption(f"الماركة: {item['ai_data'].get('brand', '-')}")
            with cols[2]:
                if st.button("حذف", key=f"del_{item['id']}"):
                    st.session_state.worker_session = [
                        x for x in st.session_state.worker_session 
                        if x['id'] != item['id']
                    ]
                    st.rerun()
        
        if st.button("حفظ واعتماد في المخزن", use_container_width=True):
            with UnitOfWork() as uow:
                repo = uow.get_repository(ItemRepository)
                log_repo_local = uow.get_repository(LogRepository)
                username = session_manager.get_username()
                
                for item in st.session_state.worker_session:
                    new_item = repo.create(
                        item_type=item['type'],
                        part_number=item.get('part_number', 'PENDING'),
                        location=item['location'],
                        condition=item['condition'],
                        image_path=item.get('image_path', ''),
                        ocr_text='',
                        status=ItemStatus.AVAILABLE
                    )
                    
                    log_repo_local.log_action(
                        item_id=new_item.item_id,
                        action_type=ActionType.INSERT,
                        username=username,
                        details=f"إدخال {item['type']} - {item.get('part_number', 'PENDING')}"
                    )
                    
                    # حفظ بيانات الذكاء الاصطناعي في قاعدة المعرفة (زي شاشة البحث بالظبط)
                    ai_data = item.get('ai_data')
                    part_num = item.get('part_number', '')
                    if ai_data and part_num and part_num != "PENDING":
                        from repositories.knowledge_repo import KnowledgeRepository
                        kb_repo = uow.get_repository(KnowledgeRepository)
                        kb_repo.create_or_update(
                            part_number=part_num,
                            Brand=ai_data.get('brand', ''),
                            Category=ai_data.get('category', ''),
                            Compatible_Model=ai_data.get('compatible_model', ''),
                            Additional_Compatibility=ai_data.get('additional_compatibility', ''),
                            market_value=ai_data.get('market_value', ''),
                            Gemini_Insights=ai_data.get('insight', '')
                        )
                    
                    notification_service.check_and_notify_request(
                        part_number=item.get('part_number', ''),
                        category=item['type'],
                        location=item['location']
                    )
            
            st.success("تم اعتماد القطع في المخزن الرسمي بنجاح!")
            st.session_state.worker_session = []
            st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

def worker_export_view():
    """عرض تصدير البيانات"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### تصدير البيانات")
    
    username = session_manager.get_username()
    from core.database import UnitOfWork
    from repositories.user_repo import UserRepository
    with UnitOfWork() as uow:
        repo = uow.get_repository(UserRepository)
        has_export_perm = repo.has_permission(username, "export")
    if not has_export_perm:
        st.warning("ليس لديك صلاحية التصدير")
        return
    
    export_type = st.selectbox("نوع التقرير", [
        "المخزن بالكامل",
        "القطع المتاحة",
        "القطع المنصرفة",
        "قاعدة المعرفة",
        "سجل الحركات"
    ])
    
    if st.button("توليد التقرير"):
        from core.database import db
        with db.get_connection() as conn:
            if export_type == "المخزن بالكامل":
                df = pd.read_sql("SELECT * FROM inventory_items", conn)
            elif export_type == "القطع المتاحة":
                df = pd.read_sql("SELECT * FROM inventory_items WHERE status='Available'", conn)
            elif export_type == "القطع المنصرفة":
                df = pd.read_sql("SELECT * FROM inventory_items WHERE status='Out'", conn)
            elif export_type == "قاعدة المعرفة":
                df = pd.read_sql("SELECT * FROM specs_knowledge_base", conn)
            else:
                df = pd.read_sql("SELECT * FROM transactions_log", conn)
        
        if not df.empty:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="تحميل ملف CSV",
                data=csv,
                file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            with UnitOfWork() as uow:
                log_repo_local = uow.get_repository(LogRepository)
                log_repo_local.log_action(
                    item_id=None,
                    action_type=ActionType.EXPORT,
                    username=session_manager.get_username(),
                    details=f"تصدير تقرير: {export_type}"
                )
        else:
            st.info("لا توجد بيانات لهذا التقرير حالياً.")
    
    st.markdown('</div>', unsafe_allow_html=True)

# استيرادات متأخرة لتجنب Circular Import
from repositories.item_repo import ItemRepository
from repositories.log_repo import LogRepository
from core.models import InventoryItem