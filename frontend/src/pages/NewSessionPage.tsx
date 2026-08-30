/** N — Tạo phiên `/sessions/new`: chọn chế độ, ghi nhận đồng ý của người dân. */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { sessionsApi } from '@/api/sessions'
import { useMutation } from '@tanstack/react-query'

export function NewSessionPage() {
  const [staffName, setStaffName] = useState('')
  const [mode, setMode] = useState<'ai_assisted' | 'manual'>('ai_assisted')
  const [consented, setConsented] = useState(false)
  const navigate = useNavigate()

  // Tạo phiên rồi ghi nhận đồng ý ngay trong cùng một thao tác gửi form —
  // hai lời gọi API riêng biệt (J2: POST /sessions, POST /sessions/{id}/consent)
  // vì backend tách bạch việc tạo phiên khỏi việc ghi nhận đồng ý.
  const createSession = useMutation({
    mutationFn: async () => {
      const session = await sessionsApi.create({ staff_name: staffName.trim(), mode })
      await sessionsApi.recordConsent(session.id, consented)
      return session
    },
    onSuccess: (session) => navigate(`/sessions/${session.id}`),
  })

  const canSubmit = staffName.trim().length > 0 && consented

  return (
    <div className="mx-auto max-w-lg p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-900">Tạo phiên hỗ trợ mới</h1>

      <form
        className="flex flex-col gap-5"
        onSubmit={(e) => {
          e.preventDefault()
          if (!canSubmit) return
          createSession.mutate()
        }}
      >
        <div>
          <label className="mb-1 block text-base font-medium text-gray-800">Tên cán bộ hỗ trợ</label>
          <input
            type="text"
            className="w-full rounded border border-gray-300 p-2 text-base"
            value={staffName}
            onChange={(e) => setStaffName(e.target.value)}
            placeholder="Ví dụ: Nguyễn Văn A"
          />
        </div>

        <div>
          <label className="mb-1 block text-base font-medium text-gray-800">Chế độ hỗ trợ</label>
          <div className="flex gap-4">
            <label className="flex items-center gap-2 text-base">
              <input
                type="radio"
                checked={mode === 'ai_assisted'}
                onChange={() => setMode('ai_assisted')}
              />
              Có trợ lý AI
            </label>
            <label className="flex items-center gap-2 text-base">
              <input type="radio" checked={mode === 'manual'} onChange={() => setMode('manual')} />
              Nhập tay hoàn toàn
            </label>
          </div>
        </div>

        <label className="flex items-start gap-2 rounded-lg border border-gray-200 bg-gray-50 p-3 text-base">
          <input
            type="checkbox"
            className="mt-1 h-5 w-5"
            checked={consented}
            onChange={(e) => setConsented(e.target.checked)}
          />
          <span>
            Người dân đã được thông báo và đồng ý cho việc ghi âm, xử lý bằng AI để hỗ trợ kê khai
            hồ sơ.
          </span>
        </label>

        {createSession.isError && (
          <p className="text-base text-red-600">Không tạo được phiên — vui lòng thử lại.</p>
        )}

        <button
          type="submit"
          disabled={!canSubmit || createSession.isPending}
          className="rounded bg-blue-600 px-4 py-3 text-base font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {createSession.isPending ? 'Đang tạo...' : 'Bắt đầu phiên'}
        </button>
      </form>
    </div>
  )
}
