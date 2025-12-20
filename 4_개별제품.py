# -*- coding: utf-8 -*-
"""
🎯 개별제품 페이지
- 고객 정보 직접 입력
- 맞춤형 상세 정보
"""

import streamlit as st
import time
import io
from datetime import date

st.set_page_config(page_title="개별제품", page_icon="🎯", layout="wide")

from common import (
    check_login, show_user_info_sidebar, apply_common_css, init_session_state,
    is_admin, FONT_OPTIONS, clear_service_cache, save_uploaded_file
)
from services import (
    get_services_by_category, add_service, update_service, delete_service,
    get_system_config, ConfigKeys
)
from contents import (
    get_chapters_by_service, add_chapter, add_chapters_bulk, delete_chapters_by_service,
    get_guidelines_by_service, add_guideline, update_guideline, delete_guideline,
    get_templates_by_service, add_template, delete_template
)
from pdf_generator import generate_full_content, PDFGenerator

# 초기화
init_session_state()
apply_common_css()
user = check_login()
show_user_info_sidebar()

st.title("🎯 개별제품")
st.caption("직접 입력 기반 · 맞춤형 상세 정보")

# =====================================================
# 세션 상태 초기화
# =====================================================
PREFIX = "ind"  # individual product

if f'{PREFIX}_view_id' not in st.session_state:
    st.session_state[f'{PREFIX}_view_id'] = None
if f'{PREFIX}_edit_mode' not in st.session_state:
    st.session_state[f'{PREFIX}_edit_mode'] = False
if f'{PREFIX}_new_mode' not in st.session_state:
    st.session_state[f'{PREFIX}_new_mode'] = False
if f'{PREFIX}_customers' not in st.session_state:
    st.session_state[f'{PREFIX}_customers'] = []
if f'{PREFIX}_selected' not in st.session_state:
    st.session_state[f'{PREFIX}_selected'] = set()
if f'{PREFIX}_progress' not in st.session_state:
    st.session_state[f'{PREFIX}_progress'] = {}
if f'{PREFIX}_completed' not in st.session_state:
    st.session_state[f'{PREFIX}_completed'] = set()
if f'{PREFIX}_reset' not in st.session_state:
    st.session_state[f'{PREFIX}_reset'] = 0
if f'{PREFIX}_pdfs' not in st.session_state:
    st.session_state[f'{PREFIX}_pdfs'] = {}

PRODUCT_TYPE = "개별상품"

# =====================================================
# 탭 구성
# =====================================================
tab1, tab2 = st.tabs(["⚙️ 상품 설정", "🚀 PDF 생성"])

# =====================================================
# ⚙️ 상품 설정 탭
# =====================================================
with tab1:
    products = get_services_by_category(PRODUCT_TYPE)
    
    # ===== 새 상품 등록 모드 =====
    if st.session_state[f'{PREFIX}_new_mode']:
        st.markdown("### ✏️ 새 개별상품 등록")
        
        new_name = st.text_input("상품명", placeholder="예: VIP 맞춤 상담")
        
        col_ch, col_guide = st.columns(2)
        with col_ch:
            st.markdown("**📑 목차** (줄바꿈 구분)")
            new_chapters = st.text_area("", height=200, key="new_ch",
                                        placeholder="1. 기본 운세\n2. 상세 분석\n3. 월별 운세\n4. 조언")
        with col_guide:
            st.markdown("**📜 AI 지침**")
            new_guideline = st.text_area("", height=200, key="new_guide",
                                         placeholder="고객의 상세 정보를 바탕으로 깊이 있는 분석...")
        
        with st.expander("🎨 디자인 설정", expanded=False):
            st.markdown("**📄 목표 페이지**")
            new_pages = st.number_input("페이지 수", value=30, min_value=1, max_value=500, help="고객 상황에 맞게 설정")
            
            st.markdown("**🔤 폰트 설정**")
            fcol1, fcol2, fcol3, fcol4 = st.columns(4)
            with fcol1:
                new_font = st.selectbox("폰트", list(FONT_OPTIONS.keys()), format_func=lambda x: FONT_OPTIONS[x])
            with fcol2:
                new_title = st.number_input("대제목", value=24, min_value=16, max_value=40)
            with fcol3:
                new_subtitle = st.number_input("소제목", value=16, min_value=12, max_value=30)
            with fcol4:
                new_body = st.number_input("본문", value=12, min_value=8, max_value=20)
            
            fcol5, fcol6, fcol7 = st.columns(3)
            with fcol5:
                new_line_height = st.slider("행간 %", 100, 300, 180)
            with fcol6:
                new_letter_spacing = st.slider("자간 %", -5, 10, 0)
            with fcol7:
                new_char_width = st.slider("장평 %", 50, 150, 100)
            
            st.markdown("**📐 여백 (mm)**")
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                new_mt = st.number_input("상단", value=25)
            with mcol2:
                new_mb = st.number_input("하단", value=25)
            with mcol3:
                new_ml = st.number_input("좌측", value=25)
            with mcol4:
                new_mr = st.number_input("우측", value=25)
            
            st.markdown("**🖼️ 이미지**")
            icol1, icol2, icol3 = st.columns(3)
            with icol1:
                new_cover = st.file_uploader("표지", type=['jpg','jpeg','png'], key="new_cover")
                if new_cover:
                    st.image(new_cover, width=80)
            with icol2:
                new_bg = st.file_uploader("내지", type=['jpg','jpeg','png'], key="new_bg")
                if new_bg:
                    st.image(new_bg, width=80)
            with icol3:
                new_info = st.file_uploader("안내지", type=['jpg','jpeg','png'], key="new_info")
                if new_info:
                    st.image(new_info, width=80)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 등록", type="primary", use_container_width=True):
                if new_name:
                    result = add_service(
                        name=new_name, product_category=PRODUCT_TYPE,
                        font_family=new_font, font_size_title=new_title,
                        font_size_subtitle=new_subtitle, font_size_body=new_body,
                        line_height=new_line_height, letter_spacing=new_letter_spacing,
                        char_width=new_char_width, margin_top=new_mt, margin_bottom=new_mb,
                        margin_left=new_ml, margin_right=new_mr, target_pages=new_pages
                    )
                    if result.get('success'):
                        sid = result['id']
                        if new_chapters:
                            add_chapters_bulk(sid, [c.strip() for c in new_chapters.split('\n') if c.strip()])
                        if new_guideline:
                            add_guideline(sid, "기본 지침", new_guideline)
                        if new_cover:
                            path = save_uploaded_file(new_cover, "cover")
                            add_template(sid, "cover", "표지", path)
                        if new_bg:
                            path = save_uploaded_file(new_bg, "bg")
                            add_template(sid, "background", "내지", path)
                        if new_info:
                            path = save_uploaded_file(new_info, "info")
                            add_template(sid, "info", "안내지", path)
                        clear_service_cache()
                        st.session_state[f'{PREFIX}_new_mode'] = False
                        st.toast("✅ 등록 완료!")
                        st.rerun()
                else:
                    st.warning("상품명을 입력하세요.")
        with col2:
            if st.button("❌ 취소", use_container_width=True):
                st.session_state[f'{PREFIX}_new_mode'] = False
                st.rerun()
    
    # ===== 상품 상세보기 =====
    elif st.session_state[f'{PREFIX}_view_id']:
        product = next((p for p in products if p['id'] == st.session_state[f'{PREFIX}_view_id']), None)
        
        if product:
            if st.button("← 목록"):
                st.session_state[f'{PREFIX}_view_id'] = None
                st.session_state[f'{PREFIX}_edit_mode'] = False
                st.rerun()
            
            chapters = get_chapters_by_service(product['id'])
            guidelines = get_guidelines_by_service(product['id'])
            templates = get_templates_by_service(product['id'])
            
            st.markdown(f"### 🎯 {product['name']}")
            
            if st.session_state[f'{PREFIX}_edit_mode']:
                # 수정 모드 (기성제품과 동일 구조)
                edit_name = st.text_input("상품명", value=product['name'])
                
                col_ch, col_guide = st.columns(2)
                with col_ch:
                    st.markdown("**📑 목차**")
                    current_ch = "\n".join([c['title'] for c in chapters])
                    edit_chapters = st.text_area("", value=current_ch, height=200, key="edit_ch")
                with col_guide:
                    st.markdown("**📜 AI 지침**")
                    current_guide = guidelines[0]['content'] if guidelines else ""
                    edit_guideline = st.text_area("", value=current_guide, height=200, key="edit_guide")
                
                with st.expander("🎨 디자인 설정"):
                    edit_pages = st.number_input("페이지", value=product.get('target_pages', 50))
                    
                    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
                    with fcol1:
                        fidx = list(FONT_OPTIONS.keys()).index(product.get('font_family', 'NanumGothic'))
                        edit_font = st.selectbox("폰트", list(FONT_OPTIONS.keys()), index=fidx, format_func=lambda x: FONT_OPTIONS[x])
                    with fcol2:
                        edit_title = st.number_input("대제목", value=product.get('font_size_title', 24))
                    with fcol3:
                        edit_subtitle = st.number_input("소제목", value=product.get('font_size_subtitle', 16))
                    with fcol4:
                        edit_body = st.number_input("본문", value=product.get('font_size_body', 12))
                    
                    fcol5, fcol6, fcol7 = st.columns(3)
                    with fcol5:
                        edit_lh = st.slider("행간", 100, 300, product.get('line_height', 180))
                    with fcol6:
                        edit_ls = st.slider("자간", -5, 10, product.get('letter_spacing', 0))
                    with fcol7:
                        edit_cw = st.slider("장평", 50, 150, product.get('char_width', 100))
                    
                    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
                    with mcol1:
                        edit_mt = st.number_input("상단", value=product.get('margin_top', 25))
                    with mcol2:
                        edit_mb = st.number_input("하단", value=product.get('margin_bottom', 25))
                    with mcol3:
                        edit_ml = st.number_input("좌측", value=product.get('margin_left', 25))
                    with mcol4:
                        edit_mr = st.number_input("우측", value=product.get('margin_right', 25))
                
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("💾 저장", type="primary", use_container_width=True):
                        update_service(product['id'], name=edit_name,
                                       font_family=edit_font, font_size_title=edit_title,
                                       font_size_subtitle=edit_subtitle, font_size_body=edit_body,
                                       line_height=edit_lh, letter_spacing=edit_ls, char_width=edit_cw,
                                       margin_top=edit_mt, margin_bottom=edit_mb,
                                       margin_left=edit_ml, margin_right=edit_mr, target_pages=edit_pages)
                        
                        delete_chapters_by_service(product['id'])
                        if edit_chapters:
                            add_chapters_bulk(product['id'], [c.strip() for c in edit_chapters.split('\n') if c.strip()])
                        
                        if guidelines:
                            update_guideline(guidelines[0]['id'], content=edit_guideline)
                        elif edit_guideline:
                            add_guideline(product['id'], "기본 지침", edit_guideline)
                        
                        clear_service_cache()
                        st.session_state[f'{PREFIX}_edit_mode'] = False
                        st.toast("✅ 저장 완료!")
                        st.rerun()
                with col2:
                    if st.button("❌ 취소", use_container_width=True):
                        st.session_state[f'{PREFIX}_edit_mode'] = False
                        st.rerun()
            
            else:
                # 보기 모드
                col_ch, col_guide = st.columns(2)
                with col_ch:
                    st.markdown("**📑 목차**")
                    if chapters:
                        for c in chapters:
                            st.text(f"• {c['title']}")
                    else:
                        st.caption("(없음)")
                with col_guide:
                    st.markdown("**📜 AI 지침**")
                    if guidelines:
                        preview = guidelines[0]['content'][:300] + "..." if len(guidelines[0]['content']) > 300 else guidelines[0]['content']
                        st.text(preview)
                    else:
                        st.caption("(없음)")
                
                st.markdown("**🖼️ 이미지**")
                icol1, icol2, icol3 = st.columns(3)
                cover_t = next((t for t in templates if t['template_type'] == 'cover'), None)
                bg_t = next((t for t in templates if t['template_type'] == 'background'), None)
                info_t = next((t for t in templates if t['template_type'] == 'info'), None)
                
                with icol1:
                    if cover_t and cover_t.get('image_path'):
                        st.image(cover_t['image_path'], width=80, caption="표지")
                    else:
                        st.caption("❌ 표지 없음")
                with icol2:
                    if bg_t and bg_t.get('image_path'):
                        st.image(bg_t['image_path'], width=80, caption="내지")
                    else:
                        st.caption("❌ 내지 없음")
                with icol3:
                    if info_t and info_t.get('image_path'):
                        st.image(info_t['image_path'], width=80, caption="안내지")
                    else:
                        st.caption("❌ 안내지 없음")
                
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 1, 2])
                with col1:
                    if st.button("✏️ 수정", use_container_width=True):
                        st.session_state[f'{PREFIX}_edit_mode'] = True
                        st.rerun()
                with col2:
                    if st.button("🗑️ 삭제", use_container_width=True):
                        delete_service(product['id'])
                        clear_service_cache()
                        st.session_state[f'{PREFIX}_view_id'] = None
                        st.toast("🗑️ 삭제됨")
                        st.rerun()
    
    # ===== 목록 모드 =====
    else:
        if st.button("➕ 새 개별상품 등록", type="primary"):
            st.session_state[f'{PREFIX}_new_mode'] = True
            st.rerun()
        
        st.markdown("---")
        
        if products:
            for p in products:
                col1, col2 = st.columns([5, 1])
                with col1:
                    if st.button(f"🎯 {p['name']}", key=f"p_{p['id']}", use_container_width=True):
                        st.session_state[f'{PREFIX}_view_id'] = p['id']
                        st.rerun()
                with col2:
                    st.caption(f"{p.get('target_pages', 50)}p")
        else:
            st.info("📭 등록된 개별상품이 없습니다.")

# =====================================================
# 🚀 PDF 생성 탭
# =====================================================
with tab2:
    products = get_services_by_category(PRODUCT_TYPE)
    
    if not products:
        st.warning("⚠️ 먼저 '상품 설정' 탭에서 상품을 등록하세요.")
        st.stop()
    
    # 상품 선택
    product_names = [f"🎯 {p['name']}" for p in products]
    selected_idx = st.selectbox("상품 선택", range(len(products)), format_func=lambda x: product_names[x])
    selected_product = products[selected_idx]
    
    st.markdown("---")
    
    # ===== 직접 입력 =====
    st.markdown("### ✍️ 고객 정보 직접 입력")
    
    rc = st.session_state[f'{PREFIX}_reset']
    
    with st.form(key=f"input_form_{rc}"):
        col1, col2 = st.columns(2)
        
        with col1:
            inp_name = st.text_input("이름 *", key=f"name_{rc}")
            inp_birth = st.date_input("생년월일 *", value=date(1990, 1, 1), key=f"birth_{rc}")
            inp_time = st.time_input("태어난 시간", key=f"time_{rc}")
            inp_lunar = st.radio("음력/양력", ["양력", "음력"], horizontal=True, key=f"lunar_{rc}")
        
        with col2:
            inp_gender = st.radio("성별 *", ["남", "여"], horizontal=True, key=f"gender_{rc}")
            inp_mbti = st.selectbox("MBTI", ["선택안함"] + ["INTJ", "INTP", "ENTJ", "ENTP", 
                                                           "INFJ", "INFP", "ENFJ", "ENFP",
                                                           "ISTJ", "ISFJ", "ESTJ", "ESFJ",
                                                           "ISTP", "ISFP", "ESTP", "ESFP"], key=f"mbti_{rc}")
            inp_blood = st.selectbox("혈액형", ["선택안함", "A형", "B형", "O형", "AB형"], key=f"blood_{rc}")
            inp_question = st.text_area("상담 질문/요청사항", height=100, key=f"question_{rc}",
                                        placeholder="궁금한 점이나 특별히 봐주셨으면 하는 부분...")
        
        submitted = st.form_submit_button("➕ 고객 추가", type="primary", use_container_width=True)
        
        if submitted:
            if inp_name:
                customer = {
                    '이름': inp_name,
                    '생년월일': str(inp_birth),
                    '시간': str(inp_time),
                    '음력양력': inp_lunar,
                    '성별': inp_gender,
                    'MBTI': inp_mbti if inp_mbti != "선택안함" else "",
                    '혈액형': inp_blood if inp_blood != "선택안함" else "",
                    '질문': inp_question
                }
                st.session_state[f'{PREFIX}_customers'].append(customer)
                st.toast(f"✅ {inp_name}님 추가!")
                st.rerun()
            else:
                st.warning("이름을 입력하세요.")
    
    st.markdown("---")
    
    # ===== 고객 목록 =====
    customers = st.session_state[f'{PREFIX}_customers']
    
    if customers:
        total = len(customers)
        selected_count = len(st.session_state[f'{PREFIX}_selected'])
        st.markdown(f"### 👥 고객 목록 ({selected_count}/{total}명 선택)")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 전체 선택", use_container_width=True, key="sel_all"):
                st.session_state[f'{PREFIX}_selected'] = set(range(total))
                st.rerun()
        with col2:
            bcol1, bcol2 = st.columns(2)
            with bcol1:
                if st.button("⬜ 전체 해제", use_container_width=True, key="desel_all"):
                    st.session_state[f'{PREFIX}_selected'] = set()
                    st.rerun()
            with bcol2:
                if st.button("🔄 초기화", use_container_width=True, key="reset_all"):
                    st.session_state[f'{PREFIX}_customers'] = []
                    st.session_state[f'{PREFIX}_selected'] = set()
                    st.session_state[f'{PREFIX}_progress'] = {}
                    st.session_state[f'{PREFIX}_completed'] = set()
                    st.session_state[f'{PREFIX}_reset'] += 1
                    st.toast("🔄 초기화!")
                    st.rerun()
        
        st.markdown("---")
        
        for idx, cust in enumerate(customers):
            col_chk, col_name, col_info, col_prog, col_dl = st.columns([0.5, 1.5, 2, 1, 0.5])
            
            with col_chk:
                checked = idx in st.session_state[f'{PREFIX}_selected']
                def toggle(i):
                    if i in st.session_state[f'{PREFIX}_selected']:
                        st.session_state[f'{PREFIX}_selected'].discard(i)
                    else:
                        st.session_state[f'{PREFIX}_selected'].add(i)
                st.checkbox("", value=checked, key=f"chk_{idx}_{rc}", label_visibility="collapsed",
                           on_change=toggle, args=(idx,))
            
            with col_name:
                st.write(f"👤 **{cust['이름']}**")
            
            with col_info:
                info = f"{cust['생년월일']} · {cust['성별']}"
                if cust.get('MBTI'):
                    info += f" · {cust['MBTI']}"
                st.caption(info)
            
            with col_prog:
                prog = st.session_state[f'{PREFIX}_progress'].get(idx, 0)
                st.progress(prog / 100)
            
            with col_dl:
                if idx in st.session_state[f'{PREFIX}_completed']:
                    pdfs = st.session_state.get(f'{PREFIX}_pdfs', {})
                    if idx in pdfs:
                        st.download_button(
                            "📥",
                            data=pdfs[idx]['pdf'],
                            file_name=f"{pdfs[idx]['name']}_{selected_product['name']}.pdf",
                            mime="application/pdf",
                            key=f"dl_{idx}"
                        )
        
        st.markdown("---")
        
        # PDF 생성 버튼
        selected_count = len(st.session_state[f'{PREFIX}_selected'])
        if selected_count > 0:
            if st.button(f"🚀 PDF 생성 ({selected_count}명)", type="primary", use_container_width=True):
                # API 키 확인
                api_key = get_system_config(ConfigKeys.ADMIN_API_KEY, "")
                if not api_key:
                    st.error("⚠️ API 키가 설정되지 않았습니다. 관리자설정에서 API 키를 입력하세요.")
                    st.stop()
                
                # 상품 정보 가져오기
                chapters = get_chapters_by_service(selected_product['id'])
                guidelines = get_guidelines_by_service(selected_product['id'])
                templates = get_templates_by_service(selected_product['id'])
                
                if not chapters:
                    st.error("⚠️ 목차가 없습니다. 상품 설정에서 목차를 추가하세요.")
                    st.stop()
                
                chapter_titles = [c['title'] for c in chapters]
                guideline_text = guidelines[0]['content'] if guidelines else ""
                
                # 템플릿 이미지 경로
                cover_img = next((t['image_path'] for t in templates if t['template_type'] == 'cover'), None)
                bg_img = next((t['image_path'] for t in templates if t['template_type'] == 'background'), None)
                info_img = next((t['image_path'] for t in templates if t['template_type'] == 'info'), None)
                
                bar = st.progress(0)
                status = st.empty()
                
                # PDF 생성기 초기화
                pdf_gen = PDFGenerator(
                    font_name=selected_product.get('font_family', 'NanumGothic'),
                    font_size=selected_product.get('font_size_body', 12),
                    line_height=int(selected_product.get('line_height', 180) / 10),
                    letter_spacing=selected_product.get('letter_spacing', 0)
                )
                
                generated_pdfs = {}
                
                for i, idx in enumerate(st.session_state[f'{PREFIX}_selected']):
                    cust = customers[idx]
                    name = cust.get('이름', f'고객{idx+1}')
                    status.text(f"⏳ {name}님 콘텐츠 생성 중... ({i+1}/{selected_count})")
                    
                    # GPT로 콘텐츠 생성
                    def progress_cb(prog, msg):
                        st.session_state[f'{PREFIX}_progress'][idx] = int(prog * 80)
                        bar.progress((i + prog * 0.8) / selected_count)
                    
                    contents = generate_full_content(
                        api_key=api_key,
                        customer_info=cust,
                        chapters=chapter_titles,
                        guideline=guideline_text,
                        service_type=selected_product['name'],
                        progress_callback=progress_cb
                    )
                    
                    status.text(f"📄 {name}님 PDF 생성 중... ({i+1}/{selected_count})")
                    
                    # PDF 생성
                    pdf_bytes = pdf_gen.create_pdf(
                        chapters_content=contents,
                        customer_name=name,
                        service_type=selected_product['name'],
                        cover_image=cover_img,
                        background_image=bg_img,
                        info_image=info_img
                    )
                    
                    generated_pdfs[idx] = {
                        'name': name,
                        'pdf': pdf_bytes
                    }
                    
                    st.session_state[f'{PREFIX}_progress'][idx] = 100
                    st.session_state[f'{PREFIX}_completed'].add(idx)
                    bar.progress((i + 1) / selected_count)
                
                # 생성된 PDF를 세션에 저장
                st.session_state[f'{PREFIX}_pdfs'] = generated_pdfs
                
                bar.progress(1.0)
                status.text(f"✅ {selected_count}명 PDF 생성 완료!")
                st.balloons()
                st.rerun()
        else:
            st.button("🚀 PDF 생성 (0명 선택)", disabled=True, use_container_width=True)
    else:
        st.info("✍️ 위 양식에서 고객 정보를 입력하세요.")
