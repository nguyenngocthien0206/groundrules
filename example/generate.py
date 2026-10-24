"""Generate the synthetic Northwind Pharmacy source extracts.

Usage: python example/generate.py --out example/data [--seed 20260915]

The output looks like what a real chain's ERP, POS vendors and returns system
drop into a landing folder: raw, inconsistent and a little late. Every name,
number and rule is invented. The same seed always gives byte-identical files.
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from synth import config, extracts  # noqa: E402
from synth.master import build_skus, build_stores  # noqa: E402
from synth.simulate import World, simulate  # noqa: E402


def generate(out: Path, seed: str = config.SEED) -> World:
    stores = build_stores(seed)
    skus = build_skus(seed)
    world = simulate(seed, stores, skus)

    extracts.write_erp_stores(out, stores)
    extracts.write_erp_skus(out, skus)
    extracts.write_erp_sku_uom(out, skus)
    extracts.write_erp_batches(out, world)
    extracts.write_erp_transfers(out, world)
    extracts.write_pos_a(out, world, seed)
    extracts.write_pos_b(out, world)
    extracts.write_pos_sync_log(out, world, seed)
    extracts.write_returns(out, world, seed)
    return world


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("example/data"))
    parser.add_argument("--seed", default=config.SEED)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    generate(args.out, args.seed)
    print(f"Wrote extracts to {args.out} in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
