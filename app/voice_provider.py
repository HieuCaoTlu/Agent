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

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói thân thiện, trả lời bằng tiếng Việt, "
        "ngắn gọn, tự nhiên như đang trò chuyện trực tiếp. "
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
        "trang, hãy gọi công cụ scan_form_fields rồi dựa vào kết quả trả về "
        "để tóm tắt ngắn gọn các trường cần điền, sau đó hỏi người dùng có "
        "muốn nhờ bạn tự điền hay tự điền lấy."
    ),
    input_audio_transcription=types.AudioTranscriptionConfig(),
    output_audio_transcription=types.AudioTranscriptionConfig(),
    realtime_input_config=types.RealtimeInputConfig(
        automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
    ),
    tools=[types.Tool(function_declarations=[_SCAN_FORM_FIELDS_DECL])],
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
        state = {"suppress_show_submit": False, "pending_scan_prompt": False}

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
                elif msg_type == "scan_fill_choice":
                    choice = message.get("choice")
                    if choice == "ai":
                        on_ai_fill_fields()
                    else:
                        await inject_text(
                            "Tôi muốn tự điền lấy, hãy giới thiệu qua các trường quan trọng cần "
                            "điền rồi để tôi tự nhập, cần hỗ trợ gì thêm tôi sẽ hỏi tiếp."
                        )
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
                        await inject_text(
                            "Hệ thống vừa quét xong trang hiện tại theo yêu cầu người dùng. Dựa "
                            f"vào các trường sau: {result.get('fields')} — hãy tóm tắt ngắn gọn "
                            "các trường cần điền rồi hỏi người dùng có muốn nhờ bạn tự điền hay "
                            "tự điền lấy.",
                            suppress_show_submit=True,
                        )
                        state["pending_scan_prompt"] = True
                elif msg_type == "stop":
                    return

        async def to_browser() -> None:
            user_buffer = ""
            ai_buffer = ""
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
                                await session.send_tool_response(
                                    function_responses=[
                                        types.FunctionResponse(id=call.id, name=call.name, response=result)
                                    ]
                                )
                                state["pending_scan_prompt"] = True
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
                        if state["pending_scan_prompt"]:
                            await websocket.send_json({"type": "show_scan_choice_buttons"})
                        state["suppress_show_submit"] = False
                        state["pending_scan_prompt"] = False
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
