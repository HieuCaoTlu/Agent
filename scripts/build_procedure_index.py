import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.sync_api import sync_playwright
from procedure_keywords import KEYWORDS

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "procedure_index.json"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def log(*a):
    print(*a, flush=True)


def survey_keyword(page, keyword: str) -> list[dict]:
    url = "https://dichvucong.gov.vn/dvc-ket-qua-thu-tuc?keyword=" + urllib.parse.quote_plus(keyword)
    page.goto(url, wait_until="networkidle", timeout=30000)
    time.sleep(1.5)
    results = page.evaluate(
        """
        () => [...document.querySelectorAll('a[href*="/thu-tuc-hanh-chinh/"]')]
          .map(a => ({ name: a.textContent.trim(), href: a.getAttribute('href') }))
          .filter(r => r.name && r.href)
        """
    )
    seen = set()
    unique = []
    for r in results:
        if r["href"] in seen:
            continue
        seen.add(r["href"])
        unique.append(r)
    return unique


def main():
    index = {}
    if OUTPUT_PATH.exists():
        index = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="vi-VN")
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()

        log("Mở trang chủ để lấy cookie/vượt WAF...")
        page.goto("https://dichvucong.gov.vn/", wait_until="networkidle", timeout=30000)
        time.sleep(1.5)

        for i, keyword in enumerate(KEYWORDS, 1):
            if keyword in index and index[keyword]:
                log(f"[{i}/{len(KEYWORDS)}] Bỏ qua (đã có): {keyword}")
                continue
            try:
                results = survey_keyword(page, keyword)
                index[keyword] = results
                log(f"[{i}/{len(KEYWORDS)}] {keyword} -> {len(results)} kết quả")
            except Exception as exc:
                log(f"[{i}/{len(KEYWORDS)}] LỖI {keyword}: {exc}")
                index[keyword] = []

            if i % 10 == 0:
                OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
                OUTPUT_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
                log(f"--- Đã lưu tạm sau {i} từ khóa ---")

        browser.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"XONG. Đã lưu {len(index)} thủ tục vào {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
