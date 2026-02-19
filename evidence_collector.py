"""
증거 수집 모듈
- URL에서 스크린샷 캡처
- 페이지 메타데이터 추출
- 이미지/스티커 내 광고 표시 감지 (Gemini Vision)
- 콘텐츠 아카이브
"""
import os
import json
import base64
from datetime import datetime
from urllib.parse import urlparse

def capture_screenshot(url: str, save_dir: str) -> dict:
    """Playwright로 URL 스크린샷 + 메타데이터 수집"""
    from playwright.sync_api import sync_playwright

    result = {
        'url': url,
        'captured_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'screenshot_path': None,
        'page_title': '',
        'page_text': '',
        'meta_description': '',
        'author': '',
        'has_ad_disclosure': False,
        'affiliate_indicators': [],
        'error': None,
    }

    os.makedirs(save_dir, exist_ok=True)
    domain = urlparse(url).netloc.replace('.', '_')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    screenshot_file = os.path.join(save_dir, f'evidence_{domain}_{ts}.png')

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 900},
                locale='ko-KR',
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()
            page.goto(url, timeout=30000, wait_until='networkidle')
            page.wait_for_timeout(2000)

            # 풀페이지 스크린샷
            page.screenshot(path=screenshot_file, full_page=True)
            result['screenshot_path'] = screenshot_file

            # 페이지 제목
            result['page_title'] = page.title()

            # 메타 정보
            meta_desc = page.query_selector('meta[name="description"]')
            if meta_desc:
                result['meta_description'] = meta_desc.get_attribute('content') or ''

            author = page.query_selector('meta[name="author"]')
            if author:
                result['author'] = author.get_attribute('content') or ''

            # 페이지 텍스트 (본문만)
            body_text = page.evaluate('() => document.body?.innerText?.substring(0, 5000) || ""')
            result['page_text'] = body_text

            # 광고 표시 여부 검사
            ad_keywords = ['#광고', '#ad', '광고포함', '협찬', '유료광고', '경제적 대가',
                          '소정의 원고료', '대가를 받', '협찬을 받', '#sponsored',
                          '광고 포함', '파트너십', '제휴 링크']
            text_lower = body_text.lower()
            for kw in ad_keywords:
                if kw.lower() in text_lower:
                    result['has_ad_disclosure'] = True
                    break

            # 어필리에이트 지표 탐지
            aff_indicators = []
            # 링크에 어필리에이트 파라미터 확인
            links = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => /ref=|affiliate|aff_id|utm_|click_id|partner|tracking/i.test(h))
                    .slice(0, 10);
            }''')
            if links:
                aff_indicators.append(f'어필리에이트 링크 {len(links)}개 발견')

            # 할인 코드 패턴
            discount_patterns = page.evaluate('''() => {
                const text = document.body.innerText;
                const patterns = text.match(/할인\\s*코드[:\\s]*[A-Za-z0-9]+|쿠폰\\s*코드[:\\s]*[A-Za-z0-9]+|discount\\s*code[:\\s]*[A-Za-z0-9]+/gi);
                return patterns ? patterns.slice(0, 5) : [];
            }''')
            if discount_patterns:
                aff_indicators.append(f'할인/쿠폰 코드 발견: {", ".join(discount_patterns[:3])}')

            # 구매 링크
            buy_links = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('a'))
                    .filter(a => /구매|buy|shop|purchase|주문/i.test(a.innerText))
                    .map(a => ({text: a.innerText.trim().substring(0, 50), href: a.href}))
                    .slice(0, 5);
            }''')
            if buy_links:
                aff_indicators.append(f'구매 유도 링크 {len(buy_links)}개 발견')

            result['affiliate_indicators'] = aff_indicators

            browser.close()

    # 이미지/스티커 내 광고 표시 분석 (Gemini Vision)
    if result.get('screenshot_path') and not result.get('error'):
        try:
            image_analysis = analyze_image_for_ad_disclosure(result['screenshot_path'])
            result['image_analysis'] = image_analysis

            # 이미지에서 광고 표시가 발견되면 has_ad_disclosure 업데이트
            if image_analysis.get('image_has_disclosure'):
                result['has_ad_disclosure'] = True
                result['ad_disclosure_source'] = 'image'  # 이미지/스티커에서 발견
                if image_analysis.get('image_disclosure_details'):
                    result['image_disclosure_details'] = image_analysis['image_disclosure_details']
            elif result['has_ad_disclosure']:
                result['ad_disclosure_source'] = 'text'  # 텍스트에서 발견
        except Exception as e:
            result['image_analysis'] = {'error': str(e), 'image_analysis_done': False}

    except Exception as e:
        result['error'] = str(e)

    # 메타데이터 저장
    meta_file = os.path.join(save_dir, f'metadata_{domain}_{ts}.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        save_data = {k: v for k, v in result.items() if k != 'page_text'}
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    return result


def analyze_image_for_ad_disclosure(screenshot_path: str) -> dict:
    """Gemini Vision으로 스크린샷 내 이미지/스티커 형태의 광고 표시 감지"""
    result = {
        'image_has_disclosure': False,
        'image_disclosure_details': [],
        'image_analysis_done': False,
        'error': None,
    }

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        result['error'] = 'GEMINI_API_KEY 미설정 — 이미지 분석 건너뜀'
        return result

    if not screenshot_path or not os.path.exists(screenshot_path):
        result['error'] = '스크린샷 파일 없음'
        return result

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # 이미지 읽기
        with open(screenshot_path, 'rb') as f:
            image_data = f.read()

        image_part = {
            'mime_type': 'image/png',
            'data': base64.b64encode(image_data).decode('utf-8')
        }

        prompt = """이 웹페이지 스크린샷을 분석하여 **광고/협찬 표시**가 있는지 확인해주세요.

특히 다음을 집중적으로 확인하세요:
1. **스티커 형태의 광고 표시** (예: "광고", "협찬", "AD", "Sponsored" 등이 적힌 이미지 스티커)
2. **배너/이미지 안에 포함된 광고 문구** (텍스트가 아닌 이미지로 삽입된 경우)
3. **블로그 상단/하단의 광고 표시 이미지**
4. **워터마크나 오버레이 형태의 표시**
5. **"소정의 원고료", "대가를 받고", "경제적 대가" 등의 문구가 이미지에 포함된 경우**

반드시 아래 JSON 형식으로만 응답하세요:
{
  "found": true/false,
  "disclosures": [
    {
      "type": "스티커|배너|텍스트이미지|워터마크|기타",
      "content": "발견된 광고 표시 내용",
      "location": "상단|중간|하단|사이드바",
      "visibility": "명확|작음|불분명"
    }
  ],
  "confidence": "높음|중간|낮음"
}"""

        response = model.generate_content([prompt, image_part])
        response_text = response.text.strip()

        # JSON 파싱
        response_text = response_text.replace('```json', '').replace('```', '').strip()
        analysis = json.loads(response_text)

        result['image_analysis_done'] = True
        result['image_has_disclosure'] = analysis.get('found', False)

        if analysis.get('disclosures'):
            for d in analysis['disclosures']:
                detail = f"[{d.get('type', '기타')}] {d.get('content', '')} (위치: {d.get('location', '미상')}, 가시성: {d.get('visibility', '미상')})"
                result['image_disclosure_details'].append(detail)

        result['confidence'] = analysis.get('confidence', '미상')

    except json.JSONDecodeError:
        result['error'] = 'Gemini 응답 파싱 실패'
        result['image_analysis_done'] = True
    except ImportError:
        # google-generativeai 미설치 시 REST API fallback
        try:
            import urllib.request
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

            with open(screenshot_path, 'rb') as f:
                img_b64 = base64.b64encode(f.read()).decode('utf-8')

            payload = json.dumps({
                "contents": [{
                    "parts": [
                        {"text": "이 웹페이지 스크린샷에서 광고/협찬 표시(스티커, 이미지, 배너 포함)가 있는지 확인해주세요. found(boolean)와 disclosures(배열)를 JSON으로 응답. disclosures 항목: type, content, location, visibility"},
                        {"inline_data": {"mime_type": "image/png", "data": img_b64}}
                    ]
                }]
            }).encode('utf-8')

            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                api_result = json.loads(resp.read().decode('utf-8'))
                text = api_result['candidates'][0]['content']['parts'][0]['text']
                text = text.replace('```json', '').replace('```', '').strip()
                analysis = json.loads(text)

                result['image_analysis_done'] = True
                result['image_has_disclosure'] = analysis.get('found', False)
                if analysis.get('disclosures'):
                    for d in analysis['disclosures']:
                        detail = f"[{d.get('type', '기타')}] {d.get('content', '')} (위치: {d.get('location', '미상')})"
                        result['image_disclosure_details'].append(detail)
        except Exception as e2:
            result['error'] = f'REST API fallback 실패: {str(e2)}'
    except Exception as e:
        result['error'] = f'이미지 분석 실패: {str(e)}'

    return result


def analyze_violation(evidence: dict) -> dict:
    """수집된 증거를 분석하여 위반 유형 판단"""
    analysis = {
        'violation_detected': False,
        'violation_types': [],
        'severity': '미확인',
        'recommendation': '',
    }

    has_affiliate = len(evidence.get('affiliate_indicators', [])) > 0
    has_disclosure = evidence.get('has_ad_disclosure', False)

    # 이미지 분석 결과 가져오기
    image_analysis = evidence.get('image_analysis', {})
    image_has_disclosure = image_analysis.get('image_has_disclosure', False)
    disclosure_source = evidence.get('ad_disclosure_source', '')
    image_details = evidence.get('image_disclosure_details', [])

    if has_affiliate and not has_disclosure:
        analysis['violation_detected'] = True
        analysis['violation_types'].append('경제적 이해관계 미표시 (추천·보증 심사지침 위반)')
        analysis['severity'] = '높음'
        analysis['recommendation'] = (
            '어필리에이트 링크/할인코드가 포함되어 있으나 '
            '"#광고", "#협찬" 등 경제적 이해관계 표시가 발견되지 않았습니다. '
            '표시·광고의 공정화에 관한 법률 제3조 위반 가능성이 있습니다.'
        )
    elif has_affiliate and has_disclosure:
        # 이미지/스티커에서만 광고 표시가 발견된 경우
        if disclosure_source == 'image' and image_details:
            analysis['disclosure_method'] = 'image'
            analysis['image_disclosure_details'] = image_details

            # 이미지/스티커 표시의 가시성 확인
            img_confidence = image_analysis.get('confidence', '미상')
            if img_confidence == '낮음':
                analysis['violation_detected'] = True
                analysis['violation_types'].append('경제적 이해관계 표시 불명확 (이미지/스티커 가시성 부족)')
                analysis['severity'] = '중간'
                analysis['recommendation'] = (
                    f'이미지/스티커 형태의 광고 표시가 발견되었으나 가시성이 낮습니다.\n'
                    f'발견된 표시: {"; ".join(image_details[:3])}\n'
                    '2024년 개정 심사지침에 따르면 소비자가 쉽게 인식할 수 있도록 '
                    '명확하게 표시해야 합니다.'
                )
            else:
                analysis['severity'] = '낮음'
                analysis['recommendation'] = (
                    f'이미지/스티커 형태로 광고 표시가 확인되었습니다.\n'
                    f'발견된 표시: {"; ".join(image_details[:3])}\n'
                    '다만 텍스트가 아닌 이미지 형태이므로 가시성이 충분한지 추가 확인을 권장합니다.'
                )
        else:
            # 텍스트에서 발견된 경우 — 기존 로직
            text = evidence.get('page_text', '')
            first_500 = text[:500].lower()
            ad_in_first = any(kw.lower() in first_500 for kw in ['#광고', '#ad', '협찬', '유료광고'])
            if not ad_in_first:
                analysis['violation_detected'] = True
                analysis['violation_types'].append('경제적 이해관계 표시 위치 부적절 (게시물 첫부분 미표시)')
                analysis['severity'] = '중간'
                analysis['recommendation'] = (
                    '광고 표시가 있으나 게시물 첫부분이 아닌 하단에 위치합니다. '
                    '2024년 개정 심사지침에 따르면 제목 또는 첫부분에 표시해야 합니다.'
                )
            else:
                analysis['severity'] = '없음'
                analysis['recommendation'] = '적절한 광고 표시가 확인되었습니다.'
    elif not has_affiliate:
        analysis['severity'] = '수동확인 필요'
        analysis['recommendation'] = (
            '자동 탐지로는 어필리에이트 지표를 발견하지 못했습니다. '
            '직접 콘텐츠를 확인하여 경제적 이해관계 여부를 판단해주세요.'
        )

    # 이미지 분석 메타 추가
    if image_analysis.get('image_analysis_done'):
        analysis['image_analysis_performed'] = True
        analysis['image_disclosure_found'] = image_has_disclosure
        if image_details:
            analysis['image_disclosure_details'] = image_details
    elif image_analysis.get('error'):
        analysis['image_analysis_performed'] = False
        analysis['image_analysis_note'] = image_analysis['error']

    return analysis
