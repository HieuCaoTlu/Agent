/**
 * O2 — danh sách lượt thoại. Mỗi lượt có nút "Sửa" và "Hỏi lại" — không có
 * phân biệt tự động "rõ/chưa rõ" (không dùng ngưỡng confidence, xem
 * Checklist C2/O2). "Gắn cờ chưa rõ" là đánh dấu chủ động của cán bộ.
 */
import { useState } from 'react'

import type { VoiceTurn } from '@/types/api'

interface TranscriptListProps {
  turns: VoiceTurn[]
  partialText: string
  onEdit: (turnId: string, newText: string) => void
  onAskAgain: () => void
  onFlag: (turnId: string) => void
}

function TurnRow({
  turn,
  onEdit,
  onFlag,
}: {
  turn: VoiceTurn
  onEdit: (turnId: string, newText: string) => void
  onFlag: (turnId: string) => void
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(turn.edited_transcript ?? turn.raw_transcript ?? '')

  const displayText = turn.edited_transcript ?? turn.raw_transcript ?? '(chưa có transcript)'

  if (editing) {
    return (
      <li className="rounded-lg border border-blue-300 bg-blue-50 p-3">
        <textarea
          className="w-full rounded border border-gray-300 p-2 text-base"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={2}
          autoFocus
        />
        <div className="mt-2 flex gap-2">
          <button
            type="button"
            className="rounded bg-blue-600 px-3 py-1 text-base text-white hover:bg-blue-700"
            onClick={() => {
              onEdit(turn.id, draft)
              setEditing(false)
            }}
          >
            Lưu
          </button>
          <button
            type="button"
            className="rounded border border-gray-300 px-3 py-1 text-base text-gray-700"
            onClick={() => setEditing(false)}
          >
            Hủy
          </button>
        </div>
      </li>
    )
  }

  return (
    <li className="rounded-lg border border-gray-200 bg-white p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="text-base text-gray-800">
          <span className="mr-2 font-mono text-sm text-gray-400">#{turn.turn_number}</span>
          {displayText}
          {turn.flagged_by_staff && (
            <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-sm text-amber-700">
              Chưa rõ
            </span>
          )}
        </p>
      </div>
      <div className="mt-2 flex gap-3 text-base">
        <button type="button" className="text-blue-600 hover:underline" onClick={() => setEditing(true)}>
          Sửa
        </button>
        <button
          type="button"
          className="text-amber-600 hover:underline"
          onClick={() => onFlag(turn.id)}
          disabled={turn.flagged_by_staff}
        >
          Gắn cờ chưa rõ
        </button>
      </div>
    </li>
  )
}

export function TranscriptList({ turns, partialText, onEdit, onAskAgain, onFlag }: TranscriptListProps) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-800">Nội dung đã ghi âm</h3>
        <button
          type="button"
          className="rounded border border-blue-300 px-3 py-1 text-base text-blue-700 hover:bg-blue-50"
          onClick={onAskAgain}
        >
          Hỏi lại
        </button>
      </div>
      <ul className="flex flex-col gap-2">
        {turns.map((turn) => (
          <TurnRow key={turn.id} turn={turn} onEdit={onEdit} onFlag={onFlag} />
        ))}
      </ul>
      {partialText && (
        <p className="rounded-lg border border-dashed border-gray-300 bg-gray-50 p-3 text-base italic text-gray-500">
          {partialText}…
        </p>
      )}
    </div>
  )
}
