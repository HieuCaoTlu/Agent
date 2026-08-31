const searchInput = document.getElementById('searchInput');
const resultCount = document.getElementById('resultCount');
const procedureList = document.getElementById('procedureList');

let allProcedures = [];
let expandedName = null;
let detailCache = {};

function normalize(text) {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

async function loadProcedures() {
  procedureList.textContent = 'Đang tải...';
  try {
    const response = await fetch('/required-documents');
    allProcedures = await response.json();
    render();
  } catch {
    procedureList.innerHTML = '<div class="empty-hint">Không tải được danh sách thủ tục.</div>';
  }
}

function render() {
  const query = normalize(searchInput.value.trim());
  const filtered = query
    ? allProcedures.filter((p) => normalize(p.name).includes(query))
    : allProcedures;

  resultCount.textContent = `${filtered.length} thủ tục`;

  if (filtered.length === 0) {
    procedureList.innerHTML = '<div class="empty-hint">Không tìm thấy thủ tục phù hợp.</div>';
    return;
  }

  procedureList.innerHTML = filtered
    .map((p) => {
      const isOpen = p.name === expandedName;
      const badge = p.has_summary
        ? '<span class="badge badge-ok">Đã tóm tắt</span>'
        : '<span class="badge">Chưa tóm tắt</span>';
      return `
        <div class="doc-item">
          <button type="button" class="doc-item-header" data-name="${escapeAttr(p.name)}">
            <span class="doc-item-name">${escapeHtml(p.name)}</span>
            <span class="doc-item-meta">${p.items_count} giấy tờ ${badge}</span>
          </button>
          <div class="doc-item-body" ${isOpen ? '' : 'hidden'} id="body-${escapeAttr(p.name)}"></div>
        </div>
      `;
    })
    .join('');

  procedureList.querySelectorAll('.doc-item-header').forEach((btn) => {
    btn.addEventListener('click', () => toggleItem(btn.dataset.name));
  });

  if (expandedName && filtered.some((p) => p.name === expandedName)) {
    renderDetail(expandedName);
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeAttr(text) {
  return text.replace(/"/g, '&quot;');
}

async function toggleItem(name) {
  if (expandedName === name) {
    expandedName = null;
    render();
    return;
  }
  expandedName = name;
  render();
  await renderDetail(name);
}

async function renderDetail(name) {
  const body = document.getElementById(`body-${CSS.escape(name)}`);
  if (!body) return;

  if (!detailCache[name]) {
    body.innerHTML = '<div class="doc-loading">Đang tải...</div>';
    try {
      const response = await fetch(`/required-documents/${encodeURIComponent(name)}`);
      detailCache[name] = await response.json();
    } catch {
      body.innerHTML = '<div class="empty-hint">Không tải được chi tiết.</div>';
      return;
    }
  }

  const detail = detailCache[name];
  const items = detail.items || [];
  const summary = detail.summary;

  let html = '';

  if (summary && summary.length) {
    html += '<div class="doc-summary"><h3>Tóm tắt</h3><ul>';
    html += summary.map((s) => `<li>${escapeHtml(s)}</li>`).join('');
    html += '</ul></div>';
  } else {
    html += `<button type="button" class="summarize-btn" data-name="${escapeAttr(name)}">Tóm tắt bằng AI</button>`;
    html += '<div class="summarize-status"></div>';
  }

  html += '<div class="doc-full"><h3>Toàn văn thành phần hồ sơ</h3>';
  if (items.length === 0) {
    html += '<div class="empty-hint">Không có dữ liệu.</div>';
  } else {
    html += '<ul>';
    html += items
      .map(
        (item) =>
          `<li><span class="item-name">${escapeHtml(item.name)}</span><span class="item-qty">${escapeHtml(item.qty || '')}</span></li>`
      )
      .join('');
    html += '</ul>';
  }
  html += '</div>';

  if (detail.href) {
    html += `<a href="${detail.href}" target="_blank" rel="noopener">Xem trên dichvucong.gov.vn</a>`;
  }

  body.innerHTML = html;
  body.hidden = false;

  const summarizeBtn = body.querySelector('.summarize-btn');
  if (summarizeBtn) {
    summarizeBtn.addEventListener('click', () => triggerSummarize(name));
  }
}

async function triggerSummarize(name) {
  const body = document.getElementById(`body-${CSS.escape(name)}`);
  const statusEl = body.querySelector('.summarize-status');
  const btn = body.querySelector('.summarize-btn');
  btn.disabled = true;
  statusEl.textContent = 'Đang tóm tắt...';
  try {
    const response = await fetch(`/required-documents/${encodeURIComponent(name)}/summarize`, { method: 'POST' });
    const result = await response.json();
    if (!response.ok) {
      statusEl.textContent = result.detail || 'Tóm tắt thất bại.';
      btn.disabled = false;
      return;
    }
    detailCache[name] = result;
    const target = allProcedures.find((p) => p.name === name);
    if (target) target.has_summary = true;
    renderDetail(name);
  } catch {
    statusEl.textContent = 'Không thể kết nối máy chủ.';
    btn.disabled = false;
  }
}

searchInput.addEventListener('input', render);

loadProcedures();
