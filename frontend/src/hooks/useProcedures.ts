/** Hook M3 — danh mục thủ tục (ít thay đổi trong ngày, cache lâu hơn mặc định). */
import { useQuery } from '@tanstack/react-query'

import { proceduresApi } from '@/api/procedures'

export function useProcedures() {
  return useQuery({
    queryKey: ['procedures'],
    queryFn: proceduresApi.list,
    staleTime: 5 * 60_000,
  })
}

export function useProcedureDetail(code: string | undefined) {
  return useQuery({
    queryKey: ['procedure', code],
    queryFn: () => proceduresApi.get(code as string),
    enabled: Boolean(code),
    staleTime: 5 * 60_000,
  })
}
