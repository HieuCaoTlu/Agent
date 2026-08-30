/** Hàm gọi API — nhóm đọc lại và xác nhận (J6). */
import { apiClient } from './client'
import type { CitizenConfirmation, ReadbackOutcome } from '@/types/api'

export const readbackApi = {
  generate: (sessionId: string) =>
    apiClient.post<ReadbackOutcome>(`/api/v1/sessions/${sessionId}/readback`),
  audioUrl: (sessionId: string) => `/api/v1/sessions/${sessionId}/readback/audio`,
  fetchAudio: (sessionId: string) =>
    apiClient.blob(`/api/v1/sessions/${sessionId}/readback/audio`),
  confirmByCitizen: (
    sessionId: string,
    params: {
      confirmed: boolean
      readbackText: string
      staffName: string
      note?: string
      readbackMethod?: string
    },
  ) =>
    apiClient.post<CitizenConfirmation>(`/api/v1/sessions/${sessionId}/citizen-confirm`, {
      confirmed: params.confirmed,
      readback_text: params.readbackText,
      staff_name: params.staffName,
      note: params.note ?? null,
      readback_method: params.readbackMethod ?? null,
    }),
}
