from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analyzer import analyze_transactions
from src.cleaner import clean_transactions
from src.loader import read_excel_file
from src.report import save_outputs


TARGET_OPTIONS = {
    "연립/다세대/다가구만 분석": ("연립", "다세대", "다가구"),
    "엑셀 전체 분석": (),
    "연립/다세대만 분석": ("연립", "다세대"),
    "다가구만 분석": ("다가구",),
}

st.set_page_config(
    page_title="빌라 실거래 엑셀 분석기",
    page_icon="🏘️",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 1.2rem; max-width: 1220px; }
    .hero-card {
        background: linear-gradient(135deg, #123c69 0%, #2563eb 62%, #14b8a6 100%);
        color: white;
        border-radius: 28px;
        padding: 34px 36px;
        margin-bottom: 18px;
        box-shadow: 0 18px 52px rgba(37, 99, 235, .24);
    }
    .hero-card h1 { margin: 0 0 10px 0; font-size: 36px; letter-spacing: -1.2px; }
    .hero-card p { margin: 0; font-size: 17px; line-height: 1.6; opacity: .96; }
    .notice-card {
        background: #fff7ed;
        border-left: 7px solid #f97316;
        border-radius: 16px;
        padding: 16px 18px;
        margin-bottom: 18px;
        line-height: 1.6;
    }
    .result-card {
        border: 2px solid #bbf7d0;
        background: linear-gradient(180deg, #f0fdf4, #ecfeff);
        border-radius: 22px;
        padding: 22px;
        margin: 12px 0 18px 0;
    }
    .result-card h3 { margin: 0 0 8px 0; color: #0b6b3a; font-size: 23px; }
    .result-card .big { font-size: 26px; font-weight: 900; letter-spacing: -1px; margin: 8px 0; line-height: 1.45; }
    div[data-testid="stMetric"] {
        background: #f8fbff;
        border: 1px solid #dbeafe;
        border-radius: 17px;
        padding: 14px;
        box-shadow: 0 5px 16px rgba(15, 23, 42, .05);
    }
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button {
        border-radius: 14px;
        padding: 0.75rem 1rem;
        font-weight: 800;
    }
    h2, h3 { letter-spacing: -0.4px; }
    </style>
    """,
    unsafe_allow_html=True,
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


def load_uploaded_excels(uploaded_files) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = Path(tmp.name)
        try:
            df = read_excel_file(tmp_path)
            df["업로드파일명"] = uploaded.name
            frames.append(df)
        finally:
            tmp_path.unlink(missing_ok=True)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def make_sample_transactions() -> pd.DataFrame:
    """Streamlit 배포 화면과 미리보기가 다르게 보이지 않도록 앱 안에서 쓰는 샘플 데이터."""
    return pd.DataFrame(
        [
            {"주택유형": "다세대", "시군구": "인천광역시 미추홀구", "법정동": "주안동", "도로명": "석바위로", "전용면적(㎡)": 39.66, "거래금액(만원)": "18,000", "계약년월": 202501, "계약일": 15, "건축년도": 2003, "층": 3},
            {"주택유형": "다세대", "시군구": "인천광역시 미추홀구", "법정동": "주안동", "도로명": "석바위로", "전용면적(㎡)": 40.00, "거래금액(만원)": "17,500", "계약년월": 202502, "계약일": 10, "건축년도": 2004, "층": 2},
            {"주택유형": "다세대", "시군구": "인천광역시 미추홀구", "법정동": "주안동", "도로명": "석바위로", "전용면적(㎡)": 38.20, "거래금액(만원)": "18,300", "계약년월": 202503, "계약일": 8, "건축년도": 2006, "층": 4},
            {"주택유형": "연립", "시군구": "인천광역시 미추홀구", "법정동": "주안동", "도로명": "경인로", "전용면적(㎡)": 52.89, "거래금액(만원)": "23,000", "계약년월": 202503, "계약일": 5, "건축년도": 2012, "층": 4},
            {"주택유형": "연립", "시군구": "인천광역시 미추홀구", "법정동": "용현동", "도로명": "인주대로", "전용면적(㎡)": 49.50, "거래금액(만원)": "19,800", "계약년월": 202504, "계약일": 12, "건축년도": 1998, "층": 2},
            {"주택유형": "다가구", "시군구": "인천광역시 미추홀구", "법정동": "도화동", "도로명": "숙골로", "전용면적(㎡)": 63.40, "거래금액(만원)": "25,500", "계약년월": 202505, "계약일": 20, "건축년도": 2016, "층": 1},
        ]
    )


def show_main_answer(analysis: dict, title_hint: str) -> None:
    combo = analysis.get("road_year_area_combo")
    if combo is not None and not combo.empty:
        top = combo.iloc[0]
        st.markdown(
            f"""
            <div class="result-card">
              <h3>핵심 발견</h3>
              <div class="big">{title_hint}에서 가장 반복적으로 거래된 유형은<br>
              “{top['법정동']} · {top['도로명']} · {top['건축년도구간']} · {top['면적구간']}” 입니다.</div>
              <div style="color:#64748b;font-size:14px;">거래량 기준 관찰 결과이며, 투자 추천을 의미하지 않습니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("법정동", str(top["법정동"]))
        c2.metric("도로명", str(top["도로명"]))
        c3.metric("연식", str(top["건축년도구간"]))
        c4.metric("면적대", str(top["면적구간"]))
        c5.metric("거래건수", f"{int(top['거래건수']):,}건")
        return

    top_dong_area = analysis.get("top_dong_area")
    if top_dong_area is not None and not top_dong_area.empty:
        top = top_dong_area.iloc[0]
        st.markdown(
            f"""
            <div class="result-card">
              <h3>핵심 발견</h3>
              <div class="big">가장 거래량이 많은 조합은 “{top['법정동']} · {top['면적구간']}” 입니다.</div>
              <div style="color:#64748b;font-size:14px;">거래량 기준 관찰 결과이며, 투자 추천을 의미하지 않습니다.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.warning("조건에 맞는 결과가 없습니다.")


st.markdown(
    """
    <div class="hero-card">
      <h1>빌라 실거래 엑셀 분석기</h1>
      <p>국토부에서 내려받은 엑셀을 업로드하면 <b>동네 → 도로명 → 연식 → 면적대</b> 순서로<br>
      실제 거래가 반복된 빌라 유형을 찾아 HTML 리포트와 엑셀 파일로 정리합니다.</p>
    </div>
    <div class="notice-card">
      <b>이번 버전 범위:</b> ① 엑셀 업로드 분석 ② 도로명·연식·면적대 조합 분석 ③ 분석 리포트/엑셀 다운로드까지 구현합니다.
      지도 연동은 다음 단계에서 추가할 수 있습니다.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.expander("UI 디자인 방향", expanded=False):
    st.markdown(
        """
        - 첫 화면은 큰 파란색 히어로 카드로 “무엇을 찾는 도구인지” 바로 보이게 합니다.
        - 왼쪽에는 업로드와 분석 옵션만 배치해서 수강생이 헷갈리지 않게 합니다.
        - 오른쪽 상단에는 한 줄 결론과 핵심 지표 카드를 먼저 보여줍니다.
        - 아래에는 도로명 TOP, 연식+면적대 조합, 추가조사 후보를 탭으로 정리합니다.
        - 결과는 HTML 리포트와 엑셀로 바로 다운로드하게 합니다.
        """
    )

left, right = st.columns([1, 2])

with left:
    st.header("1. 엑셀 업로드")
    uploaded_files = st.file_uploader(
        "국토부 실거래가 엑셀 파일",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        help="원하는 지역·년도·물건 종류는 국토부에서 직접 선택해 내려받은 뒤 여기에 올리면 됩니다.",
    )

    st.header("2. 분석 대상")
    target_label = st.selectbox("물건 종류 필터", options=list(TARGET_OPTIONS.keys()), index=0)
    target_keywords = TARGET_OPTIONS[target_label]

    st.header("3. 선택 필터")
    dong_keyword = st.text_input("특정 법정동만 보기", placeholder="예: 주안동")
    title_hint = st.text_input("리포트 제목에 넣을 지역명", placeholder="예: 인천 미추홀구 2025년 연립/다세대")

    analyze_clicked = st.button("업로드한 엑셀 분석하기", type="primary", use_container_width=True)
    sample_clicked = st.button("화면 예시 보기", use_container_width=True)

with right:
    st.header("4. 분석 결과")
    if not analyze_clicked and not sample_clicked:
        st.info("엑셀 파일을 업로드해 분석하거나, '화면 예시 보기'를 눌러 실제 Streamlit 배포 화면을 미리 확인하세요.")
        st.stop()

    if analyze_clicked and not uploaded_files:
        st.warning("먼저 엑셀 파일을 1개 이상 업로드해 주세요. 화면만 확인하려면 '화면 예시 보기'를 누르세요.")
        st.stop()

    try:
        with st.spinner("엑셀을 읽고 거래 데이터를 정리하는 중입니다..."):
            if sample_clicked and not analyze_clicked:
                raw = make_sample_transactions()
                selected_title_hint = title_hint.strip() or "인천 미추홀구 2025년 빌라 샘플"
                st.caption("샘플 데이터로 화면을 미리 보여주는 모드입니다. 실제 분석은 엑셀 업로드 후 실행하세요.")
            else:
                raw = load_uploaded_excels(uploaded_files)
                selected_title_hint = title_hint.strip() or "빌라 실거래 엑셀 분석 리포트"
            if raw.empty:
                st.warning("엑셀에서 데이터를 읽지 못했습니다.")
                st.stop()

            cleaned = clean_transactions(
                raw,
                include_keywords=target_keywords,
                dong=dong_keyword.strip() or None,
            )
            if cleaned.empty:
                st.warning("조건에 맞는 거래 데이터가 없습니다. 물건 종류 필터를 '엑셀 전체 분석'으로 바꿔 다시 시도해 보세요.")
                st.stop()

            analysis = analyze_transactions(cleaned)
            report_title = selected_title_hint

        show_main_answer(analysis, report_title)

        summary = analysis["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 거래건수", f"{summary['total_transactions']:,}건")
        m2.metric("법정동 수", f"{summary['dong_count']:,}개")
        m3.metric("도로명 수", f"{summary.get('road_count', 0):,}개")
        m4.metric("최근 거래일", summary.get("latest_trade_date") or "미상")

        st.divider()
        tab1, tab2, tab3, tab4 = st.tabs(["핵심 조합", "도로명 TOP", "추가조사 후보", "정리 데이터"])
        with tab1:
            render_dataframe_section("도로명 + 연식 + 면적대 조합 TOP 50", analysis["road_year_area_combo"], 50)
        with tab2:
            render_dataframe_section("도로명별 거래량 TOP 50", analysis["road_volume"], 50)
            render_dataframe_section("도로명 + 연식별 분석", analysis["road_build_year"], 50)
        with tab3:
            render_dataframe_section("추가조사 후보", analysis["follow_up_candidates"], 20)
            st.caption("추가조사 후보는 거래량과 평당가가 함께 관찰되는 구간입니다. 권리관계·건물상태·전세가율·임대수요 확인은 별도입니다.")
        with tab4:
            render_dataframe_section("분석에 사용된 정리 데이터", cleaned, 300)

        with tempfile.TemporaryDirectory(prefix="realestate-output-") as tmpdir:
            outputs = save_outputs(cleaned, analysis, tmpdir, title=report_title)
            st.subheader("다운로드")
            d1, d2 = st.columns(2)
            with d1:
                make_download_button("분석 리포트 다운로드", outputs["html"], "text/html")
            with d2:
                make_download_button(
                    "상세 엑셀 다운로드",
                    outputs["excel"],
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            with st.expander("고급 다운로드", expanded=False):
                d3, d4 = st.columns(2)
                with d3:
                    make_download_button("CSV 다운로드", outputs["csv"], "text/csv")
                with d4:
                    make_download_button("JSON 다운로드", outputs["json"], "application/json")

    except Exception as exc:
        st.error("분석 중 문제가 생겼습니다. 엑셀 컬럼에 시군구, 법정동, 전용면적, 거래금액이 있는지 확인해 주세요.")
        with st.expander("오류 자세히 보기", expanded=False):
            st.exception(exc)
