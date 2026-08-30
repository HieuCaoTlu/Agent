/**
 * N — Màn hình làm việc `/sessions/:id` — bố cục 2 cột (Plan.MD 11.1):
 * trái = lời nói người dân (transcript + ghi âm + checklist hồ sơ),
 * phải = thông tin gợi ý (trường dữ liệu + tiến độ + cảnh báo + đọc lại).
 */
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ConfirmDialog } from '@/components/ConfirmDialog'
import { DocumentChecklist } from '@/components/DocumentChecklist'
import { FieldCard } from '@/components/FieldCard'
import { LoadingIndicator } from '@/components/LoadingIndicator'
import { ManualModeBanner } from '@/components/ManualModeBanner'
import { ProgressBar } from '@/components/ProgressBar'
import { RecordButton } from '@/components/RecordButton'
import { ResponsibilityBanner } from '@/components/ResponsibilityBanner'
import { TranscriptList } from '@/components/TranscriptList'
import { WarningList } from '@/components/WarningList'
import { useConfirmField, useExtract, useUnconfirmField } from '@/hooks/useFields'
import { useProcedureDetail, useProcedures } from '@/hooks/useProcedures'
import { useSession } from '@/hooks/useSession'
import {
  useCancelSession,
  useOpenReview,
  useSelectProcedure,
  useStartListening,
} from '@/hooks/useSessionActions'
import { useEditTranscript, useFlagTranscript, useTurns } from '@/hooks/useTurns'
import { useVoiceStream } from '@/hooks/useVoiceStream'
import { fieldsApi } from '@/api/fields'
import { useQuery } from '@tanstack/react-query'

// TODO(N): tên cán bộ đăng nhập — MVP không có đăng nhập (xem Checklist,
// "Đã lược bỏ khỏi MVP"), lấy tạm từ session hiện tại thay vì hỏi lại.
function useStaffName(sessionId: string | undefined) {
  const { data } = useSession(sessionId)
  return data?.session.staff_name ?? ''
}

function ProcedureSelector({ sessionId }: { sessionId: string }) {
  const { data: procedures, isLoading } = useProcedures()
  const selectProcedure = useSelectProcedure(sessionId)

  if (isLoading) return <LoadingIndicator label="Đang tải danh mục thủ tục..." />

  return (
    <div className="mx-auto max-w-lg p-6">
      <h2 className="mb-4 text-xl font-semibold text-gray-900">Chọn thủ tục hành chính</h2>
      <p className="mb-4 text-base text-gray-600">
        Dựa vào nội dung người dân vừa trình bày, chọn thủ tục phù hợp bên dưới.
      </p>
      <ul className="flex flex-col gap-2">
        {procedures?.map((p) => (
          <li key={p.code}>
            <button
              type="button"
              className="w-full rounded-lg border border-gray-200 bg-white p-3 text-left text-base hover:bg-blue-50"
              onClick={() => selectProcedure.mutate(p.code)}
            >
              {p.name}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/**
 * B1 (Plan.MD) — giai đoạn ghi âm TRƯỚC khi chọn thủ tục. `session.state`
 * phải qua LISTENING (start-listening, I1) trước khi có thể chọn thủ tục
 * (select_procedure chỉ hợp lệ từ LISTENING, C1) — tự động gọi ngay khi vào
 * trang nếu phiên còn ở CREATED, không bắt cán bộ bấm thêm một nút riêng.
 */
function ListeningStage({
  sessionId,
  sessionState,
  staffName,
  turns,
  voice,
  onEditTranscript,
  onFlagTranscript,
}: {
  sessionId: string
  sessionState: string
  staffName: string
  turns: { id: string; turn_number: number }[]
  voice: ReturnType<typeof useVoiceStream>
  onEditTranscript: (turnId: string, newText: string) => void
  onFlagTranscript: (turnId: string) => void
}) {
  const startListening = useStartListening(sessionId)
  const { data: turnsFull } = useTurns(sessionId)

  useEffect(() => {
    if (sessionState === 'CREATED' && !startListening.isPending && !startListening.isSuccess) {
      startListening.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionState])

  if (sessionState === 'CREATED') {
    return (
      <div className="p-6">
        <LoadingIndicator label="Đang chuẩn bị ghi âm..." />
      </div>
    )
  }

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-6">
      <h1 className="text-xl font-semibold text-gray-900">Bước 1 — Nghe người dân trình bày</h1>
      <p className="text-base text-gray-600">
        Bấm ghi âm và để người dân trình bày nhu cầu bằng lời nói. Sau khi có ít nhất một lượt
        ghi âm, bạn có thể chọn thủ tục phù hợp.
      </p>

      <TranscriptList
        turns={turnsFull ?? []}
        partialText={voice.partialText}
        onEdit={onEditTranscript}
        onAskAgain={() => voice.start()}
        onFlag={onFlagTranscript}
      />

      <div className="flex justify-center py-4">
        <RecordButton
          status={voice.status}
          volumeLevel={voice.volumeLevel}
          recordingStartedAt={voice.recordingStartedAt}
          lastError={voice.lastError}
          onStart={() => void voice.start()}
          onStop={() => voice.stop()}
        />
      </div>

      {turns.length > 0 ? (
        <ProcedureSelector sessionId={sessionId} />
      ) : (
        <p className="text-center text-base text-gray-400">
          Ghi âm ít nhất một lượt để tiếp tục chọn thủ tục.
        </p>
      )}
      <p className="text-center text-sm text-gray-400">Cán bộ: {staffName}</p>
    </div>
  )
}

export function WorkspacePage() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false)

  const { data: snapshot, isLoading } = useSession(sessionId)
  const staffName = useStaffName(sessionId)
  const { data: turns } = useTurns(sessionId)
  const { data: procedureDetail } = useProcedureDetail(snapshot?.session.procedure_code ?? undefined)
  const { data: fieldItems, refetch: refetchFields } = useQuery({
    queryKey: ['fields', sessionId],
    queryFn: () => fieldsApi.list(sessionId as string),
    enabled: Boolean(sessionId),
  })

  const editTranscript = useEditTranscript(sessionId ?? '')
  const flagTranscript = useFlagTranscript(sessionId ?? '')
  const extract = useExtract(sessionId ?? '')
  const confirmField = useConfirmField(sessionId ?? '')
  const unconfirmField = useUnconfirmField(sessionId ?? '')
  const cancelSession = useCancelSession(sessionId ?? '')
  const openReview = useOpenReview(sessionId ?? '')

  const handleFinalTurn = useCallback(() => {
    // Lượt mới đã lưu — trích xuất lại toàn bộ transcript hiện có (UC2).
    // `include_turns` cần danh sách turn_number đầy đủ — dùng lại từ `turns`
    // đã tải; nếu chưa có (lượt đầu tiên) coi như [1].
    const allTurnNumbers = (turns ?? []).map((t) => t.turn_number)
    const nextTurnNumbers = allTurnNumbers.length > 0 ? allTurnNumbers : [1]
    extract.mutate({ includeTurns: [...new Set([...nextTurnNumbers])] })
  }, [turns, extract])

  const voice = useVoiceStream(sessionId ?? '', handleFinalTurn)

  const sessionState = snapshot?.session.state
  // B4 (Plan.MD) — cán bộ tự động "mở xem gợi ý" ngay khi trích xuất xong
  // (SUGGESTED -> REVIEWING, open-review, I1) — MVP không cần một màn hình
  // trung gian riêng cho bước bấm mở, xác nhận trường (B5) diễn ra ngay.
  useEffect(() => {
    if (sessionState === 'SUGGESTED' && !openReview.isPending && !openReview.isSuccess) {
      openReview.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionState])

  if (isLoading || !snapshot) {
    return (
      <div className="p-6">
        <LoadingIndicator label="Đang tải phiên..." />
      </div>
    )
  }

  const { session, warnings } = snapshot
  const fields = fieldItems ?? []

  if (session.procedure_code === null) {
    return (
      <ListeningStage
        sessionId={session.id}
        sessionState={session.state}
        staffName={staffName}
        turns={turns ?? []}
        voice={voice}
        onEditTranscript={(turnId, newText) => editTranscript.mutate({ turnId, newText, staffName })}
        onFlagTranscript={(turnId) => flagTranscript.mutate({ turnId, staffName })}
      />
    )
  }

  if (session.state === 'EXTRACTING' || session.state === 'SUGGESTED') {
    return (
      <div className="p-6">
        <LoadingIndicator label="Đang chuẩn bị gợi ý từ AI..." />
      </div>
    )
  }

  const requiredFields = (procedureDetail?.fields ?? []).filter((f) => f.required)
  const confirmedRequiredCount = fields.filter(
    (item) => requiredFields.some((spec) => spec.name === item.field.field_name) && item.field.is_confirmed,
  ).length
  const allRequiredConfirmed =
    requiredFields.length > 0 && confirmedRequiredCount === requiredFields.length

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-gray-900">
            Trợ lý giọng nói AI — Phường Yên Sở
          </h1>
          <div className="flex items-center gap-4">
            <span className="text-base text-gray-600">Cán bộ: {staffName}</span>
            <button
              type="button"
              className="rounded border border-red-300 px-3 py-1 text-base text-red-700 hover:bg-red-50"
              onClick={() => setCancelDialogOpen(true)}
            >
              Hủy phiên
            </button>
          </div>
        </div>
        <p className="mt-1 text-base text-gray-500">
          Phiên #{session.id.slice(0, 8)} · {procedureDetail?.name ?? session.procedure_code} ·
          Trạng thái: {session.state}
        </p>
      </header>

      {session.state === 'AI_UNAVAILABLE' && (
        <div className="px-6 pt-4">
          <ManualModeBanner />
        </div>
      )}

      <main className="grid flex-1 grid-cols-1 gap-6 p-6 lg:grid-cols-2">
        <section className="flex flex-col gap-4">
          <h2 className="text-lg font-semibold text-gray-800">Lời nói của người dân</h2>
          <TranscriptList
            turns={turns ?? []}
            partialText={voice.partialText}
            onEdit={(turnId, newText) =>
              editTranscript.mutate({ turnId, newText, staffName })
            }
            onAskAgain={() => voice.start()}
            onFlag={(turnId) => flagTranscript.mutate({ turnId, staffName })}
          />
          <div className="flex justify-center py-4">
            <RecordButton
              status={voice.status}
              volumeLevel={voice.volumeLevel}
              recordingStartedAt={voice.recordingStartedAt}
              lastError={voice.lastError}
              onStart={() => void voice.start()}
              onStop={() => voice.stop()}
            />
          </div>
          {procedureDetail && <DocumentChecklist documents={procedureDetail.required_documents} />}
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-800">Thông tin gợi ý</h2>
            {!allRequiredConfirmed && (
              <span className="text-base text-amber-700">⚠ Chưa xác nhận đủ</span>
            )}
          </div>

          <WarningList warnings={warnings} />

          <div className="flex flex-col gap-3">
            {procedureDetail?.fields.map((spec) => {
              const item = fields.find((f) => f.field.field_name === spec.name)
              if (!item) return null
              return (
                <FieldCard
                  key={spec.name}
                  spec={spec}
                  item={item}
                  onConfirm={(value) =>
                    confirmField.mutate(
                      { fieldName: spec.name, value, staffName },
                      { onSuccess: () => void refetchFields() },
                    )
                  }
                  onUnconfirm={() =>
                    unconfirmField.mutate(spec.name, { onSuccess: () => void refetchFields() })
                  }
                />
              )
            })}
          </div>

          <ProgressBar confirmed={confirmedRequiredCount} total={requiredFields.length} />

          <button
            type="button"
            disabled={!allRequiredConfirmed}
            onClick={() => navigate(`/sessions/${session.id}/readback`)}
            className="rounded bg-blue-600 px-4 py-3 text-base font-semibold text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            🔊 Đọc lại cho người dân
          </button>
        </section>
      </main>

      <ResponsibilityBanner />

      <ConfirmDialog
        open={cancelDialogOpen}
        title="Hủy phiên hỗ trợ"
        message="Bạn có chắc muốn hủy phiên này? Toàn bộ dữ liệu chưa xác nhận sẽ không được sử dụng."
        confirmLabel="Hủy phiên"
        onConfirm={() => cancelSession.mutate(undefined)}
        onCancel={() => setCancelDialogOpen(false)}
      />
    </div>
  )
}
