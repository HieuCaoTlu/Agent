/** O5 — hiển thị trạng thái đang tải cho mọi thao tác bất đồng bộ. */
export function LoadingIndicator({ label = 'Đang tải...' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-base text-gray-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600" />
      {label}
    </div>
  )
}
