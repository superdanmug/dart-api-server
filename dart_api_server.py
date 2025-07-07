from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import os
import zipfile
import xml.etree.ElementTree as ET
from io import BytesIO
from bs4 import BeautifulSoup

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 환경변수에서 DART API KEY 가져오기
DART_API_KEY = os.getenv("DART_API_KEY")

# 기업명 → 고유코드 맵
CORP_CODE_MAP = {}

# 공모 관련 키워드
OFFERING_KEYWORDS = ["증권신고서", "투자설명서", "공모", "청약"]

# 시작 시 기업코드 불러오기
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
                    name = child.findtext("corp_name")
                    code = child.findtext("corp_code")
                    if name and code:
                        CORP_CODE_MAP[name.strip()] = code.strip()

# 배정 관련 HTML 정보 추출 함수
def extract_allotment_info_as_html(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    items = soup.find_all("li")
    filtered = [item.get_text(strip=True) for item in items if "배정" in item.get_text()]
    
    # HTML 테이블 생성
    table_html = "<table border='1' style='border-collapse:collapse;'>"
    table_html += "<tr><th>구분</th><th>내용</th></tr>"
    for idx, line in enumerate(filtered, 1):
        table_html += f"<tr><td>{idx}</td><td>{line}</td></tr>"
    table_html += "</table>"
    return table_html

# 서버 기동 시 기업코드 로딩
load_corp_codes()

@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAP.get(corp)
    if not corp_code:
        return {"error": f"기업명 '{corp}'을 찾을 수 없습니다."}

    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&page_count=100"
    res = requests.get(url)
    data = res.json()

    if data.get("status") != "000":
        return {"error": "공시정보 조회 실패", "message": data.get("message")}

    reports = []
    for item in data.get("list", []):
        if any(keyword in item.get("report_nm", "") for keyword in OFFERING_KEYWORDS):
            rcept_no = item.get("rcept_no")
            html_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

            # 실제 크롤링 로직을 나중에 연결 (지금은 샘플로 구성)
            sample_html = """
            <ol>
                <li>우리사주조합: 금번 공모는 우리사주조합에 배정하지 않습니다.</li>
                <li>기관투자자(고위험고수익투자신탁, 벤처기업투자신탁 포함) : 총 공모주식의 75.0%(1,050,000주)를 배정합니다.</li>
                <li>일반청약자 : 총 공모주식의 25.00%(350,000주)를 배정합니다.</li>
                <li>따라서 금번 IPO는 일반청약자에게 350,000주를 배정할 예정이며, 균등방식 배정 예정 물량은 175,000주입니다.</li>
            </ol>
            """
            allotment_html = extract_allotment_info_as_html(sample_html)

            reports.append({
                "보고서명": item.get("report_nm"),
                "기업명": corp,
                "공시일자": item.get("rcept_dt"),
                "공시링크": html_url,
                "배정내역": allotment_html
            })

    return reports if reports else {"message": f"{corp} 관련 공모 공시가 없습니다."}
