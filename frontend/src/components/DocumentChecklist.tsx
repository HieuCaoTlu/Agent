/** O4 — checklist thành phần hồ sơ, cán bộ tự tích (không đồng bộ server — chỉ hỗ trợ nhớ tại quầy). */
import { useState } from 'react'

import type { DocumentSpec } from '@/types/api'

export function DocumentChecklist({ documents }: { documents: DocumentSpec[] }) {
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <h3 className="mb-2 text-lg font-semibold text-gray-800">Thành phần hồ sơ</h3>
      <ul className="flex flex-col gap-2">
        {documents.map((doc) => (
          <li key={doc.name} className="flex items-start gap-2 text-base">
            <input
              type="checkbox"
              className="mt-1 h-5 w-5"
              checked={checked[doc.name] ?? false}
              onChange={(e) => setChecked((prev) => ({ ...prev, [doc.name]: e.target.checked }))}
            />
            <span>
              {doc.name}
              {doc.note && <span className="ml-1 text-sm text-gray-500">({doc.note})</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
