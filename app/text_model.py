import asyncio
import json
import os

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

PROVIDER = os.environ.get("TEXT_MODEL_PROVIDER", "gemini")

GEMINI_MODEL = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.6-flash")

if PROVIDER == "ollama":
    OPENAI_COMPAT_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    OPENAI_COMPAT_MODEL = os.environ.get("OLLAMA_MODEL_NAME", "qwen2.5:7b")
    OPENAI_COMPAT_API_KEY = os.environ.get("OLLAMA_API_KEY", "ollama")
else:
    OPENAI_COMPAT_BASE_URL = os.environ.get("TEXT_MODEL_BASE_URL", "")
    OPENAI_COMPAT_MODEL = os.environ.get("TEXT_MODEL_NAME", "")
    OPENAI_COMPAT_API_KEY = os.environ.get("TEXT_MODEL_API_KEY", "")

_gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"]) if os.environ.get("GEMINI_API_KEY") else None


async def _call_gemini(prompt: str, schema: dict | None) -> str:
    config = (
        types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema)
        if schema
        else None
    )
    response = await _gemini_client.aio.models.generate_content(model=GEMINI_MODEL, contents=prompt, config=config)
    return response.text or ""


def _extract_json_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _extract_retry_after_seconds(response: httpx.Response) -> float | None:
    header_value = response.headers.get("Retry-After")
    if header_value:
        try:
            return float(header_value)
        except ValueError:
            pass
    try:
        body = response.json()
        return float(body["error"]["metadata"]["retry_after_seconds"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


async def _call_openai_compat(prompt: str, schema: dict | None) -> str:
    if schema:
        prompt = (
            f"{prompt}\n\nTrả lời DUY NHẤT một object JSON hợp lệ, đúng các trường sau, "
            f"không kèm giải thích, không kèm markdown code fence:\n{json.dumps(schema, ensure_ascii=False)}"
        )
    body = {
        "model": OPENAI_COMPAT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }
    max_attempts = 3
    async with httpx.AsyncClient(timeout=60.0) as http_client:
        for attempt in range(max_attempts):
            response = await http_client.post(
                f"{OPENAI_COMPAT_BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_COMPAT_API_KEY}"},
                json=body,
            )
            if response.status_code == 429 and attempt < max_attempts - 1:
                wait_seconds = _extract_retry_after_seconds(response) or 3.0
                await asyncio.sleep(wait_seconds)
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"{response.status_code} {response.reason_phrase}: {response.text}")
            data = response.json()
            content = data["choices"][0]["message"]["content"] or ""
            return _extract_json_block(content) if schema else content


async def generate_text(prompt: str) -> str:
    if PROVIDER == "gemini":
        return await _call_gemini(prompt, None)
    return await _call_openai_compat(prompt, None)


async def generate_json(prompt: str, schema: dict) -> dict:
    if PROVIDER == "gemini":
        text = await _call_gemini(prompt, schema)
    else:
        text = await _call_openai_compat(prompt, schema)
    return json.loads(text)
