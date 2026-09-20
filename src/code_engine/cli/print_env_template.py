from __future__ import annotations
import argparse
def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument("--provider",choices=("deepseek",),required=True); p.add_argument("--model")
    a=p.parse_args(argv)
    model=a.model or "deepseek-v4-pro"
    print(f"export L1_PROVIDER={a.provider}\nexport MODEL_NAME={model}\nexport DEEPSEEK_API_KEY=...")
    return 0
if __name__ == "__main__": raise SystemExit(main())
