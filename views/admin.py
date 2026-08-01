# views/admin.py
import streamlit as st
import pandas as pd
import time
from datetime import datetime

from core.database import UnitOfWork
from core.session import session_manager
from core.enums import Role, ActionType
from core.security import security_service
from core.config import settings
from services.auth_service import auth_service
from views.base import render_stat_box

def admin_view():
    """عرض المدير الرئيسي"""
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["مستخدمين", "تنبيهات وطلبات", "إحصائيات", "إعدادات النظام", "استيراد قاعدة المعرفة"])
    with tab1:
        admin_users_view()
    with tab2:
        admin_notifications_view()
    with tab3:
        admin_stats_view()
    with tab4:
        admin_settings_view()
    with tab5:
        admin_import_view()

def admin_users_view():
    """عرض إدارة المستخدمين"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### إدارة المستخدمين")
    
    with UnitOfWork() as uow:
        repo = uow.get_repository(UserRepository)
        users = repo.session.query(repo.model_class).all()
        
        if users:
            data = []
            for u in users:
                data.append({
                    "المستخدم": u.username,
                    "الدور": u.role,
                    "تصدير طوارئ": "نعم" if u.can_export else "لا",
                    "تتبع كامل": "نعم" if u.can_track else "لا",
                    "تعديل المخزن": "نعم" if u.can_edit else "لا",
                    "الحالة": u.status,
                    "آخر دخول": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "-"
                })
            st.dataframe(data, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### إضافة أو تعديل مستخدم")
    
    with st.form("add_user_form"):
        col1, col2 = st.columns(2)
        with col1:
            new_user = st.text_input("اسم المستخدم")
            new_pass = st.text_input("كلمة المرور", type="password")
        with col2:
            new_role = st.selectbox("الدور", [Role.WORKER, Role.ENGINEER, Role.ADMIN])
            can_export = st.checkbox("منح صلاحية التصدير")
            can_track = st.checkbox("منح صلاحية التتبع")
            can_edit = st.checkbox("منح صلاحية تعديل بيانات القطع بالمخزن")
            user_status = st.selectbox("حالة الحساب", ["Active", "Banned"])
        
        if st.form_submit_button("حفظ بيانات الحساب"):
            if new_user and new_pass:
                try:
                    with UnitOfWork() as uow:
                        repo = uow.get_repository(UserRepository)
                        log_repo_local = uow.get_repository(LogRepository)
                        
                        existing = repo.get_by_username(new_user)
                        if existing:
                            # تحديث
                            existing.password = security_service.hash_password(new_pass)
                            existing.role = new_role
                            existing.can_export = can_export
                            existing.can_track = can_track
                            existing.can_edit = can_edit
                            existing.status = user_status
                            repo.update(existing)
                            st.success(f"تم تحديث بيانات المستخدم {new_user}")
                        else:
                            # إنشاء جديد
                            repo.create_user(
                                username=new_user,
                                password=new_pass,
                                role=new_role,
                                can_export=can_export,
                                can_track=can_track,
                                can_edit=can_edit,
                                status=user_status
                            )
                            st.success(f"تم إنشاء المستخدم {new_user} بنجاح")
                        
                        log_repo_local.log_action(
                            item_id=None,
                            action_type=ActionType.USER_MGMT,
                            username=session_manager.get_username(),
                            details=f"إدارة حساب: {new_user} - دور: {new_role}"
                        )
                        st.rerun()
                except Exception as e:
                    st.error(f"خطأ: {e}")
            else:
                st.warning("أدخل اسم المستخدم وكلمة المرور.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def admin_notifications_view():
    """عرض التنبيهات والطلبات"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### التنبيهات والإشعارات الفورية")
    
    from services.notification_service import notification_service
    
    notifications = notification_service.get_recent(50)
    
    if notifications:
        data = []
        for notif in notifications:
            data.append({
                "الرسالة": notif.message,
                "التوقيت": notif.timestamp.strftime("%Y-%m-%d %H:%M") if notif.timestamp else "-",
                "مقروء": "نعم" if notif.is_read else "لا"
            })
        st.table(data)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("تحديد الكل كمقروء", use_container_width=True):
                notification_service.mark_all_read()
                st.rerun()
        with col2:
            if st.button("مسح جميع التنبيهات", use_container_width=True):
                notification_service.clear_all()
                st.rerun()
    else:
        st.info("لا توجد تنبيهات جديدة.")
    
    st.markdown("---")
    st.markdown("### طلبات واستعلامات المهندسين")
    
    with UnitOfWork() as uow:
        repo = uow.get_repository(QueryRepository)
        queries = repo.get_pending()
        
        if queries:
            data = []
            for q in queries:
                data.append({
                    "المهندس": q.username,
                    "رقم القطعة": q.part_number or "-",
                    "النوع": q.part_category or "-",
                    "السبب": q.query_reason or "-",
                    "الطالب": q.requested_by or "-",
                    "الجهاز": q.target_device or "-",
                    "التوقيت": q.timestamp.strftime("%Y-%m-%d %H:%M") if q.timestamp else "-"
                })
            st.dataframe(data, use_container_width=True)
        else:
            st.info("لا توجد طلبات معلقة من المهندسين حالياً.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def admin_stats_view():
    """عرض الإحصائيات"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### لوحة المؤشرات (Dashboard)")
    
    with UnitOfWork() as uow:
        item_repo_local = uow.get_repository(ItemRepository)
        log_repo_local = uow.get_repository(LogRepository)
        user_repo_local = uow.get_repository(UserRepository)
        
        stats = item_repo_local.get_statistics()
        total_users = user_repo_local.count()
        total_logs = log_repo_local.count()
        
        # توزيع القطع حسب النوع
        from sqlalchemy import func
        type_dist = item_repo_local.session.query(
            InventoryItem.item_type,
            func.count(InventoryItem.item_id).label('count')
        ).filter(InventoryItem.status == 'Available').group_by(
            InventoryItem.item_type
        ).all()
    
    col1, col2, col3, col4 = st.columns(4)
    render_stat_box(stats["total"], "إجمالي القطع المسجلة")
    render_stat_box(stats["available"], "الرصيد المتاح حالياً")
    render_stat_box(stats["out"], "إجمالي المنصرف")
    render_stat_box(total_users, "حسابات النظام")
    
    st.markdown("---")
    st.markdown("### توزيع الأرصدة المتاحة حسب النوع")
    
    if type_dist:
        data = []
        for row in type_dist:
            data.append({
                "النوع": row[0] or "غير محدد",
                "العدد": row[1]
            })
        
        col_chart, col_table = st.columns([2, 1])
        with col_table:
            st.dataframe(data, use_container_width=True)
        with col_chart:
            df = pd.DataFrame(data)
            if not df.empty:
                st.bar_chart(df.set_index('النوع'))
    else:
        st.info("لا توجد بيانات للأرصدة المتاحة.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def admin_settings_view():
    """عرض الإعدادات"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### إعدادات النظام المتقدمة")
    
    # حالة الذكاء الاصطناعي
    from services.ai_service import ai_service
    
    st.markdown("#### حالة ربط الذكاء الاصطناعي (AI Quota)")
    api_key = ai_service._get_api_key()
    if api_key:
        st.success("مفتاح خدمة الذكاء الاصطناعي متاح ونشط.")
    else:
        st.warning("مفتاح الخدمة غير متاح. النظام سيعمل أوفلاين وسيقوم بتسجيل القطع في طابور الانتظار.")
    
    # قاعدة البيانات
    st.markdown("---")
    st.markdown("#### إدارة قاعدة البيانات (النسخ الاحتياطي)")
    
    from core.database import db
    from pathlib import Path
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("توليد نسخة احتياطية محلية (.db)", use_container_width=True):
            if settings.DATABASE_URL:
                st.info("أنت تستخدم قاعدة بيانات سحابية (Supabase). البيانات محفوظة تلقائياً.")
            else:
                with st.spinner("جاري ضغط وإنشاء النسخة..."):
                    try:
                        backup_file = db.backup()
                        with open(backup_file, "rb") as f:
                            st.download_button(
                                "تحميل ملف النسخة الاحتياطية",
                                data=f.read(),
                                file_name=backup_file.name,
                                mime="application/octet-stream"
                            )
                    except Exception as e:
                        st.error(f"خطأ أثناء النسخ: {e}")
    
    with col2:
        if not settings.DATABASE_URL:
            uploaded_db = st.file_uploader("استعادة قاعدة بيانات محلية", type=['db'])
            if uploaded_db:
                if st.button("تأكيد الاستبدال والاستعادة (خطر)"):
                    if session_manager.get_role() == Role.ADMIN:
                        upload_dir = settings.BASE_DIR / "uploads"
                        upload_dir.mkdir(exist_ok=True)
                        backup_path = upload_dir / f"restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                        with open(backup_path, 'wb') as f:
                            f.write(uploaded_db.getbuffer())
                        
                        db.restore(backup_path)
                        st.success("تم استعادة قاعدة البيانات بنجاح! يتم الآن إعادة تحميل النظام.")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("غير مصرح لك بهذه العملية.")
        else:
            st.info("خاصية الاستعادة المحلية مغلقة لأنك متصل بخادم Supabase السحابي الموثوق.")
    
    # تغيير كلمة المرور
    st.markdown("---")
    st.markdown("#### تغيير كلمة مرور الإدارة")
    
    username = session_manager.get_username()
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        old_pass = st.text_input("كلمة المرور الحالية", type="password")
    with col_p2:
        new_pass = st.text_input("كلمة المرور الجديدة", type="password")
        confirm_pass = st.text_input("تأكيد كلمة المرور", type="password")
    
    if st.button("تنفيذ تغيير الباسورد"):
        if old_pass and new_pass and confirm_pass:
            if new_pass != confirm_pass:
                st.error("كلمة المرور غير متطابقة.")
            elif len(new_pass) < 4:
                st.error("كلمة المرور قصيرة جداً.")
            else:
                if auth_service.change_password(username, old_pass, new_pass):
                    st.success("تم تغيير كلمة المرور بنجاح!")
                else:
                    st.error("كلمة المرور الحالية غير صحيحة.")
        else:
            st.warning("الرجاء إدخال جميع البيانات.")
    
    st.markdown('</div>', unsafe_allow_html=True)

def admin_import_view():
    """استيراد قاعدة المعرفة (بيانات قطع جاهزة تم شراؤها مسبقاً) - للمدير فقط"""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.markdown("### استيراد قاعدة المعرفة (بيانات قطع جاهزة)")
    
    with UnitOfWork() as uow:
        from repositories.knowledge_repo import KnowledgeRepository
        kb_repo = uow.get_repository(KnowledgeRepository)
        current_count = kb_repo.count()
    
    col_count, col_refresh = st.columns([3, 1])
    with col_count:
        st.metric("عدد القطع الموجودة حالياً في قاعدة المعرفة", current_count)
    with col_refresh:
        st.write("")
        if st.button("تحديث العدد"):
            st.rerun()
    
    st.info(
        "ارفع ملف CSV يحتوي على الأعمدة التالية بالضبط (بنفس الأسماء والحروف):\n\n"
        "`Part_Number`, `Brand`, `Category`, `Compatible_Model`, `Additional_Compatibility`, `market_value`, `Gemini_Insights`\n\n"
        "العمود الوحيد الإجباري هو `Part_Number` - الباقي اختياري ويُترك فارغاً لو غير متاح.\n\n"
        "لو نفس رقم القطعة اتكرر في أكتر من صف (كل مرة لجهاز متوافق مختلف مثلاً)، "
        "هيتم تجميعهم تلقائياً في صف واحد، ودمج كل الأجهزة المتوافقة في خانة واحدة.\n\n"
        "**ملحوظة عن قطع النت:** لو الصفحة اتقفلت أو النت اتقطع في نص الاستيراد، الدفعات اللي خلصت "
        "قبل القطع بتفضل محفوظة. تقدر ببساطة ترفع نفس الملف تاني - مش هيتكرر، هيكمل فقط اللي ناقص."
    )
    
    uploaded_csv = st.file_uploader("رفع ملف CSV", type=['csv'], key="kb_import_csv")
    
    if uploaded_csv:
        try:
            df = pd.read_csv(uploaded_csv)
            st.write(f"تم العثور على **{len(df)}** صف. معاينة أول 5 صفوف:")
            st.dataframe(df.head())
            
            if "Part_Number" not in df.columns:
                st.error("العمود الإجباري `Part_Number` غير موجود في الملف.")
            else:
                def clean(val):
                    if pd.isna(val):
                        return ""
                    return str(val).strip()
                
                def join_unique(series):
                    vals = []
                    for v in series:
                        v = clean(v)
                        if v and v.upper() != "N/A" and v not in vals:
                            vals.append(v)
                    return "; ".join(vals)
                
                agg_dict = {}
                for col in ["Brand", "Category", "market_value", "Gemini_Insights"]:
                    if col in df.columns:
                        agg_dict[col] = "first"
                for col in ["Compatible_Model", "Additional_Compatibility"]:
                    if col in df.columns:
                        agg_dict[col] = join_unique
                
                grouped = df.groupby("Part_Number", as_index=False).agg(agg_dict) if agg_dict else df.drop_duplicates(subset=["Part_Number"])
                
                dupe_count = len(df) - len(grouped)
                if dupe_count > 0:
                    st.warning(f"تم تجميع {dupe_count} صف مكرر لنفس أرقام القطع، النتيجة النهائية: {len(grouped)} رقم قطعة فريد.")
                
                if st.button("تنفيذ الاستيراد الآن", use_container_width=True):
                    imported = 0
                    skipped = 0
                    total = len(grouped)
                    batch_size = 500
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    rows = grouped.to_dict('records')
                    
                    for start in range(0, total, batch_size):
                        batch = rows[start:start + batch_size]
                        with UnitOfWork() as uow:
                            from repositories.knowledge_repo import KnowledgeRepository
                            kb_repo = uow.get_repository(KnowledgeRepository)
                            
                            for row in batch:
                                part_number = clean(row.get("Part_Number", ""))
                                if not part_number or part_number.lower() == "nan":
                                    skipped += 1
                                    continue
                                
                                kb_repo.create_or_update(
                                    part_number=part_number,
                                    Brand=clean(row.get("Brand", "")),
                                    Category=clean(row.get("Category", "")),
                                    Compatible_Model=clean(row.get("Compatible_Model", "")),
                                    Additional_Compatibility=clean(row.get("Additional_Compatibility", "")),
                                    market_value=clean(row.get("market_value", "")),
                                    Gemini_Insights=clean(row.get("Gemini_Insights", ""))
                                )
                                imported += 1
                        
                        progress_bar.progress(min((start + batch_size) / total, 1.0))
                        status_text.text(f"تم استيراد {imported} من {total}...")
                    
                    with UnitOfWork() as uow:
                        log_repo_local = uow.get_repository(LogRepository)
                        log_repo_local.log_action(
                            item_id=None,
                            action_type=ActionType.IMPORT,
                            username=session_manager.get_username(),
                            details=f"استيراد {imported} قطعة (بعد تجميع {len(df)} صف أصلي) إلى قاعدة المعرفة من ملف CSV"
                        )
                    
                    st.success(f"تم استيراد {imported} قطعة بنجاح إلى قاعدة المعرفة.")
                    if skipped:
                        st.warning(f"تم تجاهل {skipped} صف لعدم وجود رقم قطعة صالح.")
        except Exception as e:
            st.error(f"تعذرت قراءة الملف: {e}")
    
    st.markdown('</div>', unsafe_allow_html=True)

# استيرادات متأخرة
from repositories.user_repo import UserRepository
from repositories.query_repo import QueryRepository
from repositories.item_repo import ItemRepository
from repositories.log_repo import LogRepository
from core.models import InventoryItem