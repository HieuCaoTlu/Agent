/** N — Bảng điều khiển `/`: danh sách phiên gần đây, nút tạo phiên mới. */
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { sessionsApi } from '@/api/sessions'
import { LoadingIndicator } from '@/components/LoadingIndicator'
import type { SessionState } from '@/types/api'

const STATE_LABEL: Record<SessionState, string> = {
  CREATED: 'Mới tạo',
  LISTENING: 'Đang ghi âm',
  PROCEDURE_SELECTED: 'Đã chọn thủ tục',
  EXTRACTING: 'Đang trích xuất',
  SUGGESTED: 'Có gợi ý AI',
  AI_UNAVAILABLE: 'Nhập tay (AI lỗi)',
  REVIEWING: 'Đang đối chiếu',
  FIELDS_CONFIRMED: 'Đã xác nhận trường',
  READBACK: 'Đang đọc lại',
  CITIZEN_CONFIRMED: 'Người dân đã xác nhận',
  COMPLETED: 'Hoàn tất',
  CANCELLED: 'Đã hủy',
}

export function DashboardPage() {
  const { data: sessions, isLoading, error } = useQuery({
    queryKey: ['sessions', 'recent'],
    queryFn: () => sessionsApi.listRecent(),
  })

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Phiên hỗ trợ gần đây</h1>
        <Link
          to="/sessions/new"
          className="rounded bg-blue-600 px-4 py-2 text-base font-medium text-white hover:bg-blue-700"
        >
          + Tạo phiên mới
        </Link>
      </div>

      {isLoading && <LoadingIndicator label="Đang tải danh sách phiên..." />}
      {error && <p className="text-base text-red-600">Không tải được danh sách phiên.</p>}

      {sessions && sessions.length === 0 && (
        <p className="text-base text-gray-500">Chưa có phiên nào. Bấm "Tạo phiên mới" để bắt đầu.</p>
      )}

      <ul className="flex flex-col gap-2">
        {sessions?.map((session) => (
          <li key={session.id}>
            <Link
              to={`/sessions/${session.id}`}
              className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4 hover:bg-gray-50"
            >
              <div>
                <p className="text-base font-medium text-gray-900">
                  {session.procedure_code ?? '(chưa chọn thủ tục)'}
                </p>
                <p className="text-sm text-gray-500">
                  Cán bộ: {session.staff_name} · {new Date(session.started_at).toLocaleString('vi-VN')}
                </p>
              </div>
              <span className="rounded bg-gray-100 px-2 py-1 text-sm text-gray-700">
                {STATE_LABEL[session.state]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
