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
        selected_cat = st.selectbox("التصنيف", item_categories)
    
    image_path = None
    ocr_text = ""
    part_number = ""
    
    if uploaded_file:
        with st.spinner("جاري معالجة الصورة..."):
            image_bytes = uploaded_file.getvalue()
            quality_ok, quality_msg = ocr_service.check_quality(image_bytes)
            if quality_ok:
                image_path = save_image(image_bytes)
                st.image(uploaded_file, width=150)
                
                ocr_text, part_number = ocr_service.extract_text(image_bytes)
                if ocr_text and "خطأ" not in ocr_text and "غير" not in ocr_text:
                    st.success(f"النص المستخرج: {ocr_text[:100]}...")
                    if part_number:
                        st.info(f"رقم القطعة: {part_number}")
                    else:
                        st.warning("لم يتم العثور على رقم قطعة واضح")
            else:
                st.warning(quality_msg)
    
    if selected_cat == "أخرى":
        item_type = st.text_input("نوع القطعة")
    else:
        item_type = selected_cat
    
    # محاولة استخراج رقم القطعة من Gemini لو الـ OCR مجابوش
    if not part_number and uploaded_file and image_path:
        with st.spinner("جاري تحليل الصورة بالذكاء الاصطناعي..."):
            image_bytes = uploaded_file.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            brand, category, ai_part, comp, add, val, insight = ai_service.analyze_part(
                item_type, image_base64
            )
            if ai_part and ai_part != item_type:
                part_number = ai_part
                st.info(f"رقم القطعة من الذكاء الاصطناعي: {part_number}")
    
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
                    "part_number": part_number or "PENDING",
                    "location": loc,
                    "condition": condition,
                    "image_path": image_path,
                    "ocr": ocr_text
                })
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
                if item.get('ocr'):
                    st.caption(f"OCR: {item['ocr'][:50]}...")
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
                        ocr_text=item.get('ocr', ''),
                        status=ItemStatus.AVAILABLE
                    )
                    
                    log_repo_local.log_action(
                        item_id=new_item.item_id,
                        action_type=ActionType.INSERT,
                        username=username,
                        details=f"إدخال {item['type']} - {item.get('part_number', 'PENDING')}"
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