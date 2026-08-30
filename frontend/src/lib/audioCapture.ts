/**
 * Ghi âm micro → PCM 16kHz/mono/16-bit thô — Mục M4 của Checklist.
 *
 * Blaze STT streaming yêu cầu định dạng này chính xác; thiết bị thường mặc
 * định 44.1kHz/48kHz nên cần resample. Dùng linear interpolation đơn giản
 * (đủ tốt cho giọng nói, không cần bộ lọc chống alias phức tạp ở MVP).
 */

const TARGET_SAMPLE_RATE = 16_000

export interface AudioCaptureHandle {
  stop: () => void
  /** Mức âm lượng tức thời [0, 1] — cho O1 hiển thị VU meter. */
  getVolumeLevel: () => number
}

function resampleTo16k(input: Float32Array, inputSampleRate: number): Float32Array {
  if (inputSampleRate === TARGET_SAMPLE_RATE) return input
  const ratio = inputSampleRate / TARGET_SAMPLE_RATE
  const outputLength = Math.floor(input.length / ratio)
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i++) {
    const srcIndex = i * ratio
    const lower = Math.floor(srcIndex)
    const upper = Math.min(lower + 1, input.length - 1)
    const weight = srcIndex - lower
    output[i] = input[lower] * (1 - weight) + input[upper] * weight
  }
  return output
}

function floatTo16BitPcm(input: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(input.length * 2)
  const view = new DataView(buffer)
  for (let i = 0; i < input.length; i++) {
    const clamped = Math.max(-1, Math.min(1, input[i]))
    view.setInt16(i * 2, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
  }
  return buffer
}

function toBase64(buffer: ArrayBuffer): string {
  let binary = ''
  const bytes = new Uint8Array(buffer)
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
  return btoa(binary)
}

/**
 * Bắt đầu ghi âm; `onChunk` nhận chuỗi base64 sẵn để gửi qua WebSocket
 * (`{"type": "audio", "data": ...}`, giao thức K/Plan.MD 9.2).
 */
export async function startAudioCapture(
  onChunk: (base64Pcm: string) => void,
): Promise<AudioCaptureHandle> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const audioContext = new AudioContext()
  await audioContext.audioWorklet.addModule('/pcm-worklet.js')

  const source = audioContext.createMediaStreamSource(stream)
  const worklet = new AudioWorkletNode(audioContext, 'pcm-capture-processor')

  let volumeLevel = 0

  worklet.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const samples = event.data
    // RMS đơn giản cho VU meter (O1) — không cần chính xác, chỉ cần phản hồi trực quan.
    let sumSquares = 0
    for (let i = 0; i < samples.length; i++) sumSquares += samples[i] * samples[i]
    volumeLevel = Math.sqrt(sumSquares / samples.length)

    const resampled = resampleTo16k(samples, audioContext.sampleRate)
    const pcm16 = floatTo16BitPcm(resampled)
    onChunk(toBase64(pcm16))
  }

  source.connect(worklet)

  return {
    stop: () => {
      worklet.disconnect()
      source.disconnect()
      stream.getTracks().forEach((track) => track.stop())
      void audioContext.close()
    },
    getVolumeLevel: () => volumeLevel,
  }
}
