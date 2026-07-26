# views/engineer.py
import streamlit as st
import base64
from datetime import datetime
import pandas as pd

from core.database import UnitOfWork
from core.session import session_manager
from core.enums import ActionType, ItemStatus, QueryReason, QueryStatus
from views.base import render_pagination, render_stat_box
from services.ocr_service import ocr_service
from services.ai_service import ai_service
from services.notification_service import notification_service
from repositories.user_repo import UserRepository

def engineer_view():
    """عرض المهندس الرئيسي"""
    from core.enums import Role
    username = session_manager.get_username()
    with UnitOfWork() as uow:
        repo = uow.get_repository(UserRepository)
        user = repo.get_by_username(username)
        can_edit_inventory = user and (user.role == Role.ADMIN or user.can_edit)
    
    labels = ["بحث", "صرف", "سجل"]
    if can_edit_inventory:
        labels.append("تعديل")
    
    tabs = st.tabs(labels)
    with tabs[0]:
        engineer_search_view()
    with tabs[1]:
        engineer_dispatch_view()
    with tabs[2]:
        engineer_log_view()
    if can_edit_inventory:
        with tabs[3]:
            engineer_edit_view()

def engineer_search_view():
    """عرض البحث المتقدم"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### بحث متقدم واستعلام")
    
    # إحصائيات سريعة
    with UnitOfWork() as uow:
        repo = uow.get_repository(ItemRepository)
        stats = repo.get_statistics()
    
    col1, col2 = st.columns(2)
    render_stat_box(stats["available"], "متاح بالمخزن")
    render_stat_box(stats["out"], "منصرف")
    
    st.markdown("---")
    
    search_term = st.text_input("رقم القطعة أو النوع أو الموقع")
    search_image = st.file_uploader("أو رفع صورة للبحث الذكي", type=['jpg', 'png', 'jpeg'], key="search_img_eng")
    
    image_base64 = None
    extracted_part = None
    
    if search_image:
        image_bytes = search_image.getvalue()
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        st.image(search_image, width=120)
        
        ocr_text, part_number = ocr_service.extract_text(image_bytes)
        if ocr_text and "خطأ" not in ocr_text:
            st.info(f"النص المستخرج: {ocr_text[:100]}...")
            if part_number:
                extracted_part = part_number
                st.success(f"رقم القطعة: {part_number}")
                if not search_term:
                    search_term = part_number
    
    # تفاصيل الطلب
    query_reason = st.selectbox("سبب الاستعلام", [
        QueryReason.INSPECTION,
        QueryReason.MERCHANT,
        QueryReason.DEVICE,
        QueryReason.SPECS
    ])
    
    requested_by = ""
    target_device = ""
    merchant_name = ""
    merchant_phone = ""
    
    if query_reason == QueryReason.MERCHANT:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            merchant_name = st.text_input("اسم التاجر")
        with col_m2:
            merchant_phone = st.text_input("رقم التاجر")
    elif query_reason == QueryReason.DEVICE:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            requested_by = st.text_input("اسم الطالب")
        with col_d2:
            target_device = st.text_input("اسم الجهاز المستهدف")
    
    comments = st.text_area("ملاحظات إضافية", key="search_comments")
    
    # Pagination
    page = int(st.query_params.get("page", 1))
    page_size = 50
    
    if st.button("تنفيذ البحث"):
        if search_term or image_base64:
            username = session_manager.get_username()
            
            # حفظ الاستعلام
            with UnitOfWork() as uow:
                from repositories.query_repo import QueryRepository
                query_repo = uow.get_repository(QueryRepository)
                
                query_repo.create(
                    username=username,
                    part_number=extracted_part or search_term or "",
                    part_category=search_term or "",
                    part_description=search_term or "",
                    query_reason=query_reason,
                    requested_by=requested_by,
                    target_device=target_device,
                    merchant_name=merchant_name,
                    merchant_phone=merchant_phone,
                    comments=comments,
                    status=QueryStatus.PENDING
                )
                
                log_repo_local = uow.get_repository(LogRepository)
                log_repo_local.log_action(
                    item_id=None,
                    action_type=ActionType.SEARCH,
                    username=username,
                    details=f"بحث واستعلام عن: {search_term}"
                )
            
            # البحث في المخزن
            if search_term:
                with UnitOfWork() as uow:
                    repo = uow.get_repository(ItemRepository)
                    items, total = repo.search_fts(search_term, page, page_size)
                    
                    if items:
                        st.success(f"تم العثور على {total} قطعة مطابقة")
                        data = []
                        for item in items:
                            data.append({
                                "ID": item.item_id,
                                "النوع": item.item_type,
                                "رقم القطعة": item.part_number,
                                "الموقع": item.location,
                                "الحالة": item.condition,
                                "حالة المخزون": item.status
                            })
                        st.dataframe(data, use_container_width=True)
                        
                        if total > page_size:
                            render_pagination(page, (total + page_size - 1) // page_size)
                    else:
                        st.warning("القطعة غير متوفرة حالياً في المخزن.")
                        
                        # استخدام الذكاء الاصطناعي لو القطعة مش في المخزن
                        with st.spinner("جاري تحليل البيانات بالذكاء الاصطناعي..."):
                            brand, category, ai_part, comp, add, val, insight = ai_service.analyze_part(
                                search_term, image_base64
                            )
                            if insight and not insight.startswith(("خطأ", "Pending", "تحذير")):
                                st.markdown("### معلومات فنية (الذكاء الاصطناعي)")
                                st.info(f"**الماركة:** {brand}")
                                st.info(f"**التصنيف:** {category}")
                                if ai_part and ai_part != search_term:
                                    st.info(f"**رقم القطعة المقترح:** {ai_part}")
                                st.caption(f"**ملاحظات فنية:** {insight}")
                                
                                # حفظ في قاعدة المعرفة
                                if ai_part:
                                    with UnitOfWork() as uow:
                                        from repositories.knowledge_repo import KnowledgeRepository
                                        kb_repo = uow.get_repository(KnowledgeRepository)
                                        kb_repo.create_or_update(
                                            part_number=ai_part,
                                            Brand=brand,
                                            Category=category,
                                            Compatible_Model=comp,
                                            Additional_Compatibility=add,
                                            market_value=val,
                                            Gemini_Insights=insight
                                        )
        else:
            st.warning("أدخل كلمة للبحث أو ارفع صورة")
    
    st.markdown('</div>', unsafe_allow_html=True)

def engineer_dispatch_view():
    """عرض صرف القطع"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### صرف خروج قطعة")
    
    col1, col2 = st.columns(2)
    with col1:
        item_id = st.number_input("رقم القطعة (ID)", min_value=1, step=1)
        exit_type = st.selectbox("نوع الصرف", ["بيع", "إعارة (مؤقت)", "تلف"])
    with col2:
        recipient = st.text_input("اسم المستلم / الجهة")
        comment = st.text_area("ملاحظات إضافية", key="dispatch_comment")
    
    if st.button("تنفيذ عملية الصرف"):
        if item_id and recipient:
            with UnitOfWork() as uow:
                repo = uow.get_repository(ItemRepository)
                log_repo_local = uow.get_repository(LogRepository)
                
                item = repo.get(item_id)
                if not item:
                    st.error("القطعة غير موجودة في قاعدة البيانات.")
                elif item.status != ItemStatus.AVAILABLE:
                    st.error("هذه القطعة غير متاحة للصرف (ربما صُرفت مسبقاً).")
                else:
                    repo.update_status(item_id, ItemStatus.OUT)
                    
                    log_repo_local.log_action(
                        item_id=item_id,
                        action_type=ActionType.OUT,
                        username=session_manager.get_username(),
                        details=f"صرف {item.item_type} - {item.part_number} من الرف {item.location} لـ {recipient}. النوع: {exit_type}"
                    )
                    
                    notification_service.add_notification(
                        f"تم صرف قطعة: {item.item_type} - {item.part_number} لـ {recipient}"
                    )
                    
                    st.success("تم صرف القطعة بنجاح وتسجيل الحركة.")
        else:
            st.warning("برجاء إدخال رقم القطعة واسم المستلم.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def engineer_log_view():
    """عرض سجل الحركات"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### سجل الحركات التاريخي")
    
    log_filter = st.selectbox("تصفية الفترة", ["الكل", "حركات اليوم", "آخر 7 أيام", "آخر 30 يوم"])
    
    with UnitOfWork() as uow:
        log_repo_local = uow.get_repository(LogRepository)
        
        if log_filter == "حركات اليوم":
            logs = log_repo_local.get_recent(1)
        elif log_filter == "آخر 7 أيام":
            logs = log_repo_local.get_recent(7)
        elif log_filter == "آخر 30 يوم":
            logs = log_repo_local.get_recent(30)
        else:
            logs = log_repo_local.session.query(log_repo_local.model_class).order_by(
                log_repo_local.model_class.timestamp.desc()
            ).limit(100).all()
    
    if logs:
        data = []
        for log in logs:
            data.append({
                "رقم الحركة": log.log_id,
                "ID القطعة": log.item_id or "-",
                "الإجراء": log.action_type,
                "المستخدم": log.username or "-",
                "التفاصيل": log.details[:50] + "..." if log.details and len(log.details) > 50 else log.details,
                "التوقيت": log.timestamp.strftime("%Y-%m-%d %H:%M") if log.timestamp else "-"
            })
        st.dataframe(data, use_container_width=True)
    else:
        st.info("لا توجد سجلات لعرضها.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def engineer_edit_view():
    """عرض تعديل بيانات قطعة موجودة بالمخزن - للمدير أو المهندس المصرح له فقط"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### تعديل بيانات قطعة بالمخزن")
    
    item_id = st.number_input("رقم القطعة (ID) المراد تعديلها", min_value=1, step=1, key="edit_item_id")
    
    if st.button("بحث عن القطعة"):
        with UnitOfWork() as uow:
            repo = uow.get_repository(ItemRepository)
            item = repo.get(item_id)
            if item:
                st.session_state.edit_loaded_item = {
                    "item_id": item.item_id,
                    "item_type": item.item_type,
                    "part_number": item.part_number,
                    "location": item.location,
                    "condition": item.condition,
                    "status": item.status
                }
            else:
                st.session_state.edit_loaded_item = None
                st.error("لا توجد قطعة بهذا الرقم.")
    
    loaded = st.session_state.get("edit_loaded_item")
    if loaded and loaded["item_id"] == item_id:
        st.markdown("---")
        st.info(f"جاري تعديل القطعة رقم {loaded['item_id']}")
        
        new_type = st.text_input("نوع القطعة", value=loaded["item_type"] or "")
        new_part_number = st.text_input("رقم القطعة (Part Number)", value=loaded["part_number"] or "")
        new_location = st.text_input("الموقع (الرف)", value=loaded["location"] or "")
        new_condition = st.selectbox(
            "الحالة",
            ["جديدة", "مستعملة"],
            index=0 if loaded["condition"] == "جديدة" else 1
        )
        new_status = st.selectbox(
            "حالة المخزون",
            [ItemStatus.AVAILABLE, ItemStatus.OUT],
            index=0 if loaded["status"] == ItemStatus.AVAILABLE else 1
        )
        
        if st.button("حفظ التعديلات", use_container_width=True):
            with UnitOfWork() as uow:
                repo = uow.get_repository(ItemRepository)
                log_repo_local = uow.get_repository(LogRepository)
                
                item = repo.get(loaded["item_id"])
                if item:
                    old_summary = f"{item.item_type} - {item.part_number} - {item.location} - {item.condition} - {item.status}"
                    repo.update(
                        item,
                        item_type=new_type,
                        part_number=new_part_number,
                        location=new_location,
                        condition=new_condition,
                        status=new_status
                    )
                    new_summary = f"{new_type} - {new_part_number} - {new_location} - {new_condition} - {new_status}"
                    
                    log_repo_local.log_action(
                        item_id=item.item_id,
                        action_type=ActionType.UPDATE,
                        username=session_manager.get_username(),
                        details=f"تعديل القطعة رقم {item.item_id}: من ({old_summary}) إلى ({new_summary})"
                    )
                    st.success("تم حفظ التعديلات بنجاح.")
                    st.session_state.edit_loaded_item = None
                    st.rerun()
                else:
                    st.error("تعذر العثور على القطعة، ربما تم حذفها.")
    
    st.markdown('</div>', unsafe_allow_html=True)

# استيرادات متأخرة
from repositories.item_repo import ItemRepository
from repositories.log_repo import LogRepository
