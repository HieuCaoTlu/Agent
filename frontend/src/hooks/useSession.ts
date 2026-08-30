/** Hook M3 — lấy và cache trạng thái phiên (`SessionStateSnapshot`). */
import { useQuery, useQueryClient } from '@tanstack/react-query'

import { sessionsApi } from '@/api/sessions'

export function sessionQueryKey(sessionId: string) {
  return ['session', sessionId] as const
}

export function useSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionQueryKey(sessionId ?? ''),
    queryFn: () => sessionsApi.get(sessionId as string),
    enabled: Boolean(sessionId),
  })
}

/** Buộc làm mới `useSession` sau một thao tác thay đổi trạng thái phiên. */
export function useInvalidateSession() {
  const queryClient = useQueryClient()
  return (sessionId: string) =>
    queryClient.invalidateQueries({ queryKey: sessionQueryKey(sessionId) })
}
