from __future__ import annotations

import pandas as pd

AREA_ORDER = [
    "10평 이하",
    "10~12평",
    "12~14평",
    "14~16평",
    "16~18평",
    "18~20평",
    "20~24평",
    "24~30평",
    "30평 이상",
    "미상",
]


def count_by(df: pd.DataFrame, columns: list[str], count_name: str = "거래건수") -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns + [count_name])
    return (
        df.groupby(columns, dropna=False)
        .size()
        .reset_index(name=count_name)
        .sort_values(count_name, ascending=False)
        .reset_index(drop=True)
    )


def average_by(df: pd.DataFrame, columns: list[str], value: str, name: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=columns + [name, "거래건수"])
    return (
        df.groupby(columns, dropna=False)
        .agg(**{name: (value, "mean"), "거래건수": (value, "size")})
        .reset_index()
        .assign(**{name: lambda x: x[name].round(0).astype("Int64")})
        .sort_values(name, ascending=False)
        .reset_index(drop=True)
    )


def popular_area_by_dong(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["법정동", "인기면적대", "거래건수"])
    counts = count_by(df, ["법정동", "면적구간"])
    counts["면적구간"] = pd.Categorical(counts["면적구간"], categories=AREA_ORDER, ordered=True)
    counts = counts.sort_values(["법정동", "거래건수", "면적구간"], ascending=[True, False, True])
    result = counts.drop_duplicates("법정동", keep="first").copy()
    result = result.rename(columns={"면적구간": "인기면적대"})
    return result[["법정동", "인기면적대", "거래건수"]].sort_values("거래건수", ascending=False).reset_index(drop=True)


def top_dong_area_combinations(df: pd.DataFrame) -> pd.DataFrame:
    """Find the neighborhood + size band combinations with the highest transaction volume."""
    columns = [
        "시군구",
        "법정동",
        "면적구간",
        "거래건수",
        "평균거래금액_만원",
        "평균평당가_만원",
        "최근거래일",
    ]
    if df.empty:
        return pd.DataFrame(columns=columns)

    grouped = (
        df.groupby(["시군구", "법정동", "면적구간"], dropna=False)
        .agg(
            거래건수=("거래금액_만원", "size"),
            평균거래금액_만원=("거래금액_만원", "mean"),
            평균평당가_만원=("평당가_만원", "mean"),
            최근거래일=("거래일", "max"),
        )
        .reset_index()
    )
    grouped["평균거래금액_만원"] = grouped["평균거래금액_만원"].round(0).astype("Int64")
    grouped["평균평당가_만원"] = grouped["평균평당가_만원"].round(0).astype("Int64")
    grouped["최근거래일"] = pd.to_datetime(grouped["최근거래일"], errors="coerce").dt.strftime("%Y-%m-%d")
    grouped["면적구간"] = pd.Categorical(grouped["면적구간"], categories=AREA_ORDER, ordered=True)
    return (
        grouped.sort_values(["거래건수", "평균거래금액_만원", "면적구간"], ascending=[False, False, True])
        .reset_index(drop=True)
        [columns]
    )


def latest_trade_date(df: pd.DataFrame) -> str | None:
    if df.empty or "거래일" not in df.columns:
        return None
    value = df["거래일"].max()
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def analyze_transactions(df: pd.DataFrame) -> dict:
    by_sigungu = count_by(df, ["시군구"])
    by_dong = count_by(df, ["법정동"])
    by_area = count_by(df, ["면적구간"])
    by_build_year = count_by(df, ["건축년도"])
    by_floor = count_by(df, ["층"])
    avg_price_by_dong = average_by(df, ["법정동"], "거래금액_만원", "평균거래금액_만원")
    avg_unit_price_by_dong = average_by(df, ["법정동"], "평당가_만원", "평균평당가_만원")
    popular_area = popular_area_by_dong(df)
    top_dong_area = top_dong_area_combinations(df)
    latest = latest_trade_date(df)

    summary = {
        "total_transactions": int(len(df)),
        "sigungu_count": int(df["시군구"].nunique()) if "시군구" in df.columns else 0,
        "dong_count": int(df["법정동"].nunique()) if "법정동" in df.columns else 0,
        "avg_trade_price_manwon": int(round(df["거래금액_만원"].mean())) if not df.empty else None,
        "avg_unit_price_manwon": int(round(df["평당가_만원"].mean())) if not df.empty else None,
        "latest_trade_date": latest,
    }

    return {
        "summary": summary,
        "latest_trade_date": latest,
        "by_sigungu": by_sigungu,
        "by_dong": by_dong,
        "by_area": by_area,
        "popular_area_by_dong": popular_area,
        "top_dong_area": top_dong_area,
        "avg_price_by_dong": avg_price_by_dong,
        "avg_unit_price_by_dong": avg_unit_price_by_dong,
        "by_build_year": by_build_year,
        "by_floor": by_floor,
        "top_dong_volume": by_dong.head(20),
        "top_avg_price": avg_price_by_dong.head(20),
        "top_unit_price": avg_unit_price_by_dong.head(20),
    }
