/**
 * O3 — component trường dữ liệu. Nền màu riêng cho giá trị AI gợi ý (chưa
 * xác nhận), viền đỏ + nhãn "BẮT BUỘC" cho trường bắt buộc còn thiếu, hiển
 * thị transcript làm căn cứ, câu hỏi gợi ý khi trường thiếu (`spoken_hint`).
 * Nút "Chép" (GD-4, Plan.MD 11.2) sao chép giá trị vào clipboard để cán bộ
 * dán sang Cổng dịch vụ công — hệ thống này không tự nộp hồ sơ hộ (NT-1).
 */
import { useState } from 'react'

import type { FieldSpec } from '@/types/api'
import type { FieldWithValidation } from '@/types/api'

interface FieldCardProps {
  spec: FieldSpec
  item: FieldWithValidation
  onConfirm: (value: string) => void
  onUnconfirm: () => void
}

export function FieldCard({ spec, item, onConfirm, onUnconfirm }: FieldCardProps) {
  const { field } = item
  const currentValue = field.confirmed_value ?? field.suggested_value ?? ''
  const [draft, setDraft] = useState(currentValue)

  const hasSuggestionOnly = !field.is_confirmed && field.suggested_value !== null
  const missingRequired = spec.required && !field.is_confirmed && !field.suggested_value
  const hasFormatError = field.validation_status === 'format_error'

  return (
    <div
      className={`rounded-lg border bg-white p-4 ${
        missingRequired ? 'border-2 border-red-400' : 'border-gray-200'
      }`}
    >
      <div className="mb-1 flex items-center gap-2">
        <label className="text-base font-medium text-gray-800">{spec.label}</label>
        {spec.required && (
          <span className="rounded bg-red-100 px-2 py-0.5 text-sm font-semibold text-red-700">
            BẮT BUỘC
          </span>
        )}
        {hasSuggestionOnly && (
          <span className="rounded bg-blue-100 px-2 py-0.5 text-sm text-blue-700">
            Gợi ý AI — chưa xác nhận
          </span>
        )}
      </div>

      {field.evidence_span && (
        <p className="mb-2 text-sm italic text-gray-500">Căn cứ: “{field.evidence_span}”</p>
      )}

      <div className="flex items-center gap-2">
        {spec.type === 'enum' && spec.options ? (
          <select
            className="flex-1 rounded border border-gray-300 p-2 text-base"
            value={draft}
            disabled={field.is_confirmed}
            onChange={(e) => setDraft(e.target.value)}
          >
            <option value="">-- Chọn --</option>
            {spec.options.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            className={`flex-1 rounded border p-2 text-base ${
              hasSuggestionOnly ? 'bg-blue-50' : 'bg-white'
            } border-gray-300`}
            value={draft}
            disabled={field.is_confirmed}
            onChange={(e) => setDraft(e.target.value)}
          />
        )}

        <button
          type="button"
          className="rounded border border-gray-300 px-3 py-2 text-base text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          disabled={!currentValue}
          onClick={() => void navigator.clipboard.writeText(currentValue)}
          title="Sao chép để dán sang Cổng dịch vụ công"
        >
          Chép
        </button>

        {field.is_confirmed ? (
          <button
            type="button"
            className="rounded border border-gray-300 px-3 py-2 text-base text-gray-700 hover:bg-gray-50"
            onClick={onUnconfirm}
          >
            Bỏ xác nhận
          </button>
        ) : (
          <button
            type="button"
            className="rounded bg-green-600 px-3 py-2 text-base text-white hover:bg-green-700 disabled:opacity-50"
            disabled={!draft}
            onClick={() => onConfirm(draft)}
          >
            Đã đối chiếu ✓
          </button>
        )}
      </div>

      {hasFormatError && (
        <p className="mt-1 text-base text-red-600">{field.validation_message}</p>
      )}
      {missingRequired && spec.spoken_hint && (
        <p className="mt-2 text-base text-amber-700">Gợi ý hỏi: {spec.spoken_hint}</p>
      )}
    </div>
  )
}
