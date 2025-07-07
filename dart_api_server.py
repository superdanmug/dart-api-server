from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

# CORS 설정 (GPT에서 호출 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DART API KEY 설정
DART_API_KEY = "a70b2cc3a7b333ad4b91fb0c770f69d249fab3c4"

# 상장사 코드 조회 함수
def get_corp_code(corp_name):
    # DART API에서 제공하는 기업 리스트 XML을 다운받아야 정확하지만,
    # 여기서는 간단히 주요 기업만 하드코딩 예시
    mapping = {
        "삼성전자": "00126380",
        "네이버": "00222049",
        "카카오": "00223235"
    }
    return mapping.get(corp_name)

@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = get_corp_code(corp)
    if not corp_code:
        return {"error": f"기업명 '{corp}'의 corp_code를 찾을 수 없습니다."}
    
    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&page_count=5"
    response = requests.get(url)
    data = response.json()

    if data["status"] != "000":
        return {"error": "공시 정보 조회 실패", "message": data.get("message")}

    return {
        "corp_name": corp,
        "reports": [
            {
                "title": r["report_nm"],
                "date": r["rcept_dt"],
                "url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}"
            } for r in data["list"]
        ]
    }
