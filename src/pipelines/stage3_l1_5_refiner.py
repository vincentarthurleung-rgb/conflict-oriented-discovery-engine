"""Legacy Stage3 path for deterministic legacy/L1-v2 refinement."""

import argparse

from code_engine.extraction.l1_refiner import refine_l1_file


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    refine_l1_file(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
