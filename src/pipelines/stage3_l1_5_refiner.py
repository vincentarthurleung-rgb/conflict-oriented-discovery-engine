"""
C.O.D.E. Core Pipeline - Stage 3: Layer 1.5 Anti-Hallucination Context Refiner
Universal Release 3.2.1 (Production Core - Checkpoint Resumption + Observability Edition)

[Release 3.2.1 Changes]:
- Observability: Added explicit checkpoint logging for cache hits to ensure pipeline transparency.
- Checkpoint: Pre-flight cache checks to skip already refined assets, eliminating token re-consumption.
- Input Buffer: Strips placeholder values ('unspecified') before LLM inference to minimize cognitive bias.
- Exception Handling: Enforces explicit exception propagation for orchestrator trap.
"""

import os
import sys
import json
import asyncio
import aiohttp
import time
import re

L1_INPUT_DIR = "./data/processed/l1"
L1_5_OUTPUT_DIR = "./data/processed/l1_5_refined"
AUDIT_LOG_PATH = "logs/audit_l1_5.jsonl"
CONFIG_RULES_PATH = "config/schemas/l1_5_refiner_rules.json"

os.makedirs(L1_5_OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(AUDIT_LOG_PATH), exist_ok=True)

BASE_URL = "https://api.deepseek.com"
API_URL = f"{BASE_URL}/v1/chat/completions"
API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not API_KEY:
    raise ValueError("[C.O.D.E. Fatal] 'DEEPSEEK_API_KEY' is missing. Pipeline locked.")

def load_external_refiner_contract():
    if not os.path.exists(CONFIG_RULES_PATH):
        raise FileNotFoundError(f"Config schema missing at: {CONFIG_RULES_PATH}")
    with open(CONFIG_RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f).get("regex_rules", {})

try:
    REGEX_RULES = load_external_refiner_contract()
except Exception as err:
    print(f"[Config Crash] {str(err)}", file=sys.stderr)
    sys.exit(1)


def local_regex_extract_algorithmic(sentence, field_type):
    clean_sent = sentence.lower()
    if field_type not in REGEX_RULES:
        return "unspecified"
    # Sort patterns by length (longest first) to prioritize more specific matches
    sorted_patterns = sorted(REGEX_RULES[field_type].items(), key=lambda x: len(x[1]), reverse=True)
    for standard_val, pattern in sorted_patterns:
        if re.search(pattern, clean_sent):
            return standard_val.upper().strip()
    return "unspecified"


def verify_llm_substring_evidence(sentence, extracted_value, evidence_substring):
    if not evidence_substring or evidence_substring.strip() == "":
        return False
    if evidence_substring.strip() not in sentence:
        return False
    val_lower = extracted_value.lower().strip()
    ev_lower = evidence_substring.lower().strip()
    if val_lower not in ev_lower and not any(word in ev_lower for word in val_lower.split()):
        return False
    return True


def global_format_leveller(raw_value):
    if not raw_value or raw_value.lower().strip() in ["unspecified", "default_macro_env", ""]:
        return "unspecified"
    return re.sub(r'[\s_\-]+', ' ', raw_value.upper().strip())


async def call_multifield_llm_with_retry(session, sentence, section, fields_to_query, asset_id):
    fields_desc = ", ".join(fields_to_query)
    
    prompt = f"""You are a strict text extractor, not a knowledge base. 
Given a sentence from a scientific paper and its section name, extract experimental conditions ONLY for the requested fields: [{fields_desc}] if they are explicitly mentioned. DO NOT use your own knowledge to guess missing information.

Sentence: "{sentence}"
Section: "{section}"

Output a JSON object where each requested field contains a "value" string and an "evidence" string.
- "value": The specific term extracted. If not mentioned explicitly, you MUST write "unspecified".
- "evidence": The exact verbatim substring from the sentence that supports the value. If "unspecified", keep empty "".

Return ONLY a valid JSON object matching the requested fields schema. Do not add explanations."""

    payload = {
        "model": "deepseek-v4-pro",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
        "user_id": f"refine_{asset_id}"[:50]
    }
    
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    
    for attempt in range(3):
        try:
            async with session.post(API_URL, json=payload, headers=headers, timeout=45) as resp:
                if resp.status == 200:
                    raw_text = await resp.text()
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    return json.loads(json_match.group(0)) if json_match else json.loads(raw_text)
                elif resp.status == 429:
                    await asyncio.sleep(3 ** (attempt + 1))
                else:
                    await asyncio.sleep(2)
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"DeepSeek Node Exhausted on {asset_id}: {str(e)}")
    return {}


async def refine_single_file(session, semaphore, fname):
    """
    Refine a single L1 extraction file with breakpoint resumption.
    Skips already refined assets to avoid token re-consumption.
    """
    async with semaphore:
        asset_id = fname.replace("_extracted.json", "")
        out_path = os.path.join(L1_5_OUTPUT_DIR, f"{asset_id}_refined.json")
        
        # Skip if already refined
        if os.path.exists(out_path):
            print(f"[Checkpoint] Asset {asset_id} already refined, skipping.")
            return
            
        fpath = os.path.join(L1_INPUT_DIR, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            l1_data = json.load(f)
            
        for chunk in l1_data.get("chunks_extracted", []):
            section_name = chunk.get("section", "Main_Text")
            for sample in chunk.get("raw_samples", []):
                if "causal_tuples" not in sample:
                    continue
                    
                for tuple_node in sample["causal_tuples"]:
                    evidence_sentence = tuple_node.get("evidence_sentence", "").strip()
                    if not evidence_sentence:
                        continue
                        
                    # Preserve immutable core fields
                    immutable_sign = tuple_node.get("relation_sign", 1)
                    immutable_negated = tuple_node.get("negated", False)
                    
                    ctx = tuple_node.get("context", {})
                    source_tracker = tuple_node.get("_source", {})
                    
                    all_target_fields = ["species", "localization", "time", "cell_line_or_type", "genotype", "treatment"]
                    fields_needing_llm = []
                    
                    for field in all_target_fields:
                        current_val = ctx.get(field, "unspecified")
                        
                        # Clear placeholder values and attempt regex extraction
                        if current_val in ["unspecified", "default_macro_env", ""]:
                            rule_val = local_regex_extract_algorithmic(evidence_sentence, field)
                            if rule_val != "unspecified":
                                ctx[field] = global_format_leveller(rule_val)
                                source_tracker[field] = "rule"
                            else:
                                fields_needing_llm.append(field)
                                ctx[field] = ""  # Temporary clear for LLM
                        else:
                            if field not in source_tracker:
                                source_tracker[field] = "original"
                            ctx[field] = global_format_leveller(current_val)
                            
                    if fields_needing_llm:
                        llm_payload = await call_multifield_llm_with_retry(
                            session, evidence_sentence, section_name, fields_needing_llm, asset_id
                        )
                        
                        for field in fields_needing_llm:
                            field_res = llm_payload.get(field, {})
                            llm_val = field_res.get("value", "unspecified")
                            llm_evidence = field_res.get("evidence", "")
                            
                            if llm_val != "unspecified" and verify_llm_substring_evidence(evidence_sentence, llm_val, llm_evidence):
                                ctx[field] = global_format_leveller(llm_val)
                                source_tracker[field] = "llm"
                            else:
                                ctx[field] = "unspecified"
                                source_tracker[field] = "failed_unspecified"
                                
                    # Restore any empty fields to "unspecified"
                    for field in all_target_fields:
                        if ctx[field] == "":
                            ctx[field] = "unspecified"
                            
                    tuple_node["relation_sign"] = immutable_sign
                    tuple_node["negated"] = immutable_negated
                    tuple_node["context"] = ctx
                    tuple_node["_source"] = source_tracker
                    
        l1_data["refined_status"] = "Release_3.2.1_Truth_Locked"
        with open(out_path, "w", encoding="utf-8") as out_f:
            json.dump(l1_data, out_f, ensure_ascii=False, indent=2)
        print(f"[Refined] {asset_id} successfully processed.")