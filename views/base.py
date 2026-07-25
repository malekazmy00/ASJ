# views/base.py
import streamlit as st
import time
from pathlib import Path

def load_css():
    css_path = Path(__file__).parent.parent / 'static' / 'style.css'
    if css_path.exists():
        with open(css_path, 'r', encoding='utf-8') as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

def render_header():
    st.markdown("""
    <div class="app-header">
        <div class="logo-svg">
            <svg viewBox="0 0 100 100" width="70" height="70" xmlns="http://www.w3.org/2000/svg">
              <path d="M 20 75 A 40 40 0 1 1 80 75" fill="none" stroke="#0A2540" stroke-width="10" stroke-linecap="round"/>
              <path d="M 5 55 L 30 55 L 40 25 L 60 85 L 70 55 L 95 55" fill="none" stroke="#00D2FF" stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>
            </svg>
        </div>
        <h1>ASJ Medical Systems Store</h1>
        <p>نظام إدارة المستودعات</p>
    </div>
    """, unsafe_allow_html=True)

def render_user_info():
    from core.session import session_manager
    session = session_manager.get_session()
    if session:
        st.markdown(f"""
        <div class="user-info">
            <span class="name">{session.username}</span>
            <span class="role">{session.role}</span>
            <span class="last-active">آخر نشاط: {time.strftime('%H:%M', time.localtime(session.last_activity))}</span>
        </div>
        """, unsafe_allow_html=True)

def render_main_menu(active: str, options: list):
    tabs = st.tabs([label for label, _ in options])
    for i, (label, key) in enumerate(options):
        with tabs[i]:
            if key == active or (not active and i == 0):
                st.query_params["page"] = key

def render_sub_tabs(active: str, options: list):
    tabs = st.tabs([label for label, _ in options])
    for i, (label, key) in enumerate(options):
        with tabs[i]:
            if key == active or (not active and i == 0):
                st.query_params["sub"] = key

def render_stat_box(number: int, label: str):
    st.markdown(f"""
    <div class="stat-box">
        <div class="number">{number}</div>
        <div class="label">{label}</div>
    </div>
    """, unsafe_allow_html=True)

def render_pagination(current_page: int, total_pages: int):
    if total_pages <= 1:
        return
    
    cols = st.columns(min(total_pages, 7))
    for i, col in enumerate(cols):
        page_num = i + 1
        if page_num <= total_pages:
            if col.button(
                str(page_num),
                key=f"page_{page_num}",
                use_container_width=True,
                type="primary" if page_num == current_page else "secondary"
            ):
                st.query_params["page"] = str(page_num)
                st.rerun()
