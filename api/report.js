import { generateReport } from '../lib/report.js';

export async function POST(request) {
  let data;
  try {
    data = await request.json();
  } catch {
    return Response.json({ error: '잘못된 요청입니다.' }, { status: 400 });
  }

  try {
    const pdf = await generateReport(data);
    return new Response(pdf, {
      headers: {
        'Content-Type': 'application/pdf',
        'Content-Length': String(pdf.length),
      },
    });
  } catch (e) {
    return Response.json({ error: `PDF 생성 중 오류가 발생했습니다: ${e.message}` }, { status: 500 });
  }
}
