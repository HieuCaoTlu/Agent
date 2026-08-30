/**
 * Hook M4 — WebSocket giọng nói `/api/v1/sessions/{id}/voice` (giao thức K,
 * Plan.MD 9.2). Điều phối vòng đời ghi âm: xin quyền micro, ghi PCM qua
 * `AudioWorklet`, gửi từng chunk, nhận `partial`/`final`/`error`, tự kết
 * nối lại khi mất kết nối đột ngột (không phải do người dùng chủ động dừng).
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { startAudioCapture, type AudioCaptureHandle } from '@/lib/audioCapture'

export type RecordingStatus = 'idle' | 'connecting' | 'recording' | 'processing' | 'error'

interface VoiceStreamState {
  status: RecordingStatus
  partialText: string
  lastError: string | null
  volumeLevel: number
}

export interface UseVoiceStreamResult extends VoiceStreamState {
  start: () => Promise<void>
  stop: () => void
  /** Chỉ có ý nghĩa khi status === 'recording' — dùng cho đồng hồ đếm thời lượng (O1). */
  recordingStartedAt: number | null
}

const MAX_RECONNECT_ATTEMPTS = 3

export function useVoiceStream(
  sessionId: string,
  onFinalTurn: (turnNumber: number, text: string) => void,
): UseVoiceStreamResult {
  const [state, setState] = useState<VoiceStreamState>({
    status: 'idle',
    partialText: '',
    lastError: null,
    volumeLevel: 0,
  })
  const [recordingStartedAt, setRecordingStartedAt] = useState<number | null>(null)

  const wsRef = useRef<WebSocket | null>(null)
  const captureRef = useRef<AudioCaptureHandle | null>(null)
  const userStoppedRef = useRef(false)
  const reconnectAttemptsRef = useRef(0)
  const volumeIntervalRef = useRef<number | null>(null)
  // `ws.onclose` cần gọi lại `connect` khi tự động kết nối lại — giữ tham
  // chiếu qua ref thay vì đóng trực tiếp vào `connect` (đang được định nghĩa
  // bên dưới) để tránh đọc biến khi nó chưa khởi tạo xong.
  const connectRef = useRef<() => Promise<void>>(async () => {})

  const cleanupAudio = useCallback(() => {
    captureRef.current?.stop()
    captureRef.current = null
    if (volumeIntervalRef.current !== null) {
      window.clearInterval(volumeIntervalRef.current)
      volumeIntervalRef.current = null
    }
  }, [])

  const stop = useCallback(() => {
    userStoppedRef.current = true
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))
    }
    cleanupAudio()
    setState((s) => ({ ...s, status: 'processing' }))
    setRecordingStartedAt(null)
  }, [cleanupAudio])

  const connect = useCallback(async () => {
    userStoppedRef.current = false
    setState((s) => ({ ...s, status: 'connecting', lastError: null }))

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/v1/sessions/${sessionId}/voice`)
    wsRef.current = ws

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0
      ws.send(JSON.stringify({ type: 'start' }))
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data as string) as
        | { type: 'partial'; text: string }
        | { type: 'final'; turn_id: string; turn_number: number; text: string }
        | { type: 'error'; code: string; message: string }
        | { type: 'audio_deleted'; turn_id: string }

      if (message.type === 'partial') {
        setState((s) => ({ ...s, status: 'recording', partialText: message.text }))
      } else if (message.type === 'final') {
        onFinalTurn(message.turn_number, message.text)
        setState((s) => ({ ...s, partialText: '' }))
      } else if (message.type === 'error') {
        // RECORDING_TIMEOUT (L2): backend tự chốt lượt, không đóng kết nối —
        // quay về 'idle' để cán bộ có thể bấm ghi âm lượt kế tiếp ngay.
        setState((s) => ({ ...s, status: 'idle', lastError: message.message }))
        cleanupAudio()
        setRecordingStartedAt(null)
      } else if (message.type === 'audio_deleted') {
        setState((s) => ({ ...s, status: 'idle' }))
      }
    }

    ws.onclose = () => {
      cleanupAudio()
      if (userStoppedRef.current) {
        setState((s) => ({ ...s, status: 'idle' }))
        return
      }
      // Mất kết nối đột ngột (M4: "xử lý mất kết nối, tự động kết nối lại").
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current += 1
        window.setTimeout(() => void connectRef.current(), 1000 * reconnectAttemptsRef.current)
      } else {
        setState((s) => ({
          ...s,
          status: 'error',
          lastError: 'Mất kết nối tới máy chủ ghi âm, đã thử kết nối lại nhiều lần.',
        }))
        setRecordingStartedAt(null)
      }
    }

    ws.onerror = () => {
      // Sự kiện `error` của WebSocket không mang thông tin — `onclose` sẽ
      // theo sau và xử lý reconnect/thông báo lỗi thật sự.
    }

    try {
      const capture = await startAudioCapture((base64Pcm) => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'audio', data: base64Pcm }))
        }
      })
      captureRef.current = capture
      volumeIntervalRef.current = window.setInterval(() => {
        setState((s) => ({ ...s, volumeLevel: capture.getVolumeLevel() }))
      }, 100)
      setRecordingStartedAt(Date.now())
      setState((s) => ({ ...s, status: 'recording' }))
    } catch {
      // Trình duyệt từ chối quyền micro (O1: "thông báo rõ khi trình duyệt
      // từ chối quyền micro").
      setState((s) => ({
        ...s,
        status: 'error',
        lastError: 'Không thể truy cập micro — hãy cấp quyền truy cập micro cho trình duyệt.',
      }))
      ws.close()
    }
  }, [sessionId, onFinalTurn, cleanupAudio])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    return () => {
      userStoppedRef.current = true
      cleanupAudio()
      wsRef.current?.close()
    }
  }, [cleanupAudio])

  return { ...state, start: connect, stop, recordingStartedAt }
}
