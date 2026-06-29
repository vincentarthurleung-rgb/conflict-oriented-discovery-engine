import inspect
import unittest
import code_engine.corpus.identity as identity
import code_engine.corpus.paper_registry as registry


class CorpusOfflineTests(unittest.TestCase):
    def test_corpus_has_no_remote_clients(self):
        source = inspect.getsource(identity) + inspect.getsource(registry)
        for forbidden in ("requests.", "httpx.", "CrossRef", "NCBI", "DeepSeek"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__": unittest.main()
