from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os

app = FastAPI()

# CORS 설정 (GPT 호출 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 어떤 출처에서든 허용 (테스트용)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ 환경변수에서 DART API 키 불러오기
DART_API_KEY = os.getenv("DART_API_KEY")

# 테스트용 간단한 기업명-코드 매핑 (추후 확장 가능)
CORP_CODE_MAPPING = {
    "삼성전자": "00126380",
    "네이버": "00222049",
    "카카오": "00223235",
    "LG화학": "00356370"
}

@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAPPING.get(corp)
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
