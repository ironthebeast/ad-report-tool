// 뒷광고 신고 도우미 — 클라이언트 (app.py의 Streamlit 흐름 재현)
// 상태는 브라우저 메모리에만 보관: 서버에는 아무것도 저장하지 않음

const $ = (id) => document.getElementById(id);
const MAX_PAYLOAD = 4.2 * 1024 * 1024; // Vercel 요청 본문 한도 4.5MB

const state = {
  evidence: null,
  analysis: null,
  manualScreenshots: [], // { name, dataUrl }
  autoReason: '',
};

const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

const spinner = (text) => `<div class="spinner">${escapeHtml(text)}</div>`;

// ── 사이드바 / 탭 ──
$('sidebarToggle').addEventListener('click', () => $('sidebar').classList.add('open'));
$('sidebarClose').addEventListener('click', () => $('sidebar').classList.remove('open'));

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('active', t === tab));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.id === tab.dataset.tab));
  });
});

document.querySelectorAll('input[name=rel]').forEach((r) => r.addEventListener('change', () => {
  $('otherRelWrap').hidden = document.querySelector('input[name=rel]:checked').value !== '기타';
}));

const today = new Date();
$('content_date').value = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0, 10);

// ── 스크린샷 업로드 (브라우저에서 JPEG 압축) ──
function compressImage(file, maxW = 1400, quality = 0.82) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, maxW / img.width);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#fff';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', quality));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error(`${file.name}: 이미지를 읽을 수 없습니다.`)); };
    img.src = url;
  });
}

async function addFiles(files) {
  const list = [...files].filter((f) => /^image\/(png|jpeg|gif|webp)$/.test(f.type));
  if (!list.length) return;
  $('uploadList').innerHTML = spinner('이미지를 처리하고 있습니다...');
  for (const f of list) {
    if (f.size > 10 * 1024 * 1024) {
      alertBox('uploadList', `${f.name}: 10MB 이하 파일만 업로드할 수 있습니다.`);
      continue;
    }
    try {
      state.manualScreenshots.push({ name: f.name, dataUrl: await compressImage(f) });
    } catch (e) {
      console.error(e);
    }
  }
  renderUploads();
}

function renderUploads() {
  const shots = state.manualScreenshots;
  if (!shots.length) { $('uploadList').innerHTML = ''; return; }
  $('uploadList').innerHTML = `
    <ul class="upload-list">${shots.map((s, i) => `
      <li><img src="${s.dataUrl}" alt=""><span>${escapeHtml(s.name)}</span>
      <button data-remove="${i}" aria-label="삭제">✕</button></li>`).join('')}
    </ul>
    <div class="ok-box">${shots.length}개 스크린샷이 첨부되었습니다.</div>`;
}

function alertBox(targetId, msg) {
  $(targetId).insertAdjacentHTML('beforeend', `<div class="error-box">${escapeHtml(msg)}</div>`);
}

$('fileInput').addEventListener('change', (e) => { addFiles(e.target.files); e.target.value = ''; });
$('uploadList').addEventListener('click', (e) => {
  const idx = e.target.dataset?.remove;
  if (idx !== undefined) { state.manualScreenshots.splice(Number(idx), 1); renderUploads(); }
});
const dz = $('dropzone');
dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('drag'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', (e) => { e.preventDefault(); dz.classList.remove('drag'); addFiles(e.dataTransfer.files); });

// ── STEP 1: 증거 수집 ──
$('captureBtn').addEventListener('click', async () => {
  const url = $('targetUrl').value.trim();
  if (!url) return;
  const btn = $('captureBtn');
  btn.disabled = true;
  $('captureStatus').innerHTML = spinner('증거를 수집하고 있습니다... (스크린샷 캡처 + 어필리에이트 지표 분석)');
  try {
    const res = await fetch('/api/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: /^https?:\/\//i.test(url) ? url : `https://${url}` }),
    });
    const json = await res.json().catch(() => ({ error: `서버 응답 오류 (HTTP ${res.status})` }));
    if (!res.ok || json.error) throw new Error(json.error || `HTTP ${res.status}`);
    state.evidence = json.evidence;
    state.analysis = json.analysis;
    $('captureStatus').innerHTML = '';
    renderEvidence();
    fillAutoReason();
  } catch (e) {
    $('captureStatus').innerHTML = `
      <div class="error-box">증거 수집 중 오류가 발생했습니다: ${escapeHtml(e.message)}</div>
      <div class="note-box">💡 스크린샷을 직접 촬영해 아래 업로드 기능을 사용할 수 있습니다.</div>`;
  } finally {
    btn.disabled = false;
  }
});
$('targetUrl').addEventListener('keydown', (e) => { if (e.key === 'Enter') $('captureBtn').click(); });

function renderEvidence() {
  const ev = state.evidence;
  const an = state.analysis || {};
  if (!ev) { $('evidenceResult').innerHTML = ''; return; }

  let left = `<p><strong>📋 수집 결과</strong></p><ul>
    <li><strong>페이지 제목</strong>: ${escapeHtml(ev.page_title || 'N/A')}</li>
    <li><strong>캡처 시각</strong>: ${escapeHtml(ev.captured_at || 'N/A')}</li>
    <li><strong>광고 표시 발견</strong>: ${ev.has_ad_disclosure ? '✅ 있음' : '❌ 없음'}</li></ul>`;

  if (ev.affiliate_indicators?.length) {
    left += `<p><strong>🔗 탐지된 어필리에이트 지표:</strong></p><ul>${
      ev.affiliate_indicators.map((i) => `<li>${escapeHtml(i)}</li>`).join('')}</ul>`;
  } else {
    left += '<p><em>자동 탐지로 어필리에이트 지표를 찾지 못했습니다. 수동으로 확인해주세요.</em></p>';
  }

  const ia = ev.image_analysis || {};
  if (ia.image_analysis_done) {
    left += '<hr style="margin:1rem 0"><p><strong>🖼️ 이미지/스티커 광고 표시 분석:</strong></p>';
    if (ia.image_has_disclosure) {
      left += `<p>✅ 이미지/스티커에서 광고 표시 발견</p><ul>${
        (ev.image_disclosure_details || []).map((d) => `<li>${escapeHtml(d)}</li>`).join('')}</ul>`;
    } else {
      left += '<p>❌ 이미지/스티커에서 광고 표시 미발견</p>';
    }
  } else if (ia.error) {
    left += `<p class="caption">⚠️ 이미지 분석: ${escapeHtml(ia.error)}</p>`;
  }

  const severity = an.severity || '미확인';
  const boxes = {
    높음: ['danger-box', '⛔'], 중간: ['warning-box', '⚠️'], 없음: ['success-box', '✅'],
  };
  const [cls, icon] = boxes[severity] || ['info-box', 'ℹ️'];
  let right = `<p><strong>🔎 위반 분석 결과</strong></p>
    <div class="${cls}">${icon} 위반 심각도: <b>${escapeHtml(severity)}</b><br>${
      escapeHtml(an.recommendation || '').replace(/\n/g, '<br>')}</div>`;
  if (an.violation_types?.length) {
    right += `<ul>${an.violation_types.map((v) => `<li><strong>${escapeHtml(v)}</strong></li>`).join('')}</ul>`;
  }

  $('evidenceResult').innerHTML = `
    ${ev.error ? `<div class="warning-box">⚠️ 페이지 접근 중 일부 오류: ${escapeHtml(ev.error)}</div>` : ''}
    <div class="cols"><div>${left}</div><div>${right}</div></div>
    ${ev.screenshot ? `<details class="expander"><summary>📸 캡처된 스크린샷 보기</summary>
      <div><img src="${ev.screenshot}" alt="캡처된 스크린샷">
      <p class="caption" style="text-align:center">캡처: ${escapeHtml(ev.captured_at)}</p></div></details>` : ''}`;
}

/** 자동 분석 결과로 '위법 주장 이유' 채우기 (사용자가 직접 수정한 내용은 덮어쓰지 않음) */
function fillAutoReason() {
  let auto = state.analysis?.recommendation || '';
  const inds = state.evidence?.affiliate_indicators || [];
  if (inds.length) auto += `\n\n[자동 탐지 결과]\n${inds.map((i) => `- ${i}`).join('\n')}`;
  const ta = $('violation_reason');
  if (!ta.value.trim() || ta.value === state.autoReason) ta.value = auto;
  state.autoReason = auto;
}

// ── STEP 3: PDF 생성 ──
const val = (id) => $(id).value.trim();
const checked = (id) => $(id).checked;

$('generateBtn').addEventListener('click', async () => {
  const out = $('reportResult');
  let relationship = document.querySelector('input[name=rel]:checked').value;
  if (relationship === '기타') relationship = val('other_rel');

  const required = [
    ['r_name', '신고인 성명'], ['r_birth', '신고인 생년월일'], ['r_addr', '신고인 주소'],
    ['r_phone', '신고인 전화번호'], ['resp_name', '피신고인 사업자명'],
    ['resp_addr_phone', '피신고인 주소 또는 전화번호'], ['content_desc', '표시·광고의 내용'],
    ['violation_reason', '위법하다고 주장하는 이유'],
  ];
  const missing = required.filter(([id]) => !val(id)).map(([, label]) => label);
  if (missing.length) {
    out.innerHTML = `<div class="error-box">필수 항목을 입력해주세요: ${escapeHtml(missing.join(', '))}</div>`;
    return;
  }

  const ev = state.evidence || {};
  const shots = [];
  if (ev.screenshot) shots.push(ev.screenshot);
  shots.push(...state.manualScreenshots.map((s) => s.dataUrl));

  const reportData = {
    reporter: {
      name: val('r_name'), birth_date: val('r_birth'), address: val('r_addr'), phone: val('r_phone'),
      mobile: val('r_mobile'), fax: val('r_fax'), email: val('r_email'), relationship,
    },
    respondent: {
      business_name: val('resp_name'), representative: val('resp_rep'),
      address_phone: val('resp_addr_phone'), department: val('resp_dept'),
    },
    report_content: {
      media: $('content_media').value, date: $('content_date').value,
      content: val('content_desc'), violation_reason: val('violation_reason'),
    },
    checklist: {
      false_exaggerated: checked('check_1_1'), deceptive: checked('check_1_2'),
      unfair_comparison: checked('check_1_3'), defamatory: checked('check_1_4'),
      missing_info: checked('check_2'), association_restriction: checked('check_3'), other: checked('check_4'),
    },
    attachment_desc: val('attachment_desc'),
    identity_disclosure: document.querySelector('input[name=identity]:checked').value,
    evidence: {
      screenshot: shots[0] || null,
      extra_screenshots: shots.slice(1),
      url: ev.url || val('targetUrl'),
      captured_at: ev.captured_at || '',
      analysis_text: state.analysis?.recommendation || '',
      affiliate_indicators: ev.affiliate_indicators || [],
      additional_notes: val('additional_notes'),
    },
  };

  const body = JSON.stringify(reportData);
  if (body.length > MAX_PAYLOAD) {
    out.innerHTML = `<div class="error-box">첨부 이미지 용량이 너무 큽니다 (${(body.length / 1048576).toFixed(1)}MB). 스크린샷 수를 줄여주세요.</div>`;
    return;
  }

  const btn = $('generateBtn');
  btn.disabled = true;
  out.innerHTML = spinner('HWP 양식 기반 PDF를 생성하고 있습니다...');
  try {
    const res = await fetch('/api/report', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body });
    if (!res.ok) {
      const json = await res.json().catch(() => ({}));
      throw new Error(json.error || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    const filename = `뒷광고_신고서_${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}.pdf`;
    const href = URL.createObjectURL(blob);
    out.innerHTML = `
      <div class="ok-box">✅ PDF 신고서가 생성되었습니다!</div>
      <p><strong>📄 파일명</strong>: ${escapeHtml(filename)}</p>
      <p><strong>📏 파일크기</strong>: ${blob.size.toLocaleString()} bytes</p>
      <a class="btn btn-block" style="display:block;text-align:center;text-decoration:none" href="${href}" download="${escapeHtml(filename)}">📥 PDF 다운로드</a>`;
  } catch (e) {
    out.innerHTML = `<div class="error-box">PDF 생성 중 오류가 발생했습니다: ${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
  }
});
