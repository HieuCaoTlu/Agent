/**
 * AudioWorkletProcessor — Mục M4 của Checklist.
 *
 * Blaze STT streaming yêu cầu PCM thô 16kHz/mono/16-bit — `MediaRecorder`
 * không dùng được vì nó encode sang WebM/Opus. `AudioWorklet` chạy trên
 * audio thread riêng, nhận block Float32 (thường 128 sample/lần ở sample
 * rate gốc của thiết bị — 44.1kHz/48kHz), gửi thẳng ra main thread qua
 * `port.postMessage` để main thread resample + encode Int16 (xem
 * `src/lib/audioCapture.ts` — resample trên audio thread bằng vòng lặp mẫu
 * từng frame tốn CPU hơn cần thiết cho một worklet chạy liên tục).
 */
class PcmCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const channelData = inputs[0]?.[0]
    if (channelData && channelData.length > 0) {
      // Bản sao — buffer gốc bị AudioWorklet tái sử dụng ngay sau lần gọi này.
      this.port.postMessage(channelData.slice())
    }
    return true
  }
}

registerProcessor('pcm-capture-processor', PcmCaptureProcessor)
