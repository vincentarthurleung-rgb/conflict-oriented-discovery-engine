import gzip, json
from pathlib import Path
import numpy as np

def manifest(root:Path)->Path:
 p=root/"manifest.json"; p.write_text(json.dumps({"dataset_id":"TEST","raw_dir":"x","unpacked_dir":"x","index_dir":"x","files":[
  {"role":"level5_matrix","filename":"matrix.gctx.gz","required":True,"unpack":True,"unpacked_filename":"matrix.gctx"},
  {"role":"gene_info","filename":"gene.txt.gz","required":True,"unpack":False},
  {"role":"sig_info","filename":"sig.txt.gz","required":True,"unpack":False},
  {"role":"pert_info","filename":"pert.txt.gz","required":True,"unpack":False},
  {"role":"cell_info","filename":"cell.txt.gz","required":True,"unpack":False}]})); return p

def tiny_dataset(root:Path):
 m=manifest(root); raw=root/"raw/TEST"; unpacked=root/"working/unpacked/TEST"; raw.mkdir(parents=True); unpacked.mkdir(parents=True)
 with gzip.open(raw/"sig.txt.gz","wt") as f: f.write("sig_id\tpert_iname\tcell_id\tpert_dose\tpert_time\nS1\tmetformin\tMCF7\t10 uM\t24 h\nS2\tother\tA375\t1 uM\t6 h\n")
 with gzip.open(raw/"gene.txt.gz","wt") as f: f.write("pr_gene_id\tpr_gene_symbol\tpr_is_lm\n1\tPRKAA1\t1\n2\tMTOR\t1\n3\tOTHER\t0\n")
 for name in ("pert.txt.gz","cell.txt.gz"):
  with gzip.open(raw/name,"wt") as f: f.write("id\nX\n")
 with (unpacked/"matrix.gctx").open("wb") as f: np.savez(f,row_ids=np.array(["1","2","3"]),col_ids=np.array(["S1","S2"]),matrix=np.array([[2,-1],[-2,1],[5,5]],dtype=np.float32))
 with gzip.open(raw/"matrix.gctx.gz","wb") as f: f.write((unpacked/"matrix.gctx").read_bytes())
 return m
