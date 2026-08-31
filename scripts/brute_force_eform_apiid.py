import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

EFORM_ID = 2056
MIN_ID = 1
MAX_ID = 20000
CONCURRENCY = 8
URL = "https://tokhaidientu.moj.gov.vn/api/eform-service/api/call-api"

OUT_PATH = Path(__file__).parent.parent / "data" / f"eform_{EFORM_ID}_apiid_scan.json"
PROGRESS_PATH = Path(__file__).parent.parent / "data" / f"eform_{EFORM_ID}_apiid_scan.progress"


def load_existing() -> dict:
    if OUT_PATH.exists():
        return json.loads(OUT_PATH.read_text(encoding="utf-8"))
    return {}


def save(results: dict) -> None:
    OUT_PATH.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


async def probe_one(client: httpx.AsyncClient, api_id: int) -> tuple[int, dict | None]:
    try:
        r = await client.post(URL, json={"eformId": EFORM_ID, "apiId": api_id}, timeout=8)
        data = r.json()
        if data.get("code") == 200 and isinstance(data.get("result"), list) and data["result"]:
            return api_id, {"count": len(data["result"]), "sample": data["result"][:3]}
        return api_id, None
    except Exception:
        return api_id, None


async def main():
    results = load_existing()
    already_scanned = {int(k) for k in results}
    todo = [i for i in range(MIN_ID, MAX_ID + 1) if i not in already_scanned]
    print(f"Bắt đầu quét apiId {MIN_ID}-{MAX_ID} cho eformId={EFORM_ID}, còn {len(todo)} id cần quét (đã có {len(already_scanned)} kết quả trước).")

    found_count = sum(1 for v in results.values() if v is not None)
    start_time = time.time()

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(CONCURRENCY)

        async def bounded_probe(api_id: int):
            async with sem:
                return await probe_one(client, api_id)

        batch_size = 200
        for batch_start in range(0, len(todo), batch_size):
            batch = todo[batch_start : batch_start + batch_size]
            tasks = [bounded_probe(i) for i in batch]
            batch_results = await asyncio.gather(*tasks)
            for api_id, data in batch_results:
                results[str(api_id)] = data
                if data is not None:
                    found_count += 1

            save(results)
            elapsed = time.time() - start_time
            scanned = batch_start + len(batch)
            PROGRESS_PATH.write_text(
                f"{scanned}/{len(todo)} quét xong, {found_count} apiId có dữ liệu, "
                f"{elapsed:.0f}s trôi qua\n",
                encoding="utf-8",
            )
            print(f"[{scanned}/{len(todo)}] found={found_count} elapsed={elapsed:.0f}s")

    print(f"\nHOÀN TẤT. Tổng {found_count} apiId có dữ liệu trong range {MIN_ID}-{MAX_ID}.")
    print(f"Kết quả: {OUT_PATH}")


asyncio.run(main())
