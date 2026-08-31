import json
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent.parent
FLAT_INDEX_PATH = ROOT / "data" / "procedure_flat_index.json"
CACHE_PATH = ROOT / "data" / "required_documents_cache.json"


def main():
    flat_index = json.loads(FLAT_INDEX_PATH.read_text(encoding="utf-8"))
    url_to_name = {
        "https://dichvucong.gov.vn" + entry["href"]: entry["name"] for entry in flat_index
    }

    old_cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    new_cache = {}
    unmatched = 0
    for url, entry in old_cache.items():
        name = url_to_name.get(url)
        if not name:
            unmatched += 1
            continue
        new_cache[name] = {
            "href": url,
            "items": entry.get("items") or [],
            "summary": entry.get("summary"),
        }

    CACHE_PATH.write_text(json.dumps(new_cache, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã migrate {len(new_cache)} thủ tục (key theo tên). Bỏ qua {unmatched} URL không khớp index.")


if __name__ == "__main__":
    main()
