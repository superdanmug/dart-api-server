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

# DART API 키 설정
DART_API_KEY = os.getenv("DART_API_KEY")

# 기업명 → 고유코드 맵
CORP_CODE_MAP = {}

# 공모 관련 키워드
OFFERING_KEYWORDS = ["증권신고서", "투자설명서", "공모", "청약"]

# 서버 시작 시 기업코드 불러오기
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

# 본문 HTML에서 배정 테이블 추출
def extract_allotment_table(html_text):
    soup = BeautifulSoup(html_text, "html.parser")
    ol = soup.find("ol")
    if not ol:
        return "해당 보고서에서 배정 정보를 찾을 수 없습니다."

    rows = []
    for li in ol.find_all("li"):
        text = li.get_text(strip=True)
        if any(keyword in text for keyword in ["배정", "청약자"]):
            parts = text.split(":", 1)
            if len(parts) == 2:
                rows.append(f"<tr><td>{parts[0].strip()}</td><td>{parts[1].strip()}</td></tr>")
            else:
                rows.append(f"<tr><td colspan='2'>{text}</td></tr>")

    table_html = (
        "<table border='1' style='border-collapse:collapse;'>"
        "<tr><th>구분</th><th>내용</th></tr>"
        + "".join(rows) + "</table>"
    )
    return table_html

# 서버 기동 시 호출
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
            doc_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            html_page = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

            # 실제 본문 HTML 가져오기
            view_url = f"https://dart.fss.or.kr/report/viewer.do?rcpNo={rcept_no}&dcmNo=&eleId=0&offset=0&length=0&dtd=dart3.xsd"
            try:
                html_res = requests.get(view_url, timeout=5)
                html_text = html_res.text
                table_html = extract_allotment_table(html_text)
            except:
                table_html = "<p>본문 로딩 실패</p>"

            reports.append({
                "보고서명": item.get("report_nm"),
                "기업명": corp,
                "공시일자": item.get("rcept_dt"),
                "공시링크": doc_url,
                "배정내역_HTML": table_html
            })

    return reports if reports else {"message": f"{corp} 관련 공모 공시가 없습니다."}
