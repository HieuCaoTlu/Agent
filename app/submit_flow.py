import urllib.parse

SUBMIT_PROVINCE = "Thành phố Hà Nội"
SUBMIT_WARD = "Yên Sở"


def build_search_url(procedure_name: str) -> str:
    query = urllib.parse.quote_plus(procedure_name)
    return f"https://dichvucong.gov.vn/dvc-ket-qua-thu-tuc?keyword={query}"
