# Raw Literature Cache

Raw PMC XML and PubMed abstract files are download cache and are not committed
by default. The corpus registry is retained at
`data/metadata/global_manifest.json`.

Regenerate acquisition data with the reviewed Stage0 wrappers:

```bash
python scripts/stage0_fetch_pmc.py
python scripts/stage0_5_fetch_abstracts.py
```

These commands access NCBI, rerun their configured searches, and update the
manifest. Review search criteria and network/API requirements before execution.

