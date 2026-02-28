"""
뒷광고 신고 도우미 — HWP 별지 제6호 서식 기반
- 위반 콘텐츠 URL 입력 → 자동 증거 수집 → HWP 양식 기반 PDF 신고서 생성
"""
import streamlit as st
import subprocess
import sys
import os
import gc
import tempfile
from datetime import datetime, date


# 페이지 설정 (반드시 첫 번째 Streamlit 명령이어야 함)
st.set_page_config(
    page_title='뒷광고 신고 도우미',
    page_icon='⚖️',
    layout='wide',
)


@st.cache_resource
def install_playwright():
    """
    Streamlit Cloud에서 Playwright Chromium 자동 설치.
    - check=True 제거: 설치 실패 시 예외가 캐싱되어 앱 영구 먹통 방지
    - 이미 설치된 경우 재설치 스킵 (속도 및 메모리 절약)
    """
    try:
        # 이미 설치됐는지 확인 (빠른 경로)
        check = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run"],
            capture_output=True, timeout=10,
        )
        if check.returncode == 0 and b"chromium" not in check.stdout:
            return True  # 이미 설치됨

        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            timeout=120,
        )
        return result.returncode == 0
    except Exception:
        return False


_pw_ready = install_playwright()

# ── CSS ──
st.markdown("""
<style>
    /* Streamlit Cloud 주입 요소 숨김 */
    header[data-testid="stHeader"] { display: none !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    div[data-testid="stToolbar"] { display: none !important; }
    div[data-testid="stDecoration"] { display: none !important; }
    .stDeployButton { display: none !important; }
    /* 상단 여백 보정 — 헤더 숨긴 빈 공간 제거 */
    .stApp > header { display: none !important; }
    .block-container { padding-top: 1rem !important; }
    section[data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }

    .main-header {
        font-size: 2.2rem; font-weight: 700; color: #1a1a2e;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem; color: #6b7280; margin-bottom: 2rem;
    }
    .step-badge {
        background: #2563eb; color: white; padding: 4px 12px;
        border-radius: 12px; font-size: 0.85rem; font-weight: 600;
    }
    .success-box {
        background: #d1fae5; border-left: 4px solid #10b981;
        padding: 16px; border-radius: 8px; margin: 16px 0;
    }
    .warning-box {
        background: #fef3c7; border-left: 4px solid #f59e0b;
        padding: 16px; border-radius: 8px; margin: 16px 0;
    }
    .danger-box {
        background: #ffe4e6; border-left: 4px solid #f43f5e;
        padding: 16px; border-radius: 8px; margin: 16px 0;
    }
    .info-box {
        background: #dbeafe; border-left: 4px solid #2563eb;
        padding: 16px; border-radius: 8px; margin: 16px 0;
    }
    div[data-testid="stSidebar"] { background: #f8f9fb; }
    .stButton>button {
        background: #2563eb; color: white; border: none;
        padding: 0.5rem 2rem; border-radius: 8px; font-weight: 600;
        white-space: nowrap;
    }
    .stButton>button:hover { background: #1d4ed8; }

    /* 반응형: 모바일/태블릿 */
    @media (max-width: 768px) {
        .main-header { font-size: 1.5rem !important; }
        .sub-header { font-size: 0.85rem !important; }
        /* Streamlit 컬럼이 모바일에서 세로로 쌓이도록 */
        div[data-testid="column"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 0 !important;
        }
        .stButton>button {
            padding: 0.5rem 1rem;
            width: 100% !important;
        }
    }
    @media (max-width: 480px) {
        .main-header { font-size: 1.3rem !important; }
        div[data-testid="stSidebar"] { min-width: 200px !important; }
    }

    /* 사이드바 너비 확대 + 텍스트 잘림 방지 */
    div[data-testid="stSidebar"] {
        min-width: 280px;
    }
    div[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
        word-break: keep-all;
    }

    /* 컬럼 내 요소가 잘리지 않도록 */
    div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
        gap: 0.5rem;
    }
    div[data-testid="column"] {
        min-width: 120px;
    }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ──
with st.sidebar:
    st.markdown('### ⚖️ 뒷광고 신고 도우미')
    st.markdown('---')
    st.markdown("""
    **사용 방법**
    1. 위반 콘텐츠 URL 입력
    2. 자동 증거 수집 실행
    3. HWP 양식 기반 정보 입력
    4. PDF 신고서 다운로드
    5. 아래 중 택1 제출:
       - **공정위** ([신고서식+안내](https://www.ftc.go.kr/www/contents.do?key=656))
       - **국민신문고** ([민원신청](https://www.epeople.go.kr))
    """)
    st.markdown('---')
    st.markdown("""
    **관련 법률**
    - 표시·광고의 공정화에 관한 법률
    - 추천·보증 등에 관한 표시·광고 심사지침

    **신고 대상**
    - 경제적 이해관계 미표시 (뒷광고)
    - 허위·과장 광고
    - 기만적 광고
    """)
    st.markdown('---')
    st.caption('공정거래위원회 민원: 1670-0007')
    st.caption('소비자 상담: 1372')

# ── 메인 ──
st.markdown('<p class="main-header">⚖️ 뒷광고 신고 도우미 (HWP 양식)</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">위반 URL 입력 → 증거 수집 → HWP 별지 제6호 서식 기반 PDF 생성</p>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# STEP 1: 증거 수집
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 1</span> **위반 콘텐츠 URL 입력 & 증거 수집**', unsafe_allow_html=True)

col_url, col_btn = st.columns([3, 1], gap="medium")
with col_url:
    target_url = st.text_input(
        '위반 의심 콘텐츠 URL',
        placeholder='https://instagram.com/p/... 또는 블로그/유튜브 URL',
        label_visibility='collapsed'
    )
with col_btn:
    capture_btn = st.button('🔍 증거 수집', use_container_width=True)

# 증거 수집 상태 저장
if 'evidence' not in st.session_state:
    st.session_state.evidence = None
if 'analysis' not in st.session_state:
    st.session_state.analysis = None

# 수동 스크린샷 업로드
st.markdown('**또는** 직접 스크린샷을 첨부할 수도 있습니다:')
uploaded_screenshots = st.file_uploader(
    '스크린샷 업로드 (여러 장 가능)',
    type=['png', 'jpg', 'jpeg', 'gif', 'webp'],
    accept_multiple_files=True,
    label_visibility='collapsed',
)

# 업로드된 스크린샷 저장
if 'manual_screenshots' not in st.session_state:
    st.session_state.manual_screenshots = []

if uploaded_screenshots:
    evidence_dir = os.path.join(tempfile.gettempdir(), 'ad_report_evidence')
    os.makedirs(evidence_dir, exist_ok=True)
    st.session_state.manual_screenshots = []
    for i, up_file in enumerate(uploaded_screenshots):
        save_path = os.path.join(evidence_dir, f'manual_screenshot_{i}_{up_file.name}')
        with open(save_path, 'wb') as f:
            f.write(up_file.getbuffer())
        st.session_state.manual_screenshots.append(save_path)
    st.success(f'{len(uploaded_screenshots)}개 스크린샷이 첨부되었습니다.')

if capture_btn and target_url:
    if not _pw_ready:
        st.warning(
            "⚠️ Playwright(브라우저 자동화)가 현재 로딩 중이거나 설치에 실패했습니다. "
            "잠시 후 다시 시도하거나, 아래 **스크린샷 직접 업로드** 기능을 사용해 주세요."
        )
    else:
        with st.spinner('증거를 수집하고 있습니다... (스크린샷 캡처 + 어필리에이트 지표 분석)'):
            try:
                from evidence_collector import capture_screenshot, analyze_violation
                evidence_dir = os.path.join(tempfile.gettempdir(), 'ad_report_evidence')

                evidence = capture_screenshot(target_url, evidence_dir)
                analysis = analyze_violation(evidence)
                st.session_state.evidence = evidence
                st.session_state.analysis = analysis
                gc.collect()
            except Exception as e:
                gc.collect()
                st.error(f'증거 수집 중 오류가 발생했습니다: {str(e)}')
                st.info("💡 스크린샷을 직접 촬영해 아래 업로드 기능을 사용할 수 있습니다.")

# 수집 결과 표시
if st.session_state.evidence:
    ev = st.session_state.evidence
    an = st.session_state.analysis

    if ev.get('error'):
        st.markdown(f'<div class="warning-box">⚠️ 페이지 접근 중 일부 오류: {ev["error"]}</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown('**📋 수집 결과**')
        st.markdown(f'- **페이지 제목**: {ev.get("page_title", "N/A")}')
        st.markdown(f'- **캡처 시각**: {ev.get("captured_at", "N/A")}')
        st.markdown(f'- **광고 표시 발견**: {"✅ 있음" if ev.get("has_ad_disclosure") else "❌ 없음"}')

        if ev.get('affiliate_indicators'):
            st.markdown('**🔗 탐지된 어필리에이트 지표:**')
            for ind in ev['affiliate_indicators']:
                st.markdown(f'  - {ind}')
        else:
            st.markdown('*자동 탐지로 어필리에이트 지표를 찾지 못했습니다. 수동으로 확인해주세요.*')

        # 이미지/스티커 분석 결과
        img_analysis = ev.get('image_analysis', {})
        if img_analysis.get('image_analysis_done'):
            st.markdown('---')
            st.markdown('**🖼️ 이미지/스티커 광고 표시 분석:**')
            if img_analysis.get('image_has_disclosure'):
                st.markdown('✅ 이미지/스티커에서 광고 표시 발견')
                for detail in ev.get('image_disclosure_details', []):
                    st.markdown(f'  - {detail}')
            else:
                st.markdown('❌ 이미지/스티커에서 광고 표시 미발견')
        elif img_analysis.get('error'):
            st.caption(f'⚠️ 이미지 분석: {img_analysis["error"]}')

    with col_b:
        st.markdown('**🔎 위반 분석 결과**')
        severity = an.get('severity', '미확인')
        if severity == '높음':
            st.markdown(f'<div class="danger-box">⛔ 위반 심각도: <b>{severity}</b><br>{an.get("recommendation", "")}</div>', unsafe_allow_html=True)
        elif severity == '중간':
            st.markdown(f'<div class="warning-box">⚠️ 위반 심각도: <b>{severity}</b><br>{an.get("recommendation", "")}</div>', unsafe_allow_html=True)
        elif severity == '없음':
            st.markdown(f'<div class="success-box">✅ 위반 심각도: <b>{severity}</b><br>{an.get("recommendation", "")}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="info-box">ℹ️ 위반 심각도: <b>{severity}</b><br>{an.get("recommendation", "")}</div>', unsafe_allow_html=True)

        if an.get('violation_types'):
            for vt in an['violation_types']:
                st.markdown(f'  - **{vt}**')

    # 스크린샷 표시
    if ev.get('screenshot_path') and os.path.exists(ev['screenshot_path']):
        with st.expander('📸 캡처된 스크린샷 보기'):
            st.image(ev['screenshot_path'], caption=f'캡처: {ev["captured_at"]}', use_container_width=True)

st.markdown('---')

# ═══════════════════════════════════════
# STEP 2: HWP 양식 기반 정보 입력
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 2</span> **HWP 별지 제6호 서식 기반 정보 입력**', unsafe_allow_html=True)
st.caption('(*) 표시는 필수 항목입니다. HWP 양식과 동일한 구조로 입력하세요.')

tab1, tab2, tab3, tab4 = st.tabs(['👤 신고인', '🏢 피신고인', '📝 신고내용', '✅ 사전점검표 + 기타'])

# ── Tab 1: 신고인 ──
with tab1:
    st.markdown('#### 신고인 정보')
    
    col1, col2 = st.columns(2)
    with col1:
        reporter_name = st.text_input('성명 *', key='r_name')
        reporter_address = st.text_input('주소 *', key='r_addr')
        reporter_phone = st.text_input('전화번호 *', placeholder='010-1234-5678', key='r_phone')
        reporter_fax = st.text_input('팩스번호', key='r_fax')
        
    with col2:
        reporter_birth = st.text_input('생년월일 *', placeholder='1990-01-01', key='r_birth')
        reporter_mobile = st.text_input('휴대폰', placeholder='010-1234-5678', key='r_mobile')
        reporter_email = st.text_input('이메일', key='r_email')
    
    # 피신고인과의 관계 (HWP 양식과 동일)
    st.markdown('**피신고인과의 관계 *:**')
    relationship_options = ['소비자', '행정기관', '사회단체', '경쟁사업자', '구성사업자', '기타']
    reporter_relationship = st.radio(
        '피신고인과의 관계',
        options=relationship_options,
        index=0,
        horizontal=True,
        label_visibility='collapsed'
    )
    
    if reporter_relationship == '기타':
        other_relationship = st.text_input('기타 관계 구체적으로', key='other_rel')
        reporter_relationship = other_relationship

# ── Tab 2: 피신고인 ──
with tab2:
    st.markdown('#### 피신고인 정보')
    
    col3, col4 = st.columns(2)
    with col3:
        resp_business_name = st.text_input('사업자명 *', placeholder='@계정명 또는 상호', key='resp_name')
        resp_address_phone = st.text_area(
            '주소 또는 전화번호 *', 
            placeholder='서울시 강남구... 또는 02-123-4567',
            height=80,
            key='resp_addr_phone'
        )
    with col4:
        resp_representative = st.text_input('대표자 성명', key='resp_rep')
        resp_department = st.text_input('관련부서 및 담당자', key='resp_dept')

# ── Tab 3: 신고내용 ──
with tab3:
    st.markdown('#### 신고내용')
    
    col5, col6 = st.columns(2)
    with col5:
        content_media = st.selectbox(
            '표시·광고 매체 *',
            ['인스타그램', '유튜브', '블로그 (네이버)', '블로그 (기타)', '트위터/X',
             '페이스북', '틱톡', '카페/커뮤니티', '기타 웹사이트'],
            key='content_media'
        )
        
    with col6:
        content_date = st.date_input('표시·광고 일자 *', value=date.today(), key='content_date')
    
    # 대형 텍스트 영역들 (HWP 양식과 동일)
    content_description = st.text_area(
        '표시·광고의 내용 *',
        placeholder='광고 콘텐츠의 구체적인 내용을 설명하세요. (상품명, 효과, 추천 문구 등)',
        height=120,
        key='content_desc',
        help='자동 분석 결과가 있으면 참고하여 작성하세요.'
    )
    
    # 자동 생성된 위반 이유
    auto_violation_reason = ''
    if st.session_state.analysis and st.session_state.analysis.get('recommendation'):
        auto_violation_reason = st.session_state.analysis['recommendation']
    if st.session_state.evidence and st.session_state.evidence.get('affiliate_indicators'):
        indicators = '\n'.join(f'- {i}' for i in st.session_state.evidence['affiliate_indicators'])
        auto_violation_reason += f'\n\n[자동 탐지 결과]\n{indicators}'
    
    violation_reason = st.text_area(
        '표시·광고가 위법하다고 주장하는 이유 *',
        value=auto_violation_reason,
        height=150,
        key='violation_reason',
        help='자동 분석 결과를 수정/보완할 수 있습니다.'
    )

# ── Tab 4: 사전점검표 + 기타 ──
with tab4:
    st.markdown('#### 위반행위 사전점검표')
    st.caption('해당하는 위반 유형을 체크하세요.')
    
    # HWP의 위반행위 사전점검표와 동일한 구조
    col7, col8 = st.columns(2)
    
    with col7:
        st.markdown('**제3조 (부당한 표시ㆍ광고 행위의 금지)**')
        check_false_exaggerated = st.checkbox('1-① 거짓·과장 표시ㆍ광고', key='check_1_1')
        check_deceptive = st.checkbox('1-② 기만적 표시ㆍ광고', key='check_1_2')
        check_unfair_comparison = st.checkbox('1-③ 부당비교 표시ㆍ광고', key='check_1_3')
        check_defamatory = st.checkbox('1-④ 비방적 표시ㆍ광고', key='check_1_4')
    
    with col8:
        st.markdown('**기타 위반행위**')
        check_missing_info = st.checkbox('2. 중요정보 미고시', key='check_2')
        check_association = st.checkbox('3. 사업자단체의 표시ㆍ광고 제한행위', key='check_3')
        check_other = st.checkbox('4. 기타', key='check_4')
    
    st.markdown('---')
    st.markdown('#### 첨부자료 및 신분공개')
    
    attachment_desc = st.text_input(
        '첨부자료 설명',
        value='신고 대상 표시·광고물 또는 그 사본',
        key='attachment_desc'
    )
    
    # 신분공개 동의여부 (HWP 양식과 동일)
    st.markdown('**신고인 신분공개 동의여부:**')
    identity_disclosure = st.radio(
        '신분공개',
        options=['공개', '비공개', '사건 조치 후 공개'],
        index=1,  # 기본값: 비공개
        horizontal=True,
        label_visibility='collapsed'
    )
    
    # 추가 참고사항
    additional_notes = st.text_area(
        '추가 참고사항 (첨부2 양식에 포함)',
        placeholder='추가로 신고하고 싶은 상세 내용이 있으면 입력하세요.',
        height=100,
        key='additional_notes'
    )

st.markdown('---')

# ═══════════════════════════════════════
# STEP 3: PDF 신고서 생성 & 다운로드
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 3</span> **PDF 신고서 생성 & 다운로드**', unsafe_allow_html=True)

generate_btn = st.button('📄 HWP 양식 기반 PDF 생성', type='primary', use_container_width=True)

if generate_btn:
    # 필수 항목 검증
    missing = []
    if not reporter_name: missing.append('신고인 성명')
    if not reporter_birth: missing.append('신고인 생년월일')
    if not reporter_address: missing.append('신고인 주소')
    if not reporter_phone: missing.append('신고인 전화번호')
    if not resp_business_name: missing.append('피신고인 사업자명')
    if not resp_address_phone: missing.append('피신고인 주소 또는 전화번호')
    if not content_description: missing.append('표시·광고의 내용')
    if not violation_reason: missing.append('위법하다고 주장하는 이유')

    if missing:
        st.error(f'필수 항목을 입력해주세요: {", ".join(missing)}')
    else:
        with st.spinner('HWP 양식 기반 PDF를 생성하고 있습니다...'):
            from report_generator import generate_report

            ev = st.session_state.evidence or {}
            # 수동 스크린샷이 있으면 첫 번째를 대표로 사용
            screenshot = ev.get('screenshot_path')
            manual_shots = st.session_state.get('manual_screenshots', [])
            all_screenshots = []
            if screenshot and os.path.exists(screenshot):
                all_screenshots.append(screenshot)
            all_screenshots.extend(manual_shots)

            # HWP 양식에 맞는 데이터 구조 생성
            report_data = {
                'reporter': {
                    'name': reporter_name,
                    'birth_date': reporter_birth,
                    'address': reporter_address,
                    'phone': reporter_phone,
                    'mobile': reporter_mobile,
                    'fax': reporter_fax,
                    'email': reporter_email,
                    'relationship': reporter_relationship
                },
                'respondent': {
                    'business_name': resp_business_name,
                    'representative': resp_representative,
                    'address_phone': resp_address_phone,
                    'department': resp_department
                },
                'report_content': {
                    'media': content_media,
                    'date': content_date.strftime('%Y-%m-%d'),
                    'content': content_description,
                    'violation_reason': violation_reason
                },
                'checklist': {
                    'false_exaggerated': check_false_exaggerated,
                    'deceptive': check_deceptive,
                    'unfair_comparison': check_unfair_comparison,
                    'defamatory': check_defamatory,
                    'missing_info': check_missing_info,
                    'association_restriction': check_association,
                    'other': check_other
                },
                'attachment_desc': attachment_desc,
                'identity_disclosure': identity_disclosure,
                'evidence': {
                    'screenshot_path': all_screenshots[0] if all_screenshots else None,
                    'extra_screenshots': all_screenshots[1:] if len(all_screenshots) > 1 else [],
                    'url': ev.get('url', target_url or ''),
                    'captured_at': ev.get('captured_at', ''),
                    'analysis_text': st.session_state.analysis.get('recommendation', '') if st.session_state.analysis else '',
                    'affiliate_indicators': ev.get('affiliate_indicators', []),
                    'additional_notes': additional_notes
                }
            }

            # PDF 생성
            output_dir = tempfile.gettempdir()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'뒷광고_신고서_{timestamp}.pdf'
            save_path = os.path.join(output_dir, filename)
            
            try:
                generate_report(report_data, save_path)
                
                # 다운로드 버튼
                with open(save_path, 'rb') as pdf_file:
                    pdf_data = pdf_file.read()
                    
                st.success('✅ PDF 신고서가 생성되었습니다!')
                
                # 파일 정보 표시
                st.markdown(f'**📄 파일명**: {filename}')
                st.markdown(f'**📏 파일크기**: {len(pdf_data):,} bytes')
                
                st.download_button(
                    label='📥 PDF 다운로드',
                    data=pdf_data,
                    file_name=filename,
                    mime='application/pdf',
                    use_container_width=True
                )
                
                # session state에 저장
                st.session_state.report_data = report_data
                
            except Exception as e:
                st.error(f'PDF 생성 중 오류가 발생했습니다: {str(e)}')
                st.error('시스템 폰트 문제일 수 있습니다. 관리자에게 문의해주세요.')

st.markdown('---')

# ═══════════════════════════════════════
# STEP 4: 신고 제출 링크
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 4</span> **신고 제출**', unsafe_allow_html=True)
st.caption('생성된 PDF 파일을 아래 사이트 중 하나에 제출하세요.')

col_a, col_b = st.columns(2)

with col_a:
    st.markdown('**🏛️ 공정거래위원회 신고**')
    st.markdown('''
    - **사이트**: [공정위 신고서식 안내](https://www.ftc.go.kr/www/contents.do?key=656)
    - **장점**: 신고서식 다운로드 + 국민신문고 연동
    - **준비물**: 생성한 PDF + 증거 스크린샷
    - **참고**: 불공정거래신고는 국민신문고를 통해 접수됩니다
    ''')

with col_b:
    st.markdown('**🏛️ 국민신문고 민원신청**')
    st.markdown('''
    - **사이트**: [국민신문고](https://www.epeople.go.kr)
    - **장점**: 처리 과정 추적 가능
    - **기관 선택**: 공정거래위원회
    ''')

# 버튼을 별도 row로 분리하여 항상 같은 높이에 정렬
col_btn_a, col_btn_b = st.columns(2)

with col_btn_a:
    st.link_button(
        '🔗 공정위 신고 안내 바로가기',
        'https://www.ftc.go.kr/www/contents.do?key=656',
        use_container_width=True
    )

with col_btn_b:
    st.link_button(
        '🔗 국민신문고 바로가기',
        'https://www.epeople.go.kr',
        use_container_width=True
    )

# 추가 안내
st.markdown("""
<div class="info-box">
<strong>📋 제출 시 참고사항</strong><br>
• <strong>PDF 신고서</strong>: 방금 생성한 파일을 첨부하세요<br>
• <strong>증거자료</strong>: 스크린샷도 함께 첨부하세요<br>
• <strong>처리기간</strong>: 일반적으로 30일 내외 (사안에 따라 변동)<br>
• <strong>문의전화</strong>: 공정위 상담센터 1670-0007
</div>
""", unsafe_allow_html=True)

# 법적 고지
with st.expander('⚠️ 중요 법적 고지사항'):
    st.markdown("""
    **허위 신고 금지**
    - 고의로 허위 사실을 신고하면 법적 처벌을 받을 수 있습니다.
    - 확실한 증거가 있는 경우에만 신고해주세요.
    
    **개인정보 보호**
    - 입력하신 개인정보는 신고서 생성에만 사용되며 서버에 저장되지 않습니다.
    - 브라우저를 닫으면 모든 정보가 삭제됩니다.
    
    **면책 조항**
    - 이 도구는 신고서 작성을 도와드리는 것이며, 신고 결과에 대한 책임은 신고자에게 있습니다.
    - 법적 조언이 필요한 경우 전문가와 상담하시기 바랍니다.
    """)

# 푸터
st.markdown('---')
st.markdown("""
<div style='text-align: center; color: #6b7280; font-size: 0.9rem;'>
    <p>⚖️ <strong>뒷광고 신고 도우미</strong> — 건전한 디지털 광고 환경 조성을 위해</p>
    <p>HWP 별지 제6호 서식 기반 • PDF 출력 • 공정거래위원회 호환</p>
</div>
""", unsafe_allow_html=True)