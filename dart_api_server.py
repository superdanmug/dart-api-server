from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
from datetime import datetime

app = FastAPI()

# CORS 설정 (모든 origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경변수에서 DART API 키 불러오기
DART_API_KEY = os.getenv("DART_API_KEY")

# 테스트용 기업코드 매핑 (필요시 확장 가능)
CORP_CODE_MAPPING = {
    "삼성전자": "00126380",
    "네이버": "00222469",
    "카카오": "00230253",
    "LG화학": "00356370",
    "현대자동차": "00164742",
    "삼성물산": "00126361",
    "SK하이닉스": "00164779",
    "기아": "00164744",
    "삼성SDI": "00126376",
    "포스코홀딩스": "00146986"
}


@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAPPING.get(corp)

    if not corp_code:
        return {"error": "기업 코드 없음", "message": f"{corp} 기업의 DART 코드가 없습니다."}

    # 2024년 1월 1일부터 현재까지 조회
    bgn_de = "20240101"

    url = "https://opendart.fss.or.kr/api/list.json"
    params = {
        "crtfc_key": DART_API_KEY,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "page_count": 10
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        if data.get("status") == "013":
            return {"error": "공시 정보 조회 실패", "message": "조회된 데이터가 없습니다."}
        return data
    else:
        return {"error": "API 요청 실패", "status_code": response.status_code}
