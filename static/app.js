const idleGroup = document.getElementById('idleGroup');
const chatCard = document.getElementById('chatCard');
const wave = document.getElementById('wave');
const statusEl = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const talkBtn = document.getElementById('talkBtn');
const chatLog = document.getElementById('chatLog');

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;
let isTalking = false;

let pendingUserBubble = null;
let pendingAiBubble = null;
let typingBubble = null;

function setWaveState(state) {
  wave.className = 'wave ' + state;
}

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

function renderRequiredDocumentsCard(data) {
  const card = document.createElement('div');
  card.className = 'procedure-card no-accent-border';

  const title = document.createElement('div');
  title.className = 'procedure-card-title';
  title.textContent = `Thành phần hồ sơ: ${data.procedure_name || ''}`;
  card.appendChild(title);

  const hasSummary = data.summary && data.summary.length;
  const source = hasSummary ? data.summary : data.items;
  if (!source || source.length === 0) {
    const empty = document.createElement('div');
    empty.textContent = 'Chưa có dữ liệu thành phần hồ sơ cho thủ tục này.';
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

  if (data.href) {
    const link = document.createElement('a');
    link.href = data.href;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = 'Xem chi tiết trên dichvucong.gov.vn';
    card.appendChild(link);
  }

  chatLog.appendChild(card);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderSubmissionStepsCard(data) {
  const card = document.createElement('div');
  card.className = 'procedure-card steps-card no-accent-border';

  const title = document.createElement('div');
  title.className = 'procedure-card-title';
  title.textContent = `Các bước nộp hồ sơ: ${data.procedure_name || ''}`;
  card.appendChild(title);

  const list = document.createElement('ol');
  list.className = 'steps-list';
  for (const step of data.steps || []) {
    const li = document.createElement('li');
    li.textContent = step;
    list.appendChild(li);
  }
  card.appendChild(list);

  if (data.online_fee) {
    const fee = document.createElement('div');
    fee.className = 'fee-info';
    const feeText = data.online_fee.fee || 'Chưa rõ';
    const timeText = data.online_fee.time_text ? ` · Thời gian xử lý: ${data.online_fee.time_text}` : '';
    fee.textContent = `Phí/lệ phí nộp trực tuyến: ${feeText}${timeText}`;
    card.appendChild(fee);
  }

  if (data.href) {
    const link = document.createElement('a');
    link.href = data.href;
    link.target = '_blank';
    link.rel = 'noopener';
    link.className = 'link-btn submit-link-btn';
    link.textContent = 'Mở nơi nộp hồ sơ thủ tục';
    card.appendChild(link);
  } else {
    const note = document.createElement('div');
    note.className = 'steps-note';
    note.textContent = 'Chưa tra được đường dẫn chính thức, vui lòng tìm thủ tục này trực tiếp trên dichvucong.gov.vn.';
    card.appendChild(note);
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

function handleWsMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === 'audio') {
    playPcmChunk(msg.data);
  } else if (msg.type === 'procedure_info') {
    finalizeTurn();
    renderRequiredDocumentsCard(msg.data);
  } else if (msg.type === 'submission_steps') {
    finalizeTurn();
    renderSubmissionStepsCard(msg.data);
  } else if (msg.type === 'session_error') {
    statusEl.textContent = 'Lỗi: ' + msg.message;
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

function wsUrl(path) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${location.host}${path}`;
}

async function start() {
  idleGroup.hidden = true;
  chatCard.hidden = false;
  chatLog.innerHTML = '';
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
  finalizeTurn();
  setWaveState('idle');
  chatCard.hidden = true;
  idleGroup.hidden = false;
  ws = null;
}

startBtn.onclick = start;
stopBtn.onclick = stop;
talkBtn.onclick = toggleTalking;

document.addEventListener('keydown', (e) => {
  if ((e.key !== 'Enter' && e.key !== ' ' && e.code !== 'Space') || chatCard.hidden) return;
  e.preventDefault();
  if (e.repeat) return;
  toggleTalking();
});
