from __future__ import annotations

import argparse
from pathlib import Path

from src.analyzer import analyze_transactions
from src.cleaner import clean_transactions
from src.loader import load_input_folder
from src.report import save_outputs
from src.sections import get_section_config, section_help_text
from src.utils import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="국토교통부 실거래가 엑셀 섹션별 거래량 분석기"
    )
    parser.add_argument(
        "--section",
        default="villa",
        help=f"분석 섹션 선택. 기본값 villa. 사용 가능: {section_help_text()}",
    )
    parser.add_argument("--sido", help="시도 필터. 예: 서울특별시, 경기도, 부산광역시")
    parser.add_argument("--sigungu", help="시군구 필터. 예: 양천구, 부천시, 수원시 영통구")
    parser.add_argument("--dong", help="법정동 필터. 예: 신정동, 화곡동")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    section_config = get_section_config(args.section)

    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / "input"
    output_dir = base_dir / "output"
    ensure_dir(input_dir)
    ensure_dir(output_dir)

    print(f"국토교통부 {section_config.title} 실거래가 분석을 시작합니다.")
    print(f"입력 폴더: {input_dir}")
    print(f"출력 폴더: {output_dir}")
    if args.sido:
        print(f"시도 필터: {args.sido}")
    if args.sigungu:
        print(f"시군구 필터: {args.sigungu}")
    if args.dong:
        print(f"법정동 필터: {args.dong}")

    raw = load_input_folder(input_dir)
    cleaned = clean_transactions(
        raw,
        include_keywords=section_config.include_keywords,
        sido=args.sido,
        sigungu=args.sigungu,
        dong=args.dong,
    )

    if cleaned.empty:
        raise SystemExit(
            f"분석 대상 거래가 없습니다. section={args.section}, "
            "시도/시군구/법정동 필터, 엑셀 파일의 섹션을 확인하세요."
        )

    analysis = analyze_transactions(cleaned)
    outputs = save_outputs(cleaned, analysis, output_dir, title=f"{section_config.title} 실거래가 거래량 분석 리포트")

    print("분석 완료")
    for label, path in outputs.items():
        print(f"- {label}: {path}")


if __name__ == "__main__":
    main()
