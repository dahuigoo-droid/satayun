# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
상품 등록 + 회원 권한 + PDF 개선 버전
"""

import streamlit as st
import pandas as pd
import os
import time
import base64
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

from database import init_db, SessionLocal, UserRole
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user,
    update_user_role, update_user_permission, update_user_modes,
    create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_service_by_id, add_service, delete_service, update_service,
    get_services_by_owner, get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, delete_chapter, update_chapter,
    get_guidelines_by_service, add_guideline, delete_guideline, update_guideline,
    get_templates_by_service, add_template, delete_template
)
from notices import get_all_notices, create_notice, update_notice, delete_notice, toggle_pin_notice

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
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(255,255,255,0.1);
    }
    
    /* 섹션 헤더 - 글자 부분만 배경 */
    .section-title {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 8px 20px;
        border-radius: 20px;
        color: white;
        font-weight: bold;
        font-size: 1.1rem;
        margin: 20px 0 15px 0;
    }
    
    /* 구분선 */
    .divider {
        border-top: 2px solid rgba(255,255,255,0.1);
        margin: 25px 0;
    }
    
    /* 고객 카드 */
    .customer-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        padding: 15px;
        margin: 8px 0;
    }
    
    /* 상태 배지 */
    .badge-done { 
        background: #28a745; 
        color: white; 
        padding: 2px 8px; 
        border-radius: 10px; 
        font-size: 0.8rem;
        margin-left: 10px;
    }
    .badge-pending { 
        background: #ffc107; 
        color: black; 
        padding: 2px 8px; 
        border-radius: 10px; 
        font-size: 0.8rem;
    }
    
    /* 권한 배지 */
    .permission-admin { background: #dc3545; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; }
    .permission-individual { background: #17a2b8; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; }
    .permission-execute { background: #6c757d; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태
# ============================================

defaults = {
    'logged_in': False,
    'user': None,
    'customers_df': None,
    'admin_created': False,
    'selected_customers': [],
    'completed_customers': {},
    'generated_pdfs': {},
    'processing_progress': {}
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

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
FONT_DIR = "fonts"
for d in [UPLOAD_DIR, OUTPUT_DIR, FONT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# ============================================
# 카테고리 상수
# ============================================

CATEGORIES = ["사주", "타로", "연애"]
TEMPLATE_TYPES = {
    "cover": "📕 표지",
    "background": "📄 내지",
    "info": "📋 안내지"
}

# ============================================
# 유틸리티
# ============================================

def is_admin() -> bool:
    return st.session_state.user and st.session_state.user.get('role') == 2

def can_edit_service() -> bool:
    """서비스 편집 가능 여부"""
    user = st.session_state.user
    if not user:
        return False
    if user.get('role') == 2:  # 관리자
        return True
    if user.get('permission_type') == 'individual' and user.get('service_mode') == 'separated':
        return True
    return False

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
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    
    if user.get('api_mode') == 'separated' and user.get('api_key'):
        return {"key": user['api_key'], "source": "개인"}
    return {"key": admin_api, "source": "관리자"}

def get_available_services():
    """현재 사용자가 사용 가능한 서비스 목록"""
    user = st.session_state.user
    
    if user.get('role') == 2:  # 관리자
        return get_all_services()
    
    if user.get('permission_type') == 'individual' and user.get('service_mode') == 'separated':
        # 개별 모드: 자신이 만든 서비스 + 관리자 공용 서비스
        own_services = get_services_by_owner(user['id'])
        admin_services = get_services_by_owner(None)  # owner_id가 NULL인 것
        return own_services + admin_services
    else:
        # 수행 모드: 관리자가 만든 공용 서비스만
        return get_services_by_owner(None)

def play_completion_sound():
    """완료 시 종소리"""
    sound_html = """
    <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-09.mp3" type="audio/mpeg">
    </audio>
    """
    st.markdown(sound_html, unsafe_allow_html=True)

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, customer_data: dict) -> str:
    """GPT로 챕터 내용 생성"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        customer_info = "\n".join([f"- {k}: {v}" for k, v in customer_data.items()])
        
        prompt = f"""당신은 전문 운세 작성가입니다.

[고객 정보]
{customer_info}

[작성 지침]
{guideline}

[작성할 챕터]
{chapter_title}

위 정보를 바탕으로 '{chapter_title}' 챕터의 내용을 작성해주세요.
- 고객 정보를 반영하여 개인화된 내용 작성
- 긍정적이고 희망적인 톤 유지
- 300-500자 분량
- 마크다운 없이 순수 텍스트"""
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"[내용 생성 오류: {str(e)}]"


def create_pdf_with_design(customer_name: str, chapters_content: list, templates: dict, font_settings: dict) -> bytes:
    """디자인이 적용된 PDF 생성"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import PageTemplate, Frame, BaseDocTemplate
        from reportlab.lib.colors import black
        
        buffer = BytesIO()
        
        # A4 사이즈
        page_width, page_height = A4
        
        # 기본 문서 생성
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4,
            leftMargin=25*mm, 
            rightMargin=25*mm,
            topMargin=30*mm, 
            bottomMargin=30*mm
        )
        
        # 스타일 설정
        font_size = font_settings.get('size', 12)
        line_height = font_settings.get('line_height', 18)
        
        title_style = ParagraphStyle(
            'Title',
            fontSize=24,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=black,
            fontName='Helvetica-Bold'
        )
        
        chapter_style = ParagraphStyle(
            'Chapter',
            fontSize=16,
            spaceBefore=20,
            spaceAfter=15,
            textColor=black,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'Body',
            fontSize=font_size,
            leading=line_height,
            alignment=TA_JUSTIFY,
            spaceAfter=12,
            textColor=black,
            fontName='Helvetica'
        )
        
        page_num_style = ParagraphStyle(
            'PageNum',
            fontSize=10,
            alignment=TA_CENTER,
            textColor=black
        )
        
        story = []
        
        # ===== 표지 =====
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                img = Image(cover_path, width=page_width-50*mm, height=page_height-60*mm)
                img.hAlign = 'CENTER'
                story.append(Spacer(1, 20*mm))
                story.append(img)
            except:
                story.append(Spacer(1, 80*mm))
                story.append(Paragraph(f"🔮 {customer_name}님의 운세", title_style))
        else:
            story.append(Spacer(1, 80*mm))
            story.append(Paragraph(f"🔮 {customer_name}님의 운세", title_style))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph(datetime.now().strftime("%Y년 %m월 %d일"), 
                                  ParagraphStyle('Date', fontSize=14, alignment=TA_CENTER)))
        
        story.append(PageBreak())
        
        # ===== 본문 (내지) =====
        for idx, chapter in enumerate(chapters_content):
            # 챕터 제목
            safe_title = chapter['title'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            story.append(Paragraph(f"📌 {safe_title}", chapter_style))
            
            # 내용
            content = chapter['content']
            paragraphs = content.split('\n\n') if '\n\n' in content else content.split('\n')
            
            for para in paragraphs:
                if para.strip():
                    safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    story.append(Paragraph(safe_para, body_style))
            
            story.append(Spacer(1, 15*mm))
            
            # 페이지 번호 (중앙)
            story.append(Paragraph(f"- {idx + 2} -", page_num_style))
            
            if idx < len(chapters_content) - 1:
                story.append(PageBreak())
        
        # ===== 안내지 (마지막) =====
        story.append(PageBreak())
        info_path = templates.get('info')
        if info_path and os.path.exists(info_path):
            try:
                img = Image(info_path, width=page_width-50*mm, height=page_height-60*mm)
                img.hAlign = 'CENTER'
                story.append(Spacer(1, 20*mm))
                story.append(img)
            except:
                story.append(Spacer(1, 80*mm))
                story.append(Paragraph("감사합니다", title_style))
        else:
            story.append(Spacer(1, 80*mm))
            story.append(Paragraph("감사합니다", title_style))
            story.append(Spacer(1, 20*mm))
            story.append(Paragraph("더 많은 서비스를 원하시면 문의해주세요.", 
                                  ParagraphStyle('Info', fontSize=12, alignment=TA_CENTER)))
        
        doc.build(story)
        
        return buffer.getvalue()
    
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service_id: int, font_settings: dict, api_key: str) -> bytes:
    """고객용 PDF 생성"""
    
    # 목차와 지침
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    # 템플릿(디자인)
    templates_list = get_templates_by_service(service_id)
    templates = {}
    for t in templates_list:
        if t.get('image_path') and os.path.exists(t['image_path']):
            templates[t['template_type']] = t['image_path']
    
    # 고객 이름
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    # 각 챕터별 내용 생성
    chapters_content = []
    for ch in chapters:
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({
            "title": ch['title'],
            "content": content
        })
    
    # PDF 생성
    return create_pdf_with_design(customer_name, chapters_content, templates, font_settings)

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        if st.session_state.admin_created:
            st.success("✅ 관리자 계정이 생성되었습니다!")
            st.session_state.admin_created = False
        
        tab1, tab2 = st.tabs(["🔐 로그인", "📝 회원가입"])
        
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
            reg_pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if all([reg_name, reg_email, reg_pw, reg_pw2]):
                    if reg_pw != reg_pw2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        result = register_user(reg_email, reg_pw, reg_name)
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
                admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw")
                
                if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                    if all([admin_name, admin_email, admin_pw]):
                        result = create_first_admin(admin_email, admin_pw, admin_name)
                        if result["success"]:
                            st.session_state.admin_created = True
                            st.rerun()

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        
        # 권한 배지
        if user['role'] == 2:
            st.markdown('<span class="permission-admin">관리자</span>', unsafe_allow_html=True)
        elif user.get('permission_type') == 'individual':
            st.markdown('<span class="permission-individual">개별</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="permission-execute">수행</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        menu = []
        if user["role"] == 2:
            menu.append("⚙️ 관리자 설정")
        menu.extend(["📦 서비스 작업", "👤 MyPage", "📢 공지사항"])
        
        selected = st.radio("메뉴", menu, label_visibility="collapsed")
        
        st.markdown("---")
        if st.button("🚪 로그아웃", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
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
# ⚙️ 관리자 설정
# ============================================

def show_admin_settings():
    st.title("⚙️ 관리자 설정")
    
    tab1, tab2, tab3 = st.tabs(["🔑 API/이메일", "👥 회원관리", "📦 상품등록"])
    
    # ===== API/이메일 =====
    with tab1:
        st.markdown('<span class="section-title">🔑 관리자 API 설정</span>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            api = st.text_input("OpenAI API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
            if st.button("💾 API 저장"):
                set_system_config(ConfigKeys.ADMIN_API_KEY, api)
                st.success("✅ 저장됨")
        
        with col2:
            gmail = st.text_input("Gmail 주소", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
            gmail_pw = st.text_input("앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
            if st.button("💾 이메일 저장"):
                set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
                set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
                st.success("✅ 저장됨")
    
    # ===== 회원관리 =====
    with tab2:
        st.markdown('<span class="section-title">👥 회원 관리</span>', unsafe_allow_html=True)
        
        subtab1, subtab2 = st.tabs(["전체 회원", "승인 대기"])
        
        with subtab1:
            users = get_all_users()
            
            for u in users:
                if u['id'] == st.session_state.user['id']:
                    continue  # 자기 자신 제외
                
                st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                
                with col1:
                    role_badge = "🔴 관리자" if u['role'] == 2 else "🔵 일반"
                    st.write(f"**{u['name']}** ({u['email']})")
                    st.caption(role_badge)
                
                with col2:
                    # 등급 선택
                    new_role = st.selectbox(
                        "등급",
                        [1, 2],
                        index=0 if u['role'] == 1 else 1,
                        format_func=lambda x: "일반" if x == 1 else "관리자",
                        key=f"role_{u['id']}"
                    )
                    
                    # 권한 타입 선택
                    perm_options = ["execute", "individual"]
                    current_perm = u.get('permission_type', 'execute')
                    new_perm = st.selectbox(
                        "권한",
                        perm_options,
                        index=perm_options.index(current_perm) if current_perm in perm_options else 0,
                        format_func=lambda x: "수행" if x == "execute" else "개별",
                        key=f"perm_{u['id']}"
                    )
                
                with col3:
                    # 모드 설정
                    st.caption("모드 설정")
                    mode_cols = st.columns(2)
                    
                    with mode_cols[0]:
                        api_mode = st.selectbox("API", ["unified", "separated"],
                            index=0 if u.get('api_mode') == 'unified' else 1,
                            format_func=lambda x: "통일" if x == "unified" else "분리",
                            key=f"api_m_{u['id']}")
                        
                        svc_mode = st.selectbox("서비스", ["unified", "separated"],
                            index=0 if u.get('service_mode') == 'unified' else 1,
                            format_func=lambda x: "통일" if x == "unified" else "분리",
                            key=f"svc_m_{u['id']}")
                    
                    with mode_cols[1]:
                        email_mode = st.selectbox("이메일", ["unified", "separated"],
                            index=0 if u.get('email_mode') == 'unified' else 1,
                            format_func=lambda x: "통일" if x == "unified" else "분리",
                            key=f"email_m_{u['id']}")
                        
                        design_mode = st.selectbox("디자인", ["unified", "separated"],
                            index=0 if u.get('design_mode') == 'unified' else 1,
                            format_func=lambda x: "통일" if x == "unified" else "분리",
                            key=f"design_m_{u['id']}")
                
                with col4:
                    if st.button("💾 저장", key=f"save_u_{u['id']}"):
                        update_user_role(u['id'], new_role)
                        update_user_permission(u['id'], new_perm)
                        update_user_modes(u['id'], api_mode, email_mode, svc_mode, design_mode)
                        st.success("저장됨")
                        st.rerun()
                    
                    if u['status'] == 'approved':
                        if st.button("🚫 정지", key=f"sus_{u['id']}"):
                            suspend_user(u['id'])
                            st.rerun()
        
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
    
    # ===== 상품등록 =====
    with tab3:
        st.markdown('<span class="section-title">📦 상품(서비스+디자인) 등록</span>', unsafe_allow_html=True)
        
        # 새 상품 등록
        with st.expander("➕ 새 상품 등록", expanded=False):
            st.markdown("---")
            
            # 상품명
            product_name = st.text_input("상품명", placeholder="예: 2024년 신년 사주")
            
            # 1차 분류 (카테고리)
            st.markdown("**1차 분류** (최대 3개 선택)")
            cat_cols = st.columns(3)
            selected_cats = []
            for idx, cat in enumerate(CATEGORIES):
                with cat_cols[idx]:
                    if st.checkbox(cat, key=f"new_cat_{cat}"):
                        selected_cats.append(cat)
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            # 목차 + 지침
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**📑 목차** (줄바꿈으로 구분)")
                new_chapters = st.text_area("목차", height=200, key="new_ch",
                    placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운\n4. 연애운")
            
            with col2:
                st.markdown("**📜 AI 작성 지침**")
                new_guideline = st.text_area("지침", height=200, key="new_guide",
                    placeholder="- 긍정적이고 희망적인 톤\n- 각 목차당 300자 이상")
            
            st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
            
            # 2차 분류 (디자인)
            st.markdown("**2차 분류 - 디자인 업로드**")
            des_cols = st.columns(3)
            
            with des_cols[0]:
                st.markdown("📕 **표지**")
                cover_file = st.file_uploader("표지", type=["jpg", "jpeg", "png"], key="new_cover", label_visibility="collapsed")
                if cover_file:
                    st.image(cover_file, width=100)
            
            with des_cols[1]:
                st.markdown("📄 **내지**")
                bg_file = st.file_uploader("내지", type=["jpg", "jpeg", "png"], key="new_bg", label_visibility="collapsed")
                if bg_file:
                    st.image(bg_file, width=100)
            
            with des_cols[2]:
                st.markdown("📋 **안내지**")
                info_file = st.file_uploader("안내지", type=["jpg", "jpeg", "png"], key="new_info", label_visibility="collapsed")
                if info_file:
                    st.image(info_file, width=100)
            
            st.markdown("---")
            
            if st.button("💾 상품 등록", type="primary", use_container_width=True):
                if product_name and selected_cats:
                    # 서비스 생성
                    result = add_service(product_name, "", ",".join(selected_cats), None)
                    if result.get("success"):
                        svc_id = result.get("id")
                        
                        # 목차 추가
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx + 1)
                        
                        # 지침 추가
                        if new_guideline:
                            add_guideline(svc_id, f"{product_name} 지침", new_guideline)
                        
                        # 디자인 추가
                        if cover_file:
                            path = save_uploaded_file(cover_file, f"{product_name}_cover")
                            add_template(svc_id, "cover", f"{product_name}_표지", path)
                        if bg_file:
                            path = save_uploaded_file(bg_file, f"{product_name}_bg")
                            add_template(svc_id, "background", f"{product_name}_내지", path)
                        if info_file:
                            path = save_uploaded_file(info_file, f"{product_name}_info")
                            add_template(svc_id, "info", f"{product_name}_안내지", path)
                        
                        st.success(f"✅ '{product_name}' 상품이 등록되었습니다!")
                        st.rerun()
                else:
                    st.error("상품명과 카테고리를 입력하세요.")
        
        # 등록된 상품 목록
        st.markdown("---")
        st.markdown('<span class="section-title">📋 등록된 상품</span>', unsafe_allow_html=True)
        
        services = get_all_services()
        
        if not services:
            st.info("등록된 상품이 없습니다.")
        else:
            for svc in services:
                with st.expander(f"📌 {svc['name']} ({svc.get('categories', '')})", expanded=False):
                    chapters = get_chapters_by_service(svc['id'])
                    guidelines = get_guidelines_by_service(svc['id'])
                    templates = get_templates_by_service(svc['id'])
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**📑 목차**")
                        ch_text = "\n".join([c['title'] for c in chapters])
                        edited_ch = st.text_area("목차 수정", value=ch_text, height=150, key=f"ed_ch_{svc['id']}")
                        
                        st.markdown("**📜 지침**")
                        g_text = guidelines[0]['content'] if guidelines else ""
                        edited_g = st.text_area("지침 수정", value=g_text, height=150, key=f"ed_g_{svc['id']}")
                    
                    with col2:
                        st.markdown("**🎨 디자인**")
                        t_cols = st.columns(3)
                        
                        for idx, ttype in enumerate(["cover", "background", "info"]):
                            with t_cols[idx]:
                                st.caption(TEMPLATE_TYPES[ttype])
                                t_list = [t for t in templates if t['template_type'] == ttype]
                                if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                                    st.image(t_list[0]['image_path'], width=60)
                                else:
                                    st.caption("없음")
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.button("💾 수정 저장", key=f"save_{svc['id']}"):
                            # 목차 업데이트
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
                            st.success("저장됨")
                            st.rerun()
                    
                    with col_b:
                        if st.button("🗑️ 삭제", key=f"del_{svc['id']}"):
                            delete_service(svc['id'])
                            st.rerun()

# ============================================
# 📦 서비스 작업
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    user = st.session_state.user
    
    # API 확인
    api_info = get_api_key()
    if not api_info["key"]:
        st.error("⚠️ API 키가 설정되지 않았습니다.")
        return
    
    # 개별 모드인 경우 서비스 편집 가능
    if can_edit_service():
        with st.expander("➕ 내 서비스 추가", expanded=False):
            show_service_editor(user['id'])
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 1. 서비스 선택 =====
    st.markdown('<span class="section-title">1️⃣ 서비스 선택</span>', unsafe_allow_html=True)
    
    services = get_available_services()
    if not services:
        st.warning("사용 가능한 서비스가 없습니다.")
        return
    
    selected_svc_name = st.selectbox("서비스", [s['name'] for s in services], key="work_svc")
    selected_svc = next((s for s in services if s['name'] == selected_svc_name), None)
    
    if selected_svc:
        chapters = get_chapters_by_service(selected_svc['id'])
        templates = get_templates_by_service(selected_svc['id'])
        st.success(f"✅ '{selected_svc_name}' (목차 {len(chapters)}개)")
        
        # 디자인 미리보기
        if templates:
            cols = st.columns(3)
            for idx, ttype in enumerate(["cover", "background", "info"]):
                with cols[idx]:
                    t_list = [t for t in templates if t['template_type'] == ttype]
                    if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                        st.image(t_list[0]['image_path'], width=60)
                    else:
                        st.caption(f"{TEMPLATE_TYPES[ttype]}: 없음")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 2. 폰트/스타일 =====
    st.markdown('<span class="section-title">2️⃣ 폰트/스타일</span>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        font_size = st.number_input("글자 크기", 8, 24, 12, key="f_size")
    with col2:
        line_height = st.number_input("행간", 12, 36, 18, key="line_h")
    with col3:
        st.caption("추가 설정")
    
    font_settings = {"size": font_size, "line_height": line_height}
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 3. 고객 파일 =====
    st.markdown('<span class="section-title">3️⃣ 고객 파일</span>', unsafe_allow_html=True)
    
    uploaded = st.file_uploader("엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust")
    
    if uploaded:
        df = pd.read_excel(uploaded)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 4. PDF 생성 =====
    if st.session_state.customers_df is not None and selected_svc:
        st.markdown('<span class="section-title">4️⃣ PDF 생성</span>', unsafe_allow_html=True)
        
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
        mode = st.radio("모드", ["✅ 전체", "🔘 개별"], horizontal=True, key="mode")
        
        # 고객 목록 (이름 + 진행바 + 완료 + 다운로드)
        st.markdown("---")
        
        selected = []
        for idx, row in df.iterrows():
            cust_name = row[name_col]
            is_done = idx in st.session_state.completed_customers
            progress = st.session_state.processing_progress.get(idx, 0)
            
            col1, col2, col3, col4 = st.columns([2, 3, 1, 1])
            
            with col1:
                if mode == "🔘 개별":
                    if st.checkbox(cust_name, key=f"sel_{idx}", value=is_done):
                        if not is_done:
                            selected.append(idx)
                else:
                    st.write(f"**{cust_name}**")
                    if not is_done:
                        selected.append(idx)
            
            with col2:
                if is_done:
                    st.progress(1.0)
                elif progress > 0:
                    st.progress(progress)
                else:
                    st.progress(0.0)
            
            with col3:
                if is_done:
                    st.markdown('<span class="badge-done">완료</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="badge-pending">대기</span>', unsafe_allow_html=True)
            
            with col4:
                if is_done:
                    pdf_data = st.session_state.generated_pdfs.get(idx)
                    if pdf_data:
                        st.download_button("⬇️", pdf_data, 
                            file_name=f"{cust_name}_운세.pdf",
                            mime="application/pdf",
                            key=f"dl_{idx}")
        
        st.markdown("---")
        
        # 통계
        done = len(st.session_state.completed_customers)
        total = len(df)
        st.info(f"📊 완료: {done}/{total}")
        
        # 변환 버튼
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🚀 PDF 변환", type="primary", use_container_width=True):
                pending = [i for i in selected if i not in st.session_state.completed_customers]
                
                if not pending:
                    st.warning("변환할 고객이 없습니다.")
                else:
                    status = st.empty()
                    
                    for i, idx in enumerate(pending):
                        row = df.iloc[idx]
                        cust_name = row[name_col]
                        
                        status.text(f"📝 {cust_name} 생성 중... ({i+1}/{len(pending)})")
                        st.session_state.processing_progress[idx] = (i + 1) / len(pending)
                        
                        customer_data = row.to_dict()
                        pdf_bytes = generate_pdf_for_customer(
                            customer_data,
                            selected_svc['id'],
                            font_settings,
                            api_info["key"]
                        )
                        
                        if pdf_bytes:
                            st.session_state.completed_customers[idx] = True
                            st.session_state.generated_pdfs[idx] = pdf_bytes
                            st.toast(f"🔔 {cust_name} 완료!")
                    
                    status.text("✅ 완료!")
                    st.balloons()
                    
                    # 종소리
                    play_completion_sound()
                    st.rerun()
        
        with col2:
            if st.button("🔄 초기화", use_container_width=True):
                st.session_state.completed_customers = {}
                st.session_state.generated_pdfs = {}
                st.session_state.processing_progress = {}
                st.rerun()


def show_service_editor(owner_id: int):
    """개별 모드 사용자용 서비스 편집기"""
    st.markdown("**내 서비스 추가**")
    
    svc_name = st.text_input("서비스명", key="my_svc_name")
    
    col1, col2 = st.columns(2)
    with col1:
        my_chapters = st.text_area("목차", height=150, key="my_ch")
    with col2:
        my_guideline = st.text_area("지침", height=150, key="my_g")
    
    st.markdown("**디자인**")
    d_cols = st.columns(3)
    with d_cols[0]:
        my_cover = st.file_uploader("표지", type=["jpg", "jpeg", "png"], key="my_cover")
    with d_cols[1]:
        my_bg = st.file_uploader("내지", type=["jpg", "jpeg", "png"], key="my_bg")
    with d_cols[2]:
        my_info = st.file_uploader("안내지", type=["jpg", "jpeg", "png"], key="my_info")
    
    if st.button("💾 저장", key="save_my_svc"):
        if svc_name:
            result = add_service(svc_name, "", "", owner_id)
            if result.get("success"):
                svc_id = result.get("id")
                
                if my_chapters:
                    for idx, ch in enumerate(my_chapters.strip().split("\n")):
                        if ch.strip():
                            add_chapter(svc_id, ch.strip(), "", idx + 1)
                
                if my_guideline:
                    add_guideline(svc_id, f"{svc_name} 지침", my_guideline)
                
                if my_cover:
                    path = save_uploaded_file(my_cover, f"{svc_name}_cover")
                    add_template(svc_id, "cover", f"{svc_name}_표지", path)
                if my_bg:
                    path = save_uploaded_file(my_bg, f"{svc_name}_bg")
                    add_template(svc_id, "background", f"{svc_name}_내지", path)
                if my_info:
                    path = save_uploaded_file(my_info, f"{svc_name}_info")
                    add_template(svc_id, "info", f"{svc_name}_안내지", path)
                
                st.success("저장됨!")
                st.rerun()

# ============================================
# 👤 MyPage
# ============================================

def show_mypage():
    st.title("👤 MyPage")
    user = st.session_state.user
    
    tab1, tab2 = st.tabs(["📋 내 정보", "🔑 API/이메일"])
    
    with tab1:
        new_name = st.text_input("이름", value=user['name'])
        st.text_input("이메일", value=user['email'], disabled=True)
        
        if st.button("💾 저장"):
            result = update_user_profile(user['id'], name=new_name)
            if result["success"]:
                st.session_state.user['name'] = new_name
                st.success("저장됨")
        
        st.markdown("---")
        old_pw = st.text_input("현재 비밀번호", type="password")
        new_pw = st.text_input("새 비밀번호", type="password")
        
        if st.button("🔒 비밀번호 변경"):
            if old_pw and new_pw:
                result = change_password(user['id'], old_pw, new_pw)
                if result["success"]:
                    st.success("변경됨")
                else:
                    st.error(result["error"])
    
    with tab2:
        if user.get('api_mode') == 'separated':
            my_api = st.text_input("내 API 키", value=user.get('api_key', '') or '', type="password")
            if st.button("💾 API 저장"):
                result = update_user_profile(user['id'], api_key=my_api)
                if result["success"]:
                    st.session_state.user['api_key'] = my_api
                    st.success("저장됨")
        else:
            st.info("🔒 API: 관리자 통일 모드")
        
        if user.get('email_mode') == 'separated':
            my_gmail = st.text_input("내 Gmail", value=user.get('gmail_address', '') or '')
            my_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
            if st.button("💾 이메일 저장"):
                result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_pw)
                if result["success"]:
                    st.session_state.user['gmail_address'] = my_gmail
                    st.session_state.user['gmail_app_password'] = my_pw
                    st.success("저장됨")
        else:
            st.info("🔒 이메일: 관리자 통일 모드")

# ============================================
# 📢 공지사항
# ============================================

def show_notices():
    st.title("📢 공지사항")
    
    if is_admin():
        with st.expander("✏️ 새 공지 작성", expanded=False):
            title = st.text_input("제목", key="n_title")
            content = st.text_area("내용", height=150, key="n_content")
            pinned = st.checkbox("📌 상단 고정")
            
            if st.button("💾 등록", type="primary"):
                if title and content:
                    result = create_notice(st.session_state.user['id'], title, content, None, pinned)
                    if result.get("success"):
                        st.success("등록됨!")
                        st.rerun()
    
    st.markdown("---")
    
    notices = get_all_notices()
    
    if not notices:
        st.info("등록된 공지가 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            
            with st.expander(f"{pin}**{n['title']}** ({n['created_at']})", expanded=False):
                if is_admin():
                    edit_title = st.text_input("제목", value=n['title'], key=f"et_{n['id']}")
                    edit_content = st.text_area("내용", value=n['content'], height=100, key=f"ec_{n['id']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("💾 수정", key=f"save_{n['id']}"):
                            update_notice(n['id'], edit_title, edit_content)
                            st.success("수정됨")
                            st.rerun()
                    with col2:
                        if st.button("📌 고정토글", key=f"pin_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            st.rerun()
                    with col3:
                        if st.button("🗑️ 삭제", key=f"del_{n['id']}"):
                            delete_notice(n['id'])
                            st.rerun()
                else:
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
