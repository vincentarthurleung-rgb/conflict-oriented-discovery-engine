"""
C.O.D.E. Stage 0: Literature Fetching Kernel - PMC Open Access Full-Text XML Downloader
Complete Release 1.0:
1. Fixes the vulnerability where generic Exception swallows Ctrl+C signals; precisely intercepts network and parsing exceptions.
2. Introduces manifest incremental merging to prevent loss of existing state due to query adjustments.
3. Locks XML integrity validation and exponential backoff retry defense.
"""

import os
import time
import json
import xml.etree.ElementTree as ET
from Bio import Entrez
from tqdm import tqdm
from http.client import HTTPException
from urllib.error import URLError

# NCBI email configuration (required by Entrez)
Entrez.email = "your_email"
Entrez.api_key = "your_API"

# Official open-access search filter
SEARCH_QUERY = (
    "(Ketamine[Title/Abstract]) AND "
    "(antidepressant[Title/Abstract] OR depression[Title/Abstract]) AND "
    "(NMDA[Title/Abstract] OR synaptic[Title/Abstract] OR glutamate[Title/Abstract]) AND "
    "open access[filter]"
)

MAX_DOCS = 650
OUTPUT_DIR = "./data/raw/xml"
MANIFEST_PATH = "data/metadata/unsorted_manifest.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def check_xml_integrity(file_path):
    """Verify the integrity of an existing XML file by parsing its tree structure."""
    if not os.path.exists(file_path):
        return False
    try:
        ET.parse(file_path)
        return True
    except ET.ParseError:
        return False


def fetch_pmc_papers():
    print(" [C.O.D.E. Stage 0] Launching production-grade NCBI E-utilities search...")

    try:
        handle = Entrez.esearch(
            db="pmc",
            term=SEARCH_QUERY,
            retmax=MAX_DOCS,
            datetype="pdat",
            mindate="1900/01/01",
            maxdate="2015/12/31"
        )
        record = Entrez.read(handle)
        handle.close()
    except Exception as e:
        print(f" ESearch connection failed: {e}. Please check network topology.")
        return

    pmc_ids = record.get("IdList", [])
    print(f" Open-access full-text hits: {len(pmc_ids)} articles.")

    if not pmc_ids:
        print(" No compliant articles found.")
        return

    success_pmc_ids = []
    print(" Starting download pipeline with integrity checks and resumption support...")

    for pmc_id in tqdm(pmc_ids, desc="Downloading"):
        full_pmc_id = f"PMC{pmc_id}"
        filename = os.path.join(OUTPUT_DIR, f"{full_pmc_id}.xml")

        # Resume download and purge corrupted cached files
        if os.path.exists(filename):
            if check_xml_integrity(filename):
                success_pmc_ids.append(full_pmc_id)
                continue
            else:
                print(f"\n Detected corrupted cache {full_pmc_id}.xml, forcibly removing and retrying...")
                os.remove(filename)

        max_retries = 3
        download_success = False

        for attempt in range(max_retries):
            try:
                fetch_handle = Entrez.efetch(db="pmc", id=pmc_id, retmode="xml")
                xml_data = fetch_handle.read()
                fetch_handle.close()

                # In-memory integrity check before writing
                ET.fromstring(xml_data)

                with open(filename, "wb") as f:
                    f.write(xml_data)

                success_pmc_ids.append(full_pmc_id)
                download_success = True
                time.sleep(0.35)
                break
            except (ET.ParseError, URLError, HTTPException, TimeoutError, ConnectionError) as e:
                # Patch 1: Precisely catch expected exceptions, never swallow KeyboardInterrupt or system signals
                if attempt < max_retries - 1:
                    sleep_time = 2 ** (attempt + 1)
                    time.sleep(sleep_time)
                else:
                    print(f"\n Exhausted all retries, aborting {full_pmc_id}: {e}")

        if not download_success and os.path.exists(filename):
            os.remove(filename)

    print(" Download phase for this search completed.")

    # Patch 2: Manifest state machine with merge-deduplication to prevent existing data desync after query changes
    old_papers = []
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                old_manifest = json.load(f)
                old_papers = old_manifest.get("papers", [])
        except Exception:
            pass  # Silently ignore if manifest is corrupted

    # Merge and preserve order using dict.fromkeys
    all_papers = list(dict.fromkeys(old_papers + success_pmc_ids))

    manifest_payload = {
        "metadata": {
            "query": SEARCH_QUERY,
            "total_fetched": len(all_papers),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "papers": all_papers
    }

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2, ensure_ascii=False)
    print(f" Manifest incrementally committed (total {len(all_papers)} papers) ➡️ {MANIFEST_PATH}")


if __name__ == "__main__":
    fetch_pmc_papers()