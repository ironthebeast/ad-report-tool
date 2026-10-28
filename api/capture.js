import { captureScreenshot, analyzeViolation } from '../lib/evidence.js';

export const maxDuration = 60;

export async function POST(request) {
  let url;
  try {
    ({ url } = await request.json());
  } catch {
    return Response.json({ error: '잘못된 요청입니다.' }, { status: 400 });
  }
  if (!url || !/^https?:\/\//i.test(url)) {
    return Response.json({ error: 'http(s)로 시작하는 URL을 입력해주세요.' }, { status: 400 });
  }

  try {
    const evidence = await captureScreenshot(url);
    const analysis = analyzeViolation(evidence);
    delete evidence.page_text; // 분석에만 사용, 응답 용량 절약
    return Response.json({ evidence, analysis });
  } catch (e) {
    return Response.json({ error: e.message }, { status: 500 });
  }
}
