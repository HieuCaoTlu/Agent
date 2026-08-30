import json
from pathlib import Path

SOURCE_PATH = Path(__file__).parent.parent / "data" / "procedure_index.json"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "procedure_flat_index.json"


def main():
    grouped = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    seen = set()
    flat = []
    for candidates in grouped.values():
        for c in candidates:
            if c["href"] in seen:
                continue
            seen.add(c["href"])
            flat.append(c)
    flat.sort(key=lambda c: c["name"])
    OUTPUT_PATH.write_text(json.dumps(flat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã gộp {len(flat)} thủ tục duy nhất vào {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
