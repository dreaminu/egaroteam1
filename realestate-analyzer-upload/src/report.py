from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .utils import ensure_dir


def df_to_html_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df is None or df.empty:
        return "<p class='empty'>데이터 없음</p>"
    return df.head(max_rows).to_html(index=False, classes="data-table", border=0)


def make_investment_notes(analysis: dict[str, Any]) -> list[str]:
    summary = analysis["summary"]
    notes = []
    notes.append("이 리포트는 국토교통부 실거래가 엑셀에 포함된 거래 데이터만 집계합니다.")
    notes.append("거래량이 많은 지역은 시장 참여가 상대적으로 활발했다는 의미이며, 투자 가치가 높다는 뜻은 아닙니다.")
    notes.append("재개발·재건축 가능성, 전세가율, 임대수익률은 이 매매 데이터만으로 판단하지 않았습니다.")
    if summary.get("avg_trade_price_manwon") is not None:
        notes.append(f"전체 평균 거래금액은 약 {summary['avg_trade_price_manwon']:,}만원입니다.")
    if summary.get("avg_unit_price_manwon") is not None:
        notes.append(f"전체 평균 평당가는 약 {summary['avg_unit_price_manwon']:,}만원입니다.")
    return notes


def make_follow_up_areas(analysis: dict[str, Any]) -> pd.DataFrame:
    by_dong = analysis["by_dong"].copy()
    unit = analysis["avg_unit_price_by_dong"].copy()
    if by_dong.empty or unit.empty:
        return pd.DataFrame(columns=["법정동", "거래건수", "평균평당가_만원", "확인메모"])
    merged = by_dong.merge(unit[["법정동", "평균평당가_만원"]], on="법정동", how="left")
    merged["확인메모"] = "거래량과 평당가가 함께 관찰되는 지역입니다. 개별 매물, 건물상태, 권리관계, 임대수요는 별도 확인 필요."
    return merged.sort_values(["거래건수", "평균평당가_만원"], ascending=[False, False]).head(20)


def render_html(cleaned: pd.DataFrame, analysis: dict[str, Any], title: str = "실거래가 거래량 분석 리포트") -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = analysis["summary"]
    notes = make_investment_notes(analysis)
    follow_up = make_follow_up_areas(analysis)

    note_html = "".join(f"<li>{note}</li>" for note in notes)

    return f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 32px; color: #222; background: #f7f8fa; }}
    h1, h2 {{ color: #123; }}
    .card {{ background: white; border-radius: 14px; padding: 22px; margin: 18px 0; box-shadow: 0 2px 12px rgba(0,0,0,.06); }}
    .summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .metric {{ background: #eef4ff; border-radius: 12px; padding: 16px; }}
    .metric .label {{ color: #667; font-size: 13px; }}
    .metric .value {{ font-size: 24px; font-weight: 700; margin-top: 6px; }}
    table.data-table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    table.data-table th {{ background: #1f3b57; color: white; text-align: left; padding: 9px; }}
    table.data-table td {{ border-bottom: 1px solid #e5e7eb; padding: 8px; }}
    .warning {{ background: #fff7e6; border-left: 5px solid #f0a500; padding: 14px; }}
    .empty {{ color: #777; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p>생성일시: {generated_at}</p>

  <div class="card">
    <h2>전체 요약</h2>
    <div class="summary-grid">
      <div class="metric"><div class="label">총 거래건수</div><div class="value">{summary.get('total_transactions', 0):,}</div></div>
      <div class="metric"><div class="label">시군구 수</div><div class="value">{summary.get('sigungu_count', 0):,}</div></div>
      <div class="metric"><div class="label">법정동 수</div><div class="value">{summary.get('dong_count', 0):,}</div></div>
      <div class="metric"><div class="label">평균 거래금액</div><div class="value">{summary.get('avg_trade_price_manwon') or 0:,}만원</div></div>
      <div class="metric"><div class="label">평균 평당가</div><div class="value">{summary.get('avg_unit_price_manwon') or 0:,}만원</div></div>
      <div class="metric"><div class="label">최근 거래일</div><div class="value">{summary.get('latest_trade_date') or '미상'}</div></div>
    </div>
  </div>

  <div class="card warning">
    <h2>해석 주의사항</h2>
    <ul>{note_html}</ul>
  </div>

  <div class="card"><h2>거래량 많은 동네 + 평수대 TOP 20</h2>{df_to_html_table(analysis.get('top_dong_area'), 20)}</div>
  <div class="card"><h2>시군구별 거래건수</h2>{df_to_html_table(analysis['by_sigungu'], 50)}</div>
  <div class="card"><h2>거래량 TOP 20 법정동</h2>{df_to_html_table(analysis['top_dong_volume'])}</div>
  <div class="card"><h2>면적 구간별 거래건수</h2>{df_to_html_table(analysis['by_area'], 50)}</div>
  <div class="card"><h2>법정동별 인기 면적대</h2>{df_to_html_table(analysis['popular_area_by_dong'])}</div>
  <div class="card"><h2>평균 거래가 TOP 20</h2>{df_to_html_table(analysis['top_avg_price'])}</div>
  <div class="card"><h2>평당가 TOP 20</h2>{df_to_html_table(analysis['top_unit_price'])}</div>
  <div class="card"><h2>건축년도별 거래 분포</h2>{df_to_html_table(analysis['by_build_year'], 100)}</div>
  <div class="card"><h2>층별 거래 분포</h2>{df_to_html_table(analysis['by_floor'], 100)}</div>
  <div class="card"><h2>추가 조사 필요 지역</h2>{df_to_html_table(follow_up)}</div>
</body>
</html>"""


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []
    safe = df.copy()
    for col in safe.columns:
        if pd.api.types.is_datetime64_any_dtype(safe[col]):
            safe[col] = safe[col].dt.strftime("%Y-%m-%d")
    safe = safe.where(pd.notnull(safe), None)
    return safe.to_dict(orient="records")


def save_outputs(
    cleaned: pd.DataFrame,
    analysis: dict[str, Any],
    output_dir: str | Path = "output",
    title: str = "실거래가 거래량 분석 리포트",
) -> dict[str, Path]:
    out = ensure_dir(output_dir)
    html_path = out / "realestate_report.html"
    excel_path = out / "realestate_analysis.xlsx"
    csv_path = out / "cleaned_transactions.csv"
    json_path = out / "analysis_result.json"

    html_path.write_text(render_html(cleaned, analysis, title=title), encoding="utf-8")
    cleaned.to_csv(csv_path, index=False, encoding="utf-8-sig")

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        cleaned.to_excel(writer, sheet_name="정리데이터", index=False)
        for key, value in analysis.items():
            if isinstance(value, pd.DataFrame):
                sheet = key[:31]
                value.to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame([analysis["summary"]]).to_excel(writer, sheet_name="summary", index=False)

    json_ready = {
        "summary": analysis["summary"],
        "tables": {
            key: dataframe_to_records(value)
            for key, value in analysis.items()
            if isinstance(value, pd.DataFrame)
        },
    }
    json_path.write_text(json.dumps(json_ready, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    return {
        "html": html_path,
        "excel": excel_path,
        "csv": csv_path,
        "json": json_path,
    }
