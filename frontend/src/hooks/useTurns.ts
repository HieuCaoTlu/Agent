/** Hook M3 — danh sách lượt thoại của một phiên (O2). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { turnsApi } from '@/api/turns'

function turnsQueryKey(sessionId: string) {
  return ['turns', sessionId] as const
}

export function useTurns(sessionId: string | undefined) {
  return useQuery({
    queryKey: turnsQueryKey(sessionId ?? ''),
    queryFn: () => turnsApi.list(sessionId as string),
    enabled: Boolean(sessionId),
  })
}

export function useEditTranscript(sessionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({
      turnId,
      newText,
      staffName,
    }: {
      turnId: string
      newText: string
      staffName: string
    }) => turnsApi.editTranscript(sessionId, turnId, newText, staffName),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: turnsQueryKey(sessionId) }),
  })
}

export function useFlagTranscript(sessionId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ turnId, staffName }: { turnId: string; staffName: string }) =>
      turnsApi.flag(sessionId, turnId, staffName),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: turnsQueryKey(sessionId) }),
  })
}
