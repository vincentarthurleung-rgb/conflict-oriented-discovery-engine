import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from code_engine.validation.index_builders.chembl_builder import ChEMBLIndexBuilder
from code_engine.validation.index_builders.curated_omics_builder import CuratedOmicsIndexBuilder
from code_engine.validation.index_builders.depmap_builder import DepMapIndexBuilder
from code_engine.validation.index_builders.reactome_builder import ReactomeIndexBuilder


class ValidationIndexBuilderTests(unittest.TestCase):
    def test_fixture_builders_and_dry_run(self):
        root = Path(__file__).parent / "fixtures/validation_sources"
        cases = ((CuratedOmicsIndexBuilder(), "curated_omics_small.jsonl"), (ReactomeIndexBuilder(), "reactome_small.jsonl"), (ChEMBLIndexBuilder(), "chembl_small.tsv"), (DepMapIndexBuilder(), "depmap_small.jsonl"))
        with tempfile.TemporaryDirectory() as tmp:
            for sequence, (builder, source) in enumerate(cases):
                output = Path(tmp) / str(sequence)
                result = builder.build_from_source(root / source, output)
                self.assertEqual(result.status, "completed")
                self.assertTrue((output / "schema.json").is_file())
                self.assertTrue((output / "manifest.json").is_file())
                self.assertTrue((output / "records.jsonl").is_file())
            dry = ReactomeIndexBuilder().build_from_source(root / "reactome_small.jsonl", Path(tmp) / "dry", dry_run=True)
            self.assertEqual(dry.status, "dry_run")
            self.assertFalse((Path(tmp) / "dry/records.jsonl").exists())

    def test_large_source_requires_explicit_opt_in(self):
        source = Path(__file__).parent / "fixtures/validation_sources/reactome_small.jsonl"
        with tempfile.TemporaryDirectory() as tmp, patch("code_engine.validation.index_builders.base.DEFAULT_MAX_SOURCE_BYTES", 1):
            result = ReactomeIndexBuilder().build_from_source(source, Path(tmp))
            self.assertEqual(result.status, "blocked")


if __name__ == "__main__": unittest.main()
