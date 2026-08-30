/** O4 — thanh tiến độ "Đã xác nhận N/M trường bắt buộc". */
export function ProgressBar({ confirmed, total }: { confirmed: number; total: number }) {
  const percent = total === 0 ? 0 : Math.round((confirmed / total) * 100)
  return (
    <div>
      <p className="mb-1 text-base text-gray-700">
        Đã xác nhận {confirmed}/{total} trường bắt buộc
      </p>
      <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full bg-green-600 transition-all"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  )
}
