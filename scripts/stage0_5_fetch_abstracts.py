"""
C.O.D.E. Stage 0.5: Silver Track Literature Fetching Kernel - PubMed Abstract Downloader
Complete Release 1.4 (Unified Global Contract Hardened Version)

This module retrieves PubMed abstracts for non-open-access articles matching the
search criteria, extracts metadata, assigns journal weights using the unified
knowledge base, and merges the results into the global manifest.
"""

import os
import time
import json
import xml.etree.ElementTree as ET
import difflib
from Bio import Entrez
from tqdm import tqdm
from http.client import HTTPException
from urllib.error import URLError

# NCBI email address required for E-utilities access
Entrez.email = "vincentarthurleung@gmail.com"

# Search query for non-open-access articles (silver track)
SEARCH_QUERY = (
    "(Ketamine[Title/Abstract]) AND "
    "(antidepressant[Title/Abstract] OR depression[Title/Abstract] OR rapid-acting[Title/Abstract] OR fast-acting[Title/Abstract]) AND "
    "(NMDA[Title/Abstract] OR synaptic[Title/Abstract] OR glutamate[Title/Abstract] OR AMPA[Title/Abstract] OR mTOR[Title/Abstract]) AND "
    "NOT open access[filter]"
)

MAX_DOCS = 800
RAW_OUTPUT_DIR = "./data/raw/abstracts"
OUTPUT_PAYLOAD_DIR = "./data/interim/weighted_payloads"
GLOBAL_MANIFEST_PATH = "data/metadata/global_manifest.json"

os.makedirs(RAW_OUTPUT_DIR, exist_ok=True)
os.makedirs(OUTPUT_PAYLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(GLOBAL_MANIFEST_PATH), exist_ok=True)

# Unified journal knowledge base for consistent weighting across all tracks
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
_ALIAS_MAP = {}
for norm_name, data in JOURNAL_KNOWLEDGE_BASE.items():
    for alias in data["aliases"]:
        _ALIAS_MAP[alias.strip().lower()] = norm_name
    _ALIAS_MAP[norm_name.strip().lower()] = norm_name

# Default weight for journals not found in knowledge base
DEFAULT_WEIGHT = {"if": 3.5, "weight": 0.6, "tier": "Adaptive_Silver_Pool"}


def resolve_embedded_weight(journal_title):
    """
    Map a journal title to its weight metrics using alias matching and fuzzy matching.

    Args:
        journal_title (str): The raw journal title extracted from PubMed.

    Returns:
        tuple: (metrics dict, normalized journal name)
            - metrics: dict with keys "if", "weight", "tier"
            - normalized_journal: str, the canonical journal name or original if unmapped
    """
    if not journal_title:
        return DEFAULT_WEIGHT, "Unknown"

    clean_title = journal_title.strip().lower()

    if clean_title in _ALIAS_MAP:
        norm_name = _ALIAS_MAP[clean_title]
        return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], norm_name

    # Fuzzy matching for close variations
    search_pool = list(_ALIAS_MAP.keys())
    matches = difflib.get_close_matches(clean_title, search_pool, n=1, cutoff=0.85)
    if matches:
        norm_name = _ALIAS_MAP[matches[0]]
        return JOURNAL_KNOWLEDGE_BASE[norm_name]["metrics"], norm_name

    return DEFAULT_WEIGHT, journal_title


def fetch_pubmed_abstracts():
    """
    Execute the PubMed abstract retrieval pipeline for the silver track.

    Steps:
    1. Query NCBI ESearch for PubMed IDs matching the non-open-access criteria.
    2. For each ID, fetch the XML record, extract title, abstract, journal, DOI.
    3. Apply journal weighting via resolve_embedded_weight.
    4. Save raw abstract JSON and unified payload JSON.
    5. Update the global manifest with the processed entries.
    """
    print("[C.O.D.E. Stage 0.5] Starting PubMed silver-track abstract retrieval...")

    try:
        handle = Entrez.esearch(
            db="pubmed", term=SEARCH_QUERY, retmax=MAX_DOCS,
            datetype="pdat", mindate="1900/01/01", maxdate="2015/12/31"
        )
        record = Entrez.read(handle)
        handle.close()
    except Exception as e:
        print(f"PubMed ESearch connection failed: {e}")
        return

    pubmed_ids = record.get("IdList", [])
    print(f"PubMed silver-track hits: {len(pubmed_ids)} abstract-only records.")

    if not pubmed_ids:
        return

    success_pmid_records = []

    for pmid in tqdm(pubmed_ids, desc="Harvesting & Structuring"):
        virtual_key = f"PMID{pmid}"
        raw_json_filename = os.path.join(RAW_OUTPUT_DIR, f"{virtual_key}.json")
        payload_filename = os.path.join(OUTPUT_PAYLOAD_DIR, f"{virtual_key}_payload.json")

        # Skip if already processed
        if os.path.exists(payload_filename):
            success_pmid_records.append(virtual_key)
            continue

        max_retries = 3
        fetch_success = False

        for attempt in range(max_retries):
            try:
                fetch_handle = Entrez.efetch(db="pubmed", id=pmid, retmode="xml")
                xml_data = fetch_handle.read()
                fetch_handle.close()

                root = ET.fromstring(xml_data)

                # Extract journal title
                journal = ""
                journal_node = root.find(".//Journal/Title")
                if journal_node is not None and journal_node.text:
                    journal = journal_node.text.strip()
                if not journal:
                    iso_node = root.find(".//ISOAbbreviation")
                    if iso_node is not None and iso_node.text:
                        journal = iso_node.text.strip()

                # Extract article title
                title = "Unknown Title"
                title_node = root.find(".//ArticleTitle")
                if title_node is not None:
                    title = "".join(title_node.itertext()).strip()

                # Extract abstract text
                abstract_text = ""
                abstract_nodes = root.findall(".//AbstractText")
                if abstract_nodes:
                    abstract_text = " ".join(["".join(n.itertext()).strip() for n in abstract_nodes if n.itertext()])

                if not abstract_text:
                    fetch_success = True
                    break

                # Extract DOI
                doi = None
                for article_id in root.findall(".//ArticleId"):
                    id_type = article_id.get("IdType")
                    if id_type == "doi" and article_id.text:
                        doi = article_id.text.strip()
                if not doi:
                    doi = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

                # Apply journal weighting
                metrics, normalized_journal = resolve_embedded_weight(journal)

                # Build unified payload (compatible with Stage 1 output format)
                unified_payload = {
                    "pmcid": virtual_key,
                    "doi": doi,
                    "article_title": title,
                    "journal": normalized_journal,
                    "impact_factor": metrics["if"],
                    "jcr_tier": metrics["tier"],
                    "belief_weight": metrics["weight"],
                    "is_noise_candidate": False,
                    "paragraphs": [{"section": "Abstract", "text": abstract_text}]
                }

                # Save raw abstract
                with open(raw_json_filename, "w", encoding="utf-8") as f:
                    json.dump({"pmid": pmid, "abstract": abstract_text}, f, ensure_ascii=False, indent=2)

                # Save unified payload
                with open(payload_filename, "w", encoding="utf-8") as f:
                    json.dump(unified_payload, f, ensure_ascii=False, indent=2)

                success_pmid_records.append(virtual_key)
                fetch_success = True
                time.sleep(0.35)  # Polite delay to respect NCBI rate limits
                break

            except (ET.ParseError, URLError, HTTPException, TimeoutError, ConnectionError):
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))  # Exponential backoff
                else:
                    print(f"Exhausted retries for PMID{pmid}")

        if not fetch_success and os.path.exists(payload_filename):
            os.remove(payload_filename)

    # Load existing global manifest
    global_papers = {}
    if os.path.exists(GLOBAL_MANIFEST_PATH):
        try:
            with open(GLOBAL_MANIFEST_PATH, "r", encoding="utf-8") as f:
                global_papers = json.load(f).get("papers", {})
        except Exception:
            pass

    # Merge silver-track assets into global manifest
    for full_pmid in success_pmid_records:
        global_papers[full_pmid] = {
            "type": "abstract",
            "source": "pubmed",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    manifest_payload = {
        "metadata": {
            "last_query": SEARCH_QUERY,
            "total_registered_assets": len(global_papers),
            "update_time": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "papers": global_papers
    }

    with open(GLOBAL_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2, ensure_ascii=False)
    print(f"Global manifest updated with silver-track abstracts (total assets: {len(global_papers)}) -> {GLOBAL_MANIFEST_PATH}")


if __name__ == "__main__":
    fetch_pubmed_abstracts()