const idleCard = document.getElementById('idleCard');
const chatCard = document.getElementById('chatCard');
const wave = document.getElementById('wave');
const statusEl = document.getElementById('status');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const chatLog = document.getElementById('chatLog');

let ws = null;
let audioContext = null;
let micStream = null;
let workletNode = null;

// Bubble transcript đang stream dở (chưa turn_complete) — gom nhiều mẩu
// text nhỏ Gemini gửi dần vào một bong bóng chat duy nhất mỗi lượt.
let pendingUserBubble = null;
let pendingAiBubble = null;

function setWaveState(state) {
  wave.className = 'wave ' + state; // idle | listening | speaking
}

function appendTranscript(text, who) {
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
}

// Card trực quan cho danh sách giấy tờ (dossier_cases đã parse sẵn ở
// build_index.py) — dữ liệu CÓ CẤU TRÚC THẬT từ RAG, không đoán/parse
// ngược từ lời AI nói (transcript giọng nói không đáng tin cậy cho việc
// này). Chèn như một phần tử riêng trong chat log, không phải bubble text.
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

// --- Phát audio trả lời của AI (PCM 24kHz mono từ Gemini Live API) ---
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

  const startAt = Math.max(nextPlayTime, playbackContext.currentTime);
  source.start(startAt);
  nextPlayTime = startAt + buffer.duration;

  setWaveState('speaking');
  source.onended = () => {
    if (playbackContext.currentTime >= nextPlayTime - 0.05) {
      setWaveState('idle');
    }
  };
}

// --- Ghi âm micro, resample về 16kHz PCM, gửi qua WebSocket ---
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

async function start() {
  idleCard.hidden = true;
  chatCard.hidden = false;
  chatLog.innerHTML = '';
  setWaveState('idle');
  statusEl.textContent = 'Đang kết nối...';

  ws = new WebSocket(`ws://${location.host}/ws`);

  ws.onopen = async () => {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule('/worklet.js');

    const source = audioContext.createMediaStreamSource(micStream);
    workletNode = new AudioWorkletNode(audioContext, 'mic-processor');
    workletNode.port.onmessage = (e) => {
      const resampled = resampleTo16k(e.data, audioContext.sampleRate);
      const pcm = floatTo16BitPcm(resampled);
      ws.send(JSON.stringify({ type: 'audio', data: toBase64(pcm) }));
    };
    source.connect(workletNode);

    statusEl.textContent = 'Đang lắng nghe...';
    setWaveState('idle');
  };

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'audio') {
      playPcmChunk(msg.data);
    } else if (msg.type === 'user_speaking_start') {
      statusEl.textContent = 'Đang nghe bạn nói...';
      setWaveState('listening');
    } else if (msg.type === 'user_speaking_end') {
      statusEl.textContent = 'Đang suy nghĩ...';
      setWaveState('idle');
    } else if (msg.type === 'searching') {
      statusEl.textContent = 'Đang tra cứu thông tin thủ tục...';
    } else if (msg.type === 'procedure_card') {
      finalizeTurn(); // card đứng riêng, không gộp chung bubble text trước/sau nó
      renderProcedureCard(msg.data);
    } else if (msg.type === 'user_transcript') {
      appendTranscript(msg.text, 'user');
    } else if (msg.type === 'ai_transcript') {
      appendTranscript(msg.text, 'ai');
    } else if (msg.type === 'turn_complete') {
      finalizeTurn();
      statusEl.textContent = 'Đang lắng nghe...';
      setWaveState('idle');
    } else if (msg.type === 'interrupted') {
      finalizeTurn();
      statusEl.textContent = 'Đang lắng nghe...';
      setWaveState('idle');
      nextPlayTime = playbackContext ? playbackContext.currentTime : 0;
    }
  };

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
  // Đóng luôn ngữ cảnh phát audio trả lời của AI — nếu không, mọi audio đã
  // enqueue qua source.start() (kể cả AI đang nói dở) vẫn tiếp tục phát ra
  // loa sau khi bấm "Kết thúc hỗ trợ".
  if (playbackContext) {
    playbackContext.close();
    playbackContext = null;
  }
  nextPlayTime = 0;
  finalizeTurn();
  setWaveState('idle');
  chatCard.hidden = true;
  idleCard.hidden = false;
  ws = null;
}

startBtn.onclick = start;
stopBtn.onclick = stop;
