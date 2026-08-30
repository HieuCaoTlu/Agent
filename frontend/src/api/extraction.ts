/** Hàm gọi API — nhóm trích xuất (J4). */
import { apiClient } from './client'
import type { Extraction } from '@/types/api'

export const extractionApi = {
  extract: (sessionId: string, includeTurns: number[], onlyMissing = false) =>
    apiClient.post<Extraction>(`/api/v1/sessions/${sessionId}/extract`, {
      include_turns: includeTurns,
      only_missing: onlyMissing,
    }),
  history: (sessionId: string) =>
    apiClient.get<Extraction[]>(`/api/v1/sessions/${sessionId}/extractions`),
}
