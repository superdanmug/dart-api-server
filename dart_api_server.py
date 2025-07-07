# ✅ 목표 1단계: DART 실제 본문 HTML에서 정보 자동 추출
# - HTML 페이지 내 iframe -> viewDoc.do -> 실제 본문 HTML 추출
# - 배정 비율 등 관련 텍스트 자동 수집

import requests
from bs4 import BeautifulSoup
import re

# DART rcept_no에서 본문 HTML을 가져오는 함수
def get_dart_main_html(rcept_no):
    base_url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"
    response = requests.get(base_url)
    if response.status_code != 200:
        return None, f"접속 실패: {response.status_code}"

    soup = BeautifulSoup(response.text, "html.parser")
    iframe = soup.find("iframe")
    if not iframe:
        return None, "iframe 태그 없음"

    src = iframe.get("src")
    full_url = f"https://dart.fss.or.kr{src}"
    view_res = requests.get(full_url)
    if view_res.status_code != 200:
        return None, f"본문 로딩 실패: {view_res.status_code}"

    return view_res.text, None

# 본문 HTML에서 배정 관련 정보 추출 (li 또는 p 기반)
def extract_allotment_info_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    texts = []
    for tag in soup.find_all(["li", "p", "td"]):
        txt = tag.get_text(strip=True)
        if any(keyword in txt for keyword in ["배정", "청약", "기관", "일반청약자"]):
            texts.append(txt)
    return texts[:10]  # 상위 10개 정도만 반환 (필터 강화 필요 시 추가)

# 테스트 예시
if __name__ == "__main__":
    rcept_no = "20250707000070"  # 샘플 리포트 번호
    html, err = get_dart_main_html(rcept_no)
    if err:
        print("오류:", err)
    else:
        results = extract_allotment_info_from_html(html)
        for line in results:
            print("-", line)
