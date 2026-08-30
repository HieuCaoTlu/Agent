/**
 * Hàm gọi API — nhóm trường dữ liệu (J5).
 *
 * Cố ý KHÔNG có hàm "xác nhận tất cả" — không có endpoint tương ứng ở
 * backend (NT-1/NT-3, xem `app/api/routers/fields.py`). Component O3/O5
 * không được thêm nút nào gọi vòng lặp `confirm` cho mọi trường cùng lúc.
 */
import { apiClient } from './client'
import type { Extraction, FieldState, FieldWithValidation } from '@/types/api'

export const fieldsApi = {
  list: (sessionId: string) =>
    apiClient.get<FieldWithValidation[]>(`/api/v1/sessions/${sessionId}/fields`),
  confirm: (sessionId: string, fieldName: string, value: string, staffName: string) =>
    apiClient.post<FieldState>(`/api/v1/sessions/${sessionId}/fields/${fieldName}/confirm`, {
      value,
      staff_name: staffName,
    }),
  unconfirm: (sessionId: string, fieldName: string) =>
    apiClient.post<FieldState>(`/api/v1/sessions/${sessionId}/fields/${fieldName}/unconfirm`),
  amend: (sessionId: string, fieldName: string, transcriptTurns: string[]) =>
    apiClient.post<Extraction>(`/api/v1/sessions/${sessionId}/fields/${fieldName}/amend`, {
      transcript_turns: transcriptTurns,
    }),
}
