/** O4 — hộp thoại xác nhận cho thao tác quan trọng (hủy phiên, hoàn tất). */
interface ConfirmDialogProps {
  open: boolean
  title: string
  message: string
  confirmLabel?: string
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Xác nhận',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 className="mb-2 text-lg font-semibold text-gray-900">{title}</h2>
        <p className="mb-4 text-base text-gray-700">{message}</p>
        <div className="flex justify-end gap-3">
          <button
            type="button"
            className="rounded border border-gray-300 px-4 py-2 text-base text-gray-700 hover:bg-gray-50"
            onClick={onCancel}
          >
            Hủy
          </button>
          <button
            type="button"
            className="rounded bg-red-600 px-4 py-2 text-base text-white hover:bg-red-700"
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
