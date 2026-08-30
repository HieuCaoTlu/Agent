/** Hàm gọi API — nhóm thủ tục (J1). */
import { apiClient } from './client'
import type { ProcedureDetail, ProcedureSummary } from '@/types/api'

export const proceduresApi = {
  list: () => apiClient.get<ProcedureSummary[]>('/api/v1/procedures'),
  get: (code: string) => apiClient.get<ProcedureDetail>(`/api/v1/procedures/${code}`),
}
