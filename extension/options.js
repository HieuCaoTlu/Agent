const DEFAULT_BACKEND_URL = 'ws://localhost:8013/extension';

const input = document.getElementById('backendUrl');
const status = document.getElementById('status');
const testResult = document.getElementById('testResult');
const testBtn = document.getElementById('testBtn');
const connDot = document.getElementById('connDot');
const connLabel = document.getElementById('connLabel');
const connDetail = document.getElementById('connDetail');

const STATE_LABELS = {
  connected: 'Đã kết nối',
  connecting: 'Đang kết nối...',
  disconnected: 'Mất kết nối',
  error: 'Lỗi kết nối',
};

chrome.storage.local.get(['backendUrl'], (result) => {
  input.value = result.backendUrl || DEFAULT_BACKEND_URL;
});

function isValidWsUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'ws:' || parsed.protocol === 'wss:';
  } catch (e) {
    return false;
  }
}

function refreshStatus() {
  chrome.runtime.sendMessage({ type: 'get_status' }, (result) => {
    if (chrome.runtime.lastError || !result) {
      connDot.className = 'dot error';
      connLabel.textContent = 'Không rõ trạng thái';
      connDetail.textContent = '';
      return;
    }
    connDot.className = 'dot ' + result.state;
    connLabel.textContent = STATE_LABELS[result.state] || result.state;
    connDetail.textContent = result.url ? `${result.url}${result.error ? ' — ' + result.error : ''}` : (result.error || '');
  });
}

document.getElementById('saveBtn').onclick = () => {
  const url = input.value.trim() || DEFAULT_BACKEND_URL;
  if (!isValidWsUrl(url)) {
    status.style.color = '#c62828';
    status.textContent = 'Sai định dạng URL. Phải bắt đầu bằng ws:// hoặc wss:// (vd: ws://localhost:8013/extension).';
    return;
  }
  chrome.storage.local.set({ backendUrl: url }, () => {
    status.style.color = '#2f7d32';
    status.textContent = 'Đã lưu. Extension sẽ tự kết nối lại.';
    chrome.runtime.sendMessage({ type: 'reconnect' });
    setTimeout(() => { status.textContent = ''; }, 3000);
    setTimeout(refreshStatus, 800);
  });
};

testBtn.onclick = () => {
  const url = input.value.trim() || DEFAULT_BACKEND_URL;
  if (!isValidWsUrl(url)) {
    testResult.style.color = '#c62828';
    testResult.textContent = 'Sai định dạng URL. Phải bắt đầu bằng ws:// hoặc wss://.';
    return;
  }
  testBtn.disabled = true;
  testResult.style.color = '#555';
  testResult.textContent = 'Đang kiểm tra...';
  chrome.runtime.sendMessage({ type: 'test_connection', url }, (result) => {
    testBtn.disabled = false;
    if (chrome.runtime.lastError || !result) {
      testResult.style.color = '#c62828';
      testResult.textContent = 'Không nhận được phản hồi từ extension.';
      return;
    }
    if (result.ok) {
      testResult.style.color = '#2f7d32';
      testResult.textContent = 'Kết nối thành công tới ' + url;
    } else {
      testResult.style.color = '#c62828';
      testResult.textContent = result.error || 'Kết nối thất bại.';
    }
  });
};

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'connection_state') {
    connDot.className = 'dot ' + message.state;
    connLabel.textContent = STATE_LABELS[message.state] || message.state;
    connDetail.textContent = message.url ? `${message.url}${message.error ? ' — ' + message.error : ''}` : (message.error || '');
  }
});

refreshStatus();
