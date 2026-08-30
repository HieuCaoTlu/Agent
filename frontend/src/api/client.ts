/**
 * HTTP client dùng chung — Mục M2 của Checklist.
 *
 * Bọc `fetch`, xử lý lỗi thống nhất (parse `ApiErrorBody` của backend —
 * `app/api/schemas.py::ErrorResponse`), tự sinh `X-Request-ID` mỗi request
 * (khớp `request_id` mà backend trả về trong lỗi — giúp đối chiếu log hai
 * phía khi gỡ lỗi).
 */

import type { ApiErrorBody } from '@/types/api'

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly requestId: string
  readonly fallbackAvailable: boolean

  constructor(status: number, body: ApiErrorBody) {
    super(body.error.message)
    this.name = 'ApiError'
    this.code = body.error.code
    this.status = status
    this.requestId = body.error.request_id
    this.fallbackAvailable = body.error.fallback_available
  }
}

function createRequestId(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `req-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
}

/** Gọi API JSON — dùng cho mọi endpoint trừ tải audio nhị phân (xem `fetchBlob`). */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      'X-Request-ID': createRequestId(),
    },
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    if (body?.error) {
      throw new ApiError(response.status, body)
    }
    throw new Error(`Yêu cầu thất bại (HTTP ${response.status}).`)
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

/** Tải nội dung nhị phân (audio đọc lại, J6/L1) — không parse JSON. */
async function fetchBlob(path: string, signal?: AbortSignal): Promise<Blob> {
  const response = await fetch(path, {
    headers: { 'X-Request-ID': createRequestId() },
    signal,
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as ApiErrorBody | null
    if (body?.error) {
      throw new ApiError(response.status, body)
    }
    throw new Error(`Yêu cầu thất bại (HTTP ${response.status}).`)
  }
  return response.blob()
}

export const apiClient = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { method: 'GET', signal }),
  post: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'POST', body, signal }),
  patch: <T>(path: string, body?: unknown, signal?: AbortSignal) =>
    request<T>(path, { method: 'PATCH', body, signal }),
  blob: fetchBlob,
}
