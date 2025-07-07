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

# DART API 키
DART_API_KEY = os.getenv("DART_API_KEY")

# 기업명 ↔ 고유코드 매핑 테이블
CORP_CODE_MAP = {}

# 키워드 설정
OFFERING_KEYWORDS = ["증권신고서", "투자설명서", "공모", "청약"]

# 기업 고유코드 로딩 함수
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

# 실제 DART 본문 HTML에서 배정 내용 추출하기
def extract_allotment_info_from_dart(rcp_no):
    try:
        view_url = f"https://dart.fss.or.kr/report/viewer.do?rcpNo={rcp_no}"
        res = requests.get(view_url)
        soup = BeautifulSoup(res.text, "html.parser")

        # iframe으로 본문 연결
        iframe = soup.find("iframe")
        if not iframe:
            return []

        iframe_src = iframe.get("src")
        if not iframe_src:
            return []

        html_url = f"https://dart.fss.or.kr{iframe_src}"
        html_res = requests.get(html_url)
        html_soup = BeautifulSoup(html_res.text, "html.parser")

        text_blocks = html_soup.find_all(['p', 'li', 'td'])
        allot_lines = [t.get_text(strip=True) for t in text_blocks if "배정" in t.get_text()]

        return allot_lines[:10]  # 최대 10줄 제한
    except Exception as e:
        return [f"❌ 오류 발생: {str(e)}"]

# 텍스트 리스트를 HTML 테이블로 변환
def make_html_table(lines):
    if not lines:
        return "<p>❌ 배정 관련 정보를 찾을 수 없습니다.</p>"
    table = "<table border='1' style='border-collapse:collapse;'>"
    table += "<tr><th>항목</th><th>내용</th></tr>"
    for i, line in enumerate(lines):
        table += f"<tr><td>d{i+1}</td><td>{line}</td></tr>"
    table += "</table>"
    return table

# 서버 시작 시 고유코드 로딩
load_corp_codes()

# API 엔드포인트
@app.get("/dart")
def get_dart_info(corp: str):
    corp_code = CORP_CODE_MAP.get(corp)
    if not corp_code:
        return {"error": f"'{corp}'에 해당하는 고유코드를 찾을 수 없습니다."}

    url = f"https://opendart.fss.or.kr/api/list.json?crtfc_key={DART_API_KEY}&corp_code={corp_code}&page_count=100"
    res = requests.get(url)
    data = res.json()

    if data.get("status") != "000":
        return {"error": "공시 목록 조회 실패", "message": data.get("message")}

    results = []
    for item in data.get("list", []):
        title = item.get("report_nm", "")
        if any(k in title for k in OFFERING_KEYWORDS):
            rcp_no = item.get("rcept_no")
            link = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcp_no}"

            allot_lines = extract_allotment_info_from_dart(rcp_no)
            table_html = make_html_table(allot_lines)

            results.append({
                "보고서명": title,
                "기업명": corp,
                "공시일자": item.get("rcept_dt"),
                "공시링크": link,
                "배정내역": table_html
            })

    return results if results else {"message": f"'{corp}' 관련 공모 보고서가 없습니다."}
