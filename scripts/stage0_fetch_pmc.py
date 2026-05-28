"""
C.O.D.E. Stage 0: Literature Fetching Kernel - PMC Open Access Full-Text XML Downloader
Complete Release 1.4 (Full-path synchronization version)

This module retrieves PMC open-access articles matching a predefined search query,
performs integrity validation on downloaded XML files, and maintains a global manifest
of successfully fetched papers.
"""

import os
import time
import json
import xml.etree.ElementTree as ET
from Bio import Entrez
from tqdm import tqdm
from http.client import HTTPException
from urllib.error import URLError

# NCBI email address required for E-utilities access
Entrez.email = "vincentarthurleung@gmial.com"

# Search query incorporating full-mechanism pathway operators for comprehensive coverage
SEARCH_QUERY = (
    "(Ketamine[Title/Abstract]) AND "
    "(antidepressant[Title/Abstract] OR depression[Title/Abstract] OR rapid-acting[Title/Abstract] OR fast-acting[Title/Abstract]) AND "
    "(NMDA[Title/Abstract] OR synaptic[Title/Abstract] OR glutamate[Title/Abstract] OR AMPA[Title/Abstract] OR mTOR[Title/Abstract]) AND "
    "open access[filter]"
)

MAX_DOCS = 650
OUTPUT_DIR = "./data/raw/xml"
GLOBAL_MANIFEST_PATH = "data/metadata/global_manifest.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def check_xml_integrity(file_path):
    """
    Verify that an XML file exists and can be parsed without syntax errors.

    Args:
        file_path (str): Path to the XML file.

    Returns:
        bool: True if the file exists and is a valid XML document, False otherwise.
    """
    if not os.path.exists(file_path):
        return False
    try:
        ET.parse(file_path)
        return True
    except ET.ParseError:
        return False


def fetch_pmc_papers():
    """
    Execute the full PMC paper retrieval pipeline.

    Steps:
    1. Query NCBI ESearch for PMC IDs matching the search criteria.
    2. For each ID, attempt to download the XML full text with retry logic.
    3. Validate XML integrity before saving.
    4. Update the global manifest with successfully downloaded papers.
    """
    print(" [C.O.D.E. Stage 0] Launching production-grade NCBI E-utilities search...")

    try:
        handle = Entrez.esearch(
            db="pmc", term=SEARCH_QUERY, retmax=MAX_DOCS,
            datetype="pdat", mindate="1900/01/01", maxdate="2015/12/31"
        )
        record = Entrez.read(handle)
        handle.close()
    except Exception as e:
        print(f" ESearch connection failed: {e}.")
        return

    pmc_ids = record.get("IdList", [])
    print(f" Open-access full-text hits: {len(pmc_ids)} articles.")

    if not pmc_ids:
        print(" No compliant articles found.")
        return

    success_pmc_ids = []
    print("⚡ Starting download pipeline with integrity checks and resumption support...")

    for pmc_id in tqdm(pmc_ids, desc="Downloading"):
        full_pmc_id = f"PMC{pmc_id}"
        filename = os.path.join(OUTPUT_DIR, f"{full_pmc_id}.xml")

        # Resume download by skipping valid existing files and removing corrupted ones
        if os.path.exists(filename):
            if check_xml_integrity(filename):
                success_pmc_ids.append(full_pmc_id)
                continue
            else:
                print(f"\n Detected corrupted cache {full_pmc_id}.xml, removing...")
                os.remove(filename)

        max_retries = 3
        download_success = False

        for attempt in range(max_retries):
            try:
                fetch_handle = Entrez.efetch(db="pmc", id=pmc_id, retmode="xml")
                xml_data = fetch_handle.read()
                fetch_handle.close()

                # Pre-save integrity check
                ET.fromstring(xml_data)

                with open(filename, "wb") as f:
                    f.write(xml_data)

                success_pmc_ids.append(full_pmc_id)
                download_success = True
                time.sleep(0.35)  # Polite delay to respect NCBI rate limits
                break
            except (ET.ParseError, URLError, HTTPException, TimeoutError, ConnectionError) as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))  # Exponential backoff
                else:
                    print(f"\n Exhausted all retries, aborting {full_pmc_id}: {e}")

        if not download_success and os.path.exists(filename):
            os.remove(filename)

    print(" Download phase completed.")

    # Load existing global manifest if present
    global_papers = {}
    if os.path.exists(GLOBAL_MANIFEST_PATH):
        try:
            with open(GLOBAL_MANIFEST_PATH, "r", encoding="utf-8") as f:
                global_papers = json.load(f).get("papers", {})
        except Exception:
            # Ignore corrupted manifest; will be overwritten
            pass

    # Merge newly downloaded papers into the global registry
    for pmc_id in success_pmc_ids:
        global_papers[pmc_id] = {
            "type": "fulltext",
            "source": "pmc",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    manifest_payload = {
        "metadata": {
            "query": SEARCH_QUERY,
            "total_registered_assets": len(global_papers),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        },
        "papers": global_papers
    }

    os.makedirs(os.path.dirname(GLOBAL_MANIFEST_PATH), exist_ok=True)
    with open(GLOBAL_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest_payload, f, indent=2, ensure_ascii=False)
    print(f" Manifest updated (total {len(global_papers)} assets) ➡️ {GLOBAL_MANIFEST_PATH}")


if __name__ == "__main__":
    fetch_pmc_papers()