/** Hàm gọi API — nhóm phiên (J2). */
import { apiClient } from './client'
import type { CreateSessionRequest, Session, SessionStateSnapshot } from '@/types/api'

export const sessionsApi = {
  create: (body: CreateSessionRequest) => apiClient.post<Session>('/api/v1/sessions', body),
  get: (sessionId: string) =>
    apiClient.get<SessionStateSnapshot>(`/api/v1/sessions/${sessionId}`),
  listRecent: (limit = 50, offset = 0) =>
    apiClient.get<Session[]>(`/api/v1/sessions?limit=${limit}&offset=${offset}`),
  recordConsent: (sessionId: string, consented: boolean) =>
    apiClient.post<Session>(`/api/v1/sessions/${sessionId}/consent`, { consented }),
  selectProcedure: (sessionId: string, code: string) =>
    apiClient.post<Session>(`/api/v1/sessions/${sessionId}/procedure`, { code }),
  cancel: (sessionId: string, reason?: string) =>
    apiClient.post<Session>(`/api/v1/sessions/${sessionId}/cancel`, { reason: reason ?? null }),
  complete: (sessionId: string, dossierCode: string) =>
    apiClient.post<Session>(`/api/v1/sessions/${sessionId}/complete`, {
      dossier_code: dossierCode,
    }),
}
