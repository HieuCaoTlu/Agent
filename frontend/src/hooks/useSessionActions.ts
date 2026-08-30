/** Hook M3 — mutation cho vòng đời phiên (tạo, đồng ý, chọn thủ tục, hủy, hoàn tất). */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { sessionsApi } from '@/api/sessions'
import { sessionQueryKey } from '@/hooks/useSession'
import type { CreateSessionRequest } from '@/types/api'

export function useCreateSession() {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (body: CreateSessionRequest) => sessionsApi.create(body),
    onSuccess: (session) => navigate(`/sessions/${session.id}`),
  })
}

export function useRecordConsent(sessionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (consented: boolean) => sessionsApi.recordConsent(sessionId, consented),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionQueryKey(sessionId) }),
  })
}

export function useSelectProcedure(sessionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => sessionsApi.selectProcedure(sessionId, code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionQueryKey(sessionId) }),
  })
}

export function useCancelSession(sessionId: string) {
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (reason?: string) => sessionsApi.cancel(sessionId, reason),
    onSuccess: () => navigate('/'),
  })
}

export function useCompleteSession(sessionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (dossierCode: string) => sessionsApi.complete(sessionId, dossierCode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: sessionQueryKey(sessionId) }),
  })
}
