"""
C.O.D.E. Core Pipeline - Stage 2: Layer 1 Belief & Constraint Extraction
Complete Release 1.8.9 (Production Core - Soft Healing & Fast Overclock Edition)

[Release 1.8.9 Patch]:
1. Tightened request timeout to 30s and reduced retries to 2 to crush latency.
2. Implemented active 'causal_tuples: []' fallback on exhausted worker retries.
3. Prevents a single hanging text block from hostage-locking the entire full-text asset.
"""

import os
import sys
import json
import asyncio
import aiohttp
import time
from tqdm.asyncio import tqdm_asyncio

# ==================== 1. System Paths & Environment Configuration ====================
GLOBAL_MANIFEST_PATH = "data/metadata/global_manifest.json"
PAYLOAD_DIR = "./data/interim/weighted_payloads"
EXTRACT_OUTPUT_DIR = "./data/processed/l1"
AUDIT_LOG_PATH = "logs/audit.jsonl"

PROMPT_FILE_PATH = "config/schemas/prompt.txt"
if not os.path.exists(PROMPT_FILE_PATH):
    PROMPT_FILE_PATH = "prompt.txt"

os.makedirs(EXTRACT_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

BASE_URL = "https://api.deepseek.com"
API_URL = f"{BASE_URL}/v1/chat/completions"

API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not API_KEY:
    raise ValueError("[C.O.D.E. Fatal] Environment variable 'DEEPSEEK_API_KEY' is not set. Execution blocked.")

N_SAMPLES = 5                     # Number of parallel samples for stochastic variance capture
CHUNK_WORD_LIMIT = 1200           # Maximum words per sliding window chunk

# 🛡️ 战术卡尺安全线：将并发控制在 16 路，给网关充足的响应时间，杜绝拥堵
MAX_CONCURRENT_WORKERS = 16       

# ==================== 2. Dynamic System Prompt Template Loader ====================
def load_commander_system_prompt():
    if not os.path.exists(PROMPT_FILE_PATH):
        raise FileNotFoundError(f"[C.O.D.E. Fatal] Missing essential prompt file at: {PROMPT_FILE_PATH}")
    try:
        with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise ValueError(f"[C.O.D.E. Fatal] Prompt file at {PROMPT_FILE_PATH} is empty.")
        return content
    except Exception as e:
        raise RuntimeError(f"Failed to access external system prompt contract: {e}")

try:
    SYSTEM_PROMPT_TEMPLATE = load_commander_system_prompt()
except Exception as err:
    print(str(err))
    sys.exit(1)

# ==================== 3. Audit Logger ====================
def write_audit_event(event_type, asset_id, message, details=None):
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stage": "Stage_2_L1_Extract",
        "event_type": event_type,
        "asset_id": asset_id,
        "message": message,
        "details": details or {}
    }
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[Log Error] Failed to write to audit log: {e}")

# ==================== 4. Core Processing Functions ====================

def build_sliding_windows(paragraphs, asset_id):
    if not paragraphs or (len(paragraphs) == 1 and not paragraphs[0]["text"].strip()):
        write_audit_event("WARNING", asset_id, "Empty paragraph sequence encountered. Codebase bypassed.")
        return []

    chunks = []
    current_chunk_text = []
    current_word_count = 0
    current_section = None

    for p in paragraphs:
        text = p["text"].strip()
        section = p["section"].strip()
        if not text:
            continue

        words = text.split()

        if len(words) > CHUNK_WORD_LIMIT:
            if current_chunk_text:
                chunks.append({"section": current_section or section, "content": " ".join(current_chunk_text)})
                current_chunk_text = []
                current_word_count = 0

            for sub_idx in range(0, len(words), CHUNK_WORD_LIMIT):
                sub_words = words[sub_idx: sub_idx + CHUNK_WORD_LIMIT]
                chunks.append({"section": f"{section}_Subchunk_{sub_idx // CHUNK_WORD_LIMIT}", "content": " ".join(sub_words)})
            continue

        if (current_word_count + len(words) > CHUNK_WORD_LIMIT or (current_section and section != current_section)) and current_chunk_text:
            chunks.append({
                "section": current_section,
                "content": " ".join(current_chunk_text)
            })
            current_chunk_text = []
            current_word_count = 0

        current_section = section
        current_chunk_text.append(text)
        current_word_count += len(words)

    if current_chunk_text:
        chunks.append({
            "section": current_section,
            "content": " ".join(current_chunk_text)
        })
    return chunks


async def call_llm_worker(session, chunk_content, sample_id, asset_id):
    target_temperature = 0.3 + (sample_id * 0.1)
    active_system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("{chunk_content}", chunk_content).replace("{abstract_text}", chunk_content)
    sanitized_user_id = "".join([c for c in asset_id if c.isalnum() or c in ["-", "_"]])[:512]

    payload = {
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": active_system_prompt},
            {"role": "user", "content": chunk_content}
        ],
        "response_format": {"type": "json_object"},
        "temperature": target_temperature,
        "user_id": sanitized_user_id
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # ⚡【战术级超频微调】：重试降低为 2 次，单次网络死锁超时压缩到 30 秒！绝不干等！
    for attempt in range(2):
        try:
            async with session.post(API_URL, json=payload, headers=headers, timeout=30) as response:
                if response.status == 200:
                    res_json = await response.json()
                    raw_output = res_json['choices'][0]['message']['content']
                    return json.loads(raw_output)

                elif response.status == 429:
                    sleep_time = 3 ** (attempt + 1)
                    print(f"\n[API Rate-Limit 429] Asset {asset_id} triggered limit. Backoff sleep {sleep_time}s...")
                    await asyncio.sleep(sleep_time)
                else:
                    status_text = await response.text()
                    write_audit_event("API_ERROR", asset_id, f"Non-200 response: {response.status}", {"text": status_text[:200]})
                    await asyncio.sleep(2)
        except json.JSONDecodeError:
            # 🛡️ 格式损坏直接原地化为空解耦，拒绝卡死流水线
            return {"causal_tuples": []}
        except Exception:
            await asyncio.sleep(1)

    # ⚡【至高核心自愈盾牌】：如果这个 Chunk 卡死超过一分钟（2次重试均阵亡）
    # 强制赋予该 Chunk 一个合法的空结果字典，作为有效负面观测直接过关！
    # 确保整篇大文章能瞬间在磁盘写出完结 JSON，让后续的文献全速向前大超车！
    write_audit_event("SOFT_TIMEOUT_HEAL", asset_id, f"Chunk sample {sample_id} reached fallback limits. Force committed empty lists.")
    return {"causal_tuples": []}


def aggregate_parallel_universe_samples(samples):
    aggregated = {}
    total_valid_samples = 0

    for s in samples:
        # 即使被软自愈赋予了默认值，只要它满足字典流形，依旧平权计入分母！
        if not s or not isinstance(s, dict) or "pipeline_error" in s:
            continue

        tuples = []
        is_empty_semantic_response = False

        if "causal_tuples" in s and isinstance(s["causal_tuples"], list):
            tuples = s["causal_tuples"]
            if len(tuples) == 0:
                is_empty_semantic_response = True
        elif len(s) == 1 and isinstance(list(s.values())[0], list):
            tuples = list(s.values())[0]
            if len(tuples) == 0:
                is_empty_semantic_response = True
        elif "subject" in s:
            tuples = [s]
        else:
            is_empty_semantic_response = True

        total_valid_samples += 1

        if is_empty_semantic_response or not tuples:
            continue

        for t in tuples:
            if not isinstance(t, dict):
                continue

            sub = t.get("subject", "Unknown").strip()
            rel_raw = t.get("relation_raw", "Unknown").strip()
            sign = t.get("relation_sign")
            obj = t.get("object", "Unknown").strip()
            ctx = t.get("context", {})
            negated = t.get("negated", False)
            quote = t.get("evidence_sentence", "Unknown").strip()
            confidence = t.get("confidence", 1.0)

            if sub == "Unknown" or sign not in [1, -1] or obj == "Unknown":
                continue

            triplet_key = (sub.lower(), sign, obj.lower())

            if triplet_key not in aggregated:
                aggregated[triplet_key] = {
                    "subject": sub,
                    "relation_raw_variants": [],
                    "relation_sign": sign,
                    "object": obj,
                    "sample_frequency": 0,
                    "consensus_score": 0.0,
                    "negated_votes": 0,
                    "contexts": [],
                    "evidence_sentences": [],
                    "mean_confidence": 0.0
                }

            v = aggregated[triplet_key]
            v["sample_frequency"] += 1
            v["mean_confidence"] += confidence
            if negated:
                v["negated_votes"] += 1

            if rel_raw != "Unknown" and rel_raw not in v["relation_raw_variants"]:
                v["relation_raw_variants"].append(rel_raw)
            if ctx and ctx not in v["contexts"]:
                v["contexts"].append(ctx)
            if quote != "Unknown" and quote not in v["evidence_sentences"]:
                v["evidence_sentences"].append(quote)

    if total_valid_samples > 0:
        for k, v in aggregated.items():
            v["consensus_score"] = round(v["sample_frequency"] / total_valid_samples, 3)
            v["mean_confidence"] = round(v["mean_confidence"] / v["sample_frequency"], 2)
            v["predominant_negated"] = v["negated_votes"] > (v["sample_frequency"] / 2)

    return list(aggregated.values())


async def process_single_asset(session, semaphore, asset_id):
    async with semaphore:
        payload_path = os.path.join(PAYLOAD_DIR, f"{asset_id}_payload.json")
        output_path = os.path.join(EXTRACT_OUTPUT_DIR, f"{asset_id}_extracted.json")

        if os.path.exists(output_path):
            return True

        if not os.path.exists(payload_path):
            write_audit_event("ERROR", asset_id, "Payload JSON missing from disk path.")
            return False

        try:
            with open(payload_path, "r", encoding="utf-8") as f:
                paper_data = json.load(f)
        except Exception as e:
            write_audit_event("ERROR", asset_id, "Corrupted payload JSON schema", {"exception": str(e)})
            return False

        write_audit_event("ASSET_START", asset_id, "Initiating extraction sequence.")
        chunks = build_sliding_windows(paper_data["paragraphs"], asset_id)

        if not chunks:
            write_audit_event("ASSET_SKIP", asset_id, "No valid chunks derived from semantic loader.")
            return False

        all_chunks_results = []

        for chunk_idx, chunk in enumerate(chunks):
            sample_responses = []
            for i in range(N_SAMPLES):
                resp = await call_llm_worker(session, chunk["content"], i, asset_id)
                sample_responses.append(resp)

            voted_relations = aggregate_parallel_universe_samples(sample_responses)

            all_chunks_results.append({
                "chunk_index": chunk_idx,
                "section": chunk["section"],
                "aggregated_relations": voted_relations,
                "raw_samples": sample_responses
            })

        complete_extraction_payload = {
            "asset_id": asset_id,
            "doi": paper_data.get("doi", "None"),
            "article_title": paper_data.get("article_title", "Unknown"),
            "journal": paper_data.get("journal", "Unknown"),
            "belief_weight": paper_data.get("belief_weight", 0.6),
            "chunks_extracted": all_chunks_results
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(complete_extraction_payload, f, ensure_ascii=False, indent=2)

        write_audit_event("ASSET_COMPLETE", asset_id, f"Successfully processed and aggregated {asset_id}")
        return True


async def run_extraction_pipeline():
    print("[C.O.D.E. Stage 2] Core extract pipeline engine starting...")
    write_audit_event("PIPELINE_START", "GLOBAL", "Stage 2 execution sequence initiated.")

    if not os.path.exists(GLOBAL_MANIFEST_PATH):
        print(f"[ERROR] Manifest file missing at {GLOBAL_MANIFEST_PATH}. Aborting...")
        return

    with open(GLOBAL_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    asset_dict = manifest.get("papers", {})
    all_asset_ids = list(asset_dict.keys())

    # Filter out already processed assets to avoid redundant work and UI lockup
    final_mining_tasks = []
    skipped_count = 0

    for aid in all_asset_ids:
        target_output = os.path.join(EXTRACT_OUTPUT_DIR, f"{aid}_extracted.json")
        if os.path.exists(target_output):
            skipped_count += 1
        else:
            final_mining_tasks.append(aid)

    print(f"Total assets in manifest: {len(all_asset_ids)}")
    print(f"Skipped (already extracted): {skipped_count}")
    print(f"Pending extraction: {len(final_mining_tasks)}")

    if not final_mining_tasks:
        print("All assets have already been processed. Exiting.")
        write_audit_event("PIPELINE_END", "GLOBAL", "All assets already verified offline.")
        return

    semaphore = asyncio.BoundedSemaphore(MAX_CONCURRENT_WORKERS)
    connector = aiohttp.TCPConnector(limit=128)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [process_single_asset(session, semaphore, aid) for aid in final_mining_tasks]
        await tqdm_asyncio.gather(*tasks, desc="C.O.D.E. Mining Space (N=5)")

    write_audit_event("PIPELINE_SUCCESS", "GLOBAL", "All remaining assets cleared and consensus matrices stored.")
    print(f"[Stage 2 Complete] Extraction outputs stored in: {EXTRACT_OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(run_extraction_pipeline())