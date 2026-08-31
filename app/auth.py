import json
import os
import secrets
import time
from pathlib import Path

import jwt
from dotenv import load_dotenv

# Gọi riêng ở đây thay vì phụ thuộc thứ tự import module khác (vd text_model.py
# cũng gọi load_dotenv() nhưng có thể import sau app.auth trong main.py).
load_dotenv()

# Nếu không set JWT_SECRET trong .env, tự sinh ngẫu nhiên lúc khởi động — token cũ
# (nếu có) sẽ mất hiệu lực sau mỗi lần restart. Set cố định trong .env để token
# sống sót qua restart (bắt buộc nếu chạy nhiều worker process).
JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_hex(32)
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = 24 * 3600

_USERS_PATH = Path("data/allowed_users.json")


def _load_users() -> list[str]:
    if not _USERS_PATH.exists():
        return []
    data = json.loads(_USERS_PATH.read_text(encoding="utf-8"))
    return data.get("usernames") or []


def _save_users(usernames: list[str]) -> None:
    _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _USERS_PATH.write_text(
        json.dumps({"usernames": usernames}, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_users() -> list[str]:
    return _load_users()


def add_user(username: str) -> list[str]:
    users = _load_users()
    if username not in users:
        users.append(username)
        _save_users(users)
    return users


def remove_user(username: str) -> list[str]:
    users = [u for u in _load_users() if u != username]
    _save_users(users)
    return users


def is_valid_username(username: str) -> bool:
    return username in _load_users()


def issue_token(username: str) -> str:
    now = int(time.time())
    payload = {"sub": username, "iat": now, "exp": now + JWT_TTL_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")
