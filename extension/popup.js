const backendHttpUrlInput = document.getElementById('backendHttpUrl');
const usernameInput = document.getElementById('usernameInput');
const loginBtn = document.getElementById('loginBtn');
const loginStatus = document.getElementById('loginStatus');
const webLinkBox = document.getElementById('webLinkBox');
const webLinkOutput = document.getElementById('webLinkOutput');
const copyWebLinkBtn = document.getElementById('copyWebLinkBtn');
const connDot = document.getElementById('connDot');
const connLabel = document.getElementById('connLabel');
const connDetail = document.getElementById('connDetail');

const STATE_LABELS = {
  connected: 'Đã kết nối',
  connecting: 'Đang kết nối...',
  disconnected: 'Mất kết nối',
  error: 'Lỗi kết nối',
};

chrome.storage.local.get(['backendHttpUrl', 'webLink', 'username'], (result) => {
  if (result.backendHttpUrl) backendHttpUrlInput.value = result.backendHttpUrl;
  if (result.username) usernameInput.value = result.username;
  if (result.webLink) {
    webLinkOutput.value = result.webLink;
    webLinkBox.classList.add('show');
    loginStatus.textContent = `Đang đăng nhập: ${result.username || ''}`;
    loginStatus.className = 'ok';
  }
});

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

loginBtn.onclick = async () => {
  const backendHttpUrl = backendHttpUrlInput.value.trim().replace(/\/$/, '');
  const username = usernameInput.value.trim();

  if (!backendHttpUrl || !/^https?:\/\//.test(backendHttpUrl)) {
    loginStatus.textContent = 'Địa chỉ backend phải bắt đầu bằng http:// hoặc https://.';
    loginStatus.className = 'error';
    return;
  }
  if (!username) {
    loginStatus.textContent = 'Vui lòng nhập username.';
    loginStatus.className = 'error';
    return;
  }

  loginBtn.disabled = true;
  loginStatus.textContent = 'Đang đăng nhập...';
  loginStatus.className = '';

  try {
    const response = await fetch(`${backendHttpUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    const result = await response.json();
    if (!response.ok) {
      loginStatus.textContent = result.detail || 'Đăng nhập thất bại.';
      loginStatus.className = 'error';
      return;
    }

    await chrome.storage.local.set({
      backendHttpUrl,
      backendUrl: result.extension_url,
      webLink: result.web_link,
      username,
    });

    loginStatus.textContent = 'Đăng nhập thành công.';
    loginStatus.className = 'ok';
    webLinkOutput.value = result.web_link;
    webLinkBox.classList.add('show');

    chrome.runtime.sendMessage({ type: 'reconnect' });
    setTimeout(refreshStatus, 800);
  } catch (err) {
    loginStatus.textContent = 'Không kết nối được tới backend: ' + err;
    loginStatus.className = 'error';
  } finally {
    loginBtn.disabled = false;
  }
};

copyWebLinkBtn.onclick = async () => {
  try {
    await navigator.clipboard.writeText(webLinkOutput.value);
    copyWebLinkBtn.textContent = 'Đã chép!';
  } catch {
    webLinkOutput.select();
  }
  setTimeout(() => { copyWebLinkBtn.textContent = 'Sao chép'; }, 1500);
};

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'connection_state') {
    connDot.className = 'dot ' + message.state;
    connLabel.textContent = STATE_LABELS[message.state] || message.state;
    connDetail.textContent = message.url ? `${message.url}${message.error ? ' — ' + message.error : ''}` : (message.error || '');
  }
});

refreshStatus();
