/** O4 — banner "Chế độ nhập tay" khi AI không khả dụng (session.state === AI_UNAVAILABLE, L1). */
export function ManualModeBanner() {
  return (
    <div className="rounded-lg border border-amber-400 bg-amber-50 p-3 text-base font-medium text-amber-800">
      ⚠ Chế độ nhập tay — AI trích xuất hiện không khả dụng. Cán bộ nhập trực tiếp giá trị các
      trường bên dưới.
    </div>
  )
}
