# -*- coding: utf-8 -*-
"""
🔮 사주/연애/타로 PDF 자동 생성 플랫폼
폰트 설정 + A4 규격 + 개별상품 수정 버전
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# 페이지 설정
st.set_page_config(
    page_title="PDF 자동 생성 플랫폼",
    page_icon="🔮",
    layout="wide"
)

# ============================================
# 임포트
# ============================================

from database import init_db, SessionLocal
from auth import (
    register_user, login_user, update_user_profile, change_password,
    get_all_users, get_pending_users, approve_user, suspend_user, activate_user,
    update_user_settings, create_first_admin, check_admin_exists
)
from services import (
    get_all_services, get_admin_services, get_user_services,
    add_service, update_service, delete_service, 
    get_system_config, set_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, update_chapter, delete_chapter,
    get_guidelines_by_service, add_guideline, update_guideline, delete_guideline,
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
    
    section[data-testid="stSidebar"] .stRadio > div > label > div:first-child { display: none !important; }
    section[data-testid="stSidebar"] .stRadio > div > label {
        cursor: pointer !important; padding: 10px 15px; border-radius: 8px; margin: 2px 0;
    }
    section[data-testid="stSidebar"] .stRadio > div > label:hover { background: rgba(255,255,255,0.1); }
    
    .section-title {
        display: inline-block;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 8px 20px; border-radius: 20px; color: white; font-weight: bold;
        font-size: 1rem; margin: 15px 0 10px 0;
    }
    .divider { border-top: 1px solid rgba(255,255,255,0.1); margin: 20px 0; }
    
    .badge-admin { background: #dc3545; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level1 { background: #6c757d; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level2 { background: #17a2b8; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
    .badge-level3 { background: #28a745; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.8rem; }
</style>
""", unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

defaults = {
    'logged_in': False,
    'user': None,
    'customers_df': None,
    'completed_customers': {},
    'generated_pdfs': {},
    'selected_customers': set(),
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
# 디렉토리 / 상수
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
for d in [UPLOAD_DIR, OUTPUT_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

TEMPLATE_TYPES = {"cover": "📕 표지", "background": "📄 내지", "info": "📋 안내지"}

FONT_OPTIONS = {
    "NanumGothic": "나눔고딕",
    "NanumMyeongjo": "나눔명조",
    "NanumBarunGothic": "나눔바른고딕",
}

# ============================================
# 유틸리티
# ============================================

def is_admin() -> bool:
    return st.session_state.user and st.session_state.user.get('is_admin', False)

def get_member_level() -> int:
    if not st.session_state.user:
        return 1
    return st.session_state.user.get('member_level', 1)

def save_uploaded_file(uploaded_file, prefix: str) -> str:
    if uploaded_file is None:
        return None
    filename = f"{prefix}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uploaded_file.name}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return filepath

def get_api_key() -> str:
    user = st.session_state.user
    admin_api = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
    if user.get('api_mode') == 'separated' and user.get('api_key'):
        return user['api_key']
    return admin_api

def play_sound():
    st.markdown("""
    <audio autoplay>
        <source src="https://www.soundjay.com/buttons/sounds/button-09.mp3" type="audio/mpeg">
    </audio>
    """, unsafe_allow_html=True)

def verify_pdf_generation_ready(service_id: int, api_key: str) -> tuple:
    errors = []
    if not api_key:
        errors.append("❌ API 키가 설정되지 않았습니다.")
    if not service_id:
        errors.append("❌ 상품이 선택되지 않았습니다.")
        return False, errors
    chapters = get_chapters_by_service(service_id)
    if not chapters:
        errors.append("❌ 목차가 등록되지 않았습니다.")
    guidelines = get_guidelines_by_service(service_id)
    if not guidelines:
        errors.append("⚠️ 지침이 없습니다. (기본 지침 사용)")
    if errors and any("❌" in e for e in errors):
        return False, errors
    return True, errors

def render_font_settings(prefix: str, defaults: dict = None):
    """폰트 설정 UI 렌더링"""
    if defaults is None:
        defaults = {
            "font_family": "NanumGothic",
            "font_size_title": 24,
            "font_size_subtitle": 16,
            "font_size_body": 12,
            "letter_spacing": 0,
            "line_height": 180
        }
    
    st.markdown("**🎨 폰트 설정**")
    
    col1, col2 = st.columns(2)
    with col1:
        font_idx = list(FONT_OPTIONS.keys()).index(defaults.get("font_family", "NanumGothic")) if defaults.get("font_family") in FONT_OPTIONS else 0
        font_family = st.selectbox("폰트", list(FONT_OPTIONS.keys()), 
                                   index=font_idx,
                                   format_func=lambda x: FONT_OPTIONS[x],
                                   key=f"{prefix}_font")
    with col2:
        line_height = st.slider("행간 (%)", 100, 300, defaults.get("line_height", 180), 10, key=f"{prefix}_lh")
    
    col3, col4, col5 = st.columns(3)
    with col3:
        font_size_title = st.number_input("대제목 크기", 16, 40, defaults.get("font_size_title", 24), key=f"{prefix}_title")
    with col4:
        font_size_subtitle = st.number_input("소제목 크기", 12, 30, defaults.get("font_size_subtitle", 16), key=f"{prefix}_sub")
    with col5:
        font_size_body = st.number_input("본문 크기", 8, 24, defaults.get("font_size_body", 12), key=f"{prefix}_body")
    
    letter_spacing = st.slider("자간 (%)", -20, 50, defaults.get("letter_spacing", 0), 5, key=f"{prefix}_ls")
    
    return {
        "font_family": font_family,
        "font_size_title": font_size_title,
        "font_size_subtitle": font_size_subtitle,
        "font_size_body": font_size_body,
        "letter_spacing": letter_spacing,
        "line_height": line_height
    }

# ============================================
# PDF 생성 함수
# ============================================

def generate_content_with_gpt(api_key: str, chapter_title: str, guideline: str, customer_data: dict) -> str:
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

위 정보를 바탕으로 '{chapter_title}' 챕터 내용을 작성해주세요.
- 고객 정보를 반영하여 개인화된 내용
- 긍정적이고 희망적인 톤
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


def create_pdf_document(customer_name: str, chapters_content: list, templates: dict, font_settings: dict) -> bytes:
    """PDF 문서 생성 - A4 규격 맞춤"""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Frame, PageTemplate
        from reportlab.lib.units import mm
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
        from reportlab.lib.colors import black
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        
        buffer = BytesIO()
        page_width, page_height = A4  # 595.27 x 841.89 points
        
        # 한글 폰트 등록
        font_name = 'Helvetica'
        try:
            font_paths = {
                'NanumGothic': '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
                'NanumMyeongjo': '/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf',
                'NanumBarunGothic': '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
            }
            
            selected_font = font_settings.get('font_family', 'NanumGothic')
            font_path = font_paths.get(selected_font)
            
            if font_path and os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('KoreanFont', font_path))
                font_name = 'KoreanFont'
            else:
                # 기본 폰트 시도
                for fp in font_paths.values():
                    if os.path.exists(fp):
                        pdfmetrics.registerFont(TTFont('KoreanFont', fp))
                        font_name = 'KoreanFont'
                        break
        except Exception as e:
            print(f"폰트 로드 실패: {e}")
        
        # 폰트 설정값
        title_size = font_settings.get('font_size_title', 24)
        subtitle_size = font_settings.get('font_size_subtitle', 16)
        body_size = font_settings.get('font_size_body', 12)
        line_height_pct = font_settings.get('line_height', 180)
        letter_spacing = font_settings.get('letter_spacing', 0)
        
        # 본문 마진
        margin = 25 * mm
        
        # 스타일 정의
        title_style = ParagraphStyle(
            'Title', fontSize=title_size, alignment=TA_CENTER,
            spaceAfter=30, textColor=black, fontName=font_name,
            leading=title_size * 1.5
        )
        subtitle_style = ParagraphStyle(
            'Subtitle', fontSize=subtitle_size, alignment=TA_LEFT,
            spaceBefore=20, spaceAfter=15, textColor=black, fontName=font_name,
            leading=subtitle_size * 1.5
        )
        body_style = ParagraphStyle(
            'Body', fontSize=body_size, alignment=TA_JUSTIFY,
            spaceAfter=10, textColor=black, fontName=font_name,
            leading=body_size * (line_height_pct / 100)
        )
        page_num_style = ParagraphStyle(
            'PageNum', fontSize=10, alignment=TA_CENTER, textColor=black, fontName=font_name
        )
        
        # Canvas로 직접 그리기 (표지/안내지 전체 페이지)
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # ===== 1. 표지 (전체 페이지) =====
        cover_path = templates.get('cover')
        if cover_path and os.path.exists(cover_path):
            try:
                # A4 전체 크기로 이미지 배치
                c.drawImage(cover_path, 0, 0, width=page_width, height=page_height)
            except Exception as img_err:
                c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', title_size)
                c.drawCentredString(page_width/2, page_height/2, f"{customer_name}님의 운세")
        else:
            c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', title_size)
            c.drawCentredString(page_width/2, page_height/2, f"{customer_name}님의 운세")
        
        c.showPage()
        
        # ===== 2. 본문 페이지들 =====
        for idx, chapter in enumerate(chapters_content):
            # 본문 영역
            y_position = page_height - margin
            
            # 소제목 (챕터 제목)
            c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica-Bold', subtitle_size)
            chapter_title = f"● {chapter['title']}"
            c.drawString(margin, y_position, chapter_title)
            y_position -= subtitle_size * 2
            
            # 본문 내용
            c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', body_size)
            content = chapter['content']
            
            # 텍스트 줄바꿈 처리
            max_width = page_width - (2 * margin)
            lines = []
            for para in content.split('\n'):
                if para.strip():
                    # 간단한 줄바꿈 처리
                    words = para.strip()
                    current_line = ""
                    for char in words:
                        test_line = current_line + char
                        if c.stringWidth(test_line, font_name if font_name != 'Helvetica' else 'Helvetica', body_size) < max_width:
                            current_line = test_line
                        else:
                            if current_line:
                                lines.append(current_line)
                            current_line = char
                    if current_line:
                        lines.append(current_line)
                    lines.append("")  # 단락 구분
            
            line_spacing = body_size * (line_height_pct / 100)
            for line in lines:
                if y_position < margin + 50:
                    # 페이지 번호
                    c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', 10)
                    c.drawCentredString(page_width/2, 20*mm, f"- {idx + 2} -")
                    c.showPage()
                    y_position = page_height - margin
                    c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', body_size)
                
                c.drawString(margin, y_position, line)
                y_position -= line_spacing
            
            # 페이지 번호
            c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', 10)
            c.drawCentredString(page_width/2, 20*mm, f"- {idx + 2} -")
            c.showPage()
        
        # ===== 3. 안내지 (전체 페이지) =====
        info_path = templates.get('info')
        if info_path and os.path.exists(info_path):
            try:
                c.drawImage(info_path, 0, 0, width=page_width, height=page_height)
            except:
                c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', title_size)
                c.drawCentredString(page_width/2, page_height/2, "감사합니다")
        else:
            c.setFont(font_name if font_name != 'Helvetica' else 'Helvetica', title_size)
            c.drawCentredString(page_width/2, page_height/2, "감사합니다")
        
        c.save()
        return buffer.getvalue()
    except Exception as e:
        st.error(f"PDF 생성 오류: {str(e)}")
        return None


def generate_pdf_for_customer(customer_data: dict, service: dict, api_key: str) -> bytes:
    """고객용 PDF 생성"""
    service_id = service['id']
    chapters = get_chapters_by_service(service_id)
    guidelines = get_guidelines_by_service(service_id)
    guideline_text = guidelines[0]['content'] if guidelines else "친절하고 긍정적인 톤으로 작성하세요."
    
    templates_list = get_templates_by_service(service_id)
    templates = {}
    for t in templates_list:
        if t.get('image_path') and os.path.exists(t['image_path']):
            templates[t['template_type']] = t['image_path']
    
    name_col = None
    for col in ['이름', 'name', 'Name', '성명', '고객명']:
        if col in customer_data:
            name_col = col
            break
    customer_name = customer_data.get(name_col, "고객") if name_col else "고객"
    
    font_settings = {
        'font_family': service.get('font_family', 'NanumGothic'),
        'font_size_title': service.get('font_size_title', 24),
        'font_size_subtitle': service.get('font_size_subtitle', 16),
        'font_size_body': service.get('font_size_body', 12),
        'letter_spacing': service.get('letter_spacing', 0),
        'line_height': service.get('line_height', 180),
    }
    
    chapters_content = []
    for ch in chapters:
        content = generate_content_with_gpt(api_key, ch['title'], guideline_text, customer_data)
        chapters_content.append({"title": ch['title'], "content": content})
    
    return create_pdf_document(customer_name, chapters_content, templates, font_settings)

# ============================================
# 로그인 페이지
# ============================================

def show_login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-title">🔮 PDF 자동 생성 플랫폼</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-title">사주 · 타로 · 연애</p>', unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["🔐 로그인", "📝 회원가입"])
        
        with tab1:
            email = st.text_input("이메일", key="login_email")
            pw = st.text_input("비밀번호", type="password", key="login_pw")
            
            if st.button("로그인", type="primary", use_container_width=True):
                if email and pw:
                    result = login_user(email, pw)
                    if result["success"]:
                        st.session_state.logged_in = True
                        st.session_state.user = result["user"]
                        st.rerun()
                    else:
                        st.error(result["error"])
        
        with tab2:
            name = st.text_input("이름", key="reg_name")
            email2 = st.text_input("이메일", key="reg_email")
            pw1 = st.text_input("비밀번호", type="password", key="reg_pw1")
            pw2 = st.text_input("비밀번호 확인", type="password", key="reg_pw2")
            
            if st.button("회원가입", type="primary", use_container_width=True):
                if all([name, email2, pw1, pw2]):
                    if pw1 != pw2:
                        st.error("비밀번호가 일치하지 않습니다.")
                    else:
                        result = register_user(email2, pw1, name)
                        if result["success"]:
                            st.success(result["message"])
                        else:
                            st.error(result["error"])
        
        st.markdown("---")
        
        if not check_admin_exists():
            with st.expander("🔧 최초 관리자 설정", expanded=True):
                st.warning("⚠️ 관리자 계정을 먼저 생성하세요!")
                a_name = st.text_input("관리자 이름", key="a_name")
                a_email = st.text_input("관리자 이메일", key="a_email")
                a_pw = st.text_input("관리자 비밀번호", type="password", key="a_pw")
                
                if st.button("🔑 관리자 계정 생성", type="primary", use_container_width=True):
                    if all([a_name, a_email, a_pw]):
                        result = create_first_admin(a_email, a_pw, a_name)
                        if result["success"]:
                            st.success("✅ 관리자 계정 생성됨!")
                            st.rerun()

# ============================================
# 메인 앱
# ============================================

def show_main_app():
    user = st.session_state.user
    
    with st.sidebar:
        st.markdown(f"### 👤 {user['name']}님")
        
        if user['is_admin']:
            st.markdown('<span class="badge-admin">관리자</span>', unsafe_allow_html=True)
        else:
            level = user.get('member_level', 1)
            badges = {1: "badge-level1", 2: "badge-level2", 3: "badge-level3"}
            st.markdown(f'<span class="{badges[level]}">{level}단계</span>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        menu = []
        if user['is_admin']:
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
    
    tab1, tab2, tab3 = st.tabs(["🔑 API/이메일", "👥 회원관리", "📦 기성상품 등록"])
    
    # ===== API/이메일 =====
    with tab1:
        st.markdown('<span class="section-title">🔑 관리자 API/이메일</span>', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            api = st.text_input("OpenAI API 키", value=get_system_config(ConfigKeys.ADMIN_API_KEY, ""), type="password")
            if st.button("💾 API 저장"):
                set_system_config(ConfigKeys.ADMIN_API_KEY, api)
                st.success("저장됨")
        
        with col2:
            gmail = st.text_input("Gmail", value=get_system_config(ConfigKeys.ADMIN_GMAIL, ""))
            gmail_pw = st.text_input("앱 비밀번호", value=get_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, ""), type="password")
            if st.button("💾 이메일 저장"):
                set_system_config(ConfigKeys.ADMIN_GMAIL, gmail)
                set_system_config(ConfigKeys.ADMIN_GMAIL_PASSWORD, gmail_pw)
                st.success("저장됨")
    
    # ===== 회원관리 =====
    with tab2:
        st.markdown('<span class="section-title">👥 회원 관리</span>', unsafe_allow_html=True)
        st.markdown("**1단계**: 기성상품만 | **2단계**: 개별상품만 | **3단계**: 둘 다")
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        subtab1, subtab2 = st.tabs(["전체 회원", "승인 대기"])
        
        with subtab1:
            users = get_all_users()
            for u in users:
                if u['id'] == st.session_state.user['id']:
                    continue
                
                col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
                
                with col1:
                    status_icon = "🟢" if u['status'] == 'approved' else "🔴"
                    admin_mark = "👑" if u['is_admin'] else ""
                    st.write(f"{status_icon} {admin_mark} **{u['name']}**")
                    st.caption(u['email'])
                
                with col2:
                    new_level = st.selectbox("등급", [1, 2, 3], index=u.get('member_level', 1) - 1,
                                            format_func=lambda x: f"{x}단계", key=f"lvl_{u['id']}")
                with col3:
                    new_api = st.selectbox("API", ["unified", "separated"],
                                          index=0 if u.get('api_mode') == 'unified' else 1,
                                          format_func=lambda x: "통합" if x == "unified" else "분리",
                                          key=f"api_{u['id']}")
                with col4:
                    new_email = st.selectbox("이메일", ["unified", "separated"],
                                            index=0 if u.get('email_mode') == 'unified' else 1,
                                            format_func=lambda x: "통합" if x == "unified" else "분리",
                                            key=f"email_{u['id']}")
                with col5:
                    if st.button("💾", key=f"save_{u['id']}"):
                        update_user_settings(u['id'], new_level, new_api, new_email)
                        st.rerun()
                    if u['status'] == 'approved':
                        if st.button("🚫", key=f"sus_{u['id']}"):
                            suspend_user(u['id'])
                            st.rerun()
                    elif u['status'] == 'suspended':
                        if st.button("✅", key=f"act_{u['id']}"):
                            activate_user(u['id'])
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
    
    # ===== 기성상품 등록 =====
    with tab3:
        st.markdown('<span class="section-title">📦 기성상품 등록</span>', unsafe_allow_html=True)
        
        # 새 상품 등록
        with st.expander("➕ 새 기성상품 등록", expanded=False):
            product_name = st.text_input("상품명", key="new_prod")
            
            st.markdown("**📑 목차** (줄바꿈으로 구분)")
            new_chapters = st.text_area("목차 입력", height=200, key="new_ch",
                placeholder="1. 올해의 총운\n2. 재물운\n3. 건강운")
            
            st.markdown("**📜 AI 작성 지침**")
            new_guideline = st.text_area("지침 입력", height=200, key="new_g",
                placeholder="- 긍정적인 톤\n- 300자 이상")
            
            # 폰트 설정
            font_settings = render_font_settings("new_admin")
            
            st.markdown("**🖼️ 디자인**")
            d_cols = st.columns(3)
            with d_cols[0]:
                cover = st.file_uploader("📕 표지", type=["jpg","jpeg","png"], key="new_cover")
            with d_cols[1]:
                bg = st.file_uploader("📄 내지", type=["jpg","jpeg","png"], key="new_bg")
            with d_cols[2]:
                info = st.file_uploader("📋 안내지", type=["jpg","jpeg","png"], key="new_info")
            
            if st.button("💾 기성상품 등록", type="primary", use_container_width=True):
                if product_name:
                    result = add_service(product_name, "", None, **font_settings)
                    if result.get("success"):
                        svc_id = result["id"]
                        if new_chapters:
                            for idx, ch in enumerate(new_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                        if new_guideline:
                            add_guideline(svc_id, f"{product_name} 지침", new_guideline)
                        if cover:
                            path = save_uploaded_file(cover, f"{product_name}_cover")
                            add_template(svc_id, "cover", "표지", path)
                        if bg:
                            path = save_uploaded_file(bg, f"{product_name}_bg")
                            add_template(svc_id, "background", "내지", path)
                        if info:
                            path = save_uploaded_file(info, f"{product_name}_info")
                            add_template(svc_id, "info", "안내지", path)
                        st.success(f"'{product_name}' 등록됨!")
                        st.rerun()
        
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown("**등록된 기성상품**")
        
        services = get_admin_services()
        if not services:
            st.info("등록된 기성상품이 없습니다.")
        else:
            for svc in services:
                with st.expander(f"📌 {svc['name']}"):
                    show_service_edit_form(svc, "admin")

# ============================================
# 상품 수정 폼
# ============================================

def show_service_edit_form(svc: dict, prefix: str):
    """상품 수정 폼"""
    svc_id = svc['id']
    
    chapters = get_chapters_by_service(svc_id)
    guidelines = get_guidelines_by_service(svc_id)
    templates = get_templates_by_service(svc_id)
    
    # 기본 정보
    edit_name = st.text_input("상품명", value=svc['name'], key=f"{prefix}_name_{svc_id}")
    
    # 목차
    st.markdown("**📑 목차**")
    current_chapters = "\n".join([ch['title'] for ch in chapters])
    edit_chapters = st.text_area("목차", value=current_chapters, height=150, key=f"{prefix}_ch_{svc_id}")
    
    # 지침
    st.markdown("**📜 지침**")
    current_guideline = guidelines[0]['content'] if guidelines else ""
    edit_guideline = st.text_area("지침", value=current_guideline, height=150, key=f"{prefix}_g_{svc_id}")
    
    # 폰트 설정
    font_defaults = {
        "font_family": svc.get('font_family', 'NanumGothic'),
        "font_size_title": svc.get('font_size_title', 24),
        "font_size_subtitle": svc.get('font_size_subtitle', 16),
        "font_size_body": svc.get('font_size_body', 12),
        "letter_spacing": svc.get('letter_spacing', 0),
        "line_height": svc.get('line_height', 180),
    }
    font_settings = render_font_settings(f"{prefix}_{svc_id}", font_defaults)
    
    # 디자인
    st.markdown("**🖼️ 디자인**")
    t_cols = st.columns(3)
    for idx, tt in enumerate(["cover", "background", "info"]):
        with t_cols[idx]:
            t_list = [t for t in templates if t['template_type'] == tt]
            if t_list and t_list[0].get('image_path') and os.path.exists(t_list[0]['image_path']):
                st.image(t_list[0]['image_path'], width=80)
            new_file = st.file_uploader(TEMPLATE_TYPES[tt], type=["jpg","jpeg","png"], 
                                       key=f"{prefix}_{tt}_{svc_id}")
            if new_file:
                st.session_state[f"new_{tt}_{svc_id}"] = new_file
    
    # 버튼
    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 저장", key=f"{prefix}_save_{svc_id}", type="primary", use_container_width=True):
            # 이름/폰트 업데이트
            update_service(svc_id, name=edit_name, **font_settings)
            
            # 목차 업데이트 (기존 삭제 후 새로 추가)
            for ch in chapters:
                delete_chapter(ch['id'])
            for idx, ch in enumerate(edit_chapters.strip().split("\n")):
                if ch.strip():
                    add_chapter(svc_id, ch.strip(), "", idx+1)
            
            # 지침 업데이트
            if guidelines:
                update_guideline(guidelines[0]['id'], guidelines[0]['title'], edit_guideline)
            elif edit_guideline:
                add_guideline(svc_id, f"{edit_name} 지침", edit_guideline)
            
            # 디자인 업데이트
            for tt in ["cover", "background", "info"]:
                new_file = st.session_state.get(f"new_{tt}_{svc_id}")
                if new_file:
                    path = save_uploaded_file(new_file, f"{edit_name}_{tt}")
                    # 기존 삭제 후 추가
                    for t in templates:
                        if t['template_type'] == tt:
                            delete_template(t['id'])
                    add_template(svc_id, tt, TEMPLATE_TYPES[tt], path)
            
            st.success("저장됨!")
            st.rerun()
    
    with col2:
        if st.button("🗑️ 삭제", key=f"{prefix}_del_{svc_id}", use_container_width=True):
            delete_service(svc_id)
            st.rerun()

# ============================================
# 📦 서비스 작업
# ============================================

def show_service_work():
    st.title("📦 서비스 작업")
    
    user = st.session_state.user
    level = user.get('member_level', 1) if not user['is_admin'] else 3
    api_key = get_api_key()
    
    selected_service = None
    
    # ===== 1. 상품 유형 선택 =====
    st.markdown('<span class="section-title">1️⃣ 상품 유형 선택</span>', unsafe_allow_html=True)
    
    if level == 1:
        options = ["📦 기성상품"]
    elif level == 2:
        options = ["🔧 개별상품"]
    else:
        options = ["📦 기성상품", "🔧 개별상품"]
    
    product_type = st.radio("상품 유형", options, horizontal=True, key="prod_type")
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 2. 기성상품 선택 =====
    if "기성상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 기성상품 선택</span>', unsafe_allow_html=True)
        
        admin_services = get_admin_services()
        if admin_services:
            svc_names = [s['name'] for s in admin_services]
            selected_name = st.selectbox("기성상품 목록", svc_names, key="ready_svc")
            selected_service = next((s for s in admin_services if s['name'] == selected_name), None)
            
            if selected_service:
                chapters = get_chapters_by_service(selected_service['id'])
                st.success(f"✅ '{selected_name}' 선택됨 (목차 {len(chapters)}개)")
        else:
            st.warning("등록된 기성상품이 없습니다.")
    
    # ===== 2. 개별상품 =====
    elif "개별상품" in product_type:
        st.markdown('<span class="section-title">2️⃣ 개별상품</span>', unsafe_allow_html=True)
        
        my_services = get_user_services(user['id'])
        
        if my_services:
            my_names = ["➕ 새로 만들기"] + [s['name'] for s in my_services]
            selected_my = st.selectbox("내 상품 목록", my_names, key="my_svc")
            
            if selected_my != "➕ 새로 만들기":
                selected_service = next((s for s in my_services if s['name'] == selected_my), None)
                if selected_service:
                    chapters = get_chapters_by_service(selected_service['id'])
                    st.success(f"✅ '{selected_my}' 선택됨 (목차 {len(chapters)}개)")
                    
                    # 수정 폼
                    with st.expander("✏️ 상품 수정", expanded=False):
                        show_service_edit_form(selected_service, "my")
        else:
            selected_my = "➕ 새로 만들기"
        
        # 새로 만들기
        if not my_services or selected_my == "➕ 새로 만들기":
            with st.expander("➕ 개별상품 만들기", expanded=True):
                my_name = st.text_input("상품명", key="my_prod")
                
                st.markdown("**📑 목차**")
                my_chapters = st.text_area("목차", height=150, key="my_ch")
                
                st.markdown("**📜 지침**")
                my_guide = st.text_area("지침", height=150, key="my_g")
                
                # 폰트 설정
                font_settings = render_font_settings("new_my")
                
                st.markdown("**🖼️ 디자인**")
                d_cols = st.columns(3)
                with d_cols[0]:
                    my_cover = st.file_uploader("표지", type=["jpg","jpeg","png"], key="my_cover")
                with d_cols[1]:
                    my_bg = st.file_uploader("내지", type=["jpg","jpeg","png"], key="my_bg")
                with d_cols[2]:
                    my_info = st.file_uploader("안내지", type=["jpg","jpeg","png"], key="my_info")
                
                if st.button("💾 저장", type="primary", use_container_width=True):
                    if my_name and my_chapters:
                        result = add_service(my_name, "", user['id'], **font_settings)
                        if result.get("success"):
                            svc_id = result["id"]
                            for idx, ch in enumerate(my_chapters.strip().split("\n")):
                                if ch.strip():
                                    add_chapter(svc_id, ch.strip(), "", idx+1)
                            if my_guide:
                                add_guideline(svc_id, f"{my_name} 지침", my_guide)
                            if my_cover:
                                path = save_uploaded_file(my_cover, f"{my_name}_cover")
                                add_template(svc_id, "cover", "표지", path)
                            if my_bg:
                                path = save_uploaded_file(my_bg, f"{my_name}_bg")
                                add_template(svc_id, "background", "내지", path)
                            if my_info:
                                path = save_uploaded_file(my_info, f"{my_name}_info")
                                add_template(svc_id, "info", "안내지", path)
                            st.success("저장됨!")
                            st.rerun()
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    # ===== 3. PDF 생성 =====
    st.markdown('<span class="section-title">3️⃣ PDF 생성</span>', unsafe_allow_html=True)
    
    if selected_service:
        is_ready, errors = verify_pdf_generation_ready(selected_service['id'], api_key)
        for err in errors:
            if "❌" in err:
                st.error(err)
            else:
                st.warning(err)
        if not is_ready:
            st.stop()
    else:
        st.warning("⚠️ 상품을 먼저 선택하세요.")
        st.stop()
    
    # 고객 파일
    uploaded = st.file_uploader("📂 고객 엑셀 파일 (.xlsx)", type=["xlsx", "xls"], key="cust")
    
    if uploaded:
        df = pd.read_excel(uploaded)
        st.session_state.customers_df = df
        st.success(f"✅ {len(df)}명 로드됨")
    
    if st.session_state.customers_df is not None:
        df = st.session_state.customers_df
        
        name_col = None
        for col in ['이름', 'name', 'Name', '성명', '고객명']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[0]
        
        st.markdown("---")
        
        # 선택 상태
        if 'selected_customers' not in st.session_state:
            st.session_state.selected_customers = set(range(len(df)))
        
        col_all1, col_all2 = st.columns([1, 4])
        with col_all1:
            if st.checkbox("전체 선택", value=len(st.session_state.selected_customers) == len(df)):
                st.session_state.selected_customers = set(range(len(df)))
            else:
                if len(st.session_state.selected_customers) == len(df):
                    st.session_state.selected_customers = set()
        
        st.markdown("---")
        
        # 헤더
        header_cols = st.columns([0.5, 2.5, 3, 1, 1])
        header_cols[0].markdown("**선택**")
        header_cols[1].markdown("**이름**")
        header_cols[2].markdown("**진행률**")
        header_cols[3].markdown("**상태**")
        header_cols[4].markdown("**다운**")
        
        # 고객 목록
        for idx, row in df.iterrows():
            cust_name = row[name_col]
            is_done = idx in st.session_state.completed_customers
            
            col0, col1, col2, col3, col4 = st.columns([0.5, 2.5, 3, 1, 1])
            
            with col0:
                checked = st.checkbox("", value=idx in st.session_state.selected_customers,
                                     key=f"chk_{idx}", label_visibility="collapsed")
                if checked:
                    st.session_state.selected_customers.add(idx)
                else:
                    st.session_state.selected_customers.discard(idx)
            
            with col1:
                st.write(f"**{cust_name}**")
            
            with col2:
                st.progress(1.0 if is_done else 0.0, text="100%" if is_done else "0%")
            
            with col3:
                if is_done:
                    st.markdown("✅ 완료")
            
            with col4:
                if is_done:
                    pdf_data = st.session_state.generated_pdfs.get(idx)
                    if pdf_data:
                        st.download_button("⬇️", pdf_data, f"{cust_name}_운세.pdf",
                                          "application/pdf", key=f"dl_{idx}")
        
        st.markdown("---")
        
        pending_selected = [i for i in st.session_state.selected_customers
                          if i not in st.session_state.completed_customers]
        
        st.info(f"📊 선택: {len(st.session_state.selected_customers)}명 | 완료: {len(st.session_state.completed_customers)}/{len(df)}")
        
        if st.button(f"🚀 선택한 {len(pending_selected)}명 PDF 생성", type="primary", use_container_width=True):
            if not pending_selected:
                st.warning("생성할 고객을 선택하세요.")
            else:
                status = st.empty()
                
                for i, idx in enumerate(pending_selected):
                    row = df.iloc[idx]
                    cust_name = row[name_col]
                    status.text(f"📝 {cust_name} 생성 중... ({i+1}/{len(pending_selected)})")
                    
                    pdf_bytes = generate_pdf_for_customer(row.to_dict(), selected_service, api_key)
                    
                    if pdf_bytes:
                        st.session_state.completed_customers[idx] = True
                        st.session_state.generated_pdfs[idx] = pdf_bytes
                        st.toast(f"🔔 {cust_name} 완료!")
                
                status.text("✅ 모든 PDF 생성 완료!")
                st.balloons()
                play_sound()
                st.rerun()

# ============================================
# 👤 MyPage / 📢 공지사항
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
            st.info("🔒 API: 관리자 통합 모드")
        
        if user.get('email_mode') == 'separated':
            my_gmail = st.text_input("Gmail", value=user.get('gmail_address', '') or '')
            my_pw = st.text_input("앱 비밀번호", value=user.get('gmail_app_password', '') or '', type="password")
            if st.button("💾 이메일 저장"):
                result = update_user_profile(user['id'], gmail_address=my_gmail, gmail_app_password=my_pw)
                if result["success"]:
                    st.session_state.user['gmail_address'] = my_gmail
                    st.session_state.user['gmail_app_password'] = my_pw
                    st.success("저장됨")
        else:
            st.info("🔒 이메일: 관리자 통합 모드")

def show_notices():
    st.title("📢 공지사항")
    
    if is_admin():
        with st.expander("✏️ 새 공지", expanded=False):
            title = st.text_input("제목", key="n_title")
            content = st.text_area("내용", height=150, key="n_content")
            pinned = st.checkbox("📌 고정")
            
            if st.button("💾 등록", type="primary"):
                if title and content:
                    create_notice(st.session_state.user['id'], title, content, None, pinned)
                    st.success("등록됨!")
                    st.rerun()
    
    st.markdown("---")
    
    notices = get_all_notices()
    if not notices:
        st.info("공지가 없습니다.")
    else:
        for n in notices:
            pin = "📌 " if n['is_pinned'] else ""
            with st.expander(f"{pin}**{n['title']}**"):
                if is_admin():
                    ed_title = st.text_input("제목", value=n['title'], key=f"et_{n['id']}")
                    ed_content = st.text_area("내용", value=n['content'], height=80, key=f"ec_{n['id']}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("💾", key=f"sv_{n['id']}"):
                            update_notice(n['id'], ed_title, ed_content)
                            st.rerun()
                    with c2:
                        if st.button("📌", key=f"pn_{n['id']}"):
                            toggle_pin_notice(n['id'])
                            st.rerun()
                    with c3:
                        if st.button("🗑️", key=f"dl_{n['id']}"):
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
