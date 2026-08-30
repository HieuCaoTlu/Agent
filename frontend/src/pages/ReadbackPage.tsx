/** N — Đọc lại `/sessions/:id/readback`: phát audio (hoặc hiện text nếu TTS lỗi, L1), nút xác nhận/từ chối. */
import { useEffect, useRef, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'

import { readbackApi } from '@/api/readback'
import { LoadingIndicator } from '@/components/LoadingIndicator'
import { useSession } from '@/hooks/useSession'

export function ReadbackPage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const { data: snapshot } = useSession(sessionId)
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)

  const readback = useMutation({
    mutationFn: () => readbackApi.generate(sessionId as string),
  })

  useEffect(() => {
    if (sessionId) readback.mutate()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId])

  const outcome = readback.data

  useEffect(() => {
    if (!outcome?.audio_available || !sessionId) return
    let objectUrl: string | null = null
    void readbackApi.fetchAudio(sessionId).then((blob) => {
      objectUrl = URL.createObjectURL(blob)
      setAudioUrl(objectUrl)
    })
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [outcome?.audio_available, outcome?.readback_round, sessionId])

  const confirm = useMutation({
    mutationFn: (confirmed: boolean) =>
      readbackApi.confirmByCitizen(sessionId as string, {
        confirmed,
        readbackText: outcome?.text ?? '',
        staffName: snapshot?.session.staff_name ?? '',
      }),
    onSuccess: (_, confirmed) => {
      if (confirmed) {
        navigate(`/sessions/${sessionId}/complete`)
      } else {
        navigate(`/sessions/${sessionId}`)
      }
    },
  })

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-bold text-gray-900">Đọc lại cho người dân</h1>

      {readback.isPending && <LoadingIndicator label="Đang chuẩn bị nội dung đọc lại..." />}
      {readback.isError && (
        <p className="text-base text-red-600">Không tạo được nội dung đọc lại — vui lòng thử lại.</p>
      )}

      {outcome && (
        <div className="flex flex-col gap-4">
          {outcome.used_fallback && (
            <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-base text-amber-800">
              ⚠ Không tạo được giọng đọc (TTS lỗi) — hãy đọc trực tiếp nội dung dưới đây cho người
              dân nghe.
            </p>
          )}

          <div className="rounded-lg border border-gray-200 bg-white p-4">
            <p className="whitespace-pre-line text-lg leading-relaxed text-gray-800">
              {outcome.text}
            </p>
          </div>

          {outcome.audio_available && audioUrl && (
            <audio ref={audioRef} controls src={audioUrl} className="w-full">
              <track kind="captions" />
            </audio>
          )}

          <div className="flex gap-3">
            <button
              type="button"
              className="flex-1 rounded bg-green-600 px-4 py-3 text-base font-semibold text-white hover:bg-green-700 disabled:opacity-50"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(true)}
            >
              ✓ Người dân xác nhận đúng
            </button>
            <button
              type="button"
              className="flex-1 rounded border border-red-300 px-4 py-3 text-base font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50"
              disabled={confirm.isPending}
              onClick={() => confirm.mutate(false)}
            >
              ✗ Cần sửa lại
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
