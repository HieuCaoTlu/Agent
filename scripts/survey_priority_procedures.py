import asyncio
import json
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from playwright.async_api import async_playwright
from priority_keywords import PRIORITY_KEYWORDS

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
FLAT_INDEX_PATH = ROOT / "data" / "procedure_flat_index.json"
DOCS_CACHE_PATH = ROOT / "data" / "required_documents_cache.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

SCAN_DOCS_JS = """
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
      if (name) items.push({ name, qty });
    }
  }
  return { items };
}
"""


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def search_keyword(page, keyword: str) -> list[dict]:
    url = "https://dichvucong.gov.vn/dvc-ket-qua-thu-tuc?keyword=" + urllib.parse.quote_plus(keyword)
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await page.wait_for_timeout(1500)
    results = await page.evaluate(
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


async def main():
    # RESUME: nếu procedure_flat_index.json đã có sẵn dữ liệu từ lần chạy
    # trước (search xong), dùng lại luôn — không search lại từ đầu. Chỉ
    # search lại nếu file trống/chưa tồn tại.
    existing_flat_index: list[dict] = load_json(FLAT_INDEX_PATH, [])
    docs_cache: dict = load_json(DOCS_CACHE_PATH, {})

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 900}, locale="vi-VN")
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = await context.new_page()

        print("Mở trang chủ để lấy cookie...")
        await page.goto("https://dichvucong.gov.vn/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)

        if existing_flat_index:
            print(f"Đã có sẵn {len(existing_flat_index)} thủ tục trong procedure_flat_index.json — dùng lại, bỏ qua bước search.")
            all_candidates: dict[str, dict] = {e["href"]: e for e in existing_flat_index}
        else:
            all_candidates = {}
            for i, keyword in enumerate(PRIORITY_KEYWORDS, 1):
                try:
                    results = await search_keyword(page, keyword)
                    print(f"[search {i}/{len(PRIORITY_KEYWORDS)}] {keyword} -> {len(results)} kết quả")
                    for r in results:
                        all_candidates[r["href"]] = r
                except Exception as exc:
                    print(f"[search {i}/{len(PRIORITY_KEYWORDS)}] LỖI {keyword}: {exc}")
                await page.wait_for_timeout(500)

            print(f"\nTổng {len(all_candidates)} thủ tục ứng viên duy nhất, ghi đè flat index...")
            flat_index = [{"name": cand["name"], "href": href} for href, cand in all_candidates.items()]
            flat_index.sort(key=lambda e: e["name"])
            save_json(FLAT_INDEX_PATH, flat_index)
            print(f"Đã ghi đè procedure_flat_index.json với {len(flat_index)} thủ tục.")

        print("\nQuét Thành phần hồ sơ cho từng thủ tục ứng viên...")
        done = errors = skipped = 0
        for i, (href, cand) in enumerate(all_candidates.items(), 1):
            name = cand["name"]
            if name in docs_cache and docs_cache[name].get("items"):
                skipped += 1
                continue
            url = "https://dichvucong.gov.vn" + href
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(1800)
                result = await page.evaluate(SCAN_DOCS_JS)
                items = result.get("items", [])
                docs_cache[name] = {"href": url, "items": items, "summary": None}
                done += 1
                print(f"[docs {i}/{len(all_candidates)}] OK ({len(items)} items): {name[:60]}")
            except Exception as e:
                docs_cache[name] = {"href": url, "items": [], "summary": None, "error": str(e)}
                errors += 1
                print(f"[docs {i}/{len(all_candidates)}] LỖI: {name[:60]} — {e}")

            if i % 10 == 0:
                save_json(DOCS_CACHE_PATH, docs_cache)
                print(f"--- đã lưu tạm ({done} xong, {skipped} bỏ qua, {errors} lỗi) ---")
            await page.wait_for_timeout(700)

        save_json(DOCS_CACHE_PATH, docs_cache)
        print(f"\nHOÀN TẤT: {done} thủ tục quét mới, {skipped} bỏ qua (đã có cache), {errors} lỗi.")
        await browser.close()


asyncio.run(main())
