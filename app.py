# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
멀티페이지 버전 - 메인 (로그인)
"""

import streamlit as st

st.set_page_config(page_title="PDF 자동 생성 플랫폼", page_icon="🔮", layout="wide")

from common import (
    init_session_state, apply_common_css, initialize_database,
    is_admin, get_member_level
)
from auth import login_user, register_user, create_first_admin, check_admin_exists

# ============================================
# 초기화
# ============================================

init_session_state()
apply_common_css()

try:
    initialize_database()
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">사주 · 연애 · 타로 운세 PDF를 자동으로 생성합니다</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["로그인", "회원가입"])
    
    with tab1:
        email = st.text_input("이메일", key="login_email")
        password = st.text_input("비밀번호", type="password", key="login_pw")
        
        if st.button("로그인", type="primary", use_container_width=True):
            if email and password:
                result = login_user(email, password)
                if result["success"]:
                    st.session_state.logged_in = True
                    st.session_state.user = result["user"]
                    st.rerun()
                else:
                    st.error(result["error"])
    
    with tab2:
        reg_name = st.text_input("이름", key="reg_name")
        reg_email = st.text_input("이메일", key="reg_email")
        reg_pw = st.text_input("비밀번호", type="password", key="reg_pw")
        
        if st.button("회원가입", type="primary", use_container_width=True):
            if reg_name and reg_email and reg_pw:
                result = register_user(reg_email, reg_pw, reg_name)
                if result["success"]:
                    st.success("회원가입 완료! 관리자 승인을 기다려주세요.")
                else:
                    st.error(result["error"])
    
    # 최초 관리자 설정
    if not check_admin_exists():
        st.markdown("---")
        with st.expander("🔧 최초 관리자 설정", expanded=True):
            admin_email = st.text_input("관리자 이메일", key="admin_email")
            admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw")
            admin_name = st.text_input("관리자 이름", key="admin_name")
            
            if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                if admin_email and admin_pw and admin_name:
                    result = create_first_admin(admin_email, admin_pw, admin_name)
                    if result["success"]:
                        st.success("관리자 계정 생성됨! 로그인하세요.")
                        st.rerun()

# ============================================
# 로그인 후 홈 화면
# ============================================

def show_home():
    user = st.session_state.user
    
    # 사이드바
    with st.sidebar:
        badge = "badge-admin" if user.get('is_admin') else f"badge-level{user.get('member_level', 1)}"
        badge_text = "관리자" if user.get('is_admin') else f"{user.get('member_level', 1)}단계"
        st.markdown(f"👤 **{user['name']}** <span class='{badge}'>{badge_text}</span>", unsafe_allow_html=True)
        
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()
    
    # 메인 영역
    st.title("🔮 PDF 자동 생성 플랫폼")
    st.markdown("---")
    
    st.success(f"환영합니다, **{user['name']}**님! 👋")
    
    st.markdown("### 📌 메뉴 안내")
    st.markdown("""
    왼쪽 사이드바에서 원하는 메뉴를 선택하세요:
    
    - **📦 서비스작업** - PDF 생성 (엑셀 업로드 / 수동 입력)
    - **📚 자료실** - 목차/지침 템플릿 관리
    - **👤 내정보** - 프로필, API 설정, 공지사항
    """)
    
    if is_admin():
        st.markdown("- **⚙️ 관리자** - 기성상품 관리, 회원 관리, 시스템 설정")
    
    st.markdown("---")
    
    # 빠른 시작 버튼
    col1, col2, col3 = st.columns(3)
    with col1:
        st.page_link("pages/1_📦_서비스작업.py", label="📦 서비스작업", icon="📦", use_container_width=True)
    with col2:
        st.page_link("pages/2_📚_자료실.py", label="📚 자료실", icon="📚", use_container_width=True)
    with col3:
        st.page_link("pages/4_👤_내정보.py", label="👤 내정보", icon="👤", use_container_width=True)

# ============================================
# 메인
# ============================================

def main():
    if st.session_state.get('logged_in', False):
        show_home()
    else:
        show_login_page()

if __name__ == "__main__":
    main()
