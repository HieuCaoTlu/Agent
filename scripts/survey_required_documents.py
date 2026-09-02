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
  function findHeading(text) {
    return [...document.querySelectorAll('h4')].find(
      (h) => h.textContent.trim().toLowerCase() === text.toLowerCase()
    );
  }

  const docsHeading = findHeading('Thành phần hồ sơ');
  const items = [];
  if (docsHeading && docsHeading.nextElementSibling) {
    const tables = [...docsHeading.nextElementSibling.querySelectorAll('table')];
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
  }

  const stepsHeading = findHeading('Trình tự thực hiện');
  const steps = [];
  if (stepsHeading && stepsHeading.nextElementSibling) {
    const rawText = stepsHeading.nextElementSibling.textContent || '';
    for (const line of rawText.split('\\n')) {
      const trimmed = line.trim();
      if (trimmed) steps.push(trimmed);
    }
  }

  const methodHeading = findHeading('Cách thức thực hiện');
  const methods = [];
  if (methodHeading && methodHeading.nextElementSibling) {
    const table = methodHeading.nextElementSibling.querySelector('table');
    if (table) {
      const headerCells = [...table.querySelectorAll('thead th')].map((th) => th.textContent.trim());
      const methodIdx = headerCells.findIndex((h) => h.includes('Hình thức nộp'));
      const timeIdx = headerCells.findIndex((h) => h.includes('Thời gian'));
      const feeIdx = headerCells.findIndex((h) => h.includes('Phí') || h.includes('lệ phí'));
      const descIdx = headerCells.findIndex((h) => h.includes('Mô tả'));

      const rows = [...table.querySelectorAll('tbody tr')];
      for (const row of rows) {
        const cells = [...row.querySelectorAll('td')].map((td) => td.textContent.trim());
        const methodName = methodIdx !== -1 ? cells[methodIdx] : cells[0];
        if (methodName) {
          methods.push({
            method: methodName || '',
            time: timeIdx !== -1 ? (cells[timeIdx] || '') : '',
            fee: feeIdx !== -1 ? (cells[feeIdx] || '') : '',
            description: descIdx !== -1 ? (cells[descIdx] || '') : '',
          });
        }
      }
    }
  }

  return { items, steps, methods };
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
            name = proc["name"]
            url = "https://dichvucong.gov.vn" + proc["href"]
            existing = cache.get(name)
            if existing and existing.get("items") and "steps" in existing and "methods" in existing:
                skipped += 1
                continue

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1800)
                result = await page.evaluate(SCAN_JS)
                items = result.get("items", [])
                steps = result.get("steps", [])
                methods = result.get("methods", [])
                entry = existing or {}
                entry["href"] = url
                entry["items"] = items
                entry["steps"] = steps
                entry["methods"] = methods
                entry.setdefault("summary", None)
                cache[name] = entry
                done += 1
                print(f"[{i}/{len(procedures)}] OK ({len(items)} items, {len(steps)} steps, {len(methods)} methods): {name[:60]}")
            except Exception as e:
                entry = existing or {"href": url, "items": [], "steps": [], "methods": [], "summary": None}
                entry["error"] = str(e)
                cache[name] = entry
                errors += 1
                print(f"[{i}/{len(procedures)}] LỖI: {name[:60]} — {e}")

            if i % 10 == 0:
                save_cache(cache)
                print(f"--- đã lưu tạm ({done} xong, {skipped} bỏ qua, {errors} lỗi) ---")

            await page.wait_for_timeout(800)

        save_cache(cache)
        print(f"\nHOÀN TẤT: {done} thủ tục quét mới, {skipped} bỏ qua (đã có cache), {errors} lỗi.")
        await browser.close()


asyncio.run(main())
