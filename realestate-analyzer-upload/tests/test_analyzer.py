import pandas as pd

from src.cleaner import clean_transactions
from src.analyzer import analyze_transactions


def test_clean_transactions_filters_target_housing_and_calculates_area_bucket():
    raw = pd.DataFrame([
        {
            "주택유형": "다세대",
            "시군구": "서울특별시 양천구",
            "법정동": "신정동",
            "전용면적(㎡)": 39.66,
            "거래금액(만원)": "30,000",
            "계약년월": 202406,
            "계약일": 15,
            "건축년도": 1998,
            "층": 3,
        },
        {
            "주택유형": "아파트",
            "시군구": "서울특별시 양천구",
            "법정동": "목동",
            "전용면적(㎡)": 84.9,
            "거래금액(만원)": "120,000",
            "계약년월": 202406,
            "계약일": 20,
            "건축년도": 2005,
            "층": 10,
        },
    ])

    cleaned = clean_transactions(raw, include_keywords=("다세대", "연립", "다가구"))

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["주택유형"] == "다세대"
    assert round(cleaned.iloc[0]["전용면적_평"], 2) == 12.0
    assert cleaned.iloc[0]["면적구간"] == "12~14평"
    assert cleaned.iloc[0]["거래금액_만원"] == 30000
    assert cleaned.iloc[0]["평당가_만원"] == 2500


def test_analyze_transactions_returns_required_tables():
    raw = pd.DataFrame([
        {"주택유형": "다세대", "시군구": "서울특별시 양천구", "법정동": "신정동", "전용면적(㎡)": 39.66, "거래금액(만원)": "30,000", "계약년월": 202406, "계약일": 15, "건축년도": 1998, "층": 3},
        {"주택유형": "연립", "시군구": "서울특별시 양천구", "법정동": "신정동", "전용면적(㎡)": 52.89, "거래금액(만원)": "42,000", "계약년월": 202406, "계약일": 16, "건축년도": 2001, "층": 2},
        {"주택유형": "다가구", "시군구": "서울특별시 강서구", "법정동": "화곡동", "전용면적(㎡)": 66.12, "거래금액(만원)": "55,000", "계약년월": 202405, "계약일": 11, "건축년도": 1995, "층": 1},
    ])
    cleaned = clean_transactions(raw, include_keywords=("다세대", "연립", "다가구"))

    result = analyze_transactions(cleaned)

    assert result["summary"]["total_transactions"] == 3
    assert set(result["by_sigungu"]["시군구"]) == {"서울특별시 양천구", "서울특별시 강서구"}
    popular = result["popular_area_by_dong"]
    assert "법정동" in popular.columns
    assert "인기면적대" in popular.columns
    top_combo = result["top_dong_area"]
    assert list(top_combo.columns) == ["시군구", "법정동", "면적구간", "거래건수", "평균거래금액_만원", "평균평당가_만원", "최근거래일"]
    assert not top_combo.empty
    assert top_combo.iloc[0]["거래건수"] >= 1
    assert result["latest_trade_date"] == "2024-06-16"
