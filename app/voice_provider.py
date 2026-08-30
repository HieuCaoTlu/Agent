import asyncio
import base64
import os

from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.conversation_log import ConversationLogger
from app.submit_flow import SUBMIT_PROVINCE, SUBMIT_WARD

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_VOICE_MODEL = os.environ.get("GEMINI_VOICE_MODEL", "gemini-2.5-flash-native-audio-latest")
GEMINI_VOICE_NAME = os.environ.get("GEMINI_VOICE_NAME", "Kore")
AUTO_GREET = os.environ.get("AUTO_GREET", "false").strip().lower() in ("1", "true", "yes")

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

_SCAN_FORM_FIELDS_DECL = types.FunctionDeclaration(
    name="scan_form_fields",
    description=(
        "Quét toàn bộ các trường cần điền trên trang form hồ sơ hiện tại đang "
        "mở trong trình duyệt của người dùng (chỉ dùng sau khi người dùng đã "
        "đăng nhập và đang ở màn hình điền hồ sơ thật, khi người dùng yêu cầu "
        "kiểu 'quét trang giúp tôi' hoặc hỏi 'giờ tôi phải làm gì')."
    ),
    parameters={"type": "OBJECT", "properties": {}},
)

_FILL_FORM_FIELDS_DECL = types.FunctionDeclaration(
    name="fill_form_fields",
    description=(
        "Tự động điền/tích chọn các trường đã quét được (bằng scan_form_fields) "
        "vào form trên trang hiện tại, dựa trên thông tin đã biết chắc chắn từ "
        "cuộc trò chuyện. PHẢI gọi công cụ này mỗi khi người dùng yêu cầu điền, "
        "nhập, hoặc tích/chọn BẤT KỲ trường nào — dù là yêu cầu chung chung "
        "('bạn điền giúp tôi đi') hay yêu cầu một trường cụ thể ('tích trường "
        "nơi sinh là trong nước', 'điền tên tôi vào'). KHÔNG BAO GIỜ được nói "
        "là đã điền/đã tích một trường nếu chưa thực sự gọi công cụ này và "
        "nhận kết quả xác nhận — phải đã gọi scan_form_fields trước đó trong "
        "cùng phiên."
    ),
    parameters={"type": "OBJECT", "properties": {}},
)

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói nữ, nghiêm túc, chuyên nghiệp, trả lời "
        "bằng tiếng Việt, ngắn gọn, tự nhiên như đang trò chuyện trực tiếp. "
        "Luôn mở đầu cuộc trò chuyện bằng đúng câu: 'Tôi là trợ lý giọng nói "
        "ảo của Phường Yên Sở, bạn muốn hỗ trợ thủ tục hành chính nào?' "
        f"Người dùng đang cư trú tại {SUBMIT_WARD}, {SUBMIT_PROVINCE} — nếu "
        "cần địa chỉ để hướng dẫn thủ tục, hãy dùng luôn thông tin này, không "
        "cần hỏi lại người dùng. Nếu chưa xác định rõ người dùng cần thủ tục "
        "gì, hãy hỏi lại cho rõ trước, không cần gọi công cụ nộp hồ sơ vội. "
        "Khi đã rõ và người dùng muốn nộp hồ sơ, hệ thống sẽ tự động mở trang "
        "dichvucong.gov.vn, tìm đúng thủ tục và điền sẵn tỉnh/phường giúp "
        "người dùng — hãy nói rõ điều này (ví dụ: 'Để tôi chuẩn bị mở trang "
        "nộp hồ sơ giúp bạn nhé') thay vì chỉ hướng dẫn suông, nhưng không "
        "cần nhắc lại tên phường/thành phố lúc này (đã nói ở đầu cuộc trò "
        "chuyện nếu cần). Sau khi người dùng đã đăng nhập và đang ở màn hình "
        "điền hồ sơ thật, nếu người dùng hỏi cần làm gì tiếp hoặc muốn quét "
        "trang, hãy gọi công cụ scan_form_fields — kết quả trả về có thể chỉ là "
        "số lượng và vài trường mẫu (form dài không liệt kê hết), hãy tóm tắt "
        "khái quát chứ không cần đọc hết từng trường. Sau đó, BẤT KỲ khi nào "
        "người dùng yêu cầu điền/nhập/tích/chọn một hoặc nhiều trường — dù nói "
        "chung chung ('bạn điền giúp tôi đi') hay chỉ rõ 1 trường cụ thể ('tích "
        "trường nơi sinh là trong nước') — hãy LUÔN gọi công cụ fill_form_fields "
        "trước, KHÔNG được tự trả lời là đã điền/đã tích khi chưa gọi công cụ "
        "này. Kết quả trả về có filled_count/remaining_count (số lượng) và chỉ "
        "vài ví dụ mẫu (form dài không liệt kê hết) — chỉ dựa vào đó để nói cho "
        "người dùng biết đã điền được bao nhiêu, còn thiếu gì, không suy đoán "
        "hay tự nhận là đã làm xong khi chưa có kết quả thật."
    ),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    speech_config=types.SpeechConfig(
        voice_config=types.VoiceConfig(
            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE_NAME)
        )
    ),
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
    ),
    tools=[types.Tool(function_declarations=[_SCAN_FORM_FIELDS_DECL, _FILL_FORM_FIELDS_DECL])],
)

async def run_voice_session(
    websocket: WebSocket,
    log: ConversationLogger,
    history: list[tuple[str, str]],
    on_submit_procedure,
    on_scan_form_fields,
    on_ai_fill_fields,
    on_get_required_documents,
    inject_queue: asyncio.Queue,
) -> None:
    async with _gemini_client.aio.live.connect(model=GEMINI_VOICE_MODEL, config=LIVE_CONFIG) as session:
        state = {"suppress_show_submit": False}

        async def inject_text(text: str, suppress_show_submit: bool = False, silent: bool = False) -> None:
            state["suppress_show_submit"] = suppress_show_submit
            if not silent:
                log.user_transcript(text)
                history.append(("Người dùng", text))
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )

        async def from_queue() -> None:
            while True:
                text = await inject_queue.get()
                await inject_text(text, suppress_show_submit=True)

        async def from_browser() -> None:
            while True:
                message = await websocket.receive_json()
                msg_type = message.get("type")
                if msg_type == "audio":
                    pcm_bytes = base64.b64decode(message["data"])
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")
                    )
                elif msg_type == "activity_start":
                    await session.send_realtime_input(activity_start=types.ActivityStart())
                elif msg_type == "activity_end":
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                elif msg_type == "submit_procedure":
                    on_submit_procedure(message.get("procedure_name"))
                elif msg_type == "cancel_submit":
                    await inject_text("Tôi chưa muốn nộp hồ sơ ngay bây giờ, hãy hỏi tôi cần hỗ trợ gì thêm.")
                elif msg_type == "request_required_documents":
                    on_get_required_documents()
                elif msg_type == "trigger_scan_form":
                    result = await on_scan_form_fields()
                    if result.get("error"):
                        await inject_text(
                            "Hệ thống chưa quét được thông tin trang hiện tại (lỗi: "
                            f"{result['error']}), hãy báo người dùng thử lại và có thể cần kiểm "
                            "tra tiện ích mở rộng đã kết nối chưa.",
                            suppress_show_submit=True,
                        )
                    else:
                        count = result.get("fields_count", 0)
                        sample = result.get("sample_labels") or []
                        suffix = " (và một số trường khác)" if result.get("truncated") else ""
                        await inject_text(
                            "Hệ thống vừa quét xong trang hiện tại theo yêu cầu người dùng, tìm "
                            f"thấy {count} trường cần điền, ví dụ: {', '.join(sample)}{suffix}. Hãy "
                            "tóm tắt ngắn gọn cho người dùng nghe (không cần đọc hết từng trường "
                            "nếu số lượng nhiều, chỉ cần nói khái quát các nhóm thông tin).",
                            suppress_show_submit=True,
                        )
                elif msg_type == "stop":
                    return

        async def to_browser() -> None:
            user_buffer = ""
            ai_buffer = ""
            fill_tool_called_this_turn = False
            while True:
                async for chunk in session.receive():
                    if chunk.data:
                        await websocket.send_json(
                            {"type": "audio", "data": base64.b64encode(chunk.data).decode()}
                        )
                    if chunk.tool_call and chunk.tool_call.function_calls:
                        for call in chunk.tool_call.function_calls:
                            if call.name == "scan_form_fields":
                                result = await on_scan_form_fields()
                            elif call.name == "fill_form_fields":
                                result = await on_ai_fill_fields(user_buffer)
                                fill_tool_called_this_turn = True
                            else:
                                result = {"error": f"Không hỗ trợ công cụ: {call.name}"}
                            await session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(id=call.id, name=call.name, response=result)
                                ]
                            )
                    content = chunk.server_content
                    if content and content.input_transcription and content.input_transcription.text:
                        text = content.input_transcription.text
                        user_buffer += text
                        await websocket.send_json({"type": "user_transcript", "text": text})
                    if content and content.output_transcription and content.output_transcription.text:
                        text = content.output_transcription.text
                        ai_buffer += text
                        await websocket.send_json({"type": "ai_transcript", "text": text})
                    if content and content.interrupted:
                        await websocket.send_json({"type": "interrupted"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""
                    if content and content.turn_complete:
                        if not state["suppress_show_submit"] and (
                            "nộp" in user_buffer.lower() or "nộp" in ai_buffer.lower()
                        ):
                            await websocket.send_json({"type": "show_submit_button"})
                        if not fill_tool_called_this_turn and any(
                            kw in ai_buffer.lower() for kw in ("đã điền", "đã tích", "đã chọn")
                        ):
                            log.submit_error(
                                "ai_claimed_fill_without_tool_call",
                                f"AI nói đã điền/tích nhưng không gọi fill_form_fields trong turn này: {ai_buffer}",
                            )
                        state["suppress_show_submit"] = False
                        fill_tool_called_this_turn = False
                        await websocket.send_json({"type": "turn_complete"})
                        if user_buffer:
                            log.user_transcript(user_buffer)
                            history.append(("Người dùng", user_buffer))
                            user_buffer = ""
                        if ai_buffer:
                            log.ai_transcript(ai_buffer)
                            history.append(("Trợ lý", ai_buffer))
                            ai_buffer = ""

        try:
            if AUTO_GREET:
                await inject_text(
                    "(Bắt đầu cuộc trò chuyện, hãy chào người dùng theo đúng câu đã dặn.)",
                    suppress_show_submit=True,
                    silent=True,
                )
            await asyncio.gather(from_browser(), to_browser(), from_queue())
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
