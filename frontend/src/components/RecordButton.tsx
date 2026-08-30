/** O1 — nút ghi âm lớn, trạng thái rõ ràng, VU meter, đồng hồ đếm thời lượng. */
import { useEffect, useState } from 'react'

import type { RecordingStatus } from '@/hooks/useVoiceStream'

interface RecordButtonProps {
  status: RecordingStatus
  volumeLevel: number
  recordingStartedAt: number | null
  lastError: string | null
  onStart: () => void
  onStop: () => void
}

function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000)
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const STATUS_LABEL: Record<RecordingStatus, string> = {
  idle: 'Sẵn sàng ghi âm',
  connecting: 'Đang kết nối...',
  recording: 'Đang ghi âm',
  processing: 'Đang xử lý...',
  error: 'Có lỗi xảy ra',
}

export function RecordButton({
  status,
  volumeLevel,
  recordingStartedAt,
  lastError,
  onStart,
  onStop,
}: RecordButtonProps) {
  // `null` khi chưa ghi âm — không cần state riêng cho trường hợp này, chỉ
  // effect chạy interval để cập nhật khi đang ghi (tránh setState đồng bộ
  // trong effect cho nhánh "reset về 0").
  const [elapsedMs, setElapsedMs] = useState<number | null>(null)

  useEffect(() => {
    if (recordingStartedAt === null) return
    const interval = window.setInterval(() => {
      setElapsedMs(Date.now() - recordingStartedAt)
    }, 250)
    return () => window.clearInterval(interval)
  }, [recordingStartedAt])

  const displayElapsedMs = recordingStartedAt === null ? 0 : (elapsedMs ?? 0)

  const isRecording = status === 'recording'
  const isBusy = status === 'connecting' || status === 'processing'

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        disabled={isBusy}
        onClick={isRecording ? onStop : onStart}
        className={`flex h-24 w-24 items-center justify-center rounded-full text-lg font-semibold text-white shadow-lg transition disabled:cursor-not-allowed disabled:opacity-60 ${
          isRecording ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
        }`}
        style={
          isRecording
            ? { boxShadow: `0 0 0 ${Math.min(volumeLevel * 60, 16)}px rgba(220, 38, 38, 0.3)` }
            : undefined
        }
        aria-label={isRecording ? 'Dừng ghi âm' : 'Bắt đầu ghi âm'}
      >
        {isRecording ? '⏹' : '🎙'}
      </button>

      <div className="text-center">
        <p className="text-base font-medium text-gray-800">{STATUS_LABEL[status]}</p>
        {isRecording && (
          <p className="text-2xl font-mono text-gray-600">{formatDuration(displayElapsedMs)}</p>
        )}
        {lastError && <p className="mt-1 max-w-xs text-base text-red-600">{lastError}</p>}
      </div>
    </div>
  )
}
