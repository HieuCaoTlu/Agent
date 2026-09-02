import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
ROOT_DIR = SCRIPTS_DIR.parent

STEPS = [
    "build_procedure_index.py",
    "flatten_procedure_index.py",
    "survey_required_documents.py",
]


def main():
    for step in STEPS:
        print(f"=== Chạy {step} ===")
        result = subprocess.run([sys.executable, str(SCRIPTS_DIR / step)], cwd=str(ROOT_DIR))
        if result.returncode != 0:
            print(f"{step} thất bại (code {result.returncode}), dừng lại.")
            sys.exit(result.returncode)
    print("Đã làm mới xong procedure_flat_index.json và required_documents_cache.json.")
    print("Khởi động lại backend (hoặc gọi lại /required-documents) để thấy dữ liệu mới.")


if __name__ == "__main__":
    main()
