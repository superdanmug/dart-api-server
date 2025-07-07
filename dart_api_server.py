from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DART API 키 불러오기
DART_API_KEY = os.getenv("DART_API_KEY")

# 기업명 → 고유코드 매핑
CORP_CODE_MAP = {}

# DART에서 corpCode.xml 불러오기
def load_corp_codes():
    global CORP_CODE_MAP
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={DART_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        with zipfile.ZipFile(BytesIO(response.content)) as z:
            with z.open(z.namelist()[0]) as xml_file:
                tree = ET.parse(xml_file)
                root = tree.getroot()
                for child in root:
                    corp_name = child.findtext("corp_name")
                    corp_code = child.findtext("corp_code")
                    if corp_name and corp_code:
                        CORP_CODE_MAP[corp_name.strip()] = corp_code.strip()

# 서버 시작 시 기업 코드 미리 로딩
load_corp_codes()

# 공모 관련 키워드
OFFERING_KEYWORDS = ["증권신고서", "투자설명서", "공모", "청약"]

@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAP.get(corp)
    if not corp_code:
        return {"error": "기업명 검색 실패", "message": f"DART에서 '{corp}'에 해당하는 기업 코드를 찾을 수 없습니다."}

    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&page_count=100"
    res = requests.get(url)
    data = res.json()

    if data.get("status") != "000":
        return {"error": "공시 정보 조회 실패", "message": data.get("message")}

    offering_reports = []
    for report in data.get("list", []):
        if any(keyword in report.get("report_nm", "") for keyword in OFFERING_KEYWORDS):
            offering_reports.append({
                "보고서명": report.get("report_nm"),
                "기업명": corp,
                "보고서일자": report.get("rcept_dt"),
                "공시링크": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={report.get('rcept_no')}"
            })

    if not offering_reports:
        return {"message": f"'{corp}'의 공모 관련 공시가 없습니다."}

    return offering_reports
