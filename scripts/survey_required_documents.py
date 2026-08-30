import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import async_playwright

_LIMIT = int(os.environ.get("SURVEY_LIMIT", "0")) or None

INDEX_PATH = Path(__file__).parent.parent / "data" / "procedure_flat_index.json"
CACHE_PATH = Path(__file__).parent.parent / "data" / "required_documents_cache.json"

SCAN_JS = """
() => {
  const headings = [...document.querySelectorAll('h4')].filter(
    (h) => h.textContent.trim() === 'Thành phần hồ sơ'
  );
  if (headings.length === 0) return { items: [] };

  const container = headings[0].nextElementSibling;
  if (!container) return { items: [] };

  const tables = [...container.querySelectorAll('table')];
  const items = [];
  for (const table of tables) {
    const headerCells = [...table.querySelectorAll('thead th')].map((th) => th.textContent.trim());
    const nameIdx = headerCells.findIndex((h) => h.includes('Tên giấy tờ'));
    const qtyIdx = headerCells.findIndex((h) => h.includes('Số lượng'));
    if (nameIdx === -1) continue;

    const rows = [...table.querySelectorAll('tbody tr')];
    for (const row of rows) {
      const cells = [...row.querySelectorAll('td')];
      const name = cells[nameIdx] ? cells[nameIdx].textContent.trim() : '';
      const qty = qtyIdx !== -1 && cells[qtyIdx] ? cells[qtyIdx].textContent.trim() : '';
      if (name) {
        items.push({ name, qty });
      }
    }
  }
  return { items };
}
"""


def load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


async def main():
    procedures = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if _LIMIT:
        procedures = procedures[:_LIMIT]
    cache = load_cache()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            )
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await context.new_page()

        print("Mở trang chủ để lấy cookie...")
        await page.goto("https://dichvucong.gov.vn/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        done = 0
        skipped = 0
        errors = 0
        for i, proc in enumerate(procedures, 1):
            url = "https://dichvucong.gov.vn" + proc["href"]
            if url in cache and cache[url].get("items"):
                skipped += 1
                continue

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1800)
                result = await page.evaluate(SCAN_JS)
                items = result.get("items", [])
                cache[url] = {"items": items, "summary": None}
                done += 1
                print(f"[{i}/{len(procedures)}] OK ({len(items)} items): {proc['name'][:60]}")
            except Exception as e:
                cache[url] = {"items": [], "summary": None, "error": str(e)}
                errors += 1
                print(f"[{i}/{len(procedures)}] LỖI: {proc['name'][:60]} — {e}")

            if i % 10 == 0:
                save_cache(cache)
                print(f"--- đã lưu tạm ({done} xong, {skipped} bỏ qua, {errors} lỗi) ---")

            await page.wait_for_timeout(800)

        save_cache(cache)
        print(f"\nHOÀN TẤT: {done} thủ tục quét mới, {skipped} bỏ qua (đã có cache), {errors} lỗi.")
        await browser.close()


asyncio.run(main())
