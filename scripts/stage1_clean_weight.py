"""
LEGACY ONLY. Not imported or used by System A runtime reasoning.

The static journal metrics emitted here are historical audit metadata and must
not be consumed as confidence or scoring inputs by ``src/code_engine``.

C.O.D.E. Stage 1: Journal Weighting & Full-Text Extraction Pipeline
Complete Release 1.5 (Unified Asset Settlement Master Control - Rigid Flow Edition)

This module processes all assets registered in the global manifest (both PMC full-text
XML and PubMed abstract JSON), extracts metadata and text content, applies journal
weighting from the knowledge base, and generates standardized payloads.

[Release 1.5 Patch]: Explicitly bifurcates the asset resolution stream and hardens
the fallback logic to guarantee 100% immune flow against file system desynchronization.
"""

import os
import csv
import json
import xml.etree.ElementTree as ET
import difflib
from tqdm import tqdm

XML_DIR = "./data/raw/xml"
OUTPUT_PAYLOAD_DIR = "./data/interim/weighted_payloads"
GLOBAL_MANIFEST_PATH = "data/metadata/global_manifest.json"
AUDIT_CSV_PATH = "data/metadata/literature_quality_audit.csv"

os.makedirs(OUTPUT_PAYLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(AUDIT_CSV_PATH), exist_ok=True)

# =====================================================================
# JOURNAL KNOWLEDGE BASE WITH ISSN AND ALIAS MAPPING
# =====================================================================
JOURNAL_KNOWLEDGE_BASE = {
    "Nature": {"issn": ["0028-0836", "1476-4687"], "aliases": ["nature"], "metrics": {"if": 50.5, "weight": 1.0, "tier": "CNS"}},
    "Science": {"issn": ["0036-8075", "1095-9203"], "aliases": ["science"], "metrics": {"if": 44.7, "weight": 1.0, "tier": "CNS"}},
    "Cell": {"issn": ["0092-8674", "1097-4172"], "aliases": ["cell"], "metrics": {"if": 45.5, "weight": 1.0, "tier": "CNS"}},
    "Nature Medicine": {"issn": ["1078-8956", "1546-170X"], "aliases": ["nat med", "nat. med."], "metrics": {"if": 58.0, "weight": 0.95, "tier": "Top"}},
    "Nature Neuroscience": {"issn": ["1097-6256", "1546-1726"], "aliases": ["nat neurosci", "nat. neurosci."], "metrics": {"if": 21.2, "weight": 0.9, "tier": "Top"}},
    "Molecular Psychiatry": {"issn": ["1359-4184", "1476-5578"], "aliases": ["mol psychiatry", "mol. psychiatry"], "metrics": {"if": 11.1, "weight": 0.85, "tier": "Top"}},
    "Biological Psychiatry": {"issn": ["0006-3223", "1873-2402"], "aliases": ["biol psychiatry", "biol. psychiatry"], "metrics": {"if": 10.6, "weight": 0.8, "tier": "Top"}},
    "Trends in Neurosciences": {"issn": ["0166-2236", "1878-108X"], "aliases": ["trends neurosci", "trends neurosci."], "metrics": {"if": 14.6, "weight": 0.85, "tier": "Top"}},
    "Lancet Psychiatry": {"issn": ["2215-0366", "2215-0374"], "aliases": ["lancet psychiatry", "lancet psychiat"], "metrics": {"if": 30.8, "weight": 0.9, "tier": "Top"}},
    "eLife": {"issn": ["2050-084X"], "aliases": ["elife"], "metrics": {"if": 8.4, "weight": 0.8, "tier": "Top"}},
    "The Journal of Neuroscience": {"issn": ["0270-6474", "1529-2401"], "aliases": ["journal of neuroscience", "j neurosci", "j. neurosci."], "metrics": {"if": 5.3, "weight": 0.7, "tier": "JCR-Q1"}},
    "Neuropharmacology": {"issn": ["0028-3908", "1873-7064"], "aliases": ["neuropharmacology"], "metrics": {"if": 4.5, "weight": 0.65, "tier": "JCR-Q1"}},
    "Neuropsychopharmacology": {"issn": ["0893-133X", "1740-634X"], "aliases": ["neuropsychopharmacology"], "metrics": {"if": 6.6, "weight": 0.75, "tier": "JCR-Q1"}},
    "Translational Psychiatry": {"issn": ["2158-3188"], "aliases": ["transl psychiatry", "transl. psychiatry"], "metrics": {"if": 5.8, "weight": 0.7, "tier": "JCR-Q1"}},
    "Journal of Affective Disorders": {"issn": ["0165-0327", "1573-2517"], "aliases": ["j affect disorders", "j. affect. disorders", "j affect disord"], "metrics": {"if": 4.9, "weight": 0.65, "tier": "JCR-Q1"}},
    "International Journal of Neuropsychopharmacology": {"issn": ["1461-1457", "1469-5111"], "aliases": ["int j neuropsychopharmacol", "int. j. neuropsychopharmacol."], "metrics": {"if": 4.5, "weight": 0.65, "tier": "JCR-Q1"}},
    "European Neuropsychopharmacology": {"issn": ["0924-977X", "1873-7862"], "aliases": ["eur neuropsychopharmacol", "eur. neuropsychopharmacol."], "metrics": {"if": 4.4, "weight": 0.65, "tier": "JCR-Q1"}},
    "Scientific Reports": {"issn": ["2045-2322"], "aliases": ["sci rep", "sci. rep."], "metrics": {"if": 4.6, "weight": 0.6, "tier": "JCR-Q1"}},
    "Current Neuropharmacology": {"issn": ["1570-159X", "1875-6190"], "aliases": ["curr neuropharmacol", "curr. neuropharmacol."], "metrics": {"if": 4.6, "weight": 0.65, "tier": "JCR-Q1"}},
    "Frontiers in Psychiatry": {"issn": ["1664-0640"], "aliases": ["front psychiatry", "front. psychiatry"], "metrics": {"if": 4.8, "weight": 0.65, "tier": "JCR-Q1"}},
    "Pharmaceuticals": {"issn": ["1424-8247"], "aliases": ["pharmaceuticals"], "metrics": {"if": 5.1, "weight": 0.65, "tier": "JCR-Q1"}},
    "Bioinformatics": {"issn": ["1367-4803", "1460-2059"], "aliases": ["bioinformatics"], "metrics": {"if": 4.4, "weight": 0.7, "tier": "JCR-Q1"}},
    "Journal of Psychopharmacology": {"issn": ["0269-8811", "1461-7285"], "aliases": ["journal of psychopharmacology", "journal of psychopharmacology (oxford, england)", "j psychopharmacol", "j. psychopharmacol."], "metrics": {"if": 3.2, "weight": 0.5, "tier": "JCR-Q2"}},
    "PLOS ONE": {"issn": ["1932-6203"], "aliases": ["plos one", "plos 1"], "metrics": {"if": 2.9, "weight": 0.4, "tier": "JCR-Q2"}}
}

# 🛡️ Synchronized adaptive silver pool for neutral handling of unmapped nodes
DEFAULT_WEIGHT = {"if": 3.5, "weight": 0.6, "tier": "Adaptive_Silver_Pool"}

_ISSN_MAP = {}
_ALIAS_MAP = {}
for norm_name, data in JOURNAL_KNOWLEDGE_BASE.items():
    for issn in data["issn"]:
        _ISSN_MAP[issn.strip().replace("-", "").lower()] = norm_name
    for alias in data["aliases"]:
        _ALIAS_MAP[alias.strip().lower()] = norm_name
    _ALIAS_MAP[norm_name.strip().lower()] = norm_name


def resolve_journal_weight(journal_title, issn_list=None):
    if issn_list:
        for raw_issn in issn_list:
            clean_issn = raw_issn.strip().replace("-", "").lower()
            if clean_issn in _ISSN_MAP:
                norm_name = _ISSN_MAP[clean_issn]
                return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], False, norm_name

    # 🛡️ Aligned Fallback Strategy: Unknown or missing titles enter the neutral adaptive pool
    if not journal_title or journal_title.strip().lower() == "unknown":
        return DEFAULT_WEIGHT, False, "Unknown"

    clean_title = journal_title.strip().lower()

    if clean_title in _ALIAS_MAP:
        norm_name = _ALIAS_MAP[clean_title]
        return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], False, norm_name

    if clean_title.startswith("the "):
        stripped_title = clean_title[4:]
        if stripped_title in _ALIAS_MAP:
            norm_name = _ALIAS_MAP[stripped_title]
            return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], False, norm_name

    search_pool = list(_ALIAS_MAP.keys())
    matches = difflib.get_close_matches(clean_title, search_pool, n=1, cutoff=0.85)

    if matches:
        matched_alias = matches[0]
        norm_name = _ALIAS_MAP[matched_alias]
        return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], False, norm_name

    return DEFAULT_WEIGHT, False, journal_title


def extract_full_text_paragraphs(root):
    paragraphs_payload = []
    body_node = root.find(".//body")

    if body_node is None:
        return paragraphs_payload

    parent_map = {child: parent for parent in body_node.iter() for child in parent}

    for p_node in body_node.iter("p"):
        p_text = "".join(p_node.itertext()).strip()
        if not p_text:
            continue

        section_name = "Main_Text"
        current_node = p_node
        while current_node in parent_map and current_node != body_node:
            current_node = parent_map[current_node]
            if current_node.tag == "sec":
                title_node = current_node.find("title")
                if title_node is not None:
                    section_name = "".join(title_node.itertext()).strip() or "Main_Text"
                break

        paragraphs_payload.append({
            "section": section_name,
            "text": p_text
        })

    return paragraphs_payload


def process_one_pmc(pmc_full_id):
    xml_path = os.path.join(XML_DIR, f"{pmc_full_id}.xml")
    # 🛡️ Rigid File Existence Check: Prevent downstream file opening exceptions
    if not os.path.exists(xml_path):
        print(f"\n Missing raw XML source file for {pmc_full_id}. Skipping...")
        return None

    try:
        with open(xml_path, "r", encoding="utf-8", errors="ignore") as f:
            xml_raw_string = f.read()
        cleaned_xml_string = xml_raw_string.replace('xmlns="', 'data-xmlns="').replace("xmlns='", "data-xmlns='")
        root = ET.fromstring(cleaned_xml_string)

        journal = ""
        journal_node = root.find(".//journal-meta/journal-title-group/journal-title")
        if journal_node is not None and journal_node.text:
            journal = journal_node.text.strip()

        issn_list = []
        for issn_node in root.findall(".//journal-meta/issn"):
            if issn_node.text:
                issn_list.append(issn_node.text.strip())

        title = "Unknown Title"
        title_node = root.find(".//article-meta/title-group/article-title")
        if title_node is not None:
            title = "".join(title_node.itertext()).strip()

        doi = None
        for article_id in root.findall(".//article-id"):
            if article_id.get("pub-id-type") == "doi":
                doi = article_id.text
                break
        if not doi:
            doi = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_full_id}/"

        metrics, is_noise, normalized_journal = resolve_journal_weight(journal, issn_list=issn_list)
        full_text_body = extract_full_text_paragraphs(root)

        return {
            "pmcid": pmc_full_id,
            "doi": doi,
            "article_title": title,
            "journal": normalized_journal,
            "impact_factor": metrics["if"],
            "jcr_tier": metrics["tier"],
            "belief_weight": metrics["weight"],
            "is_noise_candidate": is_noise,
            "paragraphs": full_text_body
        }
    except Exception as e:
        print(f"Error parsing {pmc_full_id}: {e}")
        return None


def run_stage1_pipeline():
    print("[C.O.D.E. Stage 1] Starting unified asset processing pipeline...")

    if not os.path.exists(GLOBAL_MANIFEST_PATH):
        print(f"Error: Global manifest not found at {GLOBAL_MANIFEST_PATH}. Please run Stage 0/0.5 first.")
        return

    with open(GLOBAL_MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    papers_dict = manifest.get("papers", {})

    if not papers_dict:
        print("Global manifest registry is empty.")
        return

    asset_ids = list(papers_dict.keys())
    audit_records = []
    journal_stats = {}

    for asset_id in tqdm(asset_ids, desc="Processing assets"):
        output_json_path = os.path.join(OUTPUT_PAYLOAD_DIR, f"{asset_id}_payload.json")

        if os.path.exists(output_json_path):
            try:
                with open(output_json_path, "r", encoding="utf-8") as f:
                    cached_payload = json.load(f)

                j_name = cached_payload["journal"]
                audit_records.append({
                    "pmcid": cached_payload["pmcid"],
                    "journal": j_name,
                    "impact_factor": cached_payload["impact_factor"],
                    "jcr_tier": cached_payload["jcr_tier"],
                    "belief_weight": cached_payload["belief_weight"],
                    "is_noise_candidate": cached_payload["is_noise_candidate"],
                    "paragraph_count": len(cached_payload["paragraphs"])
                })
                journal_stats[j_name] = journal_stats.get(j_name, 0) + 1
                continue
            except Exception:
                print(f"Corrupted payload cache {asset_id}_payload.json, removing...")
                if os.path.exists(output_json_path):
                    os.remove(output_json_path)

        # 🛡️ Bifurcation Control Gate: Stop PMID abstract assets from crashing the XML parser
        if asset_id.startswith("PMID"):
            print(f"\n⚠️ Missing pre-computed payload cache for silver-track asset {asset_id}.")
            print(f"➡️ Please re-run 'python scripts/stage0_5_fetch_abstracts.py' to recover.")
            continue

        payload = process_one_pmc(asset_id)
        if payload is None:
            continue

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        j_name = payload["journal"]
        journal_stats[j_name] = journal_stats.get(j_name, 0) + 1

        audit_records.append({
            "pmcid": payload["pmcid"],
            "journal": j_name,
            "impact_factor": payload["impact_factor"],
            "jcr_tier": payload["jcr_tier"],
            "belief_weight": payload["belief_weight"],
            "is_noise_candidate": payload["is_noise_candidate"],
            "paragraph_count": len(payload["paragraphs"])
        })

    with open(AUDIT_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        fieldnames = ["pmcid", "journal", "impact_factor", "jcr_tier", "belief_weight", "is_noise_candidate", "paragraph_count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(audit_records)

    print("Stage 1 processing completed successfully.")
    print(f"Standardized JSON payloads stored in: {OUTPUT_PAYLOAD_DIR}")
    print(f"Quality audit CSV stored in: {AUDIT_CSV_PATH}")

    print("\nTop 10 journal distribution (after disambiguation and weighting):")
    for j, c in sorted(journal_stats.items(), key=lambda x: -x[1])[:10]:
        matched = any(k.lower() == j.lower() for k in JOURNAL_KNOWLEDGE_BASE.keys())
        status = "matched/weighted" if matched else "unmatched (default weight applied)"
        print(f"  - {j}: {c} articles ({status})")


if __name__ == "__main__":
    run_stage1_pipeline()
