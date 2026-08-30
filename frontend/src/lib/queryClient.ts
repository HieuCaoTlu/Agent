import { QueryClient } from '@tanstack/react-query'

/**
 * Cấu hình TanStack Query dùng chung (M3). `refetchOnWindowFocus: false` vì
 * cán bộ làm việc trên một phiên duy nhất trong thời gian dài — làm mới ngầm
 * khi chuyển tab có thể ghi đè dữ liệu vừa nhập tay chưa kịp lưu.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 5_000,
    },
  },
})
