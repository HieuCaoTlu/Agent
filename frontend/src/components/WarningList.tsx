/** O4 — danh sách cảnh báo, sắp xếp theo mức độ nghiêm trọng. */
import type { Warning } from '@/types/api'

const SEVERITY_ORDER: Record<string, number> = { error: 0, warning: 1, info: 2 }
const SEVERITY_STYLE: Record<string, string> = {
  error: 'border-red-300 bg-red-50 text-red-800',
  warning: 'border-amber-300 bg-amber-50 text-amber-800',
  info: 'border-blue-300 bg-blue-50 text-blue-800',
}

export function WarningList({ warnings }: { warnings: Warning[] }) {
  if (warnings.length === 0) return null

  const sorted = [...warnings].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 99) - (SEVERITY_ORDER[b.severity] ?? 99),
  )

  return (
    <ul className="flex flex-col gap-2">
      {sorted.map((w, i) => (
        <li
          key={`${w.code}-${w.field}-${i}`}
          className={`rounded-lg border p-3 text-base ${SEVERITY_STYLE[w.severity] ?? SEVERITY_STYLE.info}`}
        >
          {w.message}
        </li>
      ))}
    </ul>
  )
}
