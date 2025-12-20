# -*- coding: utf-8 -*-
"""
🔮 공통 모듈 - CSS, 캐싱, 유틸리티 함수
"""

import streamlit as st
import os
from datetime import datetime

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
    get_system_config, set_system_config, ConfigKeys,
    get_chapter_library, add_chapter_library, update_chapter_library, delete_chapter_library,
    get_guideline_library, add_guideline_library, update_guideline_library, delete_guideline_library
)
from contents import (
    get_chapters_by_service, add_chapter, add_chapters_bulk, update_chapter, delete_chapter, delete_chapters_by_service,
    get_guidelines_by_service, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template
)
from notices import get_all_notices, create_notice, update_notice, delete_notice, toggle_pin_notice

# ============================================
# 상수
# ============================================

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
TEMPLATE_TYPES = {"cover": "📕 표지", "background": "📄 내지", "info": "📋 안내지"}
FONT_OPTIONS = {"NanumGothic": "나눔고딕", "NanumMyeongjo": "나눔명조", "NanumBarunGothic": "나눔바른고딕"}
CATEGORIES = ["사주", "타로", "연애", "기타"]

# ============================================
# 캐싱 함수 (속도 최적화)
# ============================================

@st.cache_data(ttl=300)
def cached_get_admin_services():
    """기성상품 목록 캐싱"""
    return get_admin_services()

@st.cache_data(ttl=300)
def cached_get_user_services(user_id: int):
    """개별상품 목록 캐싱"""
    return get_user_services(user_id)

@st.cache_data(ttl=300)
def cached_get_chapters(service_id: int):
    """목차 캐싱"""
    return get_chapters_by_service(service_id)

@st.cache_data(ttl=300)
def cached_get_guidelines(service_id: int):
    """지침 캐싱"""
    return get_guidelines_by_service(service_id)

@st.cache_data(ttl=300)
def cached_get_templates(service_id: int):
    """템플릿 캐싱"""
    return get_templates_by_service(service_id)

@st.cache_data(ttl=300)
def cached_get_notices():
    """공지사항 캐싱"""
    return get_all_notices()

def clear_service_cache():
    """서비스 관련 캐시 초기화"""
    cached_get_admin_services.clear()
    cached_get_user_services.clear()
    cached_get_chapters.clear()
    cached_get_guidelines.clear()
    cached_get_templates.clear()

def clear_notice_cache():
    """공지사항 캐시 초기화"""
    cached_get_notices.clear()

# ============================================
# CSS 적용 함수
# ============================================

def apply_common_css():
    """공통 CSS 적용"""
    st.markdown("""
    <style>
        .main-title { text-align: center; color: #fff; font-size: 2.5rem; margin-bottom: 10px; }
        .sub-title { text-align: center; color: #888; font-size: 1rem; margin-bottom: 30px; }
        
        section[data-testid="stSidebar"] .stRadio > div > label > div:first-child { display: none !important; }
        section[data-testid="stSidebar"] .stRadio > div > label {
            cursor: pointer !important; padding: 10px 15px; border-radius: 8px; margin: 2px 0;
        }
        
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
        
        .stTextArea [data-testid="stTextAreaHelp"] { display: none !important; }
        .stTextArea small { display: none !important; }
        
        .block-container { padding-top: 1rem !important; }
        div[data-testid="stVerticalBlock"] > div { gap: 0.3rem !important; }
        .stButton > button { padding: 0.4rem 1rem !important; min-height: 2.2rem !important; }
        hr { margin: 0.5rem 0 !important; border-color: rgba(255,255,255,0.1) !important; }
        
        .product-card {
            background: linear-gradient(135deg, #1e5128 0%, #2d7a3e 100%);
            padding: 10px 15px; border-radius: 8px; margin: 3px 0;
            border-left: 3px solid #4CAF50;
        }
        .thin-divider { border-top: 1px solid rgba(255,255,255,0.08); margin: 5px 0; }
        
        .work-step {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
            padding: 15px 20px; border-radius: 12px; margin: 10px 0;
            border-left: 4px solid #4CAF50;
        }
        .work-step-inactive {
            background: #2d2d2d; padding: 15px 20px; border-radius: 12px; margin: 10px 0;
            border-left: 4px solid #666; opacity: 0.6;
        }
        .work-step-title { font-size: 1.1rem; font-weight: bold; color: #fff; margin-bottom: 5px; }
        .work-step-desc { font-size: 0.9rem; color: #aaa; }
        
        .progress-card {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px; border-radius: 12px; text-align: center; margin: 10px 0;
        }
        .progress-number { font-size: 2.5rem; font-weight: bold; color: #4CAF50; }
        .progress-label { font-size: 0.9rem; color: #888; margin-top: 5px; }
        .progress-time { font-size: 0.85rem; color: #666; margin-top: 8px; }
        
        .status-success { color: #4CAF50; }
        .status-processing { color: #FFC107; }
        .status-error { color: #f44336; font-weight: bold; }
        
        .error-card {
            background: linear-gradient(135deg, #5c1a1a 0%, #3d1212 100%);
            padding: 15px; border-radius: 8px; margin: 5px 0;
            border-left: 4px solid #f44336;
        }
        .error-title { color: #f44336; font-weight: bold; }
        .error-action { color: #ffcdd2; font-size: 0.9rem; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# ============================================
# 세션 상태 초기화
# ============================================

def init_session_state():
    """세션 상태 초기화"""
    defaults = {
        'logged_in': False, 'user': None, 'customers_df': None,
        'completed_customers': {}, 'generated_pdfs': {}, 'selected_customers': set(),
        'input_mode': 'excel', 'manual_completed': False, 'manual_pdf': None,
        'pdf_hashes': {},
        'work_processing': False, 'work_errors': [], 'work_start_time': None,
        'individual_mode': 'select', 'selected_individual_service': None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

# ============================================
# 유틸리티 함수
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
    os.makedirs(UPLOAD_DIR, exist_ok=True)
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

def verify_pdf_generation_ready(service_id: int, api_key: str) -> tuple:
    errors = []
    if not api_key:
        errors.append("❌ API 키가 설정되지 않았습니다.")
    if not service_id:
        errors.append("❌ 상품이 선택되지 않았습니다.")
        return False, errors
    chapters = cached_get_chapters(service_id)
    if not chapters:
        errors.append("❌ 목차가 등록되지 않았습니다.")
    if errors and any("❌" in e for e in errors):
        return False, errors
    return True, errors

def calculate_chars_per_page(font_size_body: int, line_height: int, margin_top: int, 
                            margin_bottom: int, margin_left: int, margin_right: int) -> int:
    """페이지당 글자 수 계산"""
    page_width_mm = 210
    page_height_mm = 297
    usable_width = page_width_mm - margin_left - margin_right
    usable_height = page_height_mm - margin_top - margin_bottom
    char_height_mm = font_size_body * 0.35
    char_width_mm = font_size_body * 0.35 * 0.5
    line_spacing_mm = char_height_mm * (line_height / 100)
    lines_per_page = int(usable_height / line_spacing_mm)
    chars_per_line = int(usable_width / char_width_mm)
    chars_per_page = int(lines_per_page * chars_per_line * 0.8)
    return max(chars_per_page, 300)

# ============================================
# 업무 자동화 콘솔 유틸리티
# ============================================

def render_progress_card(completed: int, total: int, current_task: str = ""):
    """진행 상태 카드"""
    remaining = total - completed
    est_minutes = remaining * 1
    time_text = f"예상 남은 시간: 약 {est_minutes}분" if est_minutes > 0 else "곧 완료됩니다"
    
    st.markdown(f"""
    <div class="progress-card">
        <div class="progress-number">{completed} / {total}</div>
        <div class="progress-label">처리 완료</div>
        <div class="progress-time">{time_text}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if current_task:
        st.caption(f"📝 현재: {current_task}")

def render_error_card(customer_name: str, error_msg: str):
    """에러 카드"""
    if "API" in error_msg or "key" in error_msg.lower():
        action = "관리자에게 API 키 확인을 요청하세요"
    elif "timeout" in error_msg.lower():
        action = "잠시 후 다시 시도해 주세요"
    else:
        action = "이 주문은 재시도가 필요합니다"
    
    st.markdown(f"""
    <div class="error-card">
        <div class="error-title">❌ {customer_name}</div>
        <div class="error-action">{action}</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================
# 폰트 설정 UI
# ============================================

@st.fragment
def render_font_settings(prefix: str, defaults: dict = None):
    """폰트/여백 설정 UI"""
    if defaults is None:
        defaults = {"font_family": "NanumGothic", "font_size_title": 24, "font_size_subtitle": 16,
                    "font_size_body": 12, "letter_spacing": 0, "line_height": 180, "char_width": 100,
                    "margin_top": 25, "margin_bottom": 25, "margin_left": 25, "margin_right": 25,
                    "target_pages": 30}
    
    settings_key = f"{prefix}_font_settings"
    if settings_key not in st.session_state:
        st.session_state[settings_key] = defaults.copy()
    
    saved = st.session_state[settings_key]
    
    st.markdown("**📄 목표 페이지 수**")
    target_cols = st.columns([2, 3])
    with target_cols[0]:
        target_pages = st.number_input("목표 페이지", 10, 200, saved.get("target_pages", 30), 
                                       step=5, key=f"{prefix}_pages")
    
    st.markdown("**🎨 폰트 설정**")
    col1, col2, col3 = st.columns(3)
    with col1:
        font_idx = list(FONT_OPTIONS.keys()).index(saved.get("font_family", "NanumGothic")) if saved.get("font_family") in FONT_OPTIONS else 0
        font_family = st.selectbox("폰트", list(FONT_OPTIONS.keys()), index=font_idx,
                                   format_func=lambda x: FONT_OPTIONS[x], key=f"{prefix}_font")
    with col2:
        line_height = st.slider("행간 (%)", 100, 300, saved.get("line_height", 180), 10, key=f"{prefix}_lh")
    with col3:
        letter_spacing = st.slider("자간 (%)", -20, 50, saved.get("letter_spacing", 0), 5, key=f"{prefix}_ls")
    
    col4, col5, col6, col7 = st.columns(4)
    with col4:
        font_size_title = st.number_input("대제목", 16, 40, saved.get("font_size_title", 24), key=f"{prefix}_title")
    with col5:
        font_size_subtitle = st.number_input("소제목", 12, 30, saved.get("font_size_subtitle", 16), key=f"{prefix}_sub")
    with col6:
        font_size_body = st.number_input("본문", 8, 24, saved.get("font_size_body", 12), key=f"{prefix}_body")
    with col7:
        char_width = st.slider("장평 (%)", 50, 150, saved.get("char_width", 100), 5, key=f"{prefix}_cw")
    
    st.markdown("**📐 여백 설정 (mm)**")
    m_cols = st.columns(4)
    with m_cols[0]:
        margin_top = st.number_input("상단", 5, 50, saved.get("margin_top", 25), key=f"{prefix}_mt")
    with m_cols[1]:
        margin_bottom = st.number_input("하단", 5, 50, saved.get("margin_bottom", 25), key=f"{prefix}_mb")
    with m_cols[2]:
        margin_left = st.number_input("좌측", 5, 50, saved.get("margin_left", 25), key=f"{prefix}_ml")
    with m_cols[3]:
        margin_right = st.number_input("우측", 5, 50, saved.get("margin_right", 25), key=f"{prefix}_mr")
    
    chars_per_page = calculate_chars_per_page(font_size_body, line_height, margin_top, 
                                               margin_bottom, margin_left, margin_right)
    with target_cols[1]:
        st.info(f"📊 현재 설정: 페이지당 약 **{chars_per_page:,}자** | 총 **{target_pages * chars_per_page:,}자** 예상")
    
    current_settings = {"font_family": font_family, "font_size_title": font_size_title, 
                        "font_size_subtitle": font_size_subtitle, "font_size_body": font_size_body, 
                        "letter_spacing": letter_spacing, "line_height": line_height,
                        "char_width": char_width, "margin_top": margin_top, "margin_bottom": margin_bottom,
                        "margin_left": margin_left, "margin_right": margin_right, "target_pages": target_pages}
    st.session_state[settings_key] = current_settings
    
    return current_settings

# ============================================
# DB 초기화
# ============================================

@st.cache_resource
def initialize_database():
    init_db()
    return True

# ============================================
# 폰트 캐싱
# ============================================

@st.cache_resource
def get_registered_font():
    """폰트를 한 번만 등록하고 캐싱"""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    
    font_name = 'Helvetica'
    
    cjk_font_paths = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
        '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/unfonts-core/UnBatang.ttf',
    ]
    
    nanum_paths = {
        'NanumGothic': '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
        'NanumMyeongjo': '/usr/share/fonts/truetype/nanum/NanumMyeongjo.ttf',
        'NanumBarunGothic': '/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf',
    }
    
    try:
        for cjk_path in cjk_font_paths:
            if os.path.exists(cjk_path):
                try:
                    if cjk_path.endswith('.ttc'):
                        pdfmetrics.registerFont(TTFont('KoreanFont', cjk_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont('KoreanFont', cjk_path))
                    return 'KoreanFont'
                except:
                    continue
        
        for fp in nanum_paths.values():
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('KoreanFont', fp))
                return 'KoreanFont'
    except:
        pass
    
    return font_name

# ============================================
# 로그인 체크 (페이지용)
# ============================================

def check_login():
    """로그인 상태 확인 - 미로그인 시 메인으로 리다이렉트"""
    init_session_state()
    if not st.session_state.get('logged_in', False):
        st.warning("🔒 로그인이 필요합니다.")
        st.stop()
    return st.session_state.user

def show_user_info_sidebar():
    """사이드바에 사용자 정보 표시"""
    user = st.session_state.user
    if not user:
        return
    
    with st.sidebar:
        st.markdown("---")
        badge = "badge-admin" if user.get('is_admin') else f"badge-level{user.get('member_level', 1)}"
        badge_text = "관리자" if user.get('is_admin') else f"{user.get('member_level', 1)}단계"
        st.markdown(f"👤 **{user['name']}** <span class='{badge}'>{badge_text}</span>", unsafe_allow_html=True)
        
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user = None
            st.rerun()
