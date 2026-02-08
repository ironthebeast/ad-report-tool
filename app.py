"""
뒷광고 신고 도우미
- 위반 콘텐츠 URL 입력 → 자동 증거 수집 → 신고서 자동 생성
"""
import streamlit as st
import subprocess
import sys
import os
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
    """Streamlit Cloud에서 Playwright Chromium 자동 설치"""
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)


install_playwright()

# ── CSS ──
st.markdown("""
<style>
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
    }
    .stButton>button:hover { background: #1d4ed8; }
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
    3. 신고인/피신고인 정보 입력
    4. 신고서 DOCX 다운로드
    5. 아래 중 택1 제출:
       - **공정위 직접** (불공정거래신고)
       - **국민신문고** (민원신청)
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
st.markdown('<p class="main-header">⚖️ 뒷광고 신고 도우미</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">위반 URL만 입력하면 → 증거 수집 → 신고서 자동 작성 → DOCX 다운로드</p>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# STEP 1: 증거 수집
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 1</span> **위반 콘텐츠 URL 입력 & 증거 수집**', unsafe_allow_html=True)

col_url, col_btn = st.columns([4, 1])
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
    with st.spinner('증거를 수집하고 있습니다... (스크린샷 캡처 + 어필리에이트 지표 분석)'):
        try:
            from evidence_collector import capture_screenshot, analyze_violation
            evidence_dir = os.path.join(tempfile.gettempdir(), 'ad_report_evidence')
            evidence = capture_screenshot(target_url, evidence_dir)
            analysis = analyze_violation(evidence)
            st.session_state.evidence = evidence
            st.session_state.analysis = analysis
        except Exception as e:
            st.error(f'증거 수집 중 오류가 발생했습니다: {str(e)}')

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
# STEP 2: 신고 정보 입력
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 2</span> **신고 정보 입력**', unsafe_allow_html=True)
st.caption('(*) 표시는 필수 항목입니다. 나머지는 아는 만큼만 입력하세요.')

tab1, tab2, tab3 = st.tabs(['👤 신고인 정보', '🏢 피신고인 정보', '📝 위반행위 상세'])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        reporter_name = st.text_input('성명 *', key='r_name')
        reporter_birth = st.text_input('생년월일', placeholder='1990-01-01', key='r_birth')
        reporter_phone = st.text_input('전화번호 *', placeholder='010-1234-5678', key='r_phone')
    with col2:
        reporter_address = st.text_input('주소 *', key='r_addr')
        reporter_email = st.text_input('이메일', key='r_email')

with tab2:
    col3, col4 = st.columns(2)
    with col3:
        resp_name = st.text_input('사업자명 / 계정명 *', placeholder='@계정명 또는 상호', key='resp_name')
        resp_rep = st.text_input('대표자 / 운영자', key='resp_rep')
        resp_phone = st.text_input('전화번호', key='resp_phone')
    with col4:
        resp_address = st.text_input('주소 / 소재지', key='resp_addr')
        resp_website = st.text_input('웹사이트 / SNS URL *', value=target_url or '', key='resp_web')

with tab3:
    violation_type = st.selectbox(
        '위반 유형 *',
        [
            '경제적 이해관계 미표시 (뒷광고)',
            '경제적 이해관계 표시 위치 부적절 (하단/더보기 뒤에 표시)',
            '허위·과장 광고 (사실과 다른 내용)',
            '기만적 광고 (소비자를 오인시키는 표현)',
            '부당한 비교 광고',
            '기타',
        ]
    )
    violation_media = st.selectbox(
        '광고 매체 *',
        ['인스타그램', '유튜브', '블로그 (네이버)', '블로그 (기타)', '트위터/X',
         '페이스북', '틱톡', '카페/커뮤니티', '기타 웹사이트']
    )
    violation_date = st.date_input('광고 게시 일자 (추정)', value=date.today())
    violation_url = st.text_input('위반 콘텐츠 URL *', value=target_url or '', key='v_url')

    # 자동 생성된 설명 + 사용자 편집
    auto_desc = ''
    if st.session_state.analysis and st.session_state.analysis.get('recommendation'):
        auto_desc = st.session_state.analysis['recommendation']
    if st.session_state.evidence and st.session_state.evidence.get('affiliate_indicators'):
        indicators = '\n'.join(f'- {i}' for i in st.session_state.evidence['affiliate_indicators'])
        auto_desc += f'\n\n[자동 탐지 결과]\n{indicators}'

    violation_desc = st.text_area(
        '위반행위 상세 설명 *',
        value=auto_desc,
        height=200,
        help='자동 분석 결과가 미리 채워집니다. 직접 수정/추가할 수 있습니다.'
    )

    additional_notes = st.text_area(
        '추가 참고사항 (선택)',
        placeholder='추가로 알리고 싶은 내용이 있으면 입력하세요.',
        height=100,
    )

st.markdown('---')

# ═══════════════════════════════════════
# STEP 3: 신고서 생성 & 다운로드
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 3</span> **신고서 생성 & 다운로드**', unsafe_allow_html=True)

# 법적 근거 매핑
legal_basis_map = {
    '경제적 이해관계 미표시 (뒷광고)': '표시·광고의 공정화에 관한 법률 제3조 제1항 제1호 (거짓·과장의 표시광고) 및 추천·보증 등에 관한 표시·광고 심사지침 위반',
    '경제적 이해관계 표시 위치 부적절 (하단/더보기 뒤에 표시)': '추천·보증 등에 관한 표시·광고 심사지침 제7조 (경제적 이해관계 등의 표시 기준) 위반',
    '허위·과장 광고 (사실과 다른 내용)': '표시·광고의 공정화에 관한 법률 제3조 제1항 제1호 (거짓·과장의 표시광고)',
    '기만적 광고 (소비자를 오인시키는 표현)': '표시·광고의 공정화에 관한 법률 제3조 제1항 제2호 (기만적인 표시광고)',
    '부당한 비교 광고': '표시·광고의 공정화에 관한 법률 제3조 제1항 제3호 (부당하게 비교하는 표시광고)',
    '기타': '표시·광고의 공정화에 관한 법률 제3조',
}

generate_btn = st.button('📄 신고서 생성 (DOCX)', type='primary', use_container_width=True)

if generate_btn:
    # 필수 항목 검증
    missing = []
    if not reporter_name: missing.append('신고인 성명')
    if not reporter_phone: missing.append('신고인 전화번호')
    if not reporter_address: missing.append('신고인 주소')
    if not resp_name: missing.append('피신고인 사업자명/계정명')
    if not violation_url: missing.append('위반 콘텐츠 URL')
    if not violation_desc: missing.append('위반행위 상세 설명')

    if missing:
        st.error(f'필수 항목을 입력해주세요: {", ".join(missing)}')
    else:
        with st.spinner('신고서를 생성하고 있습니다...'):
            from report_generator import generate_report

            ev = st.session_state.evidence or {}
            # 수동 스크린샷이 있으면 첫 번째를 대표로 사용
            screenshot = ev.get('screenshot_path')
            manual_shots = st.session_state.get('manual_screenshots', [])
            all_screenshots = []
            if screenshot and os.path.exists(screenshot):
                all_screenshots.append(screenshot)
            all_screenshots.extend(manual_shots)

            report_data = {
                'reporter': {
                    'name': reporter_name,
                    'birth_date': reporter_birth,
                    'address': reporter_address,
                    'phone': reporter_phone,
                    'email': reporter_email,
                },
                'respondent': {
                    'business_name': resp_name,
                    'representative': resp_rep,
                    'address': resp_address,
                    'phone': resp_phone,
                    'website': resp_website,
                },
                'violation': {
                    'type': violation_type,
                    'media': violation_media,
                    'date': violation_date.strftime('%Y-%m-%d'),
                    'url': violation_url,
                    'description': violation_desc,
                    'legal_basis': legal_basis_map.get(violation_type, ''),
                },
                'evidence': {
                    'screenshot_path': all_screenshots[0] if all_screenshots else None,
                    'extra_screenshots': all_screenshots[1:] if len(all_screenshots) > 1 else [],
                    'url': ev.get('url', violation_url),
                    'captured_at': ev.get('captured_at', ''),
                    'analysis_text': st.session_state.analysis.get('recommendation', '') if st.session_state.analysis else '',
                    'affiliate_indicators': ev.get('affiliate_indicators', []),
                    'additional_notes': additional_notes,
                },
            }

            # session에 저장 (바로 제출 시 재사용)
            st.session_state.report_data = report_data
            st.session_state.all_screenshots = all_screenshots

            # 파일 생성
            output_dir = os.path.join(tempfile.gettempdir(), 'ad_report_output')
            os.makedirs(output_dir, exist_ok=True)
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_path = os.path.join(output_dir, f'신고서_{ts}.docx')

            try:
                generate_report(report_data, output_path)

                st.markdown('<div class="success-box">✅ <b>신고서가 생성되었습니다!</b></div>', unsafe_allow_html=True)

                # 다운로드 버튼
                with open(output_path, 'rb') as f:
                    st.download_button(
                        label='📥 신고서 다운로드 (DOCX)',
                        data=f.read(),
                        file_name=f'부당표시광고_신고서_{ts}.docx',
                        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        type='primary',
                    )

                # 스크린샷도 별도 다운로드
                if ev.get('screenshot_path') and os.path.exists(ev['screenshot_path']):
                    with open(ev['screenshot_path'], 'rb') as f:
                        st.download_button(
                            label='📥 증거 스크린샷 다운로드 (PNG)',
                            data=f.read(),
                            file_name=f'증거_스크린샷_{ts}.png',
                            mime='image/png',
                        )

                # 제출 안내
                st.markdown('---')
                st.markdown('### 📮 제출 방법')
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.markdown("""
                    **방법 1: 공정위 직접 신고 (추천)**
                    1. [ftc.go.kr](https://www.ftc.go.kr) 접속
                    2. **민원·참여 → 불공정거래신고**
                    3. 본인인증 → 기본정보 작성
                    4. 신고내용 + 증빙자료 첨부
                    5. 신청 완료
                    """)
                with col_s2:
                    st.markdown("""
                    **방법 2: 국민신문고 (민원신청)**
                    1. [epeople.go.kr](https://www.epeople.go.kr) 접속
                    2. 로그인 → **민원신청**
                    3. 접수기관: **"공정거래위원회"** 선택
                    4. 신고서(DOCX) + 스크린샷 첨부
                    5. 접수번호로 진행상황 추적 가능
                    """)
                with col_s3:
                    st.markdown("""
                    **방법 3: 전화/우편**
                    - 공정위 상담: **1670-0007**
                    - 소비자24: **1372**
                    - 우편: 관할 지방공정거래사무소
                    """)

            except Exception as e:
                st.error(f'신고서 생성 중 오류: {str(e)}')

# ═══════════════════════════════════════
# STEP 4: 신고 제출 (링크 + 복사)
# ═══════════════════════════════════════
st.markdown('<span class="step-badge">STEP 4</span> **신고 제출**', unsafe_allow_html=True)
st.caption('아래 민원 내용을 복사한 뒤, 링크를 클릭하여 제출 사이트에서 붙여넣기하세요.')


def _build_complaint_text(report_data: dict) -> str:
    """민원 내용 텍스트 생성"""
    v = report_data.get('violation', {})
    r = report_data.get('respondent', {})
    e = report_data.get('evidence', {})

    lines = [
        '[ 부당한 표시·광고 신고 ]',
        '',
        f'■ 피신고인: {r.get("business_name", "")}',
        f'■ 피신고인 웹사이트/SNS: {r.get("website", "")}',
        '',
        f'■ 위반 유형: {v.get("type", "")}',
        f'■ 광고 매체: {v.get("media", "")}',
        f'■ 광고 일자: {v.get("date", "")}',
        f'■ 광고 URL: {v.get("url", "")}',
        '',
        f'■ 관련 법률: {v.get("legal_basis", "")}',
        '',
        '■ 위반행위 상세:',
        v.get('description', ''),
        '',
    ]

    indicators = e.get('affiliate_indicators', [])
    if indicators:
        lines.append('■ 자동 탐지된 어필리에이트 지표:')
        for ind in indicators:
            lines.append(f'  - {ind}')
        lines.append('')

    analysis = e.get('analysis_text', '')
    if analysis:
        lines.append(f'■ AI 분석 결과: {analysis}')
        lines.append('')

    notes = e.get('additional_notes', '')
    if notes:
        lines.append(f'■ 추가 참고사항: {notes}')
        lines.append('')

    lines.append('※ 상세 신고서(DOCX)와 증거 스크린샷을 첨부파일로 함께 제출합니다.')
    lines.append('※ 본 신고 내용은 「표시·광고의 공정화에 관한 법률」에 근거합니다.')

    return '\n'.join(lines)


# 민원 텍스트 미리보기 (report_data가 있으면)
if st.session_state.get('report_data'):
    complaint_text = _build_complaint_text(st.session_state.report_data)
    st.text_area('민원 내용 (복사해서 사용)', value=complaint_text, height=200)

col1, col2 = st.columns(2)
with col1:
    st.link_button('🔗 공정위 불공정거래신고 →', 'https://www.ftc.go.kr/www/contents.do?key=320')
    st.caption('민원·참여 → 불공정거래신고 → 표시광고 선택')
with col2:
    st.link_button('🔗 국민신문고 민원신청 →', 'https://www.epeople.go.kr')
    st.caption('민원신청 → 접수기관: 공정거래위원회 선택')

# ── 하단 정보 ──
st.markdown('---')
st.info('🔒 이 도구는 데이터를 저장하지 않습니다. 입력한 정보는 세션 종료 시 자동 삭제됩니다.')
st.caption('이 도구는 표시·광고의 공정화에 관한 법률에 따른 신고를 돕기 위한 보조 도구입니다. 법률 상담이 필요한 경우 전문가와 상의하세요.')
st.caption('생성된 신고서는 DOCX 형식으로, 한글(HWP) 및 MS Word에서 열어 수정할 수 있습니다.')
