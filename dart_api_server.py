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

# DART API 키 환경변수에서 불러오기
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

# 본문에서 배정 정보 추출
def extract_allotment_from_dart(rcept_no):
    main_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
    response = requests.get(main_url)
    soup = BeautifulSoup(response.text, "html.parser")
    iframe = soup.find("iframe")
    if not iframe:
        return None

    iframe_src = iframe["src"]
    full_iframe_url = f"https://dart.fss.or.kr{iframe_src}"
    iframe_res = requests.get(full_iframe_url)
    iframe_soup = BeautifulSoup(iframe_res.text, "html.parser")

    # li 문단 기준 배정 문장만 필터링
    lines = []
    for li in iframe_soup.find_all("li"):
        txt = li.get_text(strip=True)
        if "배정" in txt and ("기관" in txt or "일반" in txt or "우리사주" in txt):
            lines.append(txt)
    return lines

# API 실행 시 기업코드 불러오기
load_corp_codes()

OFFERING_KEYWORDS = ["증권신고서", "투자설명서", "공모", "청약"]

@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAP.get(corp)
    if not corp_code:
        return {"error": f"'{corp}'에 해당하는 기업을 찾을 수 없습니다."}

    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&page_count=100"
    res = requests.get(url)
    data = res.json()

    if data.get("status") != "000":
        return {"error": "공시 정보 조회 실패", "message": data.get("message")}

    reports = []
    for item in data.get("list", []):
        if any(keyword in item.get("report_nm", "") for keyword in OFFERING_KEYWORDS):
            rcept_no = item.get("rcept_no")
            html_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
            allotment_lines = extract_allotment_from_dart(rcept_no)

            allotment_html = ""
            if allotment_lines:
                allotment_html += "<table border='1' style='border-collapse:collapse;'>"
                allotment_html += "<tr><th>구분</th><th>내용</th></tr>"
                for line in allotment_lines:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        allotment_html += f"<tr><td>{parts[0]}</td><td>{parts[1]}</td></tr>"
                    else:
                        allotment_html += f"<tr><td colspan='2'>{line}</td></tr>"
                allotment_html += "</table>"
            else:
                allotment_html = "<p>배정 정보가 확인되지 않았습니다.</p>"

            reports.append({
                "보고서명": item.get("report_nm"),
                "공시일자": item.get("rcept_dt"),
                "기업명": corp,
                "공시링크": html_url,
                "배정내역(테이블)": allotment_html
            })

    return reports if reports else {"message": f"'{corp}'에 대한 공모 공시를 찾을 수 없습니다."}
