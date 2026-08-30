const DEFAULT_BACKEND_URL = 'ws://localhost:8000/extension';
const TARGET_URL_PATTERN = 'https://dichvucong.gov.vn/*';

let socket = null;
let reconnectTimer = null;
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
  };

  socket.onmessage = async (event) => {
    const message = JSON.parse(event.data);
    try {
      const result = await handleCommand(message);
      sendResponse(message.request_id, result);
    } catch (err) {
      sendResponse(message.request_id, { error: String(err) });
    }
  };

  socket.onclose = (event) => {
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

async function sendToContentScript(action, payload) {
  if (controlledTabId === null) {
    throw new Error('Chưa có tab dichvucong.gov.vn nào đang được điều khiển.');
  }
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

async function handleCommand(message) {
  switch (message.action) {
    case 'open_url_and_scan': {
      await findOrCreateTab(message.url);
      return await sendToContentScript('scan_page', {});
    }
    case 'scan_current_page': {
      return await sendToContentScript('scan_page', {});
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
chrome.alarms.create('keepalive', { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener(() => connect());
