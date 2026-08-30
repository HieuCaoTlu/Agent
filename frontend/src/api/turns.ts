/** Hàm gọi API — nhóm lượt thoại (J3). */
import { apiClient } from './client'
import type { VoiceTurn } from '@/types/api'

export const turnsApi = {
  list: (sessionId: string) =>
    apiClient.get<VoiceTurn[]>(`/api/v1/sessions/${sessionId}/turns`),
  editTranscript: (sessionId: string, turnId: string, newText: string, staffName: string) =>
    apiClient.patch<VoiceTurn>(`/api/v1/sessions/${sessionId}/turns/${turnId}`, {
      new_text: newText,
      staff_name: staffName,
    }),
  flag: (sessionId: string, turnId: string, staffName: string) =>
    apiClient.post<VoiceTurn>(`/api/v1/sessions/${sessionId}/turns/${turnId}/flag`, {
      staff_name: staffName,
    }),
}
