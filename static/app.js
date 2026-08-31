const idleCard = document.getElementById('idleCard');
const chatCard = document.getElementById('chatCard');
const wave = document.getElementById('wave');
const statusEl = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const testScanBtn = document.getElementById('testScanBtn');
const stopBtn = document.getElementById('stopBtn');
const talkBtn = document.getElementById('talkBtn');
const submitPrompt = document.getElementById('submitPrompt');
const autoSubmitBtn = document.getElementById('autoSubmitBtn');
const cancelSubmitBtn = document.getElementById('cancelSubmitBtn');
const retryBtn = document.getElementById('retryBtn');
const postSubmitActions = document.getElementById('postSubmitActions');
const triggerScanBtn = document.getElementById('triggerScanBtn');
const requiredDocsBtn = document.getElementById('requiredDocsBtn');
const chatLog = document.getElementById('chatLog');
const extensionStatusEls = [
  document.getElementById('extensionStatus'),
  document.getElementById('extensionStatusChat'),
];

const AUTO_SUBMIT_COUNTDOWN_SEC = 3;
const EXTENSION_STATUS_POLL_MS = 5000;

// Token đăng nhập (JWT, cấp từ popup extension qua /auth/login): đọc từ query
// param ?token=... khi mở link, lưu lại localStorage để lần sau không cần kèm
// lại trong URL. Hết hạn sau 24h (JWT_TTL_SECONDS phía backend) — hết hạn thì
// /ws sẽ từ chối kết nối, cần đăng nhập lại qua extension để lấy link mới.
(function persistAuthTokenFromUrl() {
  const params = new URLSearchParams(location.search);
  const token = params.get('token');
  if (token) {
    localStorage.setItem('authToken', token);
    params.delete('token');
    const rest = params.toString();
    history.replaceState(null, '', location.pathname + (rest ? `?${rest}` : ''));
  }
})();

function wsUrl(path) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const token = localStorage.getItem('authToken') || '';
  const query = token ? `?token=${encodeURIComponent(token)}` : '';
  return `${protocol}//${location.host}${path}${query}`;
}

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;
let isTalking = false;
let lastSubmitRequest = null;
let autoSubmitTimer = null;
let autoSubmitSecondsLeft = 0;

let pendingUserBubble = null;
let pendingAiBubble = null;
let typingBubble = null;

function setWaveState(state) {
  wave.className = 'wave ' + state;
}

function setExtensionStatusUi(connected) {
  for (const el of extensionStatusEls) {
    el.className = 'extension-status ' + (connected ? 'connected' : 'disconnected');
    el.querySelector('.label').textContent = connected ? 'Kết nối: OK' : 'Kết nối: Fail';
  }
}

async function checkExtensionStatus() {
  try {
    const res = await fetch('/extension/status');
    const data = await res.json();
    setExtensionStatusUi(!!data.connected);
  } catch (err) {
    setExtensionStatusUi(false);
  }
}

checkExtensionStatus();
setInterval(checkExtensionStatus, EXTENSION_STATUS_POLL_MS);

function showTypingBubble() {
  hideTypingBubble();
  typingBubble = document.createElement('div');
  typingBubble.className = 'bubble ai typing';
  typingBubble.innerHTML = '<span></span><span></span><span></span>';
  chatLog.appendChild(typingBubble);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function hideTypingBubble() {
  if (typingBubble) {
    typingBubble.remove();
    typingBubble = null;
  }
}

function appendTranscript(text, who) {
  if (who === 'ai') hideTypingBubble();
  let bubble = who === 'user' ? pendingUserBubble : pendingAiBubble;
  if (!bubble) {
    bubble = document.createElement('div');
    bubble.className = 'bubble ' + who;
    chatLog.appendChild(bubble);
    if (who === 'user') pendingUserBubble = bubble; else pendingAiBubble = bubble;
  }
  bubble.textContent += text;
  chatLog.scrollTop = chatLog.scrollHeight;
}

function finalizeTurn() {
  pendingUserBubble = null;
  pendingAiBubble = null;
  hideTypingBubble();
}

function appendSystemBubble(text) {
  const bubble = document.createElement('div');
  bubble.className = 'bubble system';
  bubble.textContent = text;
  chatLog.appendChild(bubble);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderProcedureCard(data) {
  const card = document.createElement('div');
  card.className = 'procedure-card';

  const title = document.createElement('div');
  title.className = 'procedure-card-title';
  title.textContent = data.procedure_name;
  card.appendChild(title);

  for (const group of data.cases) {
    const groupEl = document.createElement('div');
    groupEl.className = 'procedure-card-group';

    const label = document.createElement('div');
    label.className = 'procedure-card-group-label';
    label.textContent = group.label;
    groupEl.appendChild(label);

    const list = document.createElement('ul');
    for (const item of group.items) {
      const li = document.createElement('li');
      const nameSpan = document.createElement('span');
      nameSpan.className = 'item-name';
      nameSpan.textContent = item.ten_giay_to;
      const qtySpan = document.createElement('span');
      qtySpan.className = 'item-qty';
      qtySpan.textContent = item.so_luong;
      li.appendChild(nameSpan);
      li.appendChild(qtySpan);
      list.appendChild(li);
    }
    groupEl.appendChild(list);
    card.appendChild(groupEl);
  }

  if (data.source_url) {
    const link = document.createElement('a');
    link.href = data.source_url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Xem chi tiết trên dichvucong.gov.vn';
    card.appendChild(link);
  }

  chatLog.appendChild(card);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderRequiredDocumentsCard(data) {
  const card = document.createElement('div');
  card.className = 'procedure-card no-accent-border';

  const title = document.createElement('div');
  title.className = 'procedure-card-title';
  title.textContent = 'Thành phần hồ sơ cần chuẩn bị';
  card.appendChild(title);

  const hasSummary = data.summary && data.summary.length;
  const source = hasSummary ? data.summary : data.items;
  if (!source || source.length === 0) {
    const empty = document.createElement('div');
    empty.textContent = 'Không tìm thấy thông tin thành phần hồ sơ trên trang hiện tại.';
    card.appendChild(empty);
  } else {
    const list = document.createElement('ul');
    for (const item of source) {
      const li = document.createElement('li');
      if (typeof item === 'string') {
        li.textContent = item;
      } else {
        const nameSpan = document.createElement('span');
        nameSpan.className = 'item-name';
        nameSpan.textContent = item.name;
        const qtySpan = document.createElement('span');
        qtySpan.className = 'item-qty';
        qtySpan.textContent = item.qty || '';
        li.appendChild(nameSpan);
        li.appendChild(qtySpan);
      }
      list.appendChild(li);
    }
    card.appendChild(list);
  }

  chatLog.appendChild(card);
  chatLog.scrollTop = chatLog.scrollHeight;
}

const PLAYBACK_BUFFER_SEC = 0.12;

let playbackContext = null;
let nextPlayTime = 0;

function playPcmChunk(base64Pcm) {
  if (!playbackContext) {
    playbackContext = new AudioContext({ sampleRate: 24000 });
    nextPlayTime = playbackContext.currentTime;
  }
  const bytes = Uint8Array.from(atob(base64Pcm), c => c.charCodeAt(0));
  const int16 = new Int16Array(bytes.buffer);
  const float32 = new Float32Array(int16.length);
  for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

  const buffer = playbackContext.createBuffer(1, float32.length, 24000);
  buffer.copyToChannel(float32, 0);

  const source = playbackContext.createBufferSource();
  source.buffer = buffer;
  source.connect(playbackContext.destination);

  const isNewTurn = nextPlayTime <= playbackContext.currentTime;
  const startAt = isNewTurn
    ? playbackContext.currentTime + PLAYBACK_BUFFER_SEC
    : Math.max(nextPlayTime, playbackContext.currentTime);
  source.start(startAt);
  nextPlayTime = startAt + buffer.duration;

  setWaveState('speaking');
  source.onended = () => {
    if (playbackContext.currentTime >= nextPlayTime - 0.05) {
      setWaveState('idle');
    }
  };
}

function resampleTo16k(input, inputRate) {
  if (inputRate === 16000) return input;
  const ratio = inputRate / 16000;
  const outLength = Math.floor(input.length / ratio);
  const output = new Float32Array(outLength);
  for (let i = 0; i < outLength; i++) output[i] = input[Math.floor(i * ratio)];
  return output;
}

function floatTo16BitPcm(input) {
  const buffer = new ArrayBuffer(input.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function toBase64(buffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function startAutoSubmitCountdown() {
  stopAutoSubmitCountdown();
  submitPrompt.hidden = false;
  autoSubmitSecondsLeft = AUTO_SUBMIT_COUNTDOWN_SEC;
  autoSubmitBtn.textContent = `Tự động nộp (${autoSubmitSecondsLeft}s)`;
  autoSubmitTimer = setInterval(() => {
    autoSubmitSecondsLeft -= 1;
    if (autoSubmitSecondsLeft <= 0) {
      stopAutoSubmitCountdown();
      submitPrompt.hidden = true;
      submitProcedure();
      return;
    }
    autoSubmitBtn.textContent = `Tự động nộp (${autoSubmitSecondsLeft}s)`;
  }, 1000);
}

function stopAutoSubmitCountdown() {
  if (autoSubmitTimer) {
    clearInterval(autoSubmitTimer);
    autoSubmitTimer = null;
  }
}

function cancelAutoSubmit() {
  stopAutoSubmitCountdown();
  submitPrompt.hidden = true;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'cancel_submit' }));
  }
}

function triggerScanForm() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'trigger_scan_form' }));
  }
}

function requestRequiredDocuments() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'request_required_documents' }));
  }
}

function handleWsMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === 'audio') {
    playPcmChunk(msg.data);
  } else if (msg.type === 'show_submit_button') {
    startAutoSubmitCountdown();
  } else if (msg.type === 'show_scan_form_button') {
    postSubmitActions.hidden = false;
  } else if (msg.type === 'required_documents') {
    finalizeTurn();
    renderRequiredDocumentsCard(msg.data);
  } else if (msg.type === 'submit_procedure_status') {
    statusEl.textContent = msg.message;
    appendSystemBubble(msg.message);
  } else if (msg.type === 'submit_procedure_done') {
    const doneMsg = msg.message || 'Đã mở thủ tục trên dichvucong.gov.vn — vui lòng kiểm tra và bấm "Nộp trực tuyến" nếu đúng.';
    statusEl.textContent = doneMsg;
    appendSystemBubble(doneMsg);
  } else if (msg.type === 'submit_procedure_error') {
    statusEl.textContent = 'Lỗi: ' + msg.message;
    retryBtn.hidden = false;
  } else if (msg.type === 'searching') {
    statusEl.textContent = 'Đang tra cứu thông tin thủ tục...';
  } else if (msg.type === 'procedure_card') {
    finalizeTurn();
    renderProcedureCard(msg.data);
  } else if (msg.type === 'user_transcript') {
    appendTranscript(msg.text, 'user');
  } else if (msg.type === 'ai_transcript') {
    appendTranscript(msg.text, 'ai');
  } else if (msg.type === 'turn_complete') {
    finalizeTurn();
    if (!isTalking) statusEl.textContent = 'Nhấn nút, Enter hoặc Space để bắt đầu nói';
    setWaveState('idle');
  } else if (msg.type === 'interrupted') {
    finalizeTurn();
    if (!isTalking) statusEl.textContent = 'Nhấn nút, Enter hoặc Space để bắt đầu nói';
    setWaveState('idle');
    nextPlayTime = playbackContext ? playbackContext.currentTime : 0;
  }
}

function setTalking(talking) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  isTalking = talking;
  if (talking) {
    ws.send(JSON.stringify({ type: 'activity_start' }));
    talkBtn.textContent = 'Đang nói... (nhấn để dừng)';
    talkBtn.classList.add('talking');
    statusEl.textContent = 'Đang nghe bạn nói...';
    setWaveState('listening');
  } else {
    ws.send(JSON.stringify({ type: 'activity_end' }));
    talkBtn.textContent = 'Nhấn để nói';
    talkBtn.classList.remove('talking');
    statusEl.textContent = 'Đang suy nghĩ...';
    setWaveState('idle');
    showTypingBubble();
  }
}

function toggleTalking() {
  setTalking(!isTalking);
}

async function start() {
  idleCard.hidden = true;
  chatCard.hidden = false;
  chatLog.innerHTML = '';
  stopAutoSubmitCountdown();
  submitPrompt.hidden = true;
  postSubmitActions.hidden = true;
  retryBtn.hidden = true;
  isTalking = false;
  talkBtn.textContent = 'Nhấn để nói';
  talkBtn.classList.remove('talking');
  setWaveState('idle');
  statusEl.textContent = 'Đang kết nối...';

  ws = new WebSocket(wsUrl('/ws'));

  ws.onopen = async () => {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule('/worklet.js');

    const source = audioContext.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioContext, 'mic-processor');
    workletNode.port.onmessage = (e) => {
      if (!isTalking || !ws || ws.readyState !== WebSocket.OPEN) return;
      const resampled = resampleTo16k(e.data, audioContext.sampleRate);
      const pcm = floatTo16BitPcm(resampled);
      ws.send(JSON.stringify({ type: 'audio', data: toBase64(pcm) }));
    };
    source.connect(workletNode);

    statusEl.textContent = 'Nhấn nút, Enter hoặc Space để bắt đầu nói';
    setWaveState('idle');
  };

  ws.onmessage = handleWsMessage;
  ws.onclose = () => resetUi();
}

async function startScanTest() {
  idleCard.hidden = true;
  chatCard.hidden = false;
  chatLog.innerHTML = '';
  stopAutoSubmitCountdown();
  submitPrompt.hidden = true;
  retryBtn.hidden = true;
  isTalking = false;
  talkBtn.textContent = 'Nhấn để nói';
  talkBtn.classList.remove('talking');
  setWaveState('idle');
  statusEl.textContent = 'Đang kết nối...';

  ws = new WebSocket(wsUrl('/ws'));

  ws.onopen = async () => {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule('/worklet.js');

    const source = audioContext.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioContext, 'mic-processor');
    workletNode.port.onmessage = (e) => {
      if (!isTalking || !ws || ws.readyState !== WebSocket.OPEN) return;
      const resampled = resampleTo16k(e.data, audioContext.sampleRate);
      const pcm = floatTo16BitPcm(resampled);
      ws.send(JSON.stringify({ type: 'audio', data: toBase64(pcm) }));
    };
    source.connect(workletNode);

    postSubmitActions.hidden = false;
    statusEl.textContent = 'Đang quét trang để test...';
    triggerScanForm();
  };

  ws.onmessage = handleWsMessage;
  ws.onclose = () => resetUi();
}

function stop() {
  if (ws) {
    ws.send(JSON.stringify({ type: 'stop' }));
    ws.close();
  }
  resetUi();
}

function resetUi() {
  if (workletNode) workletNode.disconnect();
  if (micStream) micStream.getTracks().forEach(t => t.stop());
  if (audioContext) audioContext.close();
  if (playbackContext) {
    playbackContext.close();
    playbackContext = null;
  }
  nextPlayTime = 0;
  isTalking = false;
  lastSubmitRequest = null;
  stopAutoSubmitCountdown();
  submitPrompt.hidden = true;
  postSubmitActions.hidden = true;
  finalizeTurn();
  setWaveState('idle');
  chatCard.hidden = true;
  idleCard.hidden = false;
  retryBtn.hidden = true;
  ws = null;
}

function retry() {
  if (ws && ws.readyState === WebSocket.OPEN && lastSubmitRequest) {
    retryBtn.hidden = true;
    statusEl.textContent = 'Đang thử lại...';
    ws.send(JSON.stringify(lastSubmitRequest));
    return;
  }
  if (ws) {
    ws.onclose = null;
    ws.close();
  }
  resetUi();
}

function submitProcedure() {
  if (!ws) return;
  stopAutoSubmitCountdown();
  submitPrompt.hidden = true;
  const request = { type: 'submit_procedure' };
  lastSubmitRequest = request;
  statusEl.textContent = 'Đang xử lý yêu cầu nộp hồ sơ...';
  ws.send(JSON.stringify(request));
}

startBtn.onclick = start;
stopBtn.onclick = stop;
talkBtn.onclick = toggleTalking;
autoSubmitBtn.onclick = submitProcedure;
cancelSubmitBtn.onclick = cancelAutoSubmit;
triggerScanBtn.onclick = triggerScanForm;
requiredDocsBtn.onclick = requestRequiredDocuments;
retryBtn.onclick = retry;
testScanBtn.onclick = startScanTest;

document.addEventListener('keydown', (e) => {
  if ((e.key !== 'Enter' && e.key !== ' ' && e.code !== 'Space') || chatCard.hidden) return;
  e.preventDefault();
  if (e.repeat) return;
  toggleTalking();
});
