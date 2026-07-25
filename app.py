# app.py - المدخل الرئيسي للتطبيق
import streamlit as st
import logging
import atexit
import random
from pathlib import Path
import sys

# إضافة المسار إلى PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

from core.config import settings
from core.database import db
from core.session import session_manager
from views.base import load_css, render_header, render_user_info
from services.ocr_service import ocr_service
from services.auth_service import auth_service

# إعداد التسجيل
from logging.handlers import RotatingFileHandler

def setup_logging():
    """إعداد نظام التسجيل"""
    log_dir = Path(settings.LOG_FILE).parent
    log_dir.mkdir(exist_ok=True)
    
    has_custom_handler = False
    for handler in logging.getLogger().handlers:
        if isinstance(handler, RotatingFileHandler) and handler.baseFilename == str(settings.LOG_FILE):
            has_custom_handler = True
            break
    
    if not has_custom_handler:
        handler = RotatingFileHandler(
            settings.LOG_FILE,
            maxBytes=settings.LOG_MAX_SIZE,
            backupCount=settings.LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(getattr(logging, settings.LOG_LEVEL))

setup_logging()
logger = logging.getLogger(__name__)

# إيقاف OCR Executor عند الخروج
def shutdown_ocr():
    ocr_service.shutdown()

atexit.register(shutdown_ocr)

# إعداد الصفحة
st.set_page_config(
    page_title=settings.APP_NAME,
    page_icon="⚕️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# تهيئة قاعدة البيانات (مرة واحدة)
if 'db_initialized' not in st.session_state:
    with st.spinner("جاري تهيئة النظام..."):
        db.init_database(create_fts=True)
        st.session_state.db_initialized = True
        logger.info("Database initialized")

# تطبيق CSS
load_css()

# استيراد الصفحات
from views.worker import worker_view, worker_export_view
from views.engineer import engineer_view
from views.admin import admin_view

def login_screen():
    """شاشة تسجيل الدخول"""
    render_header()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("### تسجيل الدخول")
        
        login_user = st.text_input("اسم المستخدم", key="login_user")
        login_pass = st.text_input("كلمة المرور", type="password", key="login_pass")
        
        if st.button("دخول", use_container_width=True):
            if login_user and login_pass:
                import hashlib
                fingerprint = hashlib.sha256(
                    f"{login_user}_{st.query_params.get('ua', 'Unknown')}".encode()
                ).hexdigest()[:32]
                
                success, role, error = auth_service.login(
                    username=login_user,
                    password=login_pass,
                    user_agent=st.query_params.get("ua", "Unknown"),
                    device_fingerprint=fingerprint
                )
                
                if success:
                    st.rerun()
                else:
                    st.error(error)
            else:
                st.warning("أدخل البيانات")
        
        st.markdown('</div>', unsafe_allow_html=True)

def main():
    """الدالة الرئيسية للتطبيق"""
    
    # تنظيف الجلسات المنتهية (مرة كل 100 طلب)
    if random.random() < 0.01:
        session_manager._storage.cleanup_expired()
    
    if session_manager.is_authenticated():
        session = session_manager.get_session()
        if session:
            session.refresh()
            st.session_state.session = session
        
        render_header()
        
        col_user, col_logout = st.columns([3, 1])
        with col_user:
            render_user_info()
        with col_logout:
            if st.button("خروج", use_container_width=True):
                auth_service.logout(session_manager.get_username())
                st.rerun()
        
        st.markdown("---")
        
        role = session_manager.get_role()
        
        if role == "worker":
            from core.database import UnitOfWork
            from repositories.user_repo import UserRepository
            with UnitOfWork() as uow:
                repo = uow.get_repository(UserRepository)
                has_export = repo.has_permission(session_manager.get_username(), "export")
            
            if has_export:
                tab1, tab2 = st.tabs(["الإدخال", "التصدير"])
                with tab1:
                    worker_view()
                with tab2:
                    worker_export_view()
            else:
                worker_view()
        elif role == "engineer":
            engineer_view()
        elif role == "admin":
            admin_view()
    else:
        login_screen()

if __name__ == "__main__":
    main()