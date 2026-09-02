import asyncio
import base64
import os

from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from app.conversation_log import ConversationLogger

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_VOICE_MODEL = os.environ.get("GEMINI_VOICE_MODEL", "gemini-2.5-flash-native-audio-latest")
GEMINI_VOICE_NAME = os.environ.get("GEMINI_VOICE_NAME", "Kore")
AUTO_GREET = os.environ.get("AUTO_GREET", "false").strip().lower() in ("1", "true", "yes")

DEFAULT_WARD = "Yên Sở"
DEFAULT_PROVINCE = "Thành phố Hà Nội"

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

_SHOW_REQUIRED_DOCUMENTS_DECL = types.FunctionDeclaration(
    name="show_required_documents",
    description=(
        "Tra cứu và hiện cho người dùng danh sách giấy tờ/thành phần hồ sơ cần "
        "chuẩn bị cho một thủ tục hành chính cụ thể. Dùng khi người dùng hỏi "
        "kiểu 'cần chuẩn bị giấy tờ gì', 'thành phần hồ sơ gồm những gì', 'cần "
        "mang theo gì'."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "procedure_name": {
                "type": "STRING",
                "description": "Tên thủ tục hành chính người dùng đang hỏi (ví dụ 'Đăng ký khai sinh').",
            },
        },
        "required": ["procedure_name"],
    },
)

_SHOW_SUBMISSION_STEPS_DECL = types.FunctionDeclaration(
    name="show_submission_steps",
    description=(
        "Hiện cho người dùng các bước cần làm để nộp hồ sơ cho một thủ tục hành "
        "chính cụ thể, kèm đường dẫn chính thức tới nơi nộp hồ sơ trên "
        "dichvucong.gov.vn và phí/lệ phí nộp trực tuyến nếu có. Dùng khi người "
        "dùng hỏi kiểu 'nộp hồ sơ ở đâu', 'các bước nộp hồ sơ thế nào', 'nộp "
        "thủ tục này như thế nào', 'nộp hồ sơ mất bao nhiêu tiền', 'phí nộp hồ "
        "sơ online là bao nhiêu'."
    ),
    parameters={
        "type": "OBJECT",
        "properties": {
            "procedure_name": {
                "type": "STRING",
                "description": "Tên thủ tục hành chính người dùng đang hỏi (ví dụ 'Đăng ký kết hôn').",
            },
        },
        "required": ["procedure_name"],
    },
)

LIVE_CONFIG = types.LiveConnectConfig(
    response_modalities=[types.Modality.AUDIO],
    system_instruction=(
        "Bạn là một trợ lý giọng nói nữ, nghiêm túc, chuyên nghiệp, trả lời "
        "bằng tiếng Việt, ngắn gọn, tự nhiên như đang trò chuyện trực tiếp. "
        "Luôn mở đầu cuộc trò chuyện bằng đúng câu: 'Tôi là trợ lý giọng nói "
        "ảo của Phường Yên Sở, bạn muốn hỗ trợ thủ tục hành chính nào?' "
        f"Người dùng đang cư trú tại {DEFAULT_WARD}, {DEFAULT_PROVINCE} — nếu "
        "cần địa chỉ để hướng dẫn thủ tục, hãy dùng luôn thông tin này, không "
        "cần hỏi lại người dùng. Nếu chưa xác định rõ người dùng cần thủ tục "
        "gì, hãy hỏi lại cho rõ trước, không cần gọi công cụ nào vội.\n\n"
        "NẾU người dùng hỏi bạn là ai/làm được gì/giúp được gì (ví dụ 'bạn "
        "làm được gì', 'bạn giúp tôi được gì', 'giới thiệu về bản thân bạn') "
        "— hãy giới thiệu ngắn gọn: bạn là trợ lý giọng nói AI hỗ trợ thủ tục "
        "hành chính công, có thể (1) tra cứu và giải thích thành phần hồ sơ "
        "cần chuẩn bị cho từng thủ tục, (2) hướng dẫn các bước nộp hồ sơ và "
        "đưa đường dẫn chính thức tới nơi nộp trên dichvucong.gov.vn. Không "
        "cần liệt kê máy móc, nói tự nhiên như đang giới thiệu bản thân. "
        "NGƯỢC LẠI, nếu người dùng hỏi thẳng vào một thủ tục/vấn đề cụ thể "
        "ngay từ đầu (không hỏi bạn là ai), hãy trả lời thẳng vào vấn đề đó, "
        "không cần giới thiệu bản thân trước.\n\n"
        "QUAN TRỌNG — không được tự bịa câu trả lời chung chung: nếu người "
        "dùng hỏi về thành phần hồ sơ hoặc cách nộp hồ sơ nhưng CHƯA nói rõ "
        "tên một thủ tục hành chính cụ thể (ví dụ chỉ hỏi 'nộp hồ sơ online "
        "cần giấy tờ gì', 'thủ tục thì cần gì'), bạn KHÔNG được tự trả lời "
        "kiểu ước lượng/chung chung (vd 'cũng tương tự thủ tục khác', 'hệ "
        "thống có thể tra cứu một số giấy tờ nếu có sẵn dữ liệu') và KHÔNG "
        "được gọi công cụ khi chưa có tên thủ tục — mọi thông tin thành phần "
        "hồ sơ và các bước nộp đều khác nhau tùy từng thủ tục cụ thể, trả lời "
        "chung chung là sai và gây hiểu nhầm. Việc DUY NHẤT cần làm lúc này "
        "là hỏi lại ngắn gọn đúng 1 câu để biết chính xác tên thủ tục (ví dụ "
        "'Bạn muốn nộp hồ sơ cho thủ tục nào ạ?'), có tên thủ tục cụ thể rồi "
        "mới gọi công cụ tương ứng.\n\n"
        "Mặc định LUÔN xem người dùng muốn nộp hồ sơ TRỰC TUYẾN qua Cổng "
        "dịch vụ công (dichvucong.gov.vn) — không cần hỏi lại người dùng là "
        "muốn nộp trực tiếp hay trực tuyến, cũng không cần nhắc câu 'giống "
        "hệt nộp trực tiếp' hay so sánh 2 hình thức, chỉ tập trung trả lời "
        "đúng vào việc nộp trực tuyến.\n\n"
        "Khi đã biết rõ tên thủ tục và người dùng hỏi cần chuẩn bị giấy tờ "
        "gì, hãy gọi công cụ show_required_documents — công cụ sẽ tự hiện "
        "danh sách chi tiết trên màn hình cho người dùng xem, bạn chỉ cần "
        "nói tóm tắt khái quát vài giấy tờ chính từ kết quả trả về (không "
        "cần đọc hết từng thứ nếu danh sách dài, vì người dùng đang nhìn "
        "thấy đầy đủ trên màn hình). Khi đã biết rõ tên thủ tục và người "
        "dùng hỏi nộp hồ sơ ở đâu/nộp như thế nào/mất phí bao nhiêu, hãy gọi "
        "công cụ show_submission_steps — công cụ sẽ tự hiện các bước, phí lệ "
        "phí nộp trực tuyến (nếu có) và nút mở nơi nộp hồ sơ trên màn hình, "
        "bạn chỉ cần tóm tắt ngắn gọn bằng lời (nhắc luôn số tiền/miễn phí "
        "nếu người dùng hỏi về phí) và nhắc người dùng bấm nút trên màn hình "
        "để mở đúng trang. Không tự đọc tên công cụ hay cú pháp gọi công cụ "
        "thành lời — nói tự nhiên rồi gọi công cụ ở phía sau, không hiển thị "
        "trong lời nói. KHÔNG "
        "được tự nhận là đã nộp hồ sơ hay đã điền hộ giúp người dùng — hệ "
        "thống không tự động thao tác trên trang nộp hồ sơ, người dùng luôn "
        "tự bấm và tự điền trên trang thật."
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
    tools=[
        types.Tool(
            function_declarations=[
                _SHOW_REQUIRED_DOCUMENTS_DECL,
                _SHOW_SUBMISSION_STEPS_DECL,
            ]
        )
    ],
)


async def run_voice_session(
    websocket: WebSocket,
    log: ConversationLogger,
    history: list[tuple[str, str]],
    on_show_required_documents,
    on_show_submission_steps,
) -> None:
    async with _gemini_client.aio.live.connect(model=GEMINI_VOICE_MODEL, config=LIVE_CONFIG) as session:

        async def inject_text(text: str, silent: bool = False) -> None:
            if not silent:
                log.user_transcript(text)
                history.append(("Người dùng", text))
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )

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
                            procedure_name = (call.args or {}).get("procedure_name") or ""
                            if call.name == "show_required_documents":
                                result = await on_show_required_documents(procedure_name)
                            elif call.name == "show_submission_steps":
                                result = await on_show_submission_steps(procedure_name)
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
                    silent=True,
                )
            await asyncio.gather(from_browser(), to_browser())
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
