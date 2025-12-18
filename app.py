# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
관리자 설정 통합 + 실제 PDF 생성 버전
"""

import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="PDF 자동 생성 플랫폼",
    page_icon="🔮",
    layout="wide"
)

# ============================================
# 데이터베이스 임포트
# ============================================

from database import init_db, SessionLocal
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user,
    update_user_role, create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, delete_service, update_service,
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter, update_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline, update_guideline,
    get_templates_by_service, add_template, delete_template,
    TEMPLATE_TYPES
)
from notices import get_all_notices, create_notice, update_notice, delete_notice, toggle_pin_notice

# ============================================
# 모드 키
# ============================================

API_MODE_KEY = "api_mode"
EMAIL_MODE_KEY = "email_mode"

# ============================================
# CSS
# ============================================

st.markdown("""
<style>
    .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
    .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
    
    /* 사이드바 라디오 버튼 숨기기 */
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child {
        display: none !important;
    }
    section[data-testid="stSidebar"] .stRadio > div > label {
        cursor: pointer !important;
        padding: 12px 15px;
        border-radius: 8px;
        margin: 3px 0;
        transition: background 0.2s;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.1);
    }
    
    /* 섹션 헤더 */
    .section-header { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px; 
        border-radius: 10px; 
        margin: 25px 0 15px 0;
        color: white;
        font-weight: bold;
    }
    
    /* 상태 배지 */
    .status-done { background: #28a745; color: white; padding: 3px 10px; border-radius: 15px; font-size: 0.85rem; }
    .status-pending { background: #ffc107; color: black; padding: 3px 10px; border-radius: 15px; font-size: 0.85rem; }
    
    /* 서비스 카드 */
    .service-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태
# ============================================

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'customers_df' not in st.session_state:
    st.session_state.customers_df = None
if 'admin_created' not in st.session_state:
    st.session_state.admin_created = False
if 'selected_customers' not in st.session_state:
    st.session_state.selected_customers = []
if 'completed_customers' not in st.session_state:
    st.session_state.completed_customers = {}
if 'generated_pdfs' not in st.session_state:
    st.session_state.generated_pdfs = {}

# ============================================
# DB 초기화
# ============================================

@st.cache_resource
def initialize_database():
    init_db()
    return True

try:
    initialize_database()
except Exception as e:
    st.error(f"DB 초기화 오류: {e}")

# ============================================
# 디렉토리
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ============================================
# 폰트 목록
# ============================================

FONT_OPTIONS = {
    "나눔고딕": "NanumGothic",
    "나눔명조": "NanumMyeongjo",
    "맑은고딕": "MalgunGothic",
    "돋움": "Dotum",
    "굴림": "Gulim",
    "바탕": "Batang",
}

TEMPLATE_TYPES_NEW = {
    "cover": "📕 표지",
    "background": "📄 내지",
    "info": "📋 안내지"
}

# ============================================
# 유틸리티
# ============================================

def check_permission(required_role: int) -> bool:
    if not st.session_state.user:
        return False
    return st.session_state.user.get('role', 0) >= required_role

def save_uploaded_file(uploaded_file, prefix: str) -> str:
    if uploaded_file is None:
        return None
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath

def get_api_key() -> dict:
    user = st.session_state.user
    api_mode = get_system_config(API_MODE_KEY, "unified")
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    user_api = user.get('api_key', '') or ''
    
    if api_mode == "unified":
        return {"key": admin_api, "source": "관리자", "mode": "unified"}
    else:
        if user_api:
            return {"key": user_api, "source": "개인", "mode": "separated"}
        return {"key": admin_api, "source": "관리자", "mode": "separated"}

def get_email_config() -> dict:
    user = st.session_state.user
    email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
    admin_gmail = get_system_config(ConfigKeys.ADMIN_GMAIL, "")
    admin_gmail_pw = get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, "")
    user_gmail = user.get('gmail_address', '') or ''
    user_gmail_pw = user.get('gmail_app_password', '') or ''
    
    if email_mode == "unified":
        if admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자"}
        return None
    else:
        if user_gmail and user_gmail_pw:
            return {"email": user_gmail, "password": user_gmail_pw, "source": "개인"}
        elif admin_gmail and admin_gmail_pw:
            return {"email": admin_gmail, "password": admin_gmail_pw, "source": "관리자"}
        return None

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, customer_data: dict) -> str:
    """GPT로 챕터 내용 생성"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        # 고객 정보 문자열
        customer_info = "\n".join([f"- {k}: {v}" for k, v in customer_data.items()])
        
        prompt = f"""당신은 전문 운세 작성가입니다.

[고객 정보]
{customer_info}

[작성 지침]
{guideline}

[작성할 챕터]
{chapter_title}

위 정보를 바탕으로 '{chapter_title}' 챕터의 내용을 작성해주세요.
- 고객의 정보를 반영하여 개인화된 내용 작성
- 긍정적이고 희망적인 톤 유지
- 300-500자 분량으로 작성
- 마크다운 없이 순수 텍스트로 작성
"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"[내용 생성 오류: {str(e)}]"


def create_pdf_document(customer_name: str, chapters_content: list, font_settings: dict, templates: dict) -> bytes:
    """PDF 문서 생성"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               leftMargin=25*mm, rightMargin=25*mm,
                               topMargin=30*mm, bottomMargin=25*mm)
        
        # 스타일 설정
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
        )
        
        chapter_style = ParagraphStyle(
            'ChapterTitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceBefore=20,
            spaceAfter=15,
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=font_settings.get('size', 12),
            leading=font_settings.get('line_height', 18),
            alignment=TA_JUSTIFY,
            spaceAfter=12,
        )
        
        # 문서 내용 구성
        story = []
        
        # 표지
        story.append(Spacer(1, 100*mm))
        story.append(Paragraph(f"🔮 {customer_name}님의 운세", title_style))
        story.append(Spacer(1, 20*mm))
        story.append(Paragraph(datetime.now().strftime("%Y년 %m월 %d일"), 
                              ParagraphStyle('Date', parent=styles['Normal'], 
                                           fontSize=14, alignment=TA_CENTER)))
        story.append(PageBreak())
        
        # 각 챕터
        for chapter in chapters_content:
            story.append(Paragraph(f"📌 {chapter['title']}", chapter_style))
            
            # 내용을 문단으로 나누기
            paragraphs = chapter['content'].split('\n\n')
            for para in paragraphs:
                if para.strip():
                    # HTML 특수문자 이스케이프
                    safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_para, body_style))
            
            story.append(Spacer(1, 10*mm))
        
        # 마지막 페이지
        story.append(PageBreak())
        story.append(Spacer(1, 80*mm))
        story.append(Paragraph("감사합니다", title_style))
        
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service_id: int, font_settings: dict, api_key: str) -> bytes:
    """고객용 PDF 생성"""
    
    # 목차와 지침 가져오기
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    # 고객 이름 찾기
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    if not name_col:
        name_col = list(customer_data.keys())[0]
    
    customer_name = customer_data.get(name_col, "고객")
    
    # 각 챕터별 내용 생성
    chapters_content = []
    for ch in chapters:
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({
            "title": ch['title'],
            "content": content
        })
    
    # PDF 생성
    pdf_bytes = create_pdf_document(customer_name, chapters_content, font_settings, {})
    
    return pdf_bytes

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        if st.session_state.admin_created:
            st.success("✅ 관리자 계정이 생성되었습니다! 위에서 로그인하세요.")
            st.session_state.admin_created = False
        
        tab1, tab2 = st.tabs(["🔐 로그인", "📝 회원가입"])
        
        with tab1:
            email = st.text_input("이메일", key="login_email")
            password = st.text_input("비밀번호", type="password", key="login_password")
            
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
            reg_password = st.text_input("비밀번호", type="password", key="reg_password")
            reg_password2 = st.text_input("비밀번호 확인", type="password", key="reg_password2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if all([reg_name, reg_email, reg_password, reg_password2]):
                    if reg_password != reg_password2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        result = register_user(reg_email, reg_password, reg_name)
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["error"])
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정", expanded=True):
                st.warning("⚠️ 관리자 계정을 먼저 생성하세요!")
                admin_name = st.text_input("관리자 이름", key="admin_name")
                admin_email = st.text_input("관리자 이메일", key="admin_email")
                admin_password = st.text_input("관리자 비밀번호", type="password", key="admin_password")
                
                if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                    if all([admin_name, admin_email, admin_password]):
                        result = create_first_admin(admin_email, admin_password, admin_name)
                        if result["success"]:
                            st.session_state.admin_created = True
                            st.rerun()
                        else:
                            st.error(result["error"])

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        role_text = {1: "1단계", 2: "2단계", 3: "관리자"}
        st.caption(f"등급: {role_text.get(user['role'], user['role'])}")
        
        st.markdown("---")
        
        menu_options = []
        if user["role"] == 3:
            menu_options.append("⚙️ 관리자 설정")
        menu_options.extend(["📦 서비스 작업", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu_options, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.customers_df = None
            st.session_state.selected_customers = []
            st.session_state.completed_customers = {}
            st.session_state.generated_pdfs = {}
            st.rerun()
    
    if selected == "⚙️ 관리자 설정":
        show_admin_settings()
    elif selected == "📦 서비스 작업":
        show_service_work()
    elif selected == "👤 MyPage":
        show_mypage()
    elif selected == "📢 공지사항":
        show_notices()

# ============================================
# ⚙️ 관리자 설정 (통합)
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔑 API/이메일", "⚡ 모드", "👥 회원관리", "📦 서비스 관리", "🎨 디자인 관리"])
    
    # ===== API/이메일 =====
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🔑 OpenAI API")
            api = st.text_input("API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
            if st.button("💾 API 저장"):
                set_system_config(ConfigKeys.ADMIN_API_KEY, api)
                st.success("✅ 저장됨")
        
        with col2:
            st.markdown("### 📧 Gmail")
            gmail = st.text_input("Gmail 주소", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
            gmail_pw = st.text_input("앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
            if st.button("💾 이메일 저장"):
                set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
                set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
                st.success("✅ 저장됨")
    
    # ===== 모드 =====
    with tab2:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### API 모드")
            api_mode = st.radio("API 사용 방식", ["unified", "separated"],
                index=0 if get_system_config(API_MODE_KEY, "unified") == "unified" else 1,
                format_func=lambda x: "🔒 통일 (관리자만)" if x == "unified" else "🔓 분리 (각자)",
                key="api_mode_radio")
        
        with col2:
            st.markdown("### 이메일 모드")
            email_mode = st.radio("이메일 사용 방식", ["unified", "separated"],
                index=0 if get_system_config(EMAIL_MODE_KEY, "unified") == "unified" else 1,
                format_func=lambda x: "🔒 통일 (관리자만)" if x == "unified" else "🔓 분리 (각자)",
                key="email_mode_radio")
        
        if st.button("💾 모드 저장", type="primary"):
            set_system_config(API_MODE_KEY, api_mode)
            set_system_config(EMAIL_MODE_KEY, email_mode)
            st.success("✅ 저장됨")
    
    # ===== 회원관리 =====
    with tab3:
        st.markdown("### 👥 회원 관리")
        
        subtab1, subtab2 = st.tabs(["전체 회원", "승인 대기"])
        
        with subtab1:
            users = get_all_users()
            for u in users:
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    st.write(f"**{u['name']}** ({u['email']})")
                
                with col2:
                    role_names = {1: "1단계", 2: "2단계", 3: "관리자"}
                    st.caption(f"등급: {role_names.get(u['role'], u['role'])} | {u['status']}")
                
                with col3:
                    if u['id'] != st.session_state.user['id']:
                        new_role = st.selectbox("등급", [1, 2, 3], 
                            index=u['role']-1 if u['role'] in [1,2,3] else 0,
                            format_func=lambda x: {1: "1단계", 2: "2단계", 3: "관리자"}[x],
                            key=f"role_{u['id']}")
                        if new_role != u['role']:
                            if st.button("변경", key=f"change_role_{u['id']}"):
                                update_user_role(u['id'], new_role)
                                st.success("변경됨")
                                st.rerun()
                
                with col4:
                    if u['id'] != st.session_state.user['id'] and u['status'] == 'approved':
                        if st.button("정지", key=f"sus_{u['id']}"):
                            suspend_user(u['id'])
                            st.rerun()
                
                st.markdown("---")
        
        with subtab2:
            pending = get_pending_users()
            if not pending:
                st.success("대기 중인 회원이 없습니다.")
            for u in pending:
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{u['name']}** ({u['email']})")
                if col2.button("✅ 승인", key=f"ap_{u['id']}", type="primary"):
                    approve_user(u['id'])
                    st.rerun()
    
    # ===== 서비스 관리 =====
    with tab4:
        st.markdown("### 📦 서비스 종류 관리 (목차 + 지침)")
        
        # 새 서비스 추가
        with st.expander("➕ 새 서비스 추가", expanded=False):
            new_svc_name = st.text_input("서비스 이름", placeholder="예: 2024년 사주", key="new_svc_name")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📑 목차 (줄바꿈으로 구분)**")
                new_chapters = st.text_area("목차", height=300, 
                    placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운\n4. 연애운", key="new_chapters")
            
            with col2:
                st.markdown("**📜 AI 작성 지침**")
                new_guideline = st.text_area("지침", height=300,
                    placeholder="- 긍정적이고 희망적인 톤으로 작성\n- 각 목차당 300자 이상", key="new_guideline")
            
            if st.button("💾 서비스 저장", type="primary"):
                if new_svc_name:
                    result = add_service(new_svc_name, "")
                    if result.get("success"):
                        svc_id = result.get("id")
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx + 1)
                        if new_guideline:
                            add_guideline(svc_id, f"{new_svc_name} 지침", new_guideline)
                        st.success(f"✅ '{new_svc_name}' 생성됨!")
                        st.rerun()
        
        # 기존 서비스 목록
        st.markdown("---")
        st.markdown("### 📋 등록된 서비스")
        
        services = get_all_services()
        for svc in services:
            with st.expander(f"📌 {svc['name']}", expanded=False):
                chapters = get_chapters_by_service(svc['id'])
                guidelines = get_guidelines_by_service(svc['id'])
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📑 목차**")
                    chapters_text = "\n".join([c['title'] for c in chapters])
                    edited_ch = st.text_area("목차 수정", value=chapters_text, height=250, key=f"edit_ch_{svc['id']}")
                
                with col2:
                    st.markdown("**📜 지침**")
                    guideline_text = guidelines[0]['content'] if guidelines else ""
                    edited_g = st.text_area("지침 수정", value=guideline_text, height=250, key=f"edit_g_{svc['id']}")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("💾 수정 저장", key=f"save_svc_{svc['id']}"):
                        # 기존 목차 삭제 후 재등록
                        for ch in chapters:
                            delete_chapter(ch['id'])
                        for idx, ch in enumerate(edited_ch.strip().split("\n")):
                            if ch.strip():
                                add_chapter(svc['id'], ch.strip(), "", idx + 1)
                        # 지침 업데이트
                        if guidelines:
                            update_guideline(guidelines[0]['id'], guidelines[0]['title'], edited_g)
                        else:
                            add_guideline(svc['id'], f"{svc['name']} 지침", edited_g)
                        st.success("✅ 저장됨")
                        st.rerun()
                
                with col_b:
                    if st.button("🗑️ 삭제", key=f"del_svc_{svc['id']}"):
                        delete_service(svc['id'])
                        st.success("삭제됨")
                        st.rerun()
    
    # ===== 디자인 관리 =====
    with tab5:
        st.markdown("### 🎨 디자인 종류 관리 (속지)")
        st.info("💡 서비스와 동일한 이름으로 디자인을 만들어야 매칭됩니다!")
        
        # 서비스 선택
        services = get_all_services()
        if not services:
            st.warning("서비스를 먼저 등록하세요.")
            return
        
        selected_svc = st.selectbox("서비스 선택", [s['name'] for s in services], key="design_svc")
        selected_svc_obj = next((s for s in services if s['name'] == selected_svc), None)
        
        if selected_svc_obj:
            st.markdown("---")
            
            # 새 디자인 업로드
            with st.expander("➕ 새 디자인 업로드", expanded=False):
                st.markdown("**속지 이미지 업로드**")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown("📕 **표지**")
                    cover_file = st.file_uploader("표지", type=["jpg", "jpeg", "png"], key="up_cover")
                    if cover_file:
                        st.image(cover_file, width=120)
                
                with col2:
                    st.markdown("📄 **내지**")
                    bg_file = st.file_uploader("내지", type=["jpg", "jpeg", "png"], key="up_bg")
                    if bg_file:
                        st.image(bg_file, width=120)
                
                with col3:
                    st.markdown("📋 **안내지**")
                    info_file = st.file_uploader("안내지", type=["jpg", "jpeg", "png"], key="up_info")
                    if info_file:
                        st.image(info_file, width=120)
                
                if st.button("💾 디자인 저장", type="primary"):
                    saved = 0
                    if cover_file:
                        path = save_uploaded_file(cover_file, f"{selected_svc}_cover")
                        add_template(selected_svc_obj['id'], "cover", f"{selected_svc}_표지", path)
                        saved += 1
                    if bg_file:
                        path = save_uploaded_file(bg_file, f"{selected_svc}_bg")
                        add_template(selected_svc_obj['id'], "background", f"{selected_svc}_내지", path)
                        saved += 1
                    if info_file:
                        path = save_uploaded_file(info_file, f"{selected_svc}_info")
                        add_template(selected_svc_obj['id'], "info", f"{selected_svc}_안내지", path)
                        saved += 1
                    if saved > 0:
                        st.success(f"✅ {saved}개 저장됨!")
                        st.rerun()
            
            # 기존 디자인 표시
            st.markdown("---")
            st.markdown("### 📋 등록된 디자인")
            
            templates = get_templates_by_service(selected_svc_obj['id'])
            
            if not templates:
                st.info("등록된 디자인이 없습니다.")
            else:
                cols = st.columns(3)
                
                for idx, ttype in enumerate(["cover", "background", "info"]):
                    with cols[idx]:
                        st.markdown(f"**{TEMPLATE_TYPES_NEW[ttype]}**")
                        type_templates = [t for t in templates if t['template_type'] == ttype]
                        
                        for t in type_templates:
                            if t.get('image_path') and os.path.exists(t['image_path']):
                                st.image(t['image_path'], width=100)
                            st.caption(t['name'])
                            if st.button("🗑️", key=f"del_t_{t['id']}"):
                                delete_template(t['id'])
                                st.rerun()

# ============================================
# 📦 서비스 작업 (일반 사용자용)
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    # API 확인
    api_info = get_api_key()
    if not api_info["key"]:
        st.error("⚠️ API 키가 설정되지 않았습니다. 관리자에게 문의하세요.")
        return
    
    # ===== 1. 서비스 선택 =====
    st.markdown('<div class="section-header">1️⃣ 서비스 선택</div>', unsafe_allow_html=True)
    
    services = get_all_services()
    if not services:
        st.warning("등록된 서비스가 없습니다. 관리자에게 문의하세요.")
        return
    
    selected_service_name = st.selectbox("서비스 종류", [s['name'] for s in services], key="work_service")
    selected_service = next((s for s in services if s['name'] == selected_service_name), None)
    
    if selected_service:
        chapters = get_chapters_by_service(selected_service['id'])
        st.success(f"✅ '{selected_service_name}' 선택됨 (목차 {len(chapters)}개)")
    
    # ===== 2. 디자인 선택 =====
    st.markdown('<div class="section-header">2️⃣ 디자인 선택</div>', unsafe_allow_html=True)
    
    if selected_service:
        templates = get_templates_by_service(selected_service['id'])
        
        if templates:
            # 이미지 미리보기
            cols = st.columns(3)
            for idx, ttype in enumerate(["cover", "background", "info"]):
                with cols[idx]:
                    st.markdown(f"**{TEMPLATE_TYPES_NEW[ttype]}**")
                    type_t = [t for t in templates if t['template_type'] == ttype]
                    if type_t and type_t[0].get('image_path') and os.path.exists(type_t[0]['image_path']):
                        st.image(type_t[0]['image_path'], width=80)
                    else:
                        st.caption("없음")
            
            st.success("✅ 디자인 적용됨")
        else:
            st.warning("등록된 디자인이 없습니다.")
    
    # ===== 3. 폰트/스타일 설정 =====
    st.markdown('<div class="section-header">3️⃣ 폰트 / 스타일 설정</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        font = st.selectbox("폰트", list(FONT_OPTIONS.keys()), key="font")
    with col2:
        font_size = st.number_input("크기", 8, 30, 12, key="font_size")
    with col3:
        char_width = st.number_input("장평%", 50, 150, 100, key="char_width")
    with col4:
        letter_spacing = st.number_input("자간", -5, 10, 0, key="letter_sp")
    with col5:
        line_height = st.number_input("행간", 10, 50, 18, key="line_h")
    
    font_settings = {
        "font": FONT_OPTIONS[font],
        "size": font_size,
        "char_width": char_width,
        "letter_spacing": letter_spacing,
        "line_height": line_height
    }
    
    # ===== 4. 고객 파일 업로드 =====
    st.markdown('<div class="section-header">4️⃣ 고객 파일 업로드</div>', unsafe_allow_html=True)
    
    uploaded_file = st.file_uploader("엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust_file")
    
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
        st.caption(f"컬럼: {', '.join(df.columns.tolist())}")
    
    # ===== 5. 고객 선택 및 PDF 변환 =====
    if st.session_state.customers_df is not None and selected_service:
        st.markdown('<div class="section-header">5️⃣ 고객 선택 및 PDF 변환</div>', unsafe_allow_html=True)
        
        df = st.session_state.customers_df
        
        # 이름 컬럼 찾기
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        # 선택 모드
        mode = st.radio("선택 모드", ["✅ 전체", "🔘 개별"], horizontal=True, key="sel_mode")
        
        st.markdown("---")
        
        # 고객 목록
        cols_per_row = 4
        selected = []
        
        for row_idx in range((len(df) + cols_per_row - 1) // cols_per_row):
            cols = st.columns(cols_per_row)
            for col_idx in range(cols_per_row):
                idx = row_idx * cols_per_row + col_idx
                if idx >= len(df):
                    break
                
                with cols[col_idx]:
                    row = df.iloc[idx]
                    cust_name = row[name_col]
                    is_done = idx in st.session_state.completed_customers
                    
                    if is_done:
                        st.markdown(f"✅ **{cust_name}**")
                        
                        # 다운로드 버튼
                        pdf_data = st.session_state.generated_pdfs.get(idx)
                        if pdf_data:
                            st.download_button(
                                "⬇️ 다운로드",
                                pdf_data,
                                file_name=f"{cust_name}_운세.pdf",
                                mime="application/pdf",
                                key=f"dl_{idx}"
                            )
                    else:
                        if mode == "🔘 개별":
                            if st.checkbox(f"⏳ {cust_name}", key=f"sel_{idx}"):
                                selected.append(idx)
                        else:
                            st.markdown(f"⏳ **{cust_name}**")
                            selected.append(idx)
        
        if mode == "✅ 전체":
            selected = [i for i in range(len(df)) if i not in st.session_state.completed_customers]
        
        st.session_state.selected_customers = selected
        
        st.markdown("---")
        
        # 현황
        done = len(st.session_state.completed_customers)
        total = len(df)
        st.info(f"📊 선택: {len(selected)}명 | ✅ 완료: {done}/{total}")
        st.progress(done / total if total > 0 else 0)
        
        # 변환 버튼
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 PDF 변환 시작", type="primary", use_container_width=True):
                if not selected:
                    st.error("선택된 고객이 없습니다.")
                else:
                    progress = st.progress(0)
                    status = st.empty()
                    
                    for i, idx in enumerate(selected):
                        row = df.iloc[idx]
                        cust_name = row[name_col]
                        
                        status.text(f"📝 {cust_name} 생성 중... ({i+1}/{len(selected)})")
                        progress.progress((i + 1) / len(selected))
                        
                        # 고객 데이터를 딕셔너리로
                        customer_data = row.to_dict()
                        
                        # PDF 생성
                        pdf_bytes = generate_pdf_for_customer(
                            customer_data, 
                            selected_service['id'], 
                            font_settings, 
                            api_info["key"]
                        )
                        
                        if pdf_bytes:
                            st.session_state.completed_customers[idx] = True
                            st.session_state.generated_pdfs[idx] = pdf_bytes
                            
                            # 완료 알림
                            st.toast(f"🔔 {cust_name} 완료!")
                    
                    status.text("✅ 모든 PDF 변환 완료!")
                    st.balloons()
                    
                    # 종소리
                    st.markdown("""
                    <audio autoplay>
                        <source src="https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3" type="audio/mpeg">
                    </audio>
                    """, unsafe_allow_html=True)
                    
                    st.rerun()
        
        with col2:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state.completed_customers = {}
                st.session_state.generated_pdfs = {}
                st.session_state.selected_customers = []
                st.rerun()

# ============================================
# 👤 MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    tab1, tab2, tab3 = st.tabs(["📋 내 정보", "🔑 API", "📧 이메일"])
    
    with tab1:
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        if st.button("💾 저장"):
            result = update_user_profile(user['id'], name=new_name)
            if result["success"]:
                st.session_state.user['name'] = new_name
                st.success("저장됨")
        
        st.markdown("---")
        st.markdown("### 비밀번호 변경")
        old_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호", type="password")
        
        if st.button("🔒 변경"):
            if old_pw and new_pw:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success("변경됨")
                else:
                    st.error(result["error"])
    
    with tab2:
        api_mode = get_system_config(API_MODE_KEY, "unified")
        if api_mode == "unified":
            st.info("🔒 통일 모드: 관리자 API 사용 중")
        else:
            my_api = st.text_input("내 API 키", value=user.get('api_key', '') or '', type="password")
            if st.button("💾 API 저장"):
                result = update_user_profile(user['id'], api_key=my_api)
                if result["success"]:
                    st.session_state.user['api_key'] = my_api
                    st.success("저장됨")
    
    with tab3:
        email_mode = get_system_config(EMAIL_MODE_KEY, "unified")
        if email_mode == "unified":
            st.info("🔒 통일 모드: 관리자 이메일 사용 중")
        else:
            my_gmail = st.text_input("내 Gmail", value=user.get('gmail_address', '') or '')
            my_gmail_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
            if st.button("💾 이메일 저장"):
                result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_gmail_pw)
                if result["success"]:
                    st.session_state.user['gmail_address'] = my_gmail
                    st.session_state.user['gmail_app_password'] = my_gmail_pw
                    st.success("저장됨")

# ============================================
# 📢 공지사항
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    user = st.session_state.user
    is_admin = user['role'] == 3
    
    # 관리자: 글쓰기
    if is_admin:
        with st.expander("✏️ 새 공지 작성", expanded=False):
            new_title = st.text_input("제목", key="n_title")
            new_content = st.text_area("내용", height=200, key="n_content")
            is_pinned = st.checkbox("📌 상단 고정")
            
            if st.button("💾 등록", type="primary"):
                if new_title and new_content:
                    result = create_notice(user['id'], new_title, new_content, None, is_pinned)
                    if result.get("success"):
                        st.success("✅ 등록됨!")
                        st.rerun()
    
    st.markdown("---")
    
    # 공지 목록
    notices = get_all_notices()
    
    if not notices:
        st.info("등록된 공지사항이 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            
            with st.expander(f"{pin}**{n['title']}** ({n['created_at']})", expanded=False):
                
                # 관리자: 수정 모드
                if is_admin:
                    edit_title = st.text_input("제목", value=n['title'], key=f"et_{n['id']}")
                    edit_content = st.text_area("내용", value=n['content'], height=150, key=f"ec_{n['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("💾 수정", key=f"save_{n['id']}"):
                            update_notice(n['id'], edit_title, edit_content)
                            st.success("수정됨")
                            st.rerun()
                    
                    with col2:
                        if st.button("📌 고정 토글", key=f"pin_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            st.rerun()
                    
                    with col3:
                        if st.button("🗑️ 삭제", key=f"del_{n['id']}"):
                            delete_notice(n['id'])
                            st.success("삭제됨")
                            st.rerun()
                else:
                    # 일반 사용자: 읽기만
                    st.write(n['content'])

# ============================================
# 메인
# ============================================

def main():
    if not st.session_state.logged_in:
        show_login_page()
    else:
        show_main_app()

if __name__ == "__main__":
    main()
