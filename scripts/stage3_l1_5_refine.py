"""Legacy Stage3 CLI forwarding to the package compatibility refiner."""

from src.pipelines.stage3_l1_5_refiner import main


if __name__ == "__main__":
    raise SystemExit(main())
