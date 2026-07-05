from __future__ import annotations

import csv
import io
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from http.cookiejar import CookieJar
from typing import Any

import pandas as pd

BASE_URL = "https://rt.molit.go.kr"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

THING_CODES = {
    "apt": "A",
    "villa": "B",
    "single_multi": "C",
    "officetel": "D",
    "pre_sale_right": "E",
    "commercial": "F",
    "land": "G",
    "factory_warehouse": "H",
    "all": "B",  # 국토부 다운로드는 탭 1개씩 받는 구조라 기본은 연립/다세대
}

SECTION_NAMES = {
    "apt": "아파트",
    "villa": "연립/다세대",
    "single_multi": "단독/다가구",
    "officetel": "오피스텔",
    "pre_sale_right": "분양/입주권",
    "commercial": "상업/업무용",
    "land": "토지",
    "factory_warehouse": "공장/창고",
    "all": "연립/다세대",
}


@dataclass(frozen=True)
class RegionSelection:
    sido_code: str
    sido_name: str
    sgg_code: str = ""
    sgg_name: str = "전체"


class MolitSiteDownloadError(RuntimeError):
    pass


class MolitSiteClient:
    """Client for the MOLIT real-transaction public website CSV download flow.

    This uses the same public website endpoints that the download page uses.
    It does not use a data.go.kr API key.
    """

    def __init__(self) -> None:
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.referer = f"{BASE_URL}/pt/xls/xls.do?&mobileAt="
        self._open_page()

    def _headers(self, ajax: bool = False) -> dict[str, str]:
        headers = {
            "User-Agent": USER_AGENT,
            "Referer": self.referer,
        }
        if ajax:
            headers["X-Requested-With"] = "XMLHttpRequest"
            headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        return headers

    def _open_page(self) -> None:
        request = urllib.request.Request(self.referer, headers=self._headers())
        self.opener.open(request, timeout=30).read()

    def post_json(self, path: str, data: dict[str, Any] | None = None) -> Any:
        encoded = urllib.parse.urlencode(data or {}).encode("utf-8")
        request = urllib.request.Request(f"{BASE_URL}{path}", data=encoded, headers=self._headers(ajax=True))
        response = self.opener.open(request, timeout=30)
        text = response.read().decode("utf-8", "replace")
        return json.loads(text)

    def get_sido_list(self) -> list[dict[str, Any]]:
        return self.post_json("/data/sido.do", {})

    def get_sgg_list(self, sido_code: str) -> list[dict[str, Any]]:
        return self.post_json("/data/sgg.do", {"signguCode": sido_code[:2]})

    def resolve_region(self, keyword: str) -> RegionSelection:
        normalized = keyword.strip()
        if not normalized:
            raise MolitSiteDownloadError("지역명을 입력하세요. 예: 인천, 서울, 양천구")

        sido_list = self.get_sido_list()
        for sido in sido_list:
            name = str(sido.get("ctprvnNm", ""))
            code = str(sido.get("signguCode", ""))
            if normalized in name or name.startswith(normalized) or normalized[:2] == name[:2]:
                return RegionSelection(sido_code=code, sido_name=name)

        for sido in sido_list:
            sido_code = str(sido.get("signguCode", ""))
            sido_name = str(sido.get("ctprvnNm", ""))
            for sgg in self.get_sgg_list(sido_code):
                sgg_name = str(sgg.get("signguNm", ""))
                sgg_code = str(sgg.get("signguCode", ""))
                if normalized in sgg_name or sgg_name in normalized:
                    return RegionSelection(
                        sido_code=sido_code,
                        sido_name=sido_name,
                        sgg_code=sgg_code,
                        sgg_name=sgg_name,
                    )

        raise MolitSiteDownloadError(f"국토부 사이트에서 지역명을 찾지 못했습니다: {keyword}")

    def build_payload(
        self,
        section_key: str,
        region: RegionSelection,
        from_date: date,
        to_date: date,
    ) -> dict[str, str]:
        thing_code = THING_CODES.get(section_key)
        if not thing_code:
            raise MolitSiteDownloadError(f"지원하지 않는 물건 종류입니다: {section_key}")
        return {
            "srhThingNo": thing_code,
            "srhDelngSecd": "1",  # 매매
            "srhAddrGbn": "1",  # 지번주소
            "srhLfstsSecd": "1",
            "srhFromDt": from_date.strftime("%Y-%m-%d"),
            "srhToDt": to_date.strftime("%Y-%m-%d"),
            "srhSidoCd": region.sido_code,
            "srhSggCd": region.sgg_code,
            "srhEmdCd": "",
            "srhLoadCd": "",
            "srhHsmpCd": "",
            "srhRoadNm": "",
            "srhFromAmount": "",
            "srhToAmount": "",
            "mobileAt": "",
            "sidoNm": region.sido_name,
            "sggNm": region.sgg_name or "전체",
            "emdNm": "전체",
            "loadNm": "전체",
            "areaNm": "면적",
            "hsmpNm": "전체",
            "srhArea": "",
            "srhLrArea": "",
        }

    def data_count(self, payload: dict[str, str]) -> int:
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{BASE_URL}/pt/xls/ptXlsDownDataCheck.do",
            data=encoded,
            headers=self._headers(ajax=True),
        )
        response = self.opener.open(request, timeout=60)
        text = response.read().decode("utf-8", "replace")
        try:
            return int(json.loads(text).get("cnt", 0))
        except Exception as exc:
            raise MolitSiteDownloadError(f"데이터 건수 확인 응답을 해석하지 못했습니다: {text[:200]}") from exc

    def download_csv_bytes(self, payload: dict[str, str]) -> bytes:
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{BASE_URL}/pt/xls/ptXlsCSVDown.do",
            data=encoded,
            headers={**self._headers(), "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
        )
        response = self.opener.open(request, timeout=180)
        return response.read()


def csv_bytes_to_dataframe(raw: bytes) -> pd.DataFrame:
    text = raw.decode("cp949", "replace")
    lines = text.splitlines()
    header_index = None
    for idx, line in enumerate(lines):
        if "시군구" in line and "거래금액" in line:
            header_index = idx
            break
    if header_index is None:
        raise MolitSiteDownloadError("다운로드한 CSV에서 거래 데이터 헤더를 찾지 못했습니다.")
    data_text = "\n".join(lines[header_index:])
    return pd.read_csv(io.StringIO(data_text), dtype=str, quoting=csv.QUOTE_MINIMAL)


def default_date_range(days: int = 365) -> tuple[date, date]:
    to_date = date.today()
    from_date = to_date - timedelta(days=days)
    return from_date, to_date


def fetch_molit_transactions(
    region_keyword: str,
    section_key: str = "villa",
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    client = MolitSiteClient()
    start, end = (from_date, to_date) if from_date and to_date else default_date_range()
    region = client.resolve_region(region_keyword)
    payload = client.build_payload(section_key=section_key, region=region, from_date=start, to_date=end)
    count = client.data_count(payload)
    if count <= 0:
        return pd.DataFrame(), {
            "count": count,
            "region": region,
            "from_date": start,
            "to_date": end,
            "payload": payload,
        }
    raw = client.download_csv_bytes(payload)
    df = csv_bytes_to_dataframe(raw)
    df["주택유형"] = SECTION_NAMES.get(section_key, section_key)
    return df, {
        "count": count,
        "region": region,
        "from_date": start,
        "to_date": end,
        "payload": payload,
    }
