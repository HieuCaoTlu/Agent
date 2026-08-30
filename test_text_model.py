import asyncio

from app import text_model


async def main() -> None:
    print(f"Provider: {text_model.PROVIDER}")
    if text_model.PROVIDER == "gemini":
        print(f"Model: {text_model.GEMINI_MODEL}")
    else:
        print(f"Base URL: {text_model.OPENAI_COMPAT_BASE_URL}")
        print(f"Model: {text_model.OPENAI_COMPAT_MODEL}")

    print("\n--- Test generate_text ---")
    text = await text_model.generate_text("Trả lời đúng 1 từ: thủ đô của Việt Nam là gì?")
    print(f"Kết quả: {text!r}")

    print("\n--- Test generate_json ---")
    schema = {
        "type": "OBJECT",
        "properties": {
            "capital": {"type": "STRING"},
            "is_in_asia": {"type": "BOOLEAN"},
        },
        "required": ["capital", "is_in_asia"],
    }
    result = await text_model.generate_json(
        "Thủ đô của Việt Nam là gì? Việt Nam có ở châu Á không? Trả JSON đúng schema.",
        schema,
    )
    print(f"Kết quả: {result!r}")

    print("\nOK — kết nối tới text model provider hoạt động bình thường.")


if __name__ == "__main__":
    asyncio.run(main())
