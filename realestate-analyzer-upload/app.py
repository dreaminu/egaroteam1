from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analyzer import analyze_transactions
from src.cleaner import clean_transactions
from src.report import save_outputs
from src.sections import SECTION_CONFIGS, get_section_config
from src.site_downloader import MolitSiteClient, MolitSiteDownloadError, fetch_molit_transactions


SECTION_LABELS = {config.title: key for key, config in SECTION_CONFIGS.items() if key != "all"}
FALLBACK_SIDO_NAMES = [
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
    "세종특별자치시",
    "경기도",
    "강원특별자치도",
    "충청북도",
    "충청남도",
    "전북특별자치도",
    "전라남도",
    "경상북도",
    "경상남도",
    "제주특별자치도",
]

st.set_page_config(
    page_title="지역별 실거래 인기 평수 찾기",
    page_icon="🏠",
    layout="wide",
)


@st.cache_data(show_spinner=False, ttl=60 * 60)
def get_sido_names() -> list[str]:
    try:
        client = MolitSiteClient()
        names = [str(item.get("ctprvnNm", "")).strip() for item in client.get_sido_list()]
        names = [name for name in names if name]
        return names or FALLBACK_SIDO_NAMES
    except Exception:
        return FALLBACK_SIDO_NAMES


@st.cache_data(show_spinner=False, ttl=60 * 60)
def fetch_from_molit_cached(
    region_keyword: str,
    section_key: str,
    from_date_iso: str,
    to_date_iso: str,
) -> tuple[pd.DataFrame, dict]:
    start = date.fromisoformat(from_date_iso)
    end = date.fromisoformat(to_date_iso)
    return fetch_molit_transactions(
        region_keyword=region_keyword,
        section_key=section_key,
        from_date=start,
        to_date=end,
    )


def render_dataframe_section(title: str, df: pd.DataFrame, max_rows: int = 20) -> None:
    st.subheader(title)
    if df.empty:
        st.info("표시할 데이터가 없습니다.")
    else:
        st.dataframe(df.head(max_rows), use_container_width=True, hide_index=True)


def make_download_button(label: str, path: Path, mime: str) -> None:
    if path.exists():
        st.download_button(
            label=label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            use_container_width=True,
        )


def show_main_answer(top_dong_area: pd.DataFrame, region_keyword: str) -> None:
    st.subheader("가장 많이 거래된 동네와 평수대")
    if top_dong_area.empty:
        st.warning("조건에 맞는 결과가 없습니다.")
        return

    top = top_dong_area.iloc[0]
    st.success(
        f"{region_keyword} 기준으로 가장 거래량이 많은 조합은 "
        f"'{top['법정동']} · {top['면적구간']}' 입니다."
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("동네", str(top["법정동"]))
    c2.metric("가장 많이 거래된 평수대", str(top["면적구간"]))
    c3.metric("거래건수", f"{int(top['거래건수']):,}건")
    c4.metric("평균 거래금액", f"{int(top['평균거래금액_만원']):,}만원")
    c5.metric("평균 평당가", f"{int(top['평균평당가_만원']):,}만원")


st.title("지역별 실거래 인기 평수 찾기")
st.caption("엑셀 업로드 없이 국토교통부 실거래가 사이트에서 데이터를 자동으로 가져와 분석합니다.")

with st.expander("이 도구가 하는 일", expanded=True):
    st.markdown(
        """
        **시도를 선택하면, 국토교통부 실거래가 공개시스템에서 1년 단위 데이터를 가져와**
        그 지역에서 가장 많이 거래된 **동네 + 평수대**를 찾아줍니다.

        예: `인천광역시` 선택 + `2025년` 선택 → 인천광역시 2025년 거래 데이터 수집 → 법정동+평수대별 거래량 분석

        주의: 거래량이 많다는 것은 해당 기간 거래가 활발했다는 뜻이지, 투자 추천이 아닙니다.
        """
    )

left, right = st.columns([1, 2])

with left:
    st.header("1. 시도 선택")
    sido_names = get_sido_names()
    default_sido_index = sido_names.index("인천광역시") if "인천광역시" in sido_names else 0
    selected_sido = st.selectbox(
        "국토교통부 실거래가공개시스템 시도",
        options=sido_names,
        index=default_sido_index,
        help="국토교통부 실거래가공개시스템에서 제공하는 시도 목록입니다.",
    )

    st.header("2. 물건 종류")
    section_title = st.selectbox(
        "분석할 부동산 종류",
        options=list(SECTION_LABELS.keys()),
        index=list(SECTION_LABELS.keys()).index("연립/다세대"),
    )
    section_key = SECTION_LABELS[section_title]
    section_config = get_section_config(section_key)

    st.header("3. 조회 연도")
    current_year = date.today().year
    years = list(range(current_year, 2005, -1))
    selected_year = st.selectbox(
        "1년 단위로 조회",
        options=years,
        index=years.index(2025) if 2025 in years else 0,
        help="선택한 연도의 1월 1일부터 12월 31일까지 조회합니다. 현재 연도는 오늘 날짜까지만 조회합니다.",
    )
    from_date = date(selected_year, 1, 1)
    to_date = date(selected_year, 12, 31)
    if selected_year == current_year:
        to_date = date.today()

    st.caption(f"조회 기간: {from_date} ~ {to_date} (1년 단위)")

    analyze_clicked = st.button("국토부에서 가져와 분석하기", type="primary", use_container_width=True)

with right:
    st.header("4. 결과")

    if not analyze_clicked:
        st.info("시도, 물건 종류, 조회 연도를 선택한 뒤 '국토부에서 가져와 분석하기'를 누르세요.")
        st.stop()

    try:
        with st.spinner("국토교통부 실거래가 사이트에서 데이터를 가져오는 중입니다..."):
            raw, meta = fetch_from_molit_cached(
                selected_sido,
                section_key,
                from_date.isoformat(),
                to_date.isoformat(),
            )

            if raw.empty:
                st.warning("국토부 사이트에서 해당 조건의 거래 데이터를 찾지 못했습니다.")
                st.stop()

            cleaned = clean_transactions(
                raw,
                include_keywords=section_config.include_keywords,
                sido=None,
                sigungu=None,
                dong=None,
            )

            if cleaned.empty:
                st.warning("가져온 데이터는 있으나 분석 대상 물건 종류로 정리된 거래가 없습니다.")
                st.stop()

            analysis = analyze_transactions(cleaned)
            top_dong_area = analysis["top_dong_area"]

            region = meta.get("region")
            if region:
                st.caption(
                    f"가져온 조건: {region.sido_name} {region.sgg_name} · "
                    f"{section_config.title} · {from_date} ~ {to_date} · 원자료 {meta.get('count', 0):,}건"
                )

            show_main_answer(top_dong_area, selected_sido)

            st.divider()
            render_dataframe_section("거래량 많은 동네 + 평수대 TOP 20", top_dong_area, 20)

            with tempfile.TemporaryDirectory(prefix="realestate-output-") as tmpdir:
                outputs = save_outputs(
                    cleaned,
                    analysis,
                    tmpdir,
                    title=f"{selected_sido} {selected_year}년 {section_config.title} 인기 평수 분석 리포트",
                )

                st.subheader("다운로드")
                d1, d2 = st.columns(2)
                with d1:
                    make_download_button("HTML 리포트 다운로드", outputs["html"], "text/html")
                with d2:
                    make_download_button(
                        "엑셀 결과 다운로드",
                        outputs["excel"],
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                with st.expander("고급 다운로드", expanded=False):
                    d3, d4 = st.columns(2)
                    with d3:
                        make_download_button("CSV 다운로드", outputs["csv"], "text/csv")
                    with d4:
                        make_download_button("JSON 다운로드", outputs["json"], "application/json")

            st.divider()
            tab1, tab2, tab3 = st.tabs(["동네별 거래량", "면적대별 거래량", "전체 정리 데이터"])
            with tab1:
                render_dataframe_section("동네별 거래량", analysis["top_dong_volume"], 20)
            with tab2:
                render_dataframe_section("면적대별 거래량", analysis["by_area"], 20)
            with tab3:
                render_dataframe_section("분석에 사용된 정리 데이터", cleaned, 200)

    except MolitSiteDownloadError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error("분석 중 오류가 발생했습니다. 시도, 연도, 물건 종류를 확인하세요.")
        st.exception(exc)
