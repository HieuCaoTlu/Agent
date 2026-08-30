"""Ghi log toàn bộ hoạt động của agent — mỗi phiên hội thoại (một kết nối
WebSocket) ghi ra 1 file JSONL riêng trong data/logs/, để chẩn đoán các
trường hợp AI trả lời sai/không dùng tool tra cứu mà không phải đoán mò.

Mỗi dòng là một sự kiện độc lập (dễ đọc lại bằng mắt hoặc script), gồm:
- session_start / session_end
- user_transcript / ai_transcript (từng mẩu gộp theo lượt)
- tool_call (tên hàm, tham số, kết quả trả về cho Gemini, có card hay không)
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("data/logs")


class ConversationLogger:
    def __init__(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex[:6]
        self.path = LOG_DIR / f"{datetime.now():%Y-%m-%d}.jsonl"
        self._write({"event": "session_start"})

    def _write(self, data: dict) -> None:
        # Timestamp gọn "YY-MM-DD HH:MM" — đủ để tra theo mốc thời gian, khỏi
        # cần độ chính xác tới giây/mili-giây như isoformat() mặc định.
        record = {
            "session_id": self.session_id,
            "ts": datetime.now().strftime("%y-%m-%d %H:%M"),
            **data,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def user_transcript(self, text: str) -> None:
        self._write({"event": "user_transcript", "text": text})

    def ai_transcript(self, text: str) -> None:
        self._write({"event": "ai_transcript", "text": text})

    def tool_call(self, name: str, query: str, result_text: str, has_card: bool) -> None:
        self._write(
            {
                "event": "tool_call",
                "name": name,
                "query": query,
                "result_preview": result_text[:300],
                "has_card": has_card,
            }
        )

    def session_end(self) -> None:
        self._write({"event": "session_end"})
