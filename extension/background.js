const DEFAULT_BACKEND_URL = 'ws://localhost:8000/extension';
const TARGET_URL_PATTERN = 'https://*.gov.vn/*';
const PING_INTERVAL_MS = 15000;
const PONG_TIMEOUT_MS = 10000;

let socket = null;
let reconnectTimer = null;
let pingTimer = null;
let pongTimeoutTimer = null;
let connectionState = 'connecting';
let lastError = '';
let currentUrl = '';

async function getBackendUrl() {
  const result = await chrome.storage.local.get(['backendUrl']);
  return result.backendUrl || DEFAULT_BACKEND_URL;
}

function setConnectionState(state, error) {
  connectionState = state;
  lastError = error || '';
  chrome.runtime.sendMessage({ type: 'connection_state', state: connectionState, error: lastError, url: currentUrl }).catch(() => {});
}

function stopPing() {
  if (pingTimer) {
    clearInterval(pingTimer);
    pingTimer = null;
  }
  if (pongTimeoutTimer) {
    clearTimeout(pongTimeoutTimer);
    pongTimeoutTimer = null;
  }
}

function startPing() {
  stopPing();
  pingTimer = setInterval(() => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type: 'ping' }));
    if (pongTimeoutTimer) clearTimeout(pongTimeoutTimer);
    pongTimeoutTimer = setTimeout(() => {
      setConnectionState('disconnected', 'Không nhận được phản hồi từ backend (pong timeout).');
      try { socket.close(); } catch (e) {}
    }, PONG_TIMEOUT_MS);
  }, PING_INTERVAL_MS);
}

async function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const url = await getBackendUrl();
  currentUrl = url;
  setConnectionState('connecting');
  try {
    socket = new WebSocket(url);
  } catch (err) {
    setConnectionState('error', String(err));
    scheduleReconnect();
    return;
  }

  socket.onopen = () => {
    console.log('[extension] Đã kết nối backend:', url);
    setConnectionState('connected');
    startPing();
  };

  socket.onmessage = async (event) => {
    const message = JSON.parse(event.data);
    if (message.type === 'pong') {
      if (pongTimeoutTimer) {
        clearTimeout(pongTimeoutTimer);
        pongTimeoutTimer = null;
      }
      return;
    }
    try {
      const result = await handleCommand(message);
      sendResponse(message.request_id, result);
    } catch (err) {
      sendResponse(message.request_id, { error: String(err) });
    }
  };

  socket.onclose = (event) => {
    stopPing();
    setConnectionState('disconnected', event.reason || `Mất kết nối (mã ${event.code}).`);
    scheduleReconnect();
  };
  socket.onerror = () => {
    setConnectionState('error', 'Không thể kết nối tới ' + url + '. Kiểm tra backend đã chạy và đúng port chưa.');
    socket.close();
  };
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, 3000);
}

function sendResponse(requestId, payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ request_id: requestId, ...payload }));
  }
}

let controlledTabId = null;

async function findOrCreateTab(url) {
  const targetUrl = url || 'https://dichvucong.gov.vn/';
  const tabs = await chrome.tabs.query({ url: TARGET_URL_PATTERN });
  if (tabs.length > 0) {
    controlledTabId = tabs[0].id;
    await chrome.tabs.update(controlledTabId, { active: true, url: targetUrl });
  } else {
    const tab = await chrome.tabs.create({ url: targetUrl });
    controlledTabId = tab.id;
  }
  await waitForTabLoad(controlledTabId);
  return controlledTabId;
}

function waitForTabLoad(tabId) {
  return new Promise((resolve) => {
    function listener(updatedTabId, info) {
      if (updatedTabId === tabId && info.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 1500);
      }
    }
    chrome.tabs.onUpdated.addListener(listener);
    chrome.tabs.get(tabId, (tab) => {
      if (tab.status === 'complete') {
        chrome.tabs.onUpdated.removeListener(listener);
        setTimeout(resolve, 1500);
      }
    });
  });
}

async function ensureControlledTab() {
  if (controlledTabId !== null) {
    try {
      await chrome.tabs.get(controlledTabId);
      return controlledTabId;
    } catch (err) {
      controlledTabId = null;
    }
  }
  const activeTabs = await chrome.tabs.query({ active: true, url: TARGET_URL_PATTERN });
  if (activeTabs.length > 0) {
    controlledTabId = activeTabs[0].id;
    return controlledTabId;
  }
  const anyTabs = await chrome.tabs.query({ url: TARGET_URL_PATTERN });
  if (anyTabs.length > 0) {
    controlledTabId = anyTabs[0].id;
    return controlledTabId;
  }
  throw new Error('Không tìm thấy tab nào thuộc *.gov.vn đang mở — hãy mở trang trước.');
}

async function sendToContentScript(action, payload) {
  await ensureControlledTab();
  let attemptError;
  for (let attempt = 0; attempt < 5; attempt++) {
    try {
      return await chrome.tabs.sendMessage(controlledTabId, { action, ...payload });
    } catch (err) {
      attemptError = err;
      await new Promise((r) => setTimeout(r, 500));
    }
  }
  throw attemptError;
}

async function getAllFrameIds() {
  await ensureControlledTab();
  try {
    const frames = await chrome.webNavigation.getAllFrames({ tabId: controlledTabId });
    return frames.map((f) => f.frameId);
  } catch (err) {
    return [0];
  }
}

async function getAllFramesWithUrl() {
  await ensureControlledTab();
  try {
    const frames = await chrome.webNavigation.getAllFrames({ tabId: controlledTabId });
    return frames.map((f) => ({ frameId: f.frameId, url: f.url }));
  } catch (err) {
    return [{ frameId: 0, url: '' }];
  }
}

async function sendToFrame(frameId, action, payload) {
  let attemptError;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await chrome.tabs.sendMessage(controlledTabId, { action, ...payload }, { frameId });
    } catch (err) {
      attemptError = err;
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  throw attemptError;
}

const EFORM_HOST = 'tokhaidientu.moj.gov.vn';

async function scanAllFramesWithComboboxes() {
  const frames = await getAllFramesWithUrl();
  const results = [];
  for (const { frameId, url } of frames) {
    const isEform = url && url.includes(EFORM_HOST);
    try {
      const action = isEform ? 'scan_eform_fields' : 'scan_form_with_comboboxes';
      const result = await sendToFrame(frameId, action, {});
      if (result && !result.error) results.push({ frameId, isEform, ...result });
    } catch (err) {
      // frame này không có content script hợp lệ hoặc không phản hồi kịp, bỏ qua
    }
  }
  return results;
}

async function fillFieldAcrossFrames(payload) {
  const frameIds = await getAllFrameIds();
  let lastError;
  for (const frameId of frameIds) {
    try {
      const result = await sendToFrame(frameId, 'fill_field', payload);
      if (result && !result.error) return result;
      lastError = result && result.error;
    } catch (err) {
      lastError = String(err);
    }
  }
  throw new Error(lastError || 'Không tìm thấy trường ở bất kỳ frame nào: ' + payload.selector);
}

async function handleCommand(message) {
  switch (message.action) {
    case 'open_url_and_scan': {
      await findOrCreateTab(message.url);
      return await sendToContentScript('scan_page', {});
    }
    case 'scan_current_page': {
      return await sendToContentScript('scan_page', {});
    }
    case 'scan_required_documents': {
      return await sendToContentScript('scan_required_documents', {});
    }
    case 'scan_form_with_comboboxes': {
      const frameResults = await scanAllFramesWithComboboxes();
      if (frameResults.length === 0) {
        throw new Error('Không quét được frame nào trên trang hiện tại.');
      }
      const htmlFrames = frameResults.filter((r) => !r.isEform);
      const eformFrames = frameResults.filter((r) => r.isEform);
      const html = htmlFrames.map((r) => r.html).join('\n<!-- frame -->\n');
      const combobox_options = htmlFrames.flatMap((r) => r.combobox_options || []);
      // eform_fields: form hộ tịch (tokhaidientu.moj.gov.vn) đã tự trích sẵn
      // field_type (t/s/d/a/c/r) + title context — KHÔNG cần AI đoán từ HTML thô
      // như các trường dichvucong.gov.vn thường, xử lý riêng ở dom_ai.analyze_form.
      const eform_fields = eformFrames.flatMap((r) => r.fields || []);
      return {
        html,
        url: frameResults[0].url,
        combobox_options,
        eform_fields,
        frame_count: frameResults.length,
      };
    }
    case 'click_selector': {
      const result = await sendToContentScript('click_selector', { selector: message.selector });
      await waitForTabLoad(controlledTabId);
      return result;
    }
    case 'run_fixed_submit_flow': {
      return await sendToContentScript('run_fixed_submit_flow', {
        province: message.province,
        ward: message.ward,
      });
    }
    case 'fill_field': {
      return await fillFieldAcrossFrames({
        selector: message.selector,
        value: message.value,
        field_type: message.field_type,
        is_combobox: message.is_combobox,
      });
    }
    default:
      throw new Error('Lệnh không xác định: ' + message.action);
  }
}

function testConnection(url) {
  return new Promise((resolve) => {
    let settled = false;
    let testSocket;
    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try { testSocket.close(); } catch (e) {}
      resolve({ ok: false, error: 'Hết thời gian chờ (5s) — kiểm tra backend đã chạy và đúng port chưa.' });
    }, 5000);

    try {
      testSocket = new WebSocket(url);
    } catch (err) {
      clearTimeout(timer);
      resolve({ ok: false, error: String(err) });
      return;
    }

    testSocket.onopen = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      testSocket.close();
      resolve({ ok: true });
    };
    testSocket.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: false, error: 'Không thể kết nối tới ' + url + '. Kiểm tra backend đã chạy và đúng port chưa.' });
    };
    testSocket.onclose = (event) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ ok: false, error: event.reason || `Kết nối bị đóng (mã ${event.code}).` });
    };
  });
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'reconnect') {
    if (socket) socket.close();
    connect();
    return false;
  }
  if (message.type === 'get_status') {
    sendResponse({ state: connectionState, error: lastError, url: currentUrl });
    return false;
  }
  if (message.type === 'test_connection') {
    testConnection(message.url).then(sendResponse);
    return true;
  }
  return false;
});

connect();
chrome.alarms.create('keepalive', { periodInMinutes: 0.5 });
chrome.alarms.onAlarm.addListener(() => {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    connect();
    return;
  }
  socket.send(JSON.stringify({ type: 'ping' }));
});
