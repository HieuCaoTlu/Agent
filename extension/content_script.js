function cleanHtmlForAi(rawHtml) {
  const doc = new DOMParser().parseFromString(rawHtml, 'text/html');
  doc.querySelectorAll('script, style, noscript, svg').forEach((el) => el.remove());
  doc.querySelectorAll('*').forEach((el) => {
    const keep = ['id', 'class', 'name', 'type', 'placeholder', 'aria-label', 'role', 'href', 'value', 'for', 'data-scan-field-id'];
    [...el.attributes].forEach((attr) => {
      if (!keep.includes(attr.name)) el.removeAttribute(attr.name);
    });
  });
  return doc.body.innerHTML;
}

function scanPage() {
  return { html: cleanHtmlForAi(document.documentElement.outerHTML), url: location.href };
}

function scanRequiredDocuments() {
  const headings = [...document.querySelectorAll('h4')].filter(
    (h) => h.textContent.trim() === 'Thành phần hồ sơ'
  );
  if (headings.length === 0) return { items: [], url: location.href };

  const container = headings[0].nextElementSibling;
  if (!container) return { items: [], url: location.href };

  const tables = [...container.querySelectorAll('table')];
  const items = [];
  for (const table of tables) {
    const headerCells = [...table.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    const nameIdx = headerCells.findIndex((h) => h.includes('Tên giấy tờ'));
    const qtyIdx = headerCells.findIndex((h) => h.includes('Số lượng'));
    if (nameIdx === -1) continue;

    const rows = [...table.querySelectorAll('tbody tr')];
    for (const row of rows) {
      const cells = [...row.querySelectorAll('td')];
      const name = cells[nameIdx] ? cells[nameIdx].textContent.trim() : '';
      const qty = qtyIdx !== -1 && cells[qtyIdx] ? cells[qtyIdx].textContent.trim() : '';
      if (name) {
        items.push({ name, qty });
      }
    }
  }
  return { items, url: location.href };
}

const SCAN_FIELD_ATTR = 'data-scan-field-id';
const SCAN_FRAME_PREFIX = Math.random().toString(36).slice(2, 8);

// Danh mục dropdown công khai của hệ thống tokhaidientu.moj.gov.vn (Bộ Tư pháp) —
// không cần đăng nhập, lấy sẵn 1 lần theo tên trường phổ biến trong form hộ tịch
// (kết hôn/khai sinh/khai tử...) để tránh phải bấm mở từng <x-select> một.
// Khảo sát thủ công 1 lần (data/eform_2056_apiid_scan* — thủ tục "Đăng ký kết
// hôn"), apiId gắn cứng theo field name suy luận từ HTML thật, KHÔNG suy luận
// được tự động (apiId không lộ ra DOM/attribute nào, chỉ thấy qua network lúc
// bấm mở dropdown thật) — cần khảo sát lại nếu gặp field mới không có trong
// danh sách này.
const EFORM_KNOWN_APIID = {
  GioiTinh: 6772,
  QuocTich: 6773,
  TinhThanh: 6770,
  DanToc: 6779,
  LoaiGiayToDinhDanh: 6778,
};

function guessEformApiIdKey(fieldName) {
  const n = fieldName.toLowerCase();
  if (n.includes('gioitinh')) return 'GioiTinh';
  if (n.includes('quoctich')) return 'QuocTich';
  if (n.includes('dantoc')) return 'DanToc';
  if (n.includes('giaytodinhdanh') || n.includes('loaigiayto')) return 'LoaiGiayToDinhDanh';
  if (n.includes('tinh') || n.includes('cutru') || n.includes('quequan')) return 'TinhThanh';
  return null;
}

async function fetchEformDropdownOptions(eformId, apiId) {
  try {
    const res = await fetch(`${location.origin}/api/eform-service/api/call-api`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ eformId, apiId }),
    });
    const data = await res.json();
    if (data.code === 200 && Array.isArray(data.result)) {
      return data.result.map((r) => r.Ten || r.TenTinhThanh || '').filter(Boolean);
    }
  } catch (err) {
    // im lặng — fallback về bấm mở dropdown thật ở nơi gọi
  }
  return null;
}

// eformId (số nguyên, vd 2056) dùng cho API call-api là JS runtime state của
// trang tokhaidientu.moj.gov.vn — KHÔNG lộ ra DOM/URL nào tìm được (khác
// KeyEformID dạng UUID trong URL path /e-form/<uuid>, đó là ID khác). Không
// có cách suy luận tĩnh — nếu window lộ sẵn biến toàn cục thì dùng, không thì
// trả null và các nơi gọi tự fallback về bấm-mở-dropdown-thật.
function getEformId() {
  try {
    if (window.eformId) return window.eformId;
    if (window.__EFORM_ID__) return window.__EFORM_ID__;
  } catch (err) {
    // ignore
  }
  return null;
}

// Quét form hộ tịch điện tử (tokhaidientu.moj.gov.vn, custom element x-input/
// x-date/x-select/x-radio/x-input-number) — khác hẳn combobox custom của
// dichvucong.gov.vn (button.custom-input-typography), cần hàm riêng vì cấu
// trúc DOM và cơ chế lấy option hoàn toàn khác nhau.
async function scanEformFields() {
  const XTAGS = ['x-input', 'x-date', 'x-select', 'x-radio', 'x-input-number'];
  const elements = [...document.querySelectorAll(XTAGS.join(','))];
  const eformId = getEformId();
  const fields = [];

  elements.forEach((el, i) => {
    el.setAttribute(SCAN_FIELD_ATTR, `${SCAN_FRAME_PREFIX}-${i}`);
  });

  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    const tag = el.tagName.toLowerCase();
    const name = el.getAttribute('name') || '';
    const selector = `[${SCAN_FIELD_ATTR}="${SCAN_FRAME_PREFIX}-${i}"]`;
    const title = findEformSectionTitle(el);

    if (tag === 'x-input' || tag === 'x-input-number') {
      fields.push({ selector, name, title, field_type: 't' });
    } else if (tag === 'x-date') {
      fields.push({ selector, name, title, field_type: 'd' });
    } else if (tag === 'x-radio') {
      const labels = [...el.querySelectorAll('label')];
      labels.forEach((label, li) => {
        const input = document.getElementById(label.getAttribute('for'));
        if (!input) return;
        input.setAttribute(SCAN_FIELD_ATTR, `${SCAN_FRAME_PREFIX}-${i}-${li}`);
        fields.push({
          selector: `[${SCAN_FIELD_ATTR}="${SCAN_FRAME_PREFIX}-${i}-${li}"]`,
          name,
          title,
          field_type: 'r',
          option_label: label.textContent.trim(),
        });
      });
    } else if (tag === 'x-select') {
      const key = guessEformApiIdKey(name);
      const apiId = key ? EFORM_KNOWN_APIID[key] : null;
      let options = null;
      if (eformId && apiId) {
        options = await fetchEformDropdownOptions(eformId, apiId);
      }
      fields.push({ selector, name, title, field_type: options ? 'a' : 's', options: options || undefined });
    }
  }

  return { fields, url: location.href };
}

function findEformSectionTitle(el) {
  let node = el;
  while (node && node !== document.body) {
    let sibling = node.previousElementSibling;
    while (sibling) {
      const strong = sibling.matches('strong') ? sibling : sibling.querySelector('strong');
      if (strong && strong.textContent.trim()) return strong.textContent.trim();
      sibling = sibling.previousElementSibling;
    }
    node = node.parentElement;
  }
  return null;
}

async function scanFormWithComboboxes() {
  const comboboxButtons = [...document.querySelectorAll('button.custom-input-typography')];
  const comboboxOptions = [];

  comboboxButtons.forEach((button, i) => button.setAttribute(SCAN_FIELD_ATTR, `${SCAN_FRAME_PREFIX}-${i}`));

  for (let i = 0; i < comboboxButtons.length; i++) {
    const button = comboboxButtons[i];
    const selector = `[${SCAN_FIELD_ATTR}="${SCAN_FRAME_PREFIX}-${i}"]`;
    try {
      simulateClick(button);
      const options = await waitForOptions(2000);
      const texts = options.map((o) => o.textContent.trim()).filter(Boolean);
      if (texts.length > 0) {
        comboboxOptions.push({ selector, options: texts });
      }
      simulateClick(button);
      await waitForNoListbox(1500);
    } catch (err) {
      await waitForNoListbox(1000);
    }
  }

  const html = cleanHtmlForAi(document.documentElement.outerHTML);

  return { html, url: location.href, combobox_options: comboboxOptions };
}

function waitForOptions(timeoutMs) {
  return new Promise((resolve) => {
    const start = Date.now();
    function check() {
      const options = document.querySelectorAll('ul[role="listbox"] li[role="option"]');
      if (options.length > 0) {
        resolve([...options]);
        return;
      }
      if (Date.now() - start > timeoutMs) {
        resolve([]);
        return;
      }
      setTimeout(check, 150);
    }
    check();
  });
}

function clickSelector({ selector }) {
  const el = document.querySelector(selector);
  if (!el) throw new Error('Không tìm thấy phần tử: ' + selector);
  simulateClick(el);
  return { ok: true };
}

function findButtonByText(text) {
  return [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === text) || null;
}

function findComboboxButtonByPlaceholder(placeholderSubstring) {
  return (
    [...document.querySelectorAll('button.custom-input-typography')].find((b) =>
      b.textContent.trim().includes(placeholderSubstring)
    ) || null
  );
}

function waitFor(checkFn, timeoutMs, intervalMs) {
  return new Promise((resolve) => {
    const start = Date.now();
    function check() {
      const value = checkFn();
      if (value) {
        resolve(value);
        return;
      }
      if (Date.now() - start > timeoutMs) {
        resolve(null);
        return;
      }
      setTimeout(check, intervalMs);
    }
    check();
  });
}

function simulateClick(el) {
  const rect = el.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  const opts = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
  el.dispatchEvent(new PointerEvent('pointerdown', opts));
  el.dispatchEvent(new MouseEvent('mousedown', opts));
  el.dispatchEvent(new PointerEvent('pointerup', opts));
  el.dispatchEvent(new MouseEvent('mouseup', opts));
  el.dispatchEvent(new MouseEvent('click', opts));
}

function waitForNoListbox(timeoutMs) {
  return new Promise((resolve) => {
    const start = Date.now();
    function check() {
      if (document.querySelectorAll('ul[role="listbox"]').length === 0) {
        resolve();
        return;
      }
      if (Date.now() - start > timeoutMs) {
        resolve();
        return;
      }
      setTimeout(check, 100);
    }
    check();
  });
}

async function chooseComboboxByPlaceholder(placeholderSubstring, text, waitForPreviousListboxClose) {
  if (waitForPreviousListboxClose) await waitForNoListbox(2000);
  let options = [];
  for (let attempt = 0; attempt < 3 && options.length === 0; attempt++) {
    const button = await waitFor(() => findComboboxButtonByPlaceholder(placeholderSubstring), 5000, 200);
    if (!button) throw new Error('Không tìm thấy ô chọn: ' + placeholderSubstring);
    simulateClick(button);
    options = await waitForOptions(2500);
  }
  if (options.length === 0) throw new Error('Danh sách lựa chọn không xuất hiện sau khi bấm combobox.');
  const normalized = text.trim().toLowerCase();
  let match = options.find((o) => o.textContent.trim().toLowerCase() === normalized);
  if (!match) {
    match = options.find((o) => o.textContent.trim().toLowerCase().includes(normalized));
  }
  if (!match) throw new Error('Không tìm thấy lựa chọn khớp: ' + text);
  simulateClick(match);
  await waitForNoListbox(2000);
}

function setNativeValue(el, value) {
  const proto = Object.getPrototypeOf(el);
  const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
  if (descriptor && descriptor.set) {
    descriptor.set.call(el, value);
  } else {
    el.value = value;
  }
  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}

async function fillField({ selector, value, field_type, is_combobox }) {
  const el = document.querySelector(selector);
  if (!el) throw new Error('Không tìm thấy trường: ' + selector);

  const resolvedType = field_type || (is_combobox ? 'combobox' : 'text');

  if (resolvedType === 'choice_option' || resolvedType === 'r') {
    simulateClick(el);
    return { ok: true };
  }

  if (resolvedType === 'combobox') {
    simulateClick(el);
    const options = await waitForOptions(2500);
    if (options.length === 0) throw new Error('Danh sách lựa chọn không xuất hiện: ' + selector);
    const normalized = value.trim().toLowerCase();
    let match = options.find((o) => o.textContent.trim().toLowerCase() === normalized);
    if (!match) match = options.find((o) => o.textContent.trim().toLowerCase().includes(normalized));
    if (!match) throw new Error('Không tìm thấy lựa chọn khớp: ' + value);
    simulateClick(match);
    await waitForNoListbox(2000);
    return { ok: true };
  }

  // "d" (x-date): 3 ô con -day/-month/-year, value dạng "dd/mm/yyyy" hoặc "yyyy-mm-dd".
  if (resolvedType === 'd' && el.tagName.toLowerCase() === 'x-date') {
    return fillEformDate(el, value);
  }

  // "a"/"s" (x-select): không có input ẩn lộ ra để set trực tiếp — vẫn phải bấm
  // mở dropdown thật rồi chọn, kể cả khi field_type là "a" (đã biết options thật
  // qua API call-api lúc quét, chỉ để AI/backend không cần đoán mù, không thay
  // thế được bước bấm chọn UI thật).
  if ((resolvedType === 'a' || resolvedType === 's') && el.tagName.toLowerCase() === 'x-select') {
    return fillEformSelect(el, value);
  }

  // "t" (x-input/x-input-number): input con nằm bên trong custom element.
  if (resolvedType === 't') {
    const inner = el.querySelector('input');
    const target = inner || el;
    target.focus();
    setNativeValue(target, value);
    target.blur();
    return { ok: true };
  }

  el.focus();
  setNativeValue(el, value);
  el.blur();
  return { ok: true };
}

function fillEformDate(xDateEl, value) {
  const normalized = value.replace(/-/g, '/');
  const parts = normalized.includes('/') ? normalized.split('/') : null;
  if (!parts || parts.length !== 3) {
    throw new Error('Định dạng ngày không hợp lệ (cần dd/mm/yyyy hoặc yyyy-mm-dd): ' + value);
  }
  // yyyy-mm-dd sau khi thay "-" thành "/" thành "yyyy/mm/dd" (năm 4 số ở đầu) —
  // phân biệt với dd/mm/yyyy (năm 4 số ở cuối) bằng độ dài phần đầu.
  const [p1, p2, p3] = parts;
  const isIsoOrder = p1.length === 4;
  const day = isIsoOrder ? p3 : p1;
  const month = p2;
  const year = isIsoOrder ? p1 : p3;

  const dayInput = xDateEl.querySelector('input[name$="-day"]');
  const monthInput = xDateEl.querySelector('input[name$="-month"]');
  const yearInput = xDateEl.querySelector('input[name$="-year"]');
  if (!dayInput || !monthInput || !yearInput) {
    throw new Error('Không tìm thấy đủ 3 ô ngày/tháng/năm trong x-date.');
  }
  setNativeValue(dayInput, day.padStart(2, '0'));
  setNativeValue(monthInput, month.padStart(2, '0'));
  setNativeValue(yearInput, year);
  return { ok: true };
}

async function fillEformSelect(xSelectEl, value) {
  const trigger = xSelectEl.querySelector('[tabindex="0"]') || xSelectEl.querySelector('div');
  if (!trigger) throw new Error('Không tìm thấy nút mở dropdown x-select.');
  simulateClick(trigger);
  const options = await waitForOptions(2500);
  if (options.length === 0) throw new Error('Danh sách lựa chọn không xuất hiện (x-select).');
  const normalized = value.trim().toLowerCase();
  let match = options.find((o) => o.textContent.trim().toLowerCase() === normalized);
  if (!match) match = options.find((o) => o.textContent.trim().toLowerCase().includes(normalized));
  if (!match) throw new Error('Không tìm thấy lựa chọn khớp trong x-select: ' + value);
  simulateClick(match);
  await waitForNoListbox(2000);
  return { ok: true };
}

async function runFixedSubmitFlow({ province, ward }) {
  await chooseComboboxByPlaceholder('Chọn Tỉnh', province);
  await chooseComboboxByPlaceholder('Chọn Phường', ward);

  const navBtn = findButtonByText('Nộp hồ sơ');
  if (!navBtn) throw new Error('Không tìm thấy nút "Nộp hồ sơ" trên trang chi tiết thủ tục.');
  simulateClick(navBtn);

  const agreeBtn = await waitFor(() => findButtonByText('Đồng ý'), 3000, 200);
  if (!agreeBtn) throw new Error('Không tìm thấy nút "Đồng ý" sau khi chọn Tỉnh/Phường.');
  simulateClick(agreeBtn);

  const wardNormalized = ward.trim().toLowerCase();
  const finalBtn = await waitFor(() => {
    const cards = [...document.querySelectorAll('div.grid.grid-cols-12')];
    for (const card of cards) {
      if (card.textContent.toLowerCase().includes(wardNormalized)) {
        const btn = [...card.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Nộp trực tuyến');
        if (btn) return btn;
      }
    }
    return null;
  }, 6000, 300);
  if (!finalBtn) throw new Error('Không tìm thấy kết quả khớp phường "' + ward + '" trong danh sách sau khi lọc.');
  finalBtn.scrollIntoView({ block: 'center' });

  return { ok: true, ready_to_submit: true };
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      let result;
      switch (message.action) {
        case 'scan_page':
          result = scanPage();
          break;
        case 'scan_required_documents':
          result = scanRequiredDocuments();
          break;
        case 'scan_form_with_comboboxes':
          result = await scanFormWithComboboxes();
          break;
        case 'scan_eform_fields':
          result = await scanEformFields();
          break;
        case 'click_selector':
          result = clickSelector(message);
          break;
        case 'run_fixed_submit_flow':
          result = await runFixedSubmitFlow(message);
          break;
        case 'fill_field':
          result = await fillField(message);
          break;
        default:
          throw new Error('Lệnh không xác định: ' + message.action);
      }
      sendResponse(result);
    } catch (err) {
      sendResponse({ error: String(err) });
    }
  })();
  return true;
});
