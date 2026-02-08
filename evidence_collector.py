"""
증거 수집 모듈
- URL에서 스크린샷 캡처
- 페이지 메타데이터 추출
- 콘텐츠 아카이브
"""
import os
import json
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

    except Exception as e:
        result['error'] = str(e)

    # 메타데이터 저장
    meta_file = os.path.join(save_dir, f'metadata_{domain}_{ts}.json')
    with open(meta_file, 'w', encoding='utf-8') as f:
        save_data = {k: v for k, v in result.items() if k != 'page_text'}
        json.dump(save_data, f, ensure_ascii=False, indent=2)

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
        # 표시 위치 확인 필요 (제목/첫부분 vs 글 끝)
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

    return analysis
