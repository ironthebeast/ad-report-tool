"""
자동 제출 모듈
- 국민신문고(epeople.go.kr) 또는 공정위(ftc.go.kr) 브라우저 열기
- 폼 필드 자동 채우기 (로그인은 사용자가 직접)
- 첨부파일 자동 등록
"""
import os
import time
from playwright.sync_api import sync_playwright


def submit_via_epeople(report_data: dict, report_path: str, screenshot_path: str = None):
    """
    국민신문고를 통한 반자동 제출
    - 브라우저를 visible 모드로 열어 사용자가 로그인
    - 로그인 후 민원 작성 폼을 자동으로 채워줌
    """
    violation = report_data.get('violation', {})
    reporter = report_data.get('reporter', {})
    respondent = report_data.get('respondent', {})

    # 민원 내용 텍스트 조합
    content = _build_complaint_text(report_data)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 사용자가 볼 수 있도록 visible
            slow_mo=300,     # 느리게 동작 (사용자가 확인 가능)
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ko-KR',
        )
        page = context.new_page()

        # 1단계: 국민신문고 접속
        print('[1/5] 국민신문고 접속 중...')
        page.goto('https://www.epeople.go.kr/index.jsp', timeout=30000)
        time.sleep(2)

        # 2단계: 사용자에게 로그인 요청
        print('[2/5] 로그인을 완료해주세요. (로그인 후 자동으로 진행됩니다)')
        print('      → 브라우저에서 로그인 버튼을 클릭하고 인증을 완료하세요.')

        # 로그인 대기 (최대 5분)
        _wait_for_user(page, timeout=300)

        # 3단계: 민원신청 페이지로 이동
        print('[3/5] 민원신청 페이지로 이동 중...')
        page.goto('https://www.epeople.go.kr/nep/pttn/gnrlPttn/gnrlPttnSmlrSearch.npaid', timeout=30000)
        time.sleep(3)

        # 4단계: 폼 자동 채우기 시도
        print('[4/5] 민원 내용을 자동으로 입력합니다...')
        _try_fill_epeople_form(page, report_data, content)

        # 5단계: 첨부파일
        print('[5/5] 첨부파일 준비 중...')
        _try_attach_files(page, report_path, screenshot_path)

        print('\n========================================')
        print('✅ 자동 입력이 완료되었습니다.')
        print('   → 내용을 확인하고 [신청] 버튼을 클릭해주세요.')
        print('   → 브라우저를 닫으면 종료됩니다.')
        print('========================================\n')

        # 사용자가 확인하고 제출할 때까지 대기
        try:
            page.wait_for_event('close', timeout=600000)  # 10분 대기
        except Exception:
            pass

        browser.close()


def submit_via_ftc(report_data: dict, report_path: str, screenshot_path: str = None):
    """
    공정거래위원회 직접 신고
    - ftc.go.kr 불공정거래 신고 페이지 열기
    - 폼 자동 채우기
    """
    content = _build_complaint_text(report_data)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            slow_mo=300,
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ko-KR',
        )
        page = context.new_page()

        print('[1/4] 공정거래위원회 신고 페이지 접속 중...')
        page.goto('https://www.ftc.go.kr/www/contents.do?key=998', timeout=30000)
        time.sleep(3)

        print('[2/4] 본인인증을 완료해주세요.')
        print('      → 브라우저에서 인증 절차를 진행하세요.')

        _wait_for_user(page, timeout=300)

        print('[3/4] 민원 내용을 자동으로 입력합니다...')
        _try_fill_ftc_form(page, report_data, content)

        print('[4/4] 첨부파일 준비 중...')
        _try_attach_files(page, report_path, screenshot_path)

        print('\n========================================')
        print('✅ 자동 입력이 완료되었습니다.')
        print('   → 내용을 확인하고 [제출] 버튼을 클릭해주세요.')
        print('========================================\n')

        try:
            page.wait_for_event('close', timeout=600000)
        except Exception:
            pass

        browser.close()


def open_submission_page(method: str, report_data: dict, content_text: str,
                         report_path: str, screenshot_path: str = None):
    """
    Streamlit에서 호출하는 통합 함수.
    브라우저를 열고 신고 페이지로 이동한 뒤,
    사용자가 로그인/인증하면 폼을 자동 채우기.
    """
    if method == 'epeople':
        url = 'https://www.epeople.go.kr/index.jsp'
        label = '국민신문고'
    else:
        url = 'https://www.ftc.go.kr/www/contents.do?key=320'
        label = '공정거래위원회'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 900},
            locale='ko-KR',
        )
        page = context.new_page()
        page.goto(url, timeout=30000)

        # 클립보드에 민원 내용 복사를 위해 텍스트 파일 생성
        txt_path = report_path.replace('.docx', '_content.txt')
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content_text)

        # 새 탭에 도우미 페이지 열기
        helper_html = _create_helper_page(content_text, report_path, screenshot_path, method=method)
        helper_path = report_path.replace('.docx', '_helper.html')
        with open(helper_path, 'w', encoding='utf-8') as f:
            f.write(helper_html)

        helper_page = context.new_page()
        helper_page.goto(f'file://{helper_path}')

        # 원래 페이지로 포커스
        page.bring_to_front()

        print(f'\n✅ {label} 페이지가 열렸습니다.')
        print('   → 도우미 탭에서 내용을 복사하여 붙여넣으세요.')
        print('   → 브라우저를 닫으면 종료됩니다.')

        try:
            page.wait_for_event('close', timeout=600000)
        except Exception:
            pass

        browser.close()

    return True


# ─── 내부 헬퍼 함수 ───

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


def _create_helper_page(content: str, report_path: str, screenshot_path: str = None, method: str = 'epeople') -> str:
    """복사-붙여넣기 도우미 HTML 페이지"""
    import html as html_mod

    escaped_content = html_mod.escape(content)
    files_info = f'<b>신고서:</b> {report_path}'
    if screenshot_path and os.path.exists(screenshot_path):
        files_info += f'<br><b>스크린샷:</b> {screenshot_path}'

    if method == 'ftc':
        step1_title = '공정위 페이지에서 본인인증'
        step1_desc = '옆 탭에서 <b>민원·참여 → 불공정거래신고</b>를 클릭하고 본인인증을 진행하세요.'
        step4_title = '신고유형 확인 → 제출'
        step4_warning = '신고유형에서 <b>"표시광고"</b>를 선택하세요.<br>내용을 최종 확인한 후 [신청] 버튼을 클릭하면 접수 완료됩니다.'
    else:
        step1_title = '국민신문고에서 로그인'
        step1_desc = '옆 탭의 국민신문고에서 로그인 후 <b>민원신청</b>을 클릭하세요.'
        step4_title = '접수기관 선택 → 제출'
        step4_warning = '접수기관을 <b>"공정거래위원회"</b>로 선택하세요.<br>내용을 최종 확인한 후 [신청] 버튼을 클릭하면 접수 완료됩니다.'

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <title>신고 도우미 - 복사하기</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Pretendard', 'Malgun Gothic', sans-serif; background: #f8f9fb; padding: 24px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        h1 {{ font-size: 1.5rem; color: #1a1a2e; margin-bottom: 8px; }}
        .subtitle {{ color: #6b7280; margin-bottom: 24px; }}
        .step {{ background: white; border-radius: 12px; padding: 20px; margin-bottom: 16px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .step-badge {{ background: #2563eb; color: white; padding: 3px 10px; border-radius: 8px;
                      font-size: 0.8rem; font-weight: 600; margin-right: 8px; }}
        .step h3 {{ display: inline; font-size: 1rem; }}
        .content-box {{ background: #f1f5f9; border: 1px solid #e2e8f0; border-radius: 8px;
                       padding: 16px; margin-top: 12px; white-space: pre-wrap; font-size: 0.85rem;
                       line-height: 1.6; max-height: 400px; overflow-y: auto; }}
        .copy-btn {{ background: #2563eb; color: white; border: none; padding: 10px 24px;
                    border-radius: 8px; font-size: 0.9rem; font-weight: 600; cursor: pointer;
                    margin-top: 12px; }}
        .copy-btn:hover {{ background: #1d4ed8; }}
        .copy-btn.copied {{ background: #10b981; }}
        .files {{ background: #dbeafe; border-radius: 8px; padding: 12px 16px; margin-top: 12px;
                 font-size: 0.85rem; }}
        .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 12px 16px;
                   border-radius: 8px; margin-top: 12px; font-size: 0.85rem; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 신고 내용 복사 도우미</h1>
        <p class="subtitle">아래 내용을 복사하여 신고 페이지에 붙여넣으세요.</p>

        <div class="step">
            <span class="step-badge">1</span>
            <h3>{step1_title}</h3>
            <p style="margin-top:8px; color:#6b7280; font-size:0.85rem;">
                {step1_desc}
            </p>
        </div>

        <div class="step">
            <span class="step-badge">2</span>
            <h3>아래 내용을 복사하여 민원 내용란에 붙여넣기</h3>
            <div class="content-box" id="complaint-content">{escaped_content}</div>
            <button class="copy-btn" onclick="copyContent()" id="copy-btn">📋 내용 복사하기</button>
        </div>

        <div class="step">
            <span class="step-badge">3</span>
            <h3>첨부파일 등록</h3>
            <div class="files">
                {files_info}
            </div>
            <p style="margin-top:8px; color:#6b7280; font-size:0.85rem;">
                위 파일들을 신고 페이지의 첨부파일란에 직접 업로드하세요.
            </p>
        </div>

        <div class="step">
            <span class="step-badge">4</span>
            <h3>{step4_title}</h3>
            <div class="warning">
                ⚠️ {step4_warning}
            </div>
        </div>
    </div>

    <script>
        function copyContent() {{
            const text = document.getElementById('complaint-content').innerText;
            navigator.clipboard.writeText(text).then(() => {{
                const btn = document.getElementById('copy-btn');
                btn.textContent = '✅ 복사 완료!';
                btn.classList.add('copied');
                setTimeout(() => {{
                    btn.textContent = '📋 내용 복사하기';
                    btn.classList.remove('copied');
                }}, 2000);
            }});
        }}
    </script>
</body>
</html>"""


def _wait_for_user(page, timeout=300):
    """사용자 로그인 대기"""
    import time
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(3)
        # URL 변경 감지 (로그인 후 리다이렉트)
        current = page.url
        if 'login' not in current.lower() and 'auth' not in current.lower():
            return True
    return False


def _try_fill_epeople_form(page, report_data, content):
    """국민신문고 폼 자동 채우기 시도"""
    try:
        # 텍스트 영역 찾기
        textareas = page.query_selector_all('textarea')
        for ta in textareas:
            ta.fill(content)
    except Exception:
        pass


def _try_fill_ftc_form(page, report_data, content):
    """공정위 폼 자동 채우기 시도"""
    try:
        textareas = page.query_selector_all('textarea')
        for ta in textareas:
            ta.fill(content)
    except Exception:
        pass


def _try_attach_files(page, report_path, screenshot_path):
    """첨부파일 등록 시도"""
    try:
        file_inputs = page.query_selector_all('input[type="file"]')
        if file_inputs and os.path.exists(report_path):
            files = [report_path]
            if screenshot_path and os.path.exists(screenshot_path):
                files.append(screenshot_path)
            file_inputs[0].set_input_files(files)
    except Exception:
        pass
