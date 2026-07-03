"""Shared I/O and injectable HTTP transport for production-v1 validators."""
from __future__ import annotations
import hashlib, json, urllib.request
from pathlib import Path
from typing import Any, Callable

Transport = Callable[[str, str, bytes | None, dict[str, str]], Any]

def http_json(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None) -> Any:
    cache_root=Path("data/cache/production_v1_validators"); key=hashlib.sha256(method.encode()+b"\0"+url.encode()+b"\0"+(data or b"")).hexdigest(); cache=cache_root/f"{key}.json"
    if cache.is_file(): return json.loads(cache.read_text(encoding="utf-8"))
    request = urllib.request.Request(url, data=data, headers=headers or {"Accept":"application/json"}, method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        value=json.loads(response.read().decode("utf-8"))
    cache_root.mkdir(parents=True,exist_ok=True); cache.write_text(json.dumps(value,ensure_ascii=False),encoding="utf-8"); return value

def call(transport: Transport | None, method: str, url: str, data: bytes | None = None, headers: dict[str,str] | None = None) -> Any:
    value = (transport or http_json)(method, url, data, headers or {})
    if isinstance(value, tuple): value = value[-1]
    if isinstance(value, bytes): value = value.decode("utf-8")
    return json.loads(value) if isinstance(value, str) else value

def write_artifacts(root: str | Path, stem: str, summary: dict, rows: list[dict]) -> dict:
    root=Path(root); root.mkdir(parents=True,exist_ok=True)
    (root/f"l7_{stem}_summary.json").write_text(json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (root/f"l7_{stem}_results.jsonl").write_text("".join(json.dumps(row,ensure_ascii=False)+"\n" for row in rows),encoding="utf-8")
    return summary
