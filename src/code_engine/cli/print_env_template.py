from __future__ import annotations
import argparse
def main(argv=None)->int:
    p=argparse.ArgumentParser(); p.add_argument("--provider",choices=("deepseek","openai"),required=True); p.add_argument("--model")
    a=p.parse_args(argv)
    model=a.model or ("deepseek-v4-pro" if a.provider=="deepseek" else "YOUR_OPENAI_MODEL")
    print(f"export L1_PROVIDER={a.provider}\nexport MODEL_NAME={model}\nexport {'DEEPSEEK_API_KEY' if a.provider=='deepseek' else 'OPENAI_API_KEY'}=...")
    return 0
if __name__ == "__main__": raise SystemExit(main())
