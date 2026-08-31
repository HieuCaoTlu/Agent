import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

OUT_DIR = Path(__file__).parent.parent / "data" / "form_inspect"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RUN_ID = time.strftime("%Y%m%d-%H%M%S")
NETWORK_LOG = OUT_DIR / f"network-{RUN_ID}.jsonl"
DOM_SNAPSHOT_DIR = OUT_DIR / f"dom-{RUN_ID}"
DOM_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

START_URL = "https://dichvucong.gov.vn/"


async def main():
    network_file = NETWORK_LOG.open("a", encoding="utf-8")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="vi-VN",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )

        def log_response(response):
            try:
                url = response.url
                if any(s in url for s in (".js", ".css", ".png", ".jpg", ".svg", ".woff", ".ico", "google", "gstatic")):
                    return
                entry = {
                    "ts": time.time(),
                    "method": response.request.method,
                    "url": url,
                    "status": response.status,
                    "request_post_data": response.request.post_data,
                }
                asyncio.create_task(_attach_body(response, entry, network_file))
            except Exception as exc:
                print("log_response error:", exc)

        async def _attach_body(response, entry, f):
            try:
                ctype = response.headers.get("content-type", "")
                if "json" in ctype or "text" in ctype:
                    body = await response.text()
                    entry["response_body"] = body[:20000]
            except Exception:
                entry["response_body"] = None
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            f.flush()

        context.on("response", log_response)

        page = await context.new_page()
        await page.goto(START_URL, wait_until="domcontentloaded")

        print("=" * 70)
        print("Trình duyệt đã mở. Hãy tự đăng nhập VNeID và thao tác form thật.")
        print(f"Network log (API calls): {NETWORK_LOG}")
        print(f"DOM snapshot sẽ lưu vào: {DOM_SNAPSHOT_DIR}")
        print("Gõ Enter trong terminal này bất kỳ lúc nào để chụp DOM snapshot")
        print("của TẤT CẢ frame hiện tại (kể cả iframe cross-origin) vào file.")
        print("Gõ 'q' rồi Enter để kết thúc và đóng trình duyệt.")
        print("=" * 70)

        snapshot_count = 0
        loop = asyncio.get_event_loop()
        while True:
            cmd = await loop.run_in_executor(None, input, "")
            if cmd.strip().lower() == "q":
                break
            snapshot_count += 1
            await dump_all_frames(page, DOM_SNAPSHOT_DIR, snapshot_count)
            print(f"Đã lưu snapshot #{snapshot_count}")

        await browser.close()
        network_file.close()
        print(f"\nXONG. Network log: {NETWORK_LOG}")
        print(f"DOM snapshots: {DOM_SNAPSHOT_DIR}")


async def dump_all_frames(page, out_dir: Path, idx: int):
    for i, frame in enumerate(page.frames):
        try:
            html = await frame.content()
            url = frame.url
            safe_url = "".join(c if c.isalnum() else "_" for c in url)[:80]
            path = out_dir / f"snap{idx}-frame{i}-{safe_url}.html"
            path.write_text(html, encoding="utf-8")
        except Exception as exc:
            print(f"  lỗi dump frame {i} ({frame.url}): {exc}")


asyncio.run(main())
