"""Run a synthetic copper demonstration or analyse a validated metal CSV."""

import argparse
from pathlib import Path

from .config import MARKETS, ModelConfig
from .data import load_csv
from .model import compute_positions, make_snapshot
from .report import write_report
from .synthetic import copper_pair


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="CTA-style metal model exposure, not observed holdings")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="Reproducible synthetic copper demonstration")
    demo.add_argument("--out-dir", default="output/demo")
    demo.add_argument("--seed", type=int, default=42)
    analyze = sub.add_parser("analyze", help="Analyse one market from a local CSV")
    analyze.add_argument("--input", required=True)
    analyze.add_argument("--market", choices=tuple(MARKETS), required=True)
    analyze.add_argument("--out-dir", default="output/analysis")
    args = parser.parse_args(argv)
    config = ModelConfig()
    if args.command == "demo":
        inputs = copper_pair(seed=args.seed)
        Path(args.out_dir).mkdir(parents=True, exist_ok=True)
        for market, prices in inputs.items():
            prices.to_csv(Path(args.out_dir) / f"{market.lower()}_synthetic_prices.csv", index=False)
    else:
        inputs = {args.market: load_csv(args.input, args.market)}
    results = {}
    for market, prices in inputs.items():
        positions = compute_positions(prices, config)
        results[market] = (positions, make_snapshot(prices, positions, config))
    print(f"Wrote {write_report(results, args.out_dir)}")


if __name__ == "__main__":
    main()

