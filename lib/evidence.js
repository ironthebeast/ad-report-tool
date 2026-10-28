/**
 * 증거 수집 모듈 (evidence_collector.py 이식)
 * - URL에서 스크린샷 캡처 (Vercel: @sparticuz/chromium, 로컬: 설치된 Chrome)
 * - 페이지 메타데이터 추출
 * - 이미지/스티커 내 광고 표시 감지 (Gemini Vision)
 */
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const KOREAN_FONT = join(ROOT, 'fonts', 'NanumGothic-Regular.ttf');

const AD_KEYWORDS = [
  '#광고', '#ad', '광고포함', '협찬', '유료광고', '경제적 대가',
  '소정의 원고료', '대가를 받', '협찬을 받', '#sponsored',
  '광고 포함', '파트너십', '제휴 링크',
  // 네이버 블로그 / 크리에이터 어필리에이트 표시
  '수익이 발생', '수수료가 지급', '수수료를 지급',
  '크리에이터 활동을 통해', '링크가 포함',
  '대가성', '원고료를 받', '무상으로 제공',
  '제품을 제공', '서비스를 제공받', '물품을 제공',
  // 추가 일반 패턴
  '이 포스팅은 광고', '이 글은 광고', '광고입니다',
  '#유료', 'paid partnership', '#partnership',
  '쿠팡 파트너스', '수익을 얻', '수익이 창출',
  '활동의 일환', '일정액의 수수료', '소정의 수수료',
];

const FIRST_PART_KEYWORDS = [
  '#광고', '#ad', '협찬', '유료광고',
  '수익이 발생', '수수료가 지급', '크리에이터 활동',
  '링크가 포함', '광고입니다', '대가성',
  '일정액의 수수료', '소정의 수수료',
];

function nowString() {
  // 한국 시간 기준 'YYYY-MM-DD HH:MM:SS'
  return new Date().toLocaleString('sv-SE', { timeZone: 'Asia/Seoul' });
}

async function launchBrowser() {
  const puppeteer = (await import('puppeteer-core')).default;

  if (process.env.VERCEL) {
    const chromium = (await import('@sparticuz/chromium')).default;
    const executablePath = await chromium.executablePath();
    // 서버리스 Chromium에는 한글 폰트가 없어 스크린샷이 깨짐 → /tmp/fonts에 복사
    const fontDir = join(tmpdir(), 'fonts');
    mkdirSync(fontDir, { recursive: true });
    const target = join(fontDir, 'NanumGothic-Regular.ttf');
    if (!existsSync(target) && existsSync(KOREAN_FONT)) copyFileSync(KOREAN_FONT, target);

    return puppeteer.launch({
      executablePath,
      args: chromium.args,
      headless: true,
    });
  }

  return puppeteer.launch({
    executablePath: process.env.CHROME_PATH
      || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });
}

/** URL 스크린샷 + 메타데이터 수집 */
export async function captureScreenshot(url) {
  const result = {
    url,
    captured_at: nowString(),
    screenshot: null, // data:image/jpeg;base64,...
    page_title: '',
    page_text: '',
    meta_description: '',
    author: '',
    has_ad_disclosure: false,
    affiliate_indicators: [],
    error: null,
  };

  let browser = null;
  try {
    browser = await launchBrowser();
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    );
    await page.setExtraHTTPHeaders({ 'Accept-Language': 'ko-KR,ko;q=0.9' });
    page.setDefaultTimeout(20000);

    // networkidle 대신 domcontentloaded — SPA(인스타/유튜브)에서 타임아웃 방지
    try {
      await page.goto(url, { timeout: 20000, waitUntil: 'domcontentloaded' });
    } catch {
      // 타임아웃이어도 이미 로드된 내용으로 진행
    }

    // 동적 콘텐츠 안정화 대기
    await new Promise((r) => setTimeout(r, 2000));

    // ── 스크린샷 캡처 (상단 1800px, JPEG로 용량 절약) ──
    try {
      const buf = await page.screenshot({
        type: 'jpeg',
        quality: 80,
        clip: { x: 0, y: 0, width: 1280, height: 1800 },
        captureBeyondViewport: true,
      });
      result.screenshot = `data:image/jpeg;base64,${Buffer.from(buf).toString('base64')}`;
    } catch (e) {
      result.error = `스크린샷 실패: ${e.message}`;
    }

    // ── 메타데이터 ──
    try { result.page_title = await page.title(); } catch { /* ignore */ }
    try {
      const meta = await page.evaluate(() => ({
        description: document.querySelector('meta[name="description"]')?.getAttribute('content') || '',
        author: document.querySelector('meta[name="author"]')?.getAttribute('content') || '',
      }));
      result.meta_description = meta.description;
      result.author = meta.author;
    } catch { /* ignore */ }

    // ── 페이지 텍스트 ──
    let bodyText = '';
    try {
      bodyText = await page.evaluate(() => document.body?.innerText?.substring(0, 5000) || '');
    } catch { /* ignore */ }
    result.page_text = bodyText;

    // ── 광고 표시 키워드 검사 ──
    const textLower = bodyText.toLowerCase();
    result.has_ad_disclosure = AD_KEYWORDS.some((kw) => textLower.includes(kw.toLowerCase()));

    // ── 어필리에이트 지표 탐지 ──
    const aff = [];
    try {
      const links = await page.evaluate(() => Array.from(document.querySelectorAll('a[href]'))
        .map((a) => a.href)
        .filter((h) => /ref=|affiliate|aff_id|utm_|click_id|partner|tracking/i.test(h))
        .slice(0, 10));
      if (links.length) aff.push(`어필리에이트 링크 ${links.length}개 발견`);
    } catch { /* ignore */ }

    try {
      const codes = await page.evaluate(() => {
        const text = document.body.innerText;
        const m = text.match(/할인\s*코드[:\s]*[A-Za-z0-9]+|쿠폰\s*코드[:\s]*[A-Za-z0-9]+|discount\s*code[:\s]*[A-Za-z0-9]+/gi);
        return m ? m.slice(0, 5) : [];
      });
      if (codes.length) aff.push(`할인/쿠폰 코드 발견: ${codes.slice(0, 3).join(', ')}`);
    } catch { /* ignore */ }

    try {
      const buyLinks = await page.evaluate(() => Array.from(document.querySelectorAll('a'))
        .filter((a) => /구매|buy|shop|purchase|주문/i.test(a.innerText))
        .slice(0, 5).length);
      if (buyLinks) aff.push(`구매 유도 링크 ${buyLinks}개 발견`);
    } catch { /* ignore */ }

    result.affiliate_indicators = aff;
  } catch (e) {
    result.error = e.message;
  } finally {
    if (browser) {
      try { await browser.close(); } catch { /* ignore */ }
    }
  }

  // 이미지/스티커 내 광고 표시 분석 (Gemini Vision)
  if (result.screenshot && !result.error) {
    try {
      const ia = await analyzeImageForAdDisclosure(result.screenshot);
      result.image_analysis = ia;
      if (ia.image_has_disclosure) {
        result.has_ad_disclosure = true;
        result.ad_disclosure_source = 'image';
        if (ia.image_disclosure_details.length) result.image_disclosure_details = ia.image_disclosure_details;
      } else if (result.has_ad_disclosure) {
        result.ad_disclosure_source = 'text';
      }
    } catch (e) {
      result.image_analysis = { error: e.message, image_analysis_done: false };
    }
  }

  return result;
}

/** Gemini Vision으로 스크린샷 내 이미지/스티커 형태의 광고 표시 감지 */
export async function analyzeImageForAdDisclosure(dataUrl) {
  const result = {
    image_has_disclosure: false,
    image_disclosure_details: [],
    image_analysis_done: false,
    error: null,
  };

  const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    result.error = 'GEMINI_API_KEY 미설정 — 이미지 분석 건너뜀';
    return result;
  }

  const [, mimeType, data] = dataUrl.match(/^data:([^;]+);base64,(.*)$/) || [];
  if (!data) {
    result.error = '스크린샷 파일 없음';
    return result;
  }

  const prompt = `이 웹페이지 스크린샷을 분석하여 **광고/협찬 표시**가 있는지 확인해주세요.

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
}`;

  try {
    const res = await fetch(
      'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-goog-api-key': apiKey },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }, { inline_data: { mime_type: mimeType, data } }] }],
          generationConfig: { maxOutputTokens: 1024, responseMimeType: 'application/json' },
        }),
        signal: AbortSignal.timeout(30000),
      },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    const text = (json.candidates?.[0]?.content?.parts?.[0]?.text || '')
      .replace(/```json/g, '').replace(/```/g, '').trim();

    let analysis;
    try {
      analysis = JSON.parse(text);
    } catch {
      result.error = 'Gemini 응답 파싱 실패';
      result.image_analysis_done = true;
      return result;
    }

    result.image_analysis_done = true;
    result.image_has_disclosure = Boolean(analysis.found);
    for (const d of analysis.disclosures || []) {
      result.image_disclosure_details.push(
        `[${d.type || '기타'}] ${d.content || ''} (위치: ${d.location || '미상'}, 가시성: ${d.visibility || '미상'})`,
      );
    }
    result.confidence = analysis.confidence || '미상';
  } catch (e) {
    result.error = `이미지 분석 실패: ${e.message}`;
  }
  return result;
}

/** 수집된 증거를 분석하여 위반 유형 판단 */
export function analyzeViolation(evidence) {
  const analysis = {
    violation_detected: false,
    violation_types: [],
    severity: '미확인',
    recommendation: '',
  };

  let hasAffiliate = (evidence.affiliate_indicators || []).length > 0;
  const hasDisclosure = Boolean(evidence.has_ad_disclosure);

  const imageAnalysis = evidence.image_analysis || {};
  const imageHasDisclosure = Boolean(imageAnalysis.image_has_disclosure);
  const disclosureSource = evidence.ad_disclosure_source || '';
  const imageDetails = evidence.image_disclosure_details || [];

  // 광고 표시 텍스트 자체가 경제적 이해관계의 증거 → 어필리에이트로 간주
  if (hasDisclosure && !hasAffiliate) hasAffiliate = true;

  if (hasAffiliate && !hasDisclosure) {
    analysis.violation_detected = true;
    analysis.violation_types.push('경제적 이해관계 미표시 (추천·보증 심사지침 위반)');
    analysis.severity = '높음';
    analysis.recommendation = '어필리에이트 링크/할인코드가 포함되어 있으나 '
      + '"#광고", "#협찬" 등 경제적 이해관계 표시가 발견되지 않았습니다. '
      + '표시·광고의 공정화에 관한 법률 제3조 위반 가능성이 있습니다.';
  } else if (hasAffiliate && hasDisclosure) {
    if (disclosureSource === 'image' && imageDetails.length) {
      analysis.disclosure_method = 'image';
      analysis.image_disclosure_details = imageDetails;
      const found = imageDetails.slice(0, 3).join('; ');
      if (imageAnalysis.confidence === '낮음') {
        analysis.violation_detected = true;
        analysis.violation_types.push('경제적 이해관계 표시 불명확 (이미지/스티커 가시성 부족)');
        analysis.severity = '중간';
        analysis.recommendation = '이미지/스티커 형태의 광고 표시가 발견되었으나 가시성이 낮습니다.\n'
          + `발견된 표시: ${found}\n`
          + '2024년 개정 심사지침에 따르면 소비자가 쉽게 인식할 수 있도록 명확하게 표시해야 합니다.';
      } else {
        analysis.severity = '낮음';
        analysis.recommendation = '이미지/스티커 형태로 광고 표시가 확인되었습니다.\n'
          + `발견된 표시: ${found}\n`
          + '다만 텍스트가 아닌 이미지 형태이므로 가시성이 충분한지 추가 확인을 권장합니다.';
      }
    } else {
      const first500 = (evidence.page_text || '').slice(0, 500).toLowerCase();
      const adInFirst = FIRST_PART_KEYWORDS.some((kw) => first500.includes(kw.toLowerCase()));
      if (!adInFirst) {
        analysis.violation_detected = true;
        analysis.violation_types.push('경제적 이해관계 표시 위치 부적절 (게시물 첫부분 미표시)');
        analysis.severity = '중간';
        analysis.recommendation = '광고 표시가 있으나 게시물 첫부분이 아닌 하단에 위치합니다. '
          + '2024년 개정 심사지침에 따르면 제목 또는 첫부분에 표시해야 합니다.';
      } else {
        analysis.severity = '없음';
        analysis.recommendation = '적절한 광고 표시가 확인되었습니다.';
      }
    }
  } else {
    analysis.severity = '수동확인 필요';
    analysis.recommendation = '자동 탐지로는 어필리에이트 지표를 발견하지 못했습니다. '
      + '직접 콘텐츠를 확인하여 경제적 이해관계 여부를 판단해주세요.';
  }

  if (imageAnalysis.image_analysis_done) {
    analysis.image_analysis_performed = true;
    analysis.image_disclosure_found = imageHasDisclosure;
    if (imageDetails.length) analysis.image_disclosure_details = imageDetails;
  } else if (imageAnalysis.error) {
    analysis.image_analysis_performed = false;
    analysis.image_analysis_note = imageAnalysis.error;
  }

  return analysis;
}
