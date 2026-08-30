function cleanHtmlForAi(rawHtml) {
  const doc = new DOMParser().parseFromString(rawHtml, 'text/html');
  doc.querySelectorAll('script, style, noscript, svg').forEach((el) => el.remove());
  doc.querySelectorAll('*').forEach((el) => {
    const keep = ['id', 'class', 'name', 'type', 'placeholder', 'aria-label', 'role', 'href', 'value', 'for'];
    [...el.attributes].forEach((attr) => {
      if (!keep.includes(attr.name)) el.removeAttribute(attr.name);
    });
  });
  return doc.body.innerHTML;
}

function scanPage() {
  return { html: cleanHtmlForAi(document.documentElement.outerHTML), url: location.href };
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

async function chooseComboboxByPlaceholder(placeholderSubstring, text) {
  await waitForNoListbox(2000);
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

async function runFixedSubmitFlow({ province, ward }) {
  const navBtn = findButtonByText('Nộp hồ sơ');
  if (!navBtn) throw new Error('Không tìm thấy nút "Nộp hồ sơ" trên trang chi tiết thủ tục.');
  simulateClick(navBtn);

  await chooseComboboxByPlaceholder('Chọn Tỉnh', province);
  await chooseComboboxByPlaceholder('Chọn Phường', ward);

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
        case 'click_selector':
          result = clickSelector(message);
          break;
        case 'run_fixed_submit_flow':
          result = await runFixedSubmitFlow(message);
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
