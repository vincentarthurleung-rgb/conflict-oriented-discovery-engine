import unittest
from code_engine.external_data.lincs_l1000 import _detect_gctx_axes

class AxisTests(unittest.TestCase):
 def test_signature_first_orientation(self): self.assertEqual(_detect_gctx_axes((3,5),5,3),(0,1))
 def test_gene_first_orientation(self): self.assertEqual(_detect_gctx_axes((5,3),5,3),(1,0))
if __name__=="__main__": unittest.main()
