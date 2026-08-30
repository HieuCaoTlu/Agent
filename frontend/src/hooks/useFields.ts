/** Hook M3 — trạng thái các trường dữ liệu của một phiên. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { extractionApi } from '@/api/extraction'
import { fieldsApi } from '@/api/fields'
import { sessionQueryKey } from '@/hooks/useSession'

function fieldsQueryKey(sessionId: string) {
  return ['fields', sessionId] as const
}

export function useFields(sessionId: string | undefined) {
  return useQuery({
    queryKey: fieldsQueryKey(sessionId ?? ''),
    queryFn: () => fieldsApi.list(sessionId as string),
    enabled: Boolean(sessionId),
  })
}

/**
 * Sau bất kỳ thao tác nào làm đổi field_states (xác nhận, sửa, trích xuất
 * lại...), làm mới cả `fields` lẫn `session` (vì `SessionStateSnapshot`
 * cũng chứa `field_states` + `warnings` tính lại — M3: "tự động làm mới dữ
 * liệu phiên sau mỗi thao tác").
 */
function useInvalidateFieldsAndSession(sessionId: string) {
  const queryClient = useQueryClient()
  return () => {
    queryClient.invalidateQueries({ queryKey: fieldsQueryKey(sessionId) })
    queryClient.invalidateQueries({ queryKey: sessionQueryKey(sessionId) })
  }
}

export function useConfirmField(sessionId: string) {
  const invalidate = useInvalidateFieldsAndSession(sessionId)
  return useMutation({
    mutationFn: ({
      fieldName,
      value,
      staffName,
    }: {
      fieldName: string
      value: string
      staffName: string
    }) => fieldsApi.confirm(sessionId, fieldName, value, staffName),
    onSuccess: invalidate,
  })
}

export function useUnconfirmField(sessionId: string) {
  const invalidate = useInvalidateFieldsAndSession(sessionId)
  return useMutation({
    mutationFn: (fieldName: string) => fieldsApi.unconfirm(sessionId, fieldName),
    onSuccess: invalidate,
  })
}

export function useAmendField(sessionId: string) {
  const invalidate = useInvalidateFieldsAndSession(sessionId)
  return useMutation({
    mutationFn: ({
      fieldName,
      transcriptTurns,
    }: {
      fieldName: string
      transcriptTurns: string[]
    }) => fieldsApi.amend(sessionId, fieldName, transcriptTurns),
    onSuccess: invalidate,
  })
}

export function useExtract(sessionId: string) {
  const invalidate = useInvalidateFieldsAndSession(sessionId)
  return useMutation({
    mutationFn: ({
      includeTurns,
      onlyMissing,
    }: {
      includeTurns: number[]
      onlyMissing?: boolean
    }) => extractionApi.extract(sessionId, includeTurns, onlyMissing),
    onSuccess: invalidate,
  })
}
