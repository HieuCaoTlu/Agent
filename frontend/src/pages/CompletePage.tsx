/** N — Hoàn tất `/sessions/:id/complete`: nhập mã hồ sơ, kết thúc phiên. */
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { useCompleteSession } from '@/hooks/useSessionActions'

export function CompletePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [dossierCode, setDossierCode] = useState('')
  const completeSession = useCompleteSession(sessionId ?? '')

  return (
    <div className="mx-auto max-w-lg p-6">
      <h1 className="mb-4 text-2xl font-bold text-gray-900">Hoàn tất phiên</h1>
      <p className="mb-4 text-base text-gray-600">
        Nhập mã hồ sơ được cấp sau khi nộp lên Cổng dịch vụ công để kết thúc phiên hỗ trợ.
      </p>

      <form
        className="flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault()
          if (!dossierCode.trim()) return
          completeSession.mutate(dossierCode.trim(), {
            onSuccess: () => navigate('/'),
          })
        }}
      >
        <div>
          <label className="mb-1 block text-base font-medium text-gray-800">Mã hồ sơ</label>
          <input
            type="text"
            className="w-full rounded border border-gray-300 p-2 text-base"
            value={dossierCode}
            onChange={(e) => setDossierCode(e.target.value)}
            placeholder="Ví dụ: HS-2026-000123"
          />
        </div>

        {completeSession.isError && (
          <p className="text-base text-red-600">Không hoàn tất được phiên — vui lòng thử lại.</p>
        )}

        <button
          type="submit"
          disabled={!dossierCode.trim() || completeSession.isPending}
          className="rounded bg-green-600 px-4 py-3 text-base font-semibold text-white hover:bg-green-700 disabled:opacity-50"
        >
          {completeSession.isPending ? 'Đang lưu...' : 'Kết thúc phiên'}
        </button>
      </form>
    </div>
  )
}
