/**
 * 신고서 생성 모듈 (report_generator.py 이식)
 * - 공정거래위원회 별지 제6호 서식 기반 PDF 생성
 * - HWP 양식과 일치하는 테이블 레이아웃 (좌표 단위: mm, 원본과 동일)
 */
import PDFDocument from 'pdfkit';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const FONT_PATH = join(ROOT, 'fonts', 'NanumGothic-Regular.ttf');

const MM = 72 / 25.4;
const PAGE_W = 210;
const RIGHT_MARGIN = 10;
const CELL_PAD = 1;
const CHECKED = '▣';
const UNCHECKED = '□';
// 나눔고딕에 없는 원문자 → 직접 그림
const CIRCLED = { '①': '1', '②': '2', '③': '3', '④': '4' };

class KoreanPDF {
  constructor() {
    this.doc = new PDFDocument({ size: 'A4', margin: 0, autoFirstPage: false });
    this.doc.registerFont('Korean', FONT_PATH);
    this.doc.font('Korean');
  }

  addPage() {
    this.doc.addPage({ size: 'A4', margin: 0 });
  }

  rect(x, y, w, h) {
    this.doc.lineWidth(0.2 * MM).rect(x * MM, y * MM, w * MM, h * MM).stroke();
  }

  /** 한 줄 텍스트 너비(mm) */
  width(text, size) {
    this.doc.fontSize(size);
    let w = 0;
    for (const part of splitCircled(text)) {
      w += part.circled ? size * 0.9 : this.doc.widthOfString(part.text);
    }
    return w / MM;
  }

  /** (x, baseline 기준이 아닌) 줄 상단 y(mm)에 한 줄 출력 */
  line(x, y, text, size) {
    const { doc } = this;
    doc.fontSize(size);
    let cx = x * MM;
    for (const part of splitCircled(text)) {
      if (part.circled) {
        const d = size * 0.85;
        const r = d / 2;
        const cy = y * MM + doc.currentLineHeight() / 2;
        doc.lineWidth(0.5).circle(cx + r + size * 0.025, cy, r).stroke();
        doc.fontSize(size * 0.65);
        const dw = doc.widthOfString(part.text);
        doc.text(part.text, cx + r + size * 0.025 - dw / 2, cy - doc.currentLineHeight() / 2,
          { lineBreak: false });
        doc.fontSize(size);
        cx += size * 0.9;
      } else if (part.text) {
        doc.text(part.text, cx, y * MM, { lineBreak: false });
        cx += doc.widthOfString(part.text);
      }
    }
  }

  lineHeightMM(size) {
    this.doc.fontSize(size);
    return this.doc.currentLineHeight() / MM;
  }

  /** fpdf cell(w, h, text, align) 동작 재현: 셀 높이 h 안에서 세로 중앙 정렬 */
  cell(x, y, w, h, text, size, align = 'L') {
    const lines = String(text ?? '').split('\n');
    const lh = this.lineHeightMM(size);
    let ty = y + (h - lh * lines.length) / 2;
    for (const ln of lines) {
      let tx = x + CELL_PAD;
      if (align === 'C') tx = x + (w - this.width(ln, size)) / 2;
      this.line(tx, ty, ln, size);
      ty += lh;
    }
  }

  /** korean_text: set_xy(x, y) + cell(0, 5, ...) — 폭 0은 오른쪽 여백까지 */
  koreanText(x, y, text, size = 10, align = 'L') {
    // 가운데 정렬은 페이지 기준 (원본은 x~오른쪽 여백 기준이라 제목이 오른쪽으로 치우쳤음)
    if (align === 'C') this.cell(0, y, PAGE_W, 5, text, size, 'C');
    else this.cell(x - CELL_PAD, y, PAGE_W - RIGHT_MARGIN - x + CELL_PAD, 5, text, size, align);
  }

  /** draw_cell: 테두리 + 셀 중앙 텍스트 */
  drawCell(x, y, w, h, text = '', size = 9, align = 'L', border = true) {
    if (border) this.rect(x, y, w, h);
    if (text) this.cell(x, y + h / 2 - 2, w, 4, text, size, align);
  }

  image(dataUrl, x, y, w, h) {
    const buf = Buffer.from(dataUrl.split(',')[1] || '', 'base64');
    // 원본은 170x200에 강제로 늘렸음 → 비율 유지하며 영역 안에 맞춤
    this.doc.image(buf, x * MM, y * MM, { fit: [w * MM, h * MM], align: 'center' });
  }

  toBuffer() {
    return new Promise((resolve, reject) => {
      const chunks = [];
      this.doc.on('data', (c) => chunks.push(c));
      this.doc.on('end', () => resolve(Buffer.concat(chunks)));
      this.doc.on('error', reject);
      this.doc.end();
    });
  }
}

function splitCircled(text) {
  const parts = [];
  let buf = '';
  for (const ch of String(text)) {
    if (CIRCLED[ch]) {
      if (buf) parts.push({ text: buf });
      parts.push({ text: CIRCLED[ch], circled: true });
      buf = '';
    } else {
      buf += ch;
    }
  }
  if (buf) parts.push({ text: buf });
  return parts;
}

function koreanDate() {
  const d = new Date(new Date().toLocaleString('en-US', { timeZone: 'Asia/Seoul' }));
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}년  ${p(d.getMonth() + 1)}월  ${p(d.getDate())}일`;
}

/**
 * HWP 별지 제6호 서식 기반 PDF 신고서 생성
 * data 구조는 report_generator.generate_report와 동일하며,
 * evidence.screenshot / evidence.extra_screenshots는 data URL(base64) 이미지.
 */
export async function generateReport(data) {
  const pdf = new KoreanPDF();
  generateMainReportPage(pdf, data);   // 페이지 1: 메인 신고서
  generateChecklistPage(pdf, data);    // 페이지 2: 첨부1 - 사전점검표
  generateAdditionalPage(pdf, data);   // 페이지 3: 첨부2 - 추가 작성 양식
  addEvidencePages(pdf, data);         // 페이지 4+: 증거 스크린샷
  return pdf.toBuffer();
}

function generateMainReportPage(pdf, data) {
  pdf.addPage();
  pdf.koreanText(20, 20, '■ 공정거래위원회의 회의운영 및 사건절차 등에 관한 규칙 [별지 제6호 서식]', 10);
  pdf.koreanText(70, 35, '표시ㆍ광고의 공정화에 관한 법률 위반행위 신고서', 14, 'C');
  pdf.koreanText(20, 50, '※ (*) 표시항목은 필수사항이니 반드시 기재하여 주시고, 나머지 사항은 효율적인 심사를 위하여', 8);
  pdf.koreanText(25, 55, '가능한 한 기재해 주시기 바랍니다.', 8);

  const tableEnd = drawMainTable(pdf, data, 65);

  // 원본은 240 고정이라 신분공개 행과 겹쳤음 → 표 아래로 배치
  const footerY = Math.max(240, tableEnd + 4);
  pdf.koreanText(20, footerY, '「표시·광고의 공정화에 관한 법률」 제16조제2항 및 「공정거래위원회 회의 운영 및', 9);
  pdf.koreanText(20, footerY + 4, '사건절차 등에 관한 규칙」 제10조제2항에 의하여 위와 같이 신고합니다.', 9);
  pdf.koreanText(150, footerY + 11, koreanDate(), 10);
  pdf.koreanText(120, footerY + 18, '신 고 인 :                  (서명 또는 인)', 10);
  pdf.koreanText(20, footerY + 26, '공정거래위원회위원장 귀하', 10);
}

function drawMainTable(pdf, data, startY) {
  const x = 20;
  const reporter = data.reporter || {};
  const respondent = data.respondent || {};
  const content = data.report_content || {};

  // 신고인 섹션 (5행)
  const rh = [8, 8, 8, 8, 8];
  pdf.drawCell(x, startY, 15, rh.reduce((a, b) => a + b), '신\n고\n인', 10, 'C');

  let y = startY;
  pdf.drawCell(x + 15, y, 25, rh[0], '성명(*)', 9);
  pdf.drawCell(x + 40, y, 70, rh[0], reporter.name || '', 9);
  pdf.drawCell(x + 110, y, 25, rh[0], '생년월일(*)', 9);
  pdf.drawCell(x + 135, y, 35, rh[0], reporter.birth_date || '', 9);

  y += rh[0];
  pdf.drawCell(x + 15, y, 25, rh[1], '주소(*)', 9);
  pdf.drawCell(x + 40, y, 130, rh[1], reporter.address || '', 9);

  y += rh[1];
  pdf.drawCell(x + 15, y, 25, rh[2] + rh[3], '연락처', 9, 'C');
  pdf.drawCell(x + 40, y, 25, rh[2], '전화번호(*)', 9);
  pdf.drawCell(x + 65, y, 45, rh[2], reporter.phone || '', 9);
  pdf.drawCell(x + 110, y, 25, rh[2], '휴대폰', 9);
  pdf.drawCell(x + 135, y, 35, rh[2], reporter.mobile || '', 9);

  y += rh[2];
  pdf.drawCell(x + 40, y, 25, rh[3], '팩스번호', 9);
  pdf.drawCell(x + 65, y, 45, rh[3], reporter.fax || '', 9);
  pdf.drawCell(x + 110, y, 25, rh[3], '이메일', 9);
  pdf.drawCell(x + 135, y, 35, rh[3], reporter.email || '', 9);

  y += rh[3];
  pdf.drawCell(x + 15, y, 25, rh[4], '피신고인과의 관계', 8);
  pdf.drawCell(x + 40, y, 130, rh[4], relationshipCheckboxes(reporter.relationship || ''), 8);

  // 피신고인 섹션 (3행)
  y += rh[4] + 2;
  const rp = [8, 8, 8];
  pdf.drawCell(x, y, 15, rp.reduce((a, b) => a + b), '피\n신\n고\n인', 10, 'C');

  pdf.drawCell(x + 15, y, 25, rp[0], '사업자명(*)', 9);
  pdf.drawCell(x + 40, y, 70, rp[0], respondent.business_name || '', 9);
  pdf.drawCell(x + 110, y, 25, rp[0], '대표자 성명', 9);
  pdf.drawCell(x + 135, y, 35, rp[0], respondent.representative || '', 9);

  y += rp[0];
  pdf.drawCell(x + 15, y, 25, rp[1] + rp[2], '주소 또는\n전화번호(*)', 9);
  pdf.drawCell(x + 40, y, 130, rp[1], (respondent.address_phone || '').replace(/\n/g, ' '), 9);

  y += rp[1];
  pdf.drawCell(x + 40, y, 70, rp[2], '', 9);
  pdf.drawCell(x + 110, y, 25, rp[2], '관련부서 및\n담당자', 8);
  pdf.drawCell(x + 135, y, 35, rp[2], respondent.department || '', 9);

  // 신고내용 섹션 (3행)
  y += rp[2] + 2;
  const ch = [10, 35, 50];
  pdf.drawCell(x, y, 15, ch.reduce((a, b) => a + b), '신\n고\n내\n용', 10, 'C');

  pdf.drawCell(x + 15, y, 25, ch[0], '표시·광고\n매체(*)', 9);
  pdf.drawCell(x + 40, y, 70, ch[0], content.media || '', 9);
  pdf.drawCell(x + 110, y, 25, ch[0], '표시·광고\n일자(*)', 9);
  pdf.drawCell(x + 135, y, 35, ch[0], content.date || '', 9);

  y += ch[0];
  pdf.drawCell(x + 15, y, 25, ch[1], '표시·광고의\n내용(*)', 9);
  drawMultilineText(pdf, x + 40, y, 130, ch[1], content.content || '', 9);

  y += ch[1];
  pdf.drawCell(x + 15, y, 25, ch[2], '표시·광고가\n위법하다고\n주장하는\n이유(*)', 9);
  drawMultilineText(pdf, x + 40, y, 130, ch[2], content.violation_reason || '', 9);

  // 첨부자료 및 신분공개
  y += ch[2] + 2;
  const attachment = data.attachment_desc || '신고 대상 표시·광고물 또는 그 사본(*)';
  pdf.drawCell(x, y, 15, 10, '첨부\n자료', 10, 'C');
  pdf.drawCell(x + 15, y, 155, 10, attachment, 9);

  y += 12;
  pdf.drawCell(x, y, 15, 15, '신고인\n신분공개\n동의여부', 8, 'C');
  pdf.drawCell(x + 15, y, 155, 15, identityCheckboxes(data.identity_disclosure || '비공개'), 9);
  return y + 15;
}

function relationshipCheckboxes(relationship) {
  const rels = ['소비자', '행정기관', '사회단체', '경쟁사업자', '구성사업자', '기타'];
  const mark = (rel) => (rel === relationship ? CHECKED : UNCHECKED);
  const isOther = relationship && !rels.slice(0, -1).includes(relationship);
  const otherText = isOther && relationship !== '기타' ? relationship : '';
  const items = rels.map((rel) => {
    if (rel === '기타') return `${isOther ? CHECKED : UNCHECKED} 기타(${otherText})`;
    return `${mark(rel)} ${rel}`;
  });
  return items.join('   ');
}

function identityCheckboxes(disclosure) {
  return ['공개', '비공개', '사건 조치 후 공개']
    .map((k) => `${k === disclosure ? CHECKED : UNCHECKED} ${k}`)
    .join('\n');
}

/** 셀 너비에 맞춰 자동 줄바꿈, 셀 높이 초과분은 생략 */
function wrapLines(pdf, text, maxW, size) {
  const out = [];
  for (const para of String(text).split('\n')) {
    let cur = '';
    for (const ch of para) {
      if (cur && pdf.width(cur + ch, size) > maxW) {
        out.push(cur);
        cur = ch === ' ' ? '' : ch;
      } else {
        cur += ch;
      }
    }
    out.push(cur);
  }
  return out;
}

function drawMultilineText(pdf, x, y, w, h, text, size) {
  pdf.rect(x, y, w, h);
  if (!text) return;
  const lineH = 4;
  const lines = wrapLines(pdf, text, w - 2 * CELL_PAD - 1, size);
  const maxLines = Math.floor((h - 1) / lineH);
  lines.slice(0, maxLines).forEach((ln, i) => {
    if (i === maxLines - 1 && lines.length > maxLines) ln = `${ln.slice(0, -2)}...`;
    pdf.cell(x, y + 1 + i * lineH, w - 2, lineH, ln, size);
  });
}

function generateChecklistPage(pdf, data) {
  pdf.addPage();
  pdf.koreanText(70, 20, '<첨부 1 : 신고서 작성 안내 및 위반행위 사전점검표>', 12, 'C');
  pdf.koreanText(20, 40, '◆ 위반행위 사전점검표', 11);
  drawChecklistTable(pdf, data.checklist || {}, 55);
}

function drawChecklistTable(pdf, checklist, startY) {
  const x = 20;
  let y = startY;
  const mark = (v) => (v ? CHECKED : UNCHECKED);

  pdf.drawCell(x, y, 15, 8, '연번', 10, 'C');
  pdf.drawCell(x + 15, y, 40, 8, '관련 법 조항', 10, 'C');
  pdf.drawCell(x + 55, y, 80, 8, '위반 사실', 10, 'C');
  pdf.drawCell(x + 135, y, 25, 8, '해당 여부', 10, 'C');
  y += 8;

  // 1 — 제3조 (4개 하위 항목)
  const art3 = [
    ['false_exaggerated', '1-①', '사실과 다르게 표시ㆍ광고하거나 사실을 지나치게\n부풀려 거짓ㆍ과장의 표시ㆍ광고 행위', 18],
    ['deceptive', '1-②', '사실을 은폐하거나 축소하는 등의 방법으로\n기만적인 표시ㆍ광고 행위', 14],
    ['unfair_comparison', '1-③', '비교 대상 및 기준을 분명하게 밝히지 않거나 객관적\n근거 없이 유리하게 비교하는 부당비교 표시ㆍ광고 행위', 14],
    ['defamatory', '1-④', '다른 사업자등을 비방하거나 불리한 사실만을\n표시ㆍ광고하여 비방하는 표시ㆍ광고 행위', 14],
  ];
  const art3H = art3.reduce((a, r) => a + r[3], 0);
  pdf.drawCell(x, y, 15, art3H, '1', 10, 'C');
  pdf.drawCell(x + 15, y, 40, art3H, '제3조\n(부당한 표시ㆍ광고\n행위의 금지)', 9, 'C');
  for (const [key, label, desc, h] of art3) {
    pdf.drawCell(x + 55, y, 80, h, desc, 8);
    pdf.drawCell(x + 135, y, 25, h, `${label} (${mark(checklist[key])})`, 9, 'C');
    y += h;
  }

  const rows = [
    ['missing_info', '2', '제4조\n(중요정보의 고시)', '고시된 중요정보를 표시ㆍ광고하지 아니한 행위'],
    ['association_restriction', '3', '제6조\n(사업자단체의\n표시ㆍ광고 제한행위)', '사업자단체가 구성사업자의 표시ㆍ광고를\n부당하게 제한하는 행위'],
    ['other', '4', '기타', '그 밖에 법 위반이 의심되는 행위'],
  ];
  for (const [key, no, law, desc] of rows) {
    const h = 15;
    pdf.drawCell(x, y, 15, h, no, 10, 'C');
    pdf.drawCell(x + 15, y, 40, h, law, 9, 'C');
    pdf.drawCell(x + 55, y, 80, h, desc, 8);
    pdf.drawCell(x + 135, y, 25, h, `${no} (${mark(checklist[key])})`, 9, 'C');
    y += h;
  }
}

function generateAdditionalPage(pdf, data) {
  pdf.addPage();
  pdf.koreanText(70, 20, '<첨부 2 : 신고내용 추가 작성 양식>', 12, 'C');

  const x = 20;
  let y = 40;
  pdf.drawCell(x, y, 80, 10, '위반사실 해당여부 (사전점검표에 체크한 번호)', 9);
  pdf.drawCell(x + 80, y, 80, 10, checkedNumbers(data.checklist || {}) || '예) 1-①', 9);
  y += 10;

  pdf.drawCell(x, y, 30, 120, '신고내용', 10, 'C');
  drawMultilineText(pdf, x + 30, y, 130, 120, (data.evidence || {}).additional_notes || '', 9);
  y += 120;

  pdf.drawCell(x, y, 30, 30, '증거자료', 10, 'C');
  drawMultilineText(pdf, x + 30, y, 130, 30, evidenceList(data), 9);
}

function checkedNumbers(checklist) {
  const map = [
    ['false_exaggerated', '1-①'], ['deceptive', '1-②'], ['unfair_comparison', '1-③'],
    ['defamatory', '1-④'], ['missing_info', '2'], ['association_restriction', '3'], ['other', '4'],
  ];
  return map.filter(([k]) => checklist[k]).map(([, n]) => n).join(', ');
}

function allScreenshots(data) {
  const ev = data.evidence || {};
  return [ev.screenshot, ...(ev.extra_screenshots || [])]
    .filter((s) => typeof s === 'string' && s.startsWith('data:image/'));
}

function evidenceList(data) {
  const ev = data.evidence || {};
  const items = [];
  if (ev.url) items.push(`대상 URL: ${ev.url}`);
  const shots = allScreenshots(data);
  shots.forEach((_, i) => {
    items.push(i === 0 && ev.screenshot ? '자료 1번: 메인 스크린샷' : `자료 ${i + 1}번: 추가 스크린샷 ${ev.screenshot ? i : i + 1}`);
  });
  if (!shots.length) items.push('스크린샷 자료 (별도 첨부)');
  return items.join('\n');
}

function addEvidencePages(pdf, data) {
  const ev = data.evidence || {};
  allScreenshots(data).forEach((shot, i) => {
    pdf.addPage();
    pdf.koreanText(20, 20, `증거자료 ${i + 1}번: 스크린샷`, 12);
    try {
      pdf.image(shot, 20, 40, 170, 200);
      if (ev.captured_at) pdf.koreanText(20, 245, `캡처 시각: ${ev.captured_at}`, 9);
    } catch (e) {
      pdf.koreanText(20, 100, `이미지 로드 실패: ${e.message}`, 10);
    }
  });
}
