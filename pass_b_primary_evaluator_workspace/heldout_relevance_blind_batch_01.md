# Held-out PASS B — relevance review

Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.
All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.
Do not calculate partial or running metrics.

Allowed relevance_state: DIRECTLY_RELEVANT, PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED, RELATED_BUT_WRONG_PROPOSITION, WRONG_ENDPOINT, WRONG_ENTITY, WRONG_EVIDENCE_MODE, WRONG_THERAPY, TOPIC_ONLY, INSUFFICIENT_SOURCE_EVIDENCE

### Packet heldout_rrpv1_0001

Case: heldout_v1_001
Ambiguity: LOW

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "phospho-STAT3 increase",
    "STAT3 phosphorylation",
    "experimentally supported STAT3 activation",
    "nuclear/activity evidence explicitly used as STAT3 activation"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_001",
  "context_qualifiers": [
    "hepatocytes or hepatic cells"
  ],
  "frozen": true,
  "measurement_property_endpoint": "phosphorylation / activation",
  "measurement_target": "STAT3",
  "object": "STAT3",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "IL-6 exposure activates STAT3 signaling in hepatocyte/hepatic-cell models.",
  "relation_family": "activates",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "generic IL-6/STAT3 co-expression is not activation"
  ],
  "scientific_proposition_target_id": "heldout_v1_001:scientific_proposition:v1",
  "subject": "IL-6",
  "therapy": null
}
```

Publication:
```json
{
  "title": "SPOP downregulation promotes bladder cancer progression based on cancer cell-macrophage crosstalk via STAT3/CCL2/IL-6 axis and is regulated by VEZF1.",
  "pmid": "39479456",
  "pmcid": "PMC11519788",
  "doi": "10.7150/thno.101575"
}
```

Abstract:
Background: Cancer cells are intimately intertwined with tumor microenvironment (TME), fostering a symbiotic relationship propelling cancer progression. However, the interaction between cancer cells and tumor-associated macrophages (TAMs) in urothelial bladder cancer (UBC) remains poorly understood. Methods: UBC cell lines (5637, T24 and SW780), along with a monocytic cell line (U937) capable of differentiating into macrophage, were used in a co-culture system for cell proliferation and stemness by MTT, sphere formation assays. VEZF1/SPOP/STAT3/CCL2/ IL-6 axis was determined by luciferase reporter, ChIP, RNA-seq, co-IP, in vitro ubiquitination, RT-qPCR array and ELISA analyses. Results: We observed the frequent downregulation of SPOP, an E3 ubiquitin ligase, was positively associated with tumor progression and TAM infiltration in UBC patients and T24 xenografts. Cancer cell-TAM crosstalk promoting tumor aggressiveness was demonstrated dependent on SPOP deficiency: 1) In UBC cells, STAT3 was identified as a novel substrate of SPOP, and SPOP deficiency increased STAT3 protein stability, elevated chemokine CCL2 secretion, which induced chemotaxis and M2 polarization of macrophage; 2) In co-cultured macrophages, IL-6 secretion enhanced UBC cell proliferation and stemness. Additionally, transcription factor VEZF1 could directly activate SPOP transcription, and its overexpression suppressed the above effects in UBC cells. Conclusions: A pivotal role of SPOP in maintaining UBC stemness and remodeling immunosuppressive TME was revealed. Both the intrinsic signaling (dysregulated VEZF1/SPOP/STAT3 axis) and the extrinsic cues from TME (CCL2-IL-6 axis based on macrophages) promoted UBC progression. Targeting this crosstalk may offer a promising therapeutic strategy for UBC patients with SPOP deficiency.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11519788.xml
SHA-256: d31f659c1d96f6d6a5a857db81035a0b39667c94afa5f5d0eb209f2f942702f7

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 2,
    "text": "Tumor environment is regarded as a key determinant of tumor progression, especially for the plasticity and heterogeneity of cancer stem-like cells (CSCs). Within the tumor stroma, macrophages can constitute up to 50% of the cell population in certain solid tumors 3. As such, tumor-associated macrophages (TAMs) are pivotal in mediating tumor-stroma interactions, thereby promoting cancer growth, immune evasion, and recurrence 4-6. On the other hand, CSC (a cancer cell subpopulation within the tumor) has the capability to repopulate the entire tumor bulk 7. While several signaling pathways, including those driven by STAT3, Hedgehog/Gli1, and Wnt/β-catenin, are known to be active in bladder CSCs, the sustenance of their stem-like properties is intricately regulated by a combination of intrinsic signaling cascades and extrinsic cues from tumor microenvironment (TME) and the broader tumor macroenvironment (TMaE) 8-12. Hence, targeting the complex crosstalk within TME, such as the one between CSCs and macrophages presents a promising therapeutic strategy that could simultaneously impact cancer stemness and enhance the efficacy of cancer treatments."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 4,
    "text": "In this study, we identified SPOP downregulation, which was associated with TAM infiltration in human UBC samples, promoted UBC cell proliferation and stemness, induced by macrophage. Furthermore, STAT3 served as a novel substrate for SPOP protein in UBC cells, with SPOP downregulation resulting in the elevated STAT3 and CCL2 levels. The secretion of CCL2 by UBC cells and IL-6 by macrophages within the TME acted in concert to augment tumor stemness and promote UBC progression. Finally, we demonstrated that the deficiency of transcription factor VEZF1 was a key factor driving the downregulation of SPOP in UBC patients."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 8,
    "text": "Modified RIPA buffer (25 mM Tris.HCl pH 7.6, 150 mM NaCl, 1% NP-40, 0.1% SDS) and NP-40 lysis buffer (P0013F; Beyotime, China), supplemented with protease and phosphatase inhibitors, were used for cell lysis in Western blotting and co-IP assays, respectively. For co-IP assay, cells were pretreated with MG132 (10 μM, S2619; Selleck, USA) for 6 h before harvest. After centrifugation, the supernatant was incubated with the indicated antibodies (Table S3) at 4℃ overnight, followed by the addition of Protein A/G PLUS-Agarose (sc-2003; Santa Cruz Biotechnology, USA) at 4℃ for 2 h. The agarose beads were washed five times with cell lysis buffer, and the precipitated proteins were subjected to Western blotting analysis. For in vitro ubiquitination assay, 293T cells were co-transfected with Flag-SPOP, HA-STAT3 and Myc-Ub plasmids. 6 h prior to cell harvest, the proteasome inhibitor MG132 (10 μM, Selleck) was added to the medium. HA antibody was used for co-IP and Myc antibody (Table S3) was used to detect ubiquitination level."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 12,
    "text": "To generate the stable overexpression/knockdown cell lines, 293T cells were transfected with three plasmids (psPAX2, pMD2.G and lentiviral plasmid of interest) using Lipofectamine 2000 (#11668019; ThermoFisher Scientific) to produce lentiviral particles. Stattic (20 μM, HY-13818; MedChemExpress, USA), RS 504393 (2 μM, HY-15418; MedChemExpress), IL-6 (50 ng/ml, #200-6; PeproTech, USA) and neutralizing IL-6 antibody (100 ng/ml, MAB2061; R&D systems, USA) (Table S3) were used for cell function assays."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 13,
    "text": "pCMV10-3×FLAG-SPOP, pCDH-3×FLAG-SPOP-T2A (puromycin), pCS2-1×Myc-Ub, pCS2-4×HA-STAT3 and pCDH-3×FLAG-VEZF1 (puromycin) were constructed using PrimeSTAR MAX DNA Polymerase (R045A; Takara) and ClonExpress MultiS One Step Cloning Kit (C113-02; Vazyme). The pCS2-4×HA-STAT3-mutants were also constructed using the Mut Express II Fast Mutagenesis Kit V2 (C214-01; Vazyme). pLKO.1-shSPOP-1 (puromycin), pLKO.1-shSPOP-2 (puromycin), and pLKO.1-shSTAT3 (blasticidin) were constructed to knockdown the expression of SPOP or STAT3. The primer sequences for plasmid construction were listed in Table S2."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 22,
    "text": "CCL2 and IL-6 levels in culture medium from co-culture system were measured by Human CCL2/MCP-1 ELISA kit (EK1872; MultiSciences (Lianke) Biotech, Hangzhou, China) and Human IL-6 ELISA kit (EH004-96; ExCell Bio, Shanghai, China), normalized to the medium volumes."
  }
]
```

Fields fulltext was expected to resolve:
["context"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0002

Case: heldout_v1_001
Ambiguity: LOW

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "phospho-STAT3 increase",
    "STAT3 phosphorylation",
    "experimentally supported STAT3 activation",
    "nuclear/activity evidence explicitly used as STAT3 activation"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_001",
  "context_qualifiers": [
    "hepatocytes or hepatic cells"
  ],
  "frozen": true,
  "measurement_property_endpoint": "phosphorylation / activation",
  "measurement_target": "STAT3",
  "object": "STAT3",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "IL-6 exposure activates STAT3 signaling in hepatocyte/hepatic-cell models.",
  "relation_family": "activates",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "generic IL-6/STAT3 co-expression is not activation"
  ],
  "scientific_proposition_target_id": "heldout_v1_001:scientific_proposition:v1",
  "subject": "IL-6",
  "therapy": null
}
```

Publication:
```json
{
  "title": "IL-6/STAT3 Axis Activates Glut5 to Regulate Fructose Metabolism and Tumorigenesis.",
  "pmid": "35813468",
  "pmcid": "PMC9254469",
  "doi": "10.7150/ijbs.68990"
}
```

Abstract:
Cancer cells frequently use fructose as an alternative energy and carbon source, to fuel glycolysis and support the synthesis of various biomacromolecules. Glut5 is the only fructose-specific transporter, which lacks the ability to transport other carbohydrates such as glucose and galactose. Interplay between inflammatory factors and cancer cells renders inflammatory tissue environment as a predisposing condition for cancer development. Nevertheless, how inflammatory factors coordinate with fructose metabolism to facilitate tumor growth remains largely elusive. Here we show that treatment with IL-6 activates fructose uptake and fructolysis in oral squamous cell carcinoma (OSCC) cells and prostate cancer cells. Mechanistic study shows that transcription factor STAT3 associates with Glut5 promoter region and enhances Glut5 transcription in response to IL-6 treatment. Knockdown of Glut5 abolished IL-6-induced fructose uptake and utilization of fructose, and compromises IL-6-elicited tumor cell proliferation. Further, positive correlation between Glut5 and IL-6 expression is observed in multiple cancers. Our findings demonstrate a regulatory cascade underlying the crosstalk between inflammation and fructose metabolism in cancer cells, and highlights Glut5 as a novel oncogenic factor.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9254469.xml
SHA-256: c55d3246915fdb7ec2045551c87948eef412ded6aea8658a989bcd6c81506592

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "interleukin-6",
      "STAT3"
    ],
    "paragraph_index": 3,
    "text": "The discovery of the interconnection between inflammation and cancer development could be traced back to 1863, when Rudolf Virchow observed that chronic inflammatory sites were frequently the origin of malignant tumors 4. So far, a large body of studies demonstrates that inflammation does play a huge role in cancer development, whereas it can also be used as a targeted strategy to cure cancer 5. Inflammatory conditions can activate or accelerate carcinogenic transformation, and malignant cells with genetic and epigenetic alterations, in turn, can generate an inflammatory microenvironment that further contributes to tumor progression 6. Interleukin 6 (IL-6)/Signal Transducer and Activator of Transcription 3 (STAT3) signaling axis has been considered as an essential intrinsic pathway of cancer inflammation 7. IL-6 stimulation leads to Janus Kinase 2 (JAK2)-dependent phosphorylation of cytoplasmic STAT3, which facilitates STAT3 dimerization and translocation to the nucleus to function as a transcriptional factor 8, 9. In cancer cells, abnormal IL-6 expression and constitutive hyperactivation of STAT3 are closely correlated with an enhanced cancer cell proliferation and drug resistance. Nevertheless, the crosstalk between IL-6/STAT3 axis and fructose metabolism is still relatively unknown."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 4,
    "text": "Here, we demonstrate that, in response to IL-6 treatment, STAT3 enhances the transcription of Glut5 by associating with its promoter region. IL-6/STAT3 axis-mediated Glut5 expression enhances fructose uptake and utilization, and promotes tumor cell growth."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 5,
    "text": "Antibodies recognizing Glut5 (ab279363), Ki67 (ab16667), and recombinant human IL-6 protein (ab9627) were obtained from Abcam. Antibodies recognizing STAT3 (#9139), and STAT3-pY705 (#9145) were obtained from Cell Signaling Technology. 14C6-fructose was purchased from Biotrend, Köln (#MC1459-50)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 6,
    "text": "Human IL-6, and STAT3 were amplified and inserted into pcDNA3.1 or SFB-pCDH vector. Mutant Glut5 promoter constructs were prepared as follows: STAT3-mut, 'TTCCAGGAA' into 'AAAAAGGAA'; SOX2-mut, 'AAACAAA' into 'GCGAGCG'; PPARγ-mut, 'TGTTCTTTCACC' into 'TGCGCCGCAGTC'."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 7,
    "text": "shRNAs were prepared using the following sequences: STAT3 shRNA, TAC CTA AGG CCA TGA ACT T (targeting non-coding region); Glut5 shRNA-1, TTG GCT CTA AAC AAA TGC C; Glut5 shRNA-2, TAT GTT GTT GAA CAG CAA G."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 18,
    "text": "To determine the impact of inflammation on fructose metabolism in cancer cells, prostate cancer DU145 cells and oral squamous cell carcinoma (OSCC) HSC-3 cells were cultured with DMEM medium containing 10 mM fructose. The cells were treated with active recombinant IL-6 protein for 24 h. We found that the level of intracellular fructose was markedly elevated after IL-6 treatment in either DU145 or HSC-3 cells (Figure 1B). Consistently, IL-6 treatment elevated the radiation signal in the whole cell lysates by more than 10 folds, after incubation with [14C]-fructose for 30 min (Figure 1C). Fructose could be converted into GA3P during fructolysis, and further used for the biosynthesis of protein, RNA, and phospholipids in membranes 2. As expected, a roughly 1.5-fold increase in GA3P level was also detected (Figure 1D), hinting that IL-6 treatment enhanced fructolysis. Further, a markedly stronger radiation signal was detected in total protein, total RNA, and cell membrane samples derived from IL-6-treated cells (Figure 1E-1G). These data suggest that IL-6 treatment strengthens both the uptake and utilization of fructose."
  }
]
```

Fields fulltext was expected to resolve:
["context"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0011

Case: heldout_v1_002
Ambiguity: LOW

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "mature extracellular IL-1β secretion",
    "mature IL-1β release"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_002",
  "context_qualifiers": [
    "macrophages"
  ],
  "frozen": true,
  "measurement_property_endpoint": "secretion / extracellular release",
  "measurement_target": "mature IL-1β",
  "object": "IL-1β secretion",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "Activation of the NLRP3 inflammasome increases mature IL-1β secretion from macrophages.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "pro-IL-1β transcription/expression alone does not satisfy the endpoint"
  ],
  "scientific_proposition_target_id": "heldout_v1_002:scientific_proposition:v1",
  "subject": "NLRP3 activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Macrophage NLRP3 activation and IL-1β release drive osimertinib-induced antitumor immunity.",
  "pmid": "41052880",
  "pmcid": "PMC12506461",
  "doi": "10.1136/jitc-2025-012182"
}
```

Abstract:
Despite the clinical efficacy of epidermal growth factor receptor tyrosine kinase inhibitors (EGFR-TKIs) in non-small cell lung cancer (NSCLC), patient outcomes vary even among those with identical EGFR mutations. This study investigates whether osimertinib, a third-generation EGFR-TKI, activates the nucleotide-binding oligomerization domain-like receptor protein-3 (NLRP3) inflammasome in macrophages to drive antitumor immunity and explores its mechanistic basis.
Using bone marrow-derived macrophages from wild-type and gene-deficient mice, human peripheral blood mononuclear cells, and a Lewis lung cancer murine model, we assessed osimertinib-induced NLRP3 inflammasome activation, interleukin (IL)-1β secretion, pyroptosis, and tumor microenvironment (TME) remodeling. Mechanistic studies evaluated lysosomal dysfunction, calcium overload, mitochondrial damage, and reactive oxygen species (ROS) production. Clinical correlations were analyzed in patients with NSCLC treated with EGFR-TKIs.
Osimertinib triggered NLRP3 inflammasome activation in macrophages via lysosomal dysfunction-induced calcium overload, leading to mitochondrial damage and ROS production, which acted as damage-associated molecular patterns to activate NLRP3. This process promoted IL-1β release, pyroptosis, and CD8+ T-cell activation while suppressing regulatory T cells in the TME. In murine models, osimertinib's antitumor effects were abrogated by NLRP3 inhibition (MCC950) and enhanced by recombinant IL-1β (rIL-1β) co-administration (p<0.01). Clinically, high NLRP3 and IL-1β expression in tumor-associated macrophages (TAMs) correlated with prolonged progression-free survival (p<0.01) and overall survival (p<0.01) in EGFR-TKI-treated patients with NSCLC.
Osimertinib exerts off-target immunomodulatory effects by activating the tumor-extrinsic NLRP3 inflammasome, linking mitochondrial-lysosomal crosstalk to antitumor immunity. NLRP3 and IL-1β in TAMs emerge as predictive biomarkers for EGFR-TKI efficacy, while rIL-1β combination therapy represents a novel strategy to enhance clinical outcomes.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12506461.xml
SHA-256: 53d3a5b80d7470f3d9d5f00c8f1fef484ce797e8719d41dcf21b2c8c4ecadcb3

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 1,
    "text": "Epidermal growth factor receptor tyrosine kinase inhibitors (EGFR-TKIs), including third-generation agents like osimertinib, are standard therapies for patients with non-small cell lung cancer (NSCLC) with activating EGFR mutations. However, clinical outcomes remain heterogeneous even among patients with identical EGFR mutations, suggesting the involvement of non-canonical mechanisms. Prior studies established that certain TKIs (eg, gefitinib, imatinib) activate the nucleotide-binding oligomerization domain-like receptor protein-3(NLRP3) inflammasome in macrophages, potentially contributing to adverse inflammatory effects. Beyond TKIs, other antitumor therapies (eg, chemotherapy, radiotherapy) are known to activate NLRP3 in immune cells, triggering interleukin (IL)-1β-driven antitumor immunity. NLRP3 activation in myeloid cells, such as dendritic cells or macrophages, enhances CD8+ T-cell responses, while in immunosuppressive myeloid-derived suppressor cells, it may paradoxically dampen immunity."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "Despite these insights, the role of NLRP3 in TKI efficacy and its mechanistic basis in reshaping the tumor microenvironment (TME) remained unexplored. This study elucidates a novel off-target immunomodulatory mechanism of osimertinib, linking lysosomal-mitochondrial crosstalk to NLRP3 inflammasome activation and antitumor immunity. Osimertinib induces lysosomal dysfunction in macrophages, triggering transient receptor potential mucolipin 1-mediated calcium efflux, mitochondrial damage, and reactive oxygen species (ROS) production. These ROS act as damage-associated molecular patterns to activate the NLRP3 inflammasome, driving caspase-1-dependent IL-1β secretion, pyroptosis, and CD8+ T-cell activation while suppressing regulatory T cells in the TME. High NLRP3 and IL-1β expression in tumor-associated macrophages (TAMs) correlates with prolonged progression-free survival and overall survival in patients with EGFR-mutant NSCLC treated with osimertinib, establishing these markers as predictive biomarkers."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "Clinical practice: NLRP3/IL-1β expression in TAMs could serve as biomarkers to stratify patients likely to benefit from osimertinib. Multiplex immunofluorescence assays for these markers may enhance prognostic precision in NSCLC."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "Therapeutic strategies: combining osimertinib with recombinant IL-1β or small-molecule NLRP3 agonists (eg, CY-09) could overcome resistance in patients with low inflammasome activity. Conversely, NLRP3 inhibitors (eg, MCC950) might mitigate inflammatory toxicities without compromising EGFR-targeted efficacy."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3"
    ],
    "paragraph_index": 5,
    "text": "Drug development: this study underscores the need to evaluate immunomodulatory “off-target” effects during TKI development. Dual-target agents that simultaneously inhibit EGFR and activate NLRP3 could be engineered for enhanced efficacy."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "Guideline integration: clinical trials testing IL-1β supplementation or NLRP3 modulators alongside EGFR-TKIs may inform future treatment protocols, particularly for patients with innate or acquired resistance to osimertinib."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0012

Case: heldout_v1_002
Ambiguity: LOW

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "mature extracellular IL-1β secretion",
    "mature IL-1β release"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_002",
  "context_qualifiers": [
    "macrophages"
  ],
  "frozen": true,
  "measurement_property_endpoint": "secretion / extracellular release",
  "measurement_target": "mature IL-1β",
  "object": "IL-1β secretion",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "Activation of the NLRP3 inflammasome increases mature IL-1β secretion from macrophages.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "pro-IL-1β transcription/expression alone does not satisfy the endpoint"
  ],
  "scientific_proposition_target_id": "heldout_v1_002:scientific_proposition:v1",
  "subject": "NLRP3 activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "NEK7 phosphorylation amplifies NLRP3 inflammasome activation downstream of potassium efflux and gasdermin D.",
  "pmid": "39752537",
  "pmcid": "PMC12020992",
  "doi": "10.1126/sciimmunol.adl2993"
}
```

Abstract:
The NLRP3 inflammasome plays a critical role in innate immunity and inflammatory diseases. NIMA-related kinase 7 (NEK7) is essential for inflammasome activation, and its interaction with NLRP3 is enhanced by K+ efflux. However, the mechanism by which K+ efflux promotes this interaction remains unknown. Here, we show that NEK7 is rapidly phosphorylated at threonine-190/191 by JNK1 downstream of K+ efflux and gasdermin D (GSDMD) after NLRP3 activation. NEK7 phosphorylation enhances the binding between NEK7 and NLRP3, which further promotes inflammasome assembly and activation. Mutant mice and macrophages in which Thr190 and Thr191 of Nek7 were replaced by valine exhibited impaired NEK7 phosphorylation, NLRP3 inflammasome activation, and IL-1β secretion. Thus, NEK7 phosphorylation is an important event that acts downstream of K+ efflux and GSDMD to further enhance NLRP3 inflammasome activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12020992.xml
SHA-256: 2a14f831aecbbcc6346410956c5f3653f5ffaa15fbb18c97fcce2bd5a9afd0fc

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 1,
    "text": "Inflammasomes are multimeric protein complexes that are activated in the presence of microbial signals or sterile cellular injury to induce host immune responses via the activation of caspase-1 (CASP1) (1). Inflammasome assembly and activation are initiated by host pattern recognition receptors (PRRs), which sense molecular motifs conserved in microbes, endogenously derived damage-associated molecules, and cellular activities induced by pathogens (1). The best-characterized inflammasome is induced through NLRP3, a PRR that belongs to the NLR (nucleotide-binding oligomerization domain and leucine-rich repeat-containing) protein family (1). Inherited activating mutations in NLRP3 cause several autoinflammatory syndromes, whereas chronic activation of the NLRP3 inflammasome can contribute to the pathogenesis of acquired inflammatory disorders, including atherosclerosis, diabetes, gouty arthritis, and Alzheimer’s disease (2)."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "A two-signal model has been proposed for NLRP3 inflammasome activation in mouse macrophages (1). In this model, a priming signal induced by ligands for Toll-like receptors or the cytokines IL-1β or TNF-α leads to the upregulation of NLRP3 and pro-IL-1β, as well as the post-translational modification of NLRP3, which facilitates inflammasome activation (3). Following priming, the canonical NLRP3 inflammasome can be activated by an array of stimuli, including adenosine-5′-triphosphate (ATP), nigericin, and crystalline substances (4). In response to these stimuli, NLRP3 recruits the adaptor ASC, which activates caspase-1 enabling the processing and release of active IL-1β and IL-18 as well as the processing of gasdermin D (GSDMD). The cleaved N-terminus of GSDMD inserts into the plasma membrane, forming pores that promote pyroptosis, a lytic form of cell death (1). In addition to being cleaved by caspase-1, GSDMD can also be processed by the noncanonical inflammasome following caspase-11 activation (5). The resulting GSDMD pores mediate potassium (K+) efflux, which precedes and activates the NLRP3 inflammasome in the noncanonical pathway (6–8)."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 3,
    "text": "K+ efflux is induced by most NLRP3-activating stimuli and is the best-established signal for NLRP3 activation (9). We and others have demonstrated that NEK7 is an indispensable component of the mouse NLRP3 inflammasome that interacts with NLRP3 to promote inflammasome activation (10–12). The interaction between NEK7 and NLRP3 is dependent on K+ efflux (10). However, the mechanism by which K+ efflux regulates the interaction between NEK7 and NLRP3 to promote inflammasome activation is unknown. In this study, we show that NEK7 is phosphorylated during NLRP3 activation, which is induced via K+ efflux, GSDMD pore formation, and c-Jun N-terminal kinase 1 (JNK1). Thus, NEK phosphorylation enhances the interaction between NEK7 and NLRP3 and further promotes the activation of the NLRP3 inflammasome."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 4,
    "text": "ATP stimulation induced a slower migrating NEK7 band on gels, which correlated with caspase-1 activation as denoted by the presence of the processed p20 subunit of caspase-1 in mouse bone marrow-derived macrophages (BMDMs) (Fig. 1A). Treatment of cell extracts from ATP-stimulated macrophages with lambda phosphatase caused the disappearance of the slower migrating NEK7 band (Fig. 1B), suggesting that the slower migrating band represents a phosphorylated form of NEK7. To verify that NEK7 was phosphorylated in response to extracellular ATP, we ran the same protein extracts on Phos-Tag gels, which confirmed that NEK7 was phosphorylated after LPS + ATP stimulation (Fig. 1B). To determine whether NEK7 is phosphorylated in response to activating stimuli other than ATP, we stimulated BMDMs with LPS alone or stimulated the LPS-primed macrophages with ATP, nigericin, and silica nanoparticles (nano-SiO2) to induce NLRP3 activation. Immunoblotting of the Phos-tag gel with anti-NEK7 showed that in addition to ATP, stimulation with nigericin and nano-SiO2 also induced NEK7 phosphorylation (Fig. 1C). NEK7 phosphorylation was detected within 15 min after ATP stimulation, which correlated with the kinetics of caspase-1 activation (Fig. 1D). Furthermore, phosphorylated NEK7 coimmunoprecipitated with a triple-tagged NLRP3 (Fig. 1D), suggesting the phosphorylated NEK7 is an integral component of the NLRP3 inflammasome. Thus, NEK7 is phosphorylated in response to several stimuli that activate the NLRP3 inflammasome."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "We next determined whether NEK7 phosphorylation was dependent on NLRP3 by assessing NEK7 phosphorylation in wild-type and Nlrp3−/− macrophages. We observed that there was no induction of NEK7 phosphorylation and caspase-1 p20 processing in LPS-primed Nlrp3−/− BMDMs stimulated with ATP when compared to wild-type macrophages (Fig. 2A), indicating that NLRP3 was required for the induction of NEK7 phosphorylation. Treatment with MCC950, a small molecule NLRP3 inhibitor, abolished NEK7 phosphorylation (fig. S1, A and B), suggesting that NLRP3 activation is required for NEK7 phosphorylation. We next investigated whether other NLRP3 inflammasome component was required for NEK7 phosphorylation by examining NEK7 phosphorylation in wild-type and Casp1−/− macrophages. Similar to what was observed in Nlrp3−/− macrophages, NEK7 phosphorylation was diminished in LPS-primed Casp1−/− macrophages stimulated with ATP (Fig. 2B). Considering that NEK7 interacts with the inflammasome during activation (10, 12), we asked whether NEK7 phosphorylation is induced via interactions with components of the NLRP3 inflammasome or signaling events downstream of caspase-1 activation. To address this question, we used the caspase-1 inhibitor VX-765 to block caspase-1 activation processing downstream of NLRP3. Treatment of macrophages with VX-765 inhibited caspase-1 p20 processing (Fig. 2C) and IL-1β production in a dose-dependent manner, whereas TNF-α secretion was not affected (Fig. 2D). Inhibition of caspase-1 processing correlated with the loss of NEK7 phosphorylation (Fig. 2C). These results indicated t"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 6,
    "text": "K+ efflux is induced by most NLRP3-activating stimuli and is required for NLRP3 activation, except for imiquimod, a single-stranded RNA analogue (9, 13). Stimulation of LPS-primed macrophages with imiquimod induced caspase-1 activation but did not trigger NEK7 phosphorylation (fig. S2). We then stimulated LPS-primed mouse macrophages with ATP, nigericin, or nano-SiO2 to induce NLRP3 activation in the presence of medium containing 5 mM or 50 mM KCl, a dose that effectively blocks K+ efflux (9). Phosphorylation of NEK7 was observed when the cells were cultured in 5 mM KCl medium, which correlated with caspase-1 activation (Fig. 3A). By contrast, NEK7 phosphorylation and caspase-1 activation were abrogated when BMDMs were cultured in 50 mM KCl–containing medium (Fig. 3A). NEK7 phosphorylation was also induced by cytosolic LPS, which triggers caspase-11 activation via the noncanonical NLRP3 inflammasome pathway (Fig. 3B). NEK7 phosphorylation induced by caspase-11 activation was also dependent on K+ efflux as it was abrogated by incubation of macrophages in medium containing 50 mM KCl (Fig. 3B). Thus, NEK7 phosphorylation is induced downstream of K+ efflux."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0021

Case: heldout_v1_003
Ambiguity: MEDIUM

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "fibroblast COL1A1 abundance",
    "fibroblast type-I collagen abundance"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_003",
  "context_qualifiers": [
    "fibroblasts"
  ],
  "frozen": true,
  "measurement_property_endpoint": "gene or protein abundance",
  "measurement_target": "COL1A1 / collagen I",
  "object": "collagen I expression",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "TGF-β signaling increases COL1A1 / type-I collagen expression in fibroblast models.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "fibrotic tissue association without a fibroblast-level regulatory relation is insufficient"
  ],
  "scientific_proposition_target_id": "heldout_v1_003:scientific_proposition:v1",
  "subject": "TGF-β signaling",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Arctigenin Reduces Myofibroblast Activities in Oral Submucous Fibrosis by LINC00974 Inhibition.",
  "pmid": "30884781",
  "pmcid": "PMC6470833",
  "doi": "10.3390/ijms20061328"
}
```

Abstract:
Oral submucous fibrosis (OSF) is an oral precancerous condition associated with the habit of areca nut chewing and the TGF-β pathway. Currently, there is no curative treatment to completely heal OSF, and it is imperative to alleviate patients' symptoms and prevent it from undergoing malignant transformation. Arctigenin, a lignan extracted from Arctium lappa, has been reported to have a variety of pharmacological activities, including anti-fibrosis. In the present study, we examined the effect of arctigenin on the cell proliferation of buccal mucosal fibroblasts (BMFs) and fibrotic BMFs (fBMFs), followed by assessment of myofibroblast activities. We found that arctigenin was able to abolish the arecoline-induced collagen gel contractility, migration, invasion, and wound healing capacities of BMFs and downregulate the myofibroblast characteristics of fBMFs in a dose-dependent manner. Most importantly, the production of TGF-β in fBMFs was reduced after exposure to arctigenin, along with the suppression of p-Smad2, α-smooth muscle actin, and type I collagen A1. In addition, arctigenin was shown to diminish the expression of LINC00974, which has been proven to activate TGF-β/Smad signaling for oral fibrogenesis. Taken together, we demonstrated that arctigenin may act as a suitable adjunct therapy for OSF.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6470833.xml
SHA-256: fc6e139c0e2390e2ea5fc650b2c7efd76c4c7eff3e9d8eb5508ce12b9adc5eea

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "collagen I"
    ],
    "paragraph_index": 1,
    "text": "Oral submucous fibrosis (OSF) is a premalignant disorder [1] characterized by chronic inflammation and progressive accumulation of collagen in the oral cavity. The common clinical symptoms include blanched mucosa and stiffness of the mouth, leading to limited food consumption, impaired speaking ability, and difficulty of maintaining oral hygiene. These symptoms cause significant social, economic, and quality-of-life burdens to patients. Moreover, the rate of mortality greatly increases once OSF progresses to neoplasia, because oral cancer is one of the most common cancers and has a fast metastasis rate [2]. Accordingly, it is crucial to explore potential therapeutic methods to attenuate OSF progression."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 2,
    "text": "Epidemiological evidence has suggested that areca nut chewing is the most significant risk factor for OSF [3]. The treatment of buccal mucosal fibroblasts (BMFs) with arecoline, an alkaloid extracted from the areca nut, has been found to increase collagen synthesis and the expression of extracellular matrix-associated genes, such as tissue inhibitor of metalloproteinase-1 [4], plasminogen activator inhibitor-1 [5], and connective tissue growth factor [6]. In addition, areca nut constituents have also been shown to activate the TGF-β/p-Smad2 pathway, leading to enhanced myofibroblast activation as demonstrated by higher α-smooth muscle (α-SMA), γ-SMA, and collagen gel contraction [7,8]. It is known that TGF-β drives fibroblast–myofibroblast transdifferentiation via the induction of a contractile phenotype and up-regulation of α-SMA. Those alterations are related to the increase in collagen gene expression and are regulated by Smad proteins [9]. Consequently, a therapeutic strategy that targets the TGF-β pathway in myofibroblast transdifferentiation may serve as a promising approach."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 3,
    "text": "Arctigenin is a lignan found in certain plants, such as Arctium lappa. Arctigenin has been reported to have numerous biological activities, including antioxidant [10], anti-inflammatory [11], and antitumor [12] properties. As for fibrosis, various studies have also demonstrated its anti-fibrotic effects. For instance, arctigenin inhibits platelet-derived growth factor-BB-activated hepatic stellate cell proliferation and arrests their cell cycle via PI3K/Akt/FOXO3a signaling [13]. In renal tubular epithelial cells, arctigenin suppresses TGF-β-induced expression of monocyte chemoattractant protein-1 (MCP-1) and the subsequent epithelial-to-mesenchymal transition (EMT) through the reactive oxygen species (ROS)-dependent ERK/NF-κB signaling pathway [14]. Moreover, arctigenin suppresses the EMT of renal tubules by reducing TGF-β1 and Smad2/3 phosphorylation, as well as up-regulating Smad7 expression [15]. These studies indicate the potential of using arctigenin as an anti-fibrosis agent via various pathways, including TGF-β. Nevertheless, its effect on the premalignant disorder OSF has yet to be evaluated."
  },
  {
    "matched_frozen_surfaces": [
      "type I collagen"
    ],
    "paragraph_index": 5,
    "text": "Arecoline (20 μg/mL) has been used to induce myofibroblast activation in human primary BMFs with increased expression of α-SMA and other fibrogenic genes, such as vimentin and type I collagen [16]. In order to test whether arctigenin was able to impede the effect of arecoline on BMFs, we examined a variety of phenotypic analyses of myofibroblast activities. Our results suggested that the arecoline-increased collagen gel contractility (Figure 2A) and migration ability (Figure 2B) was suppressed by arctigenin in a concentration-dependent manner. Moreover, the arecoline-induced enhancement of cell motility was avoided in the presence of arctigenin as assessed by invasion (Figure 3A) and wound healing (Figure 3B) assays. These findings indicate that arctigenin may possess the potential to obviate the excessive activation of myofibroblasts caused by areca nut."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 6,
    "text": "It has long been known that TGF-β initiates the inflammatory response by recruiting fibroblasts to the site of injury during the early phases of tissue recovery [17], and the invasive fibroblast phenotype is essential for severe fibrogenesis [18]. Consequently, we sought to evaluate the anti-fibrotic effect of arctigenin in fBMFs. We found that the fBMFs displayed a significant reduction of cell contraction capability at 5–20 μM of arctigenin (Figure 4A), suggesting that arctigenin may be capable of relieving oral rigidity without causing damage to the normal BMFs. Moreover, we observed that cell migration was conspicuously downregulated in response to the increased concentration of arctigenin using a Transwell system (Figure 4B). Similarly, there was a marked reduction in the invasion (Figure 5A) and wound healing (Figure 5B) capacities as the concentration of arctigenin increased. Altogether, we demonstrated that arctigenin inhibits these upregulated myofibroblast activities."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "COL1A1",
      "type I collagen"
    ],
    "paragraph_index": 7,
    "text": "The TGF-β/p-Smad2 signaling pathway is implicated in oral fibrogenesis. As shown in Figure 6A, arctigenin significantly mitigates the secretion of TGF-β of two fBMFs strains in a dose-dependent fashion. In accordance with this finding, the protein expression level of phosphorylated Smad2 was downregulated, as well as myofibroblast marker α-SMA, extracellular cell matrix (ECM) molecules, and type I collagen A1, (Col1a1), following arctigenin administration (Figure 6B). Our recent work has demonstrated that long non-coding RNA LINC00974 activates TGF-β/Smad signaling to promote oral fibrogenesis [19]. We found that the TGF-β production and phosphorylated Smad2 expression were repressed in the LINC00974-inhibited myofibroblasts [19]. Arctigenin reduced the expression of Linc00974 in fBMFs (Figure 6C). In the current study, we showed that the expression of LINC00974 was dose-dependently suppressed by the administration of arctigenin using qRT-PCR analysis (Figure 6D). Collectively, our results suggest that arctigenin has anti-fibrotic effects on fBMFs via TGF-β/Smad signaling mediated by LINC00974."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0022

Case: heldout_v1_003
Ambiguity: MEDIUM

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "fibroblast COL1A1 abundance",
    "fibroblast type-I collagen abundance"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_003",
  "context_qualifiers": [
    "fibroblasts"
  ],
  "frozen": true,
  "measurement_property_endpoint": "gene or protein abundance",
  "measurement_target": "COL1A1 / collagen I",
  "object": "collagen I expression",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "TGF-β signaling increases COL1A1 / type-I collagen expression in fibroblast models.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "fibrotic tissue association without a fibroblast-level regulatory relation is insufficient"
  ],
  "scientific_proposition_target_id": "heldout_v1_003:scientific_proposition:v1",
  "subject": "TGF-β signaling",
  "therapy": null
}
```

Publication:
```json
{
  "title": "A strategic expression method of miR-29b and its anti-fibrotic effect based on RNA-sequencing analysis.",
  "pmid": "33332475",
  "pmcid": "PMC7746150",
  "doi": "10.1371/journal.pone.0244065"
}
```

Abstract:
Tissue fibrosis is a significant health issue associated with organ dysfunction and failure. Increased deposition of collagen and other extracellular matrix (ECM) proteins in the interstitial area is a major process in tissue fibrosis. The microRNA-29 (miR-29) family has been demonstrated as anti-fibrotic microRNAs. Our recent work showed that dysregulation of miR-29 contributes to the formation of cardiac fibrosis in animal models of uremic cardiomyopathy, whereas replenishing miR-29 attenuated cardiac fibrosis in these animals. However, excessive overexpression of miR-29 is a concern because microRNAs usually have multiple targets, which could result in unknown and unexpected side effect. In the current study, we constructed a novel Col1a1-miR-29b vector using collagen 1a1 (Col1a1) promoter, which can strategically express miR-29b-3p (miR-29b) in response to increased collagen synthesis and reach a dynamic balance between collagen and miR-29b. Our experimental results showed that in mouse embryonic fibroblasts (MEF cells) transfected with Col1a1-miR-29b vector, the miR-29b expression is about 1000 times less than that in cells transfected with CMV-miR-29b vector, which uses cytomegalovirus (CMV) as a promoter for miR-29b expression. Moreover, TGF-β treatment increased the miR-29b expression by about 20 times in cells transfected with Col1a1-miR-29b, suggesting a dynamic response to fibrotic stimulation. Western blot using cell lysates and culture media demonstrated that transfection of Col1a1-miR-29b vector significantly reduced TGF-β induced collagen synthesis and secretion, and the effect was as effective as the CMV-miR-29b vector. Using RNA-sequencing analysis, we found that 249 genes were significantly altered (180 upregulated and 69 downregulated, at least 2-fold change and adjusted p-value <0.05) after TGF-β treatment in MEF cells transfected with empty vector. The Kyoto Encyclopedia of Genes and Genomes (KEGG) pathway analysis using GAGE R-package showed that the top 5 upregulated pathways after TGF-β treatment were mostly fibrosis-related, including focal adhesion, ECM reaction, and TGF-β signaling pathways. As expected, transfection of Col1a1-miR-29b or CMV-miR-29b vector partially reversed the activation of these pathways. We also analyzed the expression pattern of the top 100 miR-29b targeting genes in these cells using the RNA-sequencing data. We identified that miR-29b targeted a broad spectrum of ECM genes, but the inhibition effect is mostly moderate. In summary, our work demonstrated that the Col1a1-miR-29b vector can be used as a dynamic regulator of collagen and other ECM protein expression in response to fibrotic stimulation, which could potentially reduce unnecessary side effect due to excessive miR-29b levels while remaining an effective potential therapeutic approach for fibrosis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7746150.xml
SHA-256: b470dc936e42ebfb6f23a5efa6e838c2eacf88dd74b0993a3e6387937c07179f

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 3,
    "text": "Our recent work [25–27] has demonstrated that Na/K-ATPase signaling downregulates miR-29b expression through Src/NFκB pathway and induces collagen synthesis and tissue fibrosis. We also showed that transfection of miR-29b mimics or restoring endogenous miR-29b by blocking Na/K-ATPase signaling using pNaKtide, a Src inhibiting peptide developed in our laboratory, inhibited collagen synthesis in primary cultured cardiac fibroblasts and attenuated cardiac fibrosis in animal models of uremic cardiomyopathy [25, 28]. However, due to its multi-target effect, an excessive amount of miR-29b could induce unexpected side effects such as aortic dilation and aneurysm [29]. In the current project, we constructed an expression vector that can strategically express miR-29b using a Col1a1 promoter to dynamically regulate collagen synthesis in response to fibrotic stimulation, which will result in the lower basal level of miR-29b, while remaining a potential therapeutic for fibrosis."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 5,
    "text": "To screen a Col1a1 promoter that is responsive to fibrotic stimulation, we cloned several Col1a1 promoter sequences into a pcDNA3 plasmid with luciferase (Col1a1-luc). Based on this luciferase assay result, we selected a rat Col1a1 promoter for the construction of the Col1a1-miR-29b vector. To test the in vivo delivery of the vector, we engineered a Col1a1-EGFP and a CMV-RFP into the pcDNA3 plasmid, in which the EGFP serves as a marker for activation of Col1a1 promoter, while the RFP serves as a marker for transfection efficiency."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 6,
    "text": "To construct the miR-29b overexpression vector (Col1a1-miR-29b), a pcDNA3 plasmid was used as a backbone for the construction of miR-29b expression vectors. First, an EGFP sequence and human miR-29b-1 sequence was engineered into the downstream of the Col1a1 promoter in the pcDNA3 plasmid. The miR-29b gene sequence was cloned from a pcDNA3-miR29b plasmid (Addgene, Plasmid No.: 21121). An mRFP1 sequence was inserted under the SV40 promoter in the same plasmid as a transfection marker. To construct the CMV-miR-29b expression vector, we replaced the Col1a1 promoter with a CMV promoter and all other structure of the plasmid was kept the same. This CMV promoted miR-29b expression vector (CMV-miR-29b) serves as a positive control in all experiments. An empty pcDNA3 vector was used as a negative control."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "COL1A1"
    ],
    "paragraph_index": 7,
    "text": "Mouse Embryonic Fibroblasts (MEF) were obtained from American Type Culture Collection and maintained in Dulbecco's modified Eagle's medium (DMEM) supplemented with 10% fetal bovine serum, 100 units/ml penicillin, and 100 μg/ml streptomycin in 5% CO2 humidified incubator. MEF cells grown on 12-well plates were transfected with 1 pmol DNA/ml media (about 3 μg/ml for CMV-miR29b and 5 μg/ml for Col1a1-miR29b based on the vector size) using Lipofectamine 3000 reagent from ThermoFisher Scientific (Cat. No.: L3000008) following the manufacturer's protocol. Empty pcDNA3 vector-transfected cells were used as non-treatment control. At 6 h post-transfection, MEF cells were treated with TGF-β (R&D systems, Cat. No.: 240-B) for an additional 24 h. Cells without TGF-β treatment were used as non-treatment control. Cell lysates were then collected for Western blot or RNA extraction at the end of the experiment. Culture media were also collected for the measurement of secreted collagen."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 8,
    "text": "The plasmid with Col1a1-EGFP and CMV-RFP was packed into lentiviruses by a commercial company (VectorBuilder Inc. at Chicago, IL). For MEF cells transfection, purified lentivirus (~109 TU/ml) was premixed with polybrene (final concentration of 8 μg/ml) and added to cultured MEF cells in a 6-well plate at 60 μl of the virus suspension per well. Cells were cultured for an additional 48h and the fluorescence of EGFP and RFP were examined under a fluorescent microscope. For in vivo delivery, experimental mice were anesthetized with 2% isoflurane, and about 100 μl of lentivirus (109 TU/ml) mixed with polybrene was instilled to the lung surface of C57BL/6 mice by the intra-trachea method. On the 7th day after the delivery, mice were euthanized by injection of ketamine/xylazine (500/50 mg/kg bodyweight), and the lung tissue was collected into the OTC-containing chamber for preparation of frozen tissue sections. The EGFP and RFP fluorescence were imaged using a Leica confocal microscope."
  },
  {
    "matched_frozen_surfaces": [
      "type I collagen"
    ],
    "paragraph_index": 9,
    "text": "Cell lysates collected in ice-cold Radioimmunoprecipitation (RIPA) buffer (Santa Cruz Biotechnology, Cat No.: sc-24948) containing 2 mM PMSF, 1% protease inhibitor cocktail, and 1 mM sodium orthovanadate were centrifuged at 14,000 g for 15 min, and the supernatants were used for Western blot. Equal protein amount of cell lysates or an equal volume of cell culture medium were separated on an SDS-PAGE gel, and Western blot was performed to probe for type I collagen using an anti-collagen primary antibody (SouthernBiotech, Cat. No.: 1310–01). GAPDH (Santa Cruz Biotechnology, Cat. No.: sc-25778) was used as a loading control for Western blots using cell lysates."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0031

Case: heldout_v1_004
Ambiguity: MEDIUM

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "GSIS",
    "glucose-stimulated insulin secretion"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_004",
  "context_qualifiers": [
    "pancreatic beta cells"
  ],
  "frozen": true,
  "measurement_property_endpoint": "GSIS / glucose-stimulated secretion",
  "measurement_target": "insulin secretion",
  "object": "glucose-stimulated insulin secretion",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "GLP-1 receptor activation increases glucose-stimulated insulin secretion in pancreatic beta cells.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "generic insulin abundance or basal insulin expression is not equivalent to GSIS"
  ],
  "scientific_proposition_target_id": "heldout_v1_004:scientific_proposition:v1",
  "subject": "GLP-1 receptor activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Glucagon-like peptide-1 potentiates glucose-stimulated insulin secretion via the transient receptor potential melastatin 2 channel.",
  "pmid": "29201240",
  "pmcid": "PMC5704267",
  "doi": "10.3892/etm.2017.5136"
}
```

Abstract:
The transient receptor potential melastatin 2 (TRPM2) channel, a Ca2+ permeable channel activated by cAMP, is expressed on pancreatic β-cells and is responsible for the regulation of insulin secretion. It is known that glucose-stimulated insulin secretion (GSIS) can be potentiated by glucagon like peptide-1 (GLP-1), and that the changes in the extracellular glucose concentration alter the levels of intracellular adenosine ATP and cAMP. The present study hypothesized that TRPM2 mediates the modulatory effect of GLP-1 on insulin secretion. The results demonstrated that silencing of TRPM2 eliminated GLP-1-enhanced insulin secretion, indicating the involvement of TRPM2 in this process. In addition, the results of current recordings of TRPM2 and measurement of the resulting insulin secretion in β-cells in the presence of GLP-1 and various concentrations of glucose suggest that GLP-1 regulates GSIS via the TRPM2 channel. Furthermore, inhibiting the activity or expression of TRPM2 attenuated GLP-1-induced GSIS. By using specific activators or inhibitors, the present study demonstrated that the two primary downstream effectors of the GLP-1 receptor, exchange protein directly activated by cAMP and protein kinase A, differentially influence GSIS and GLP-1-potentiated GSIS. In conclusion, the present study revealed the role of TRPM2 in GLP-1-regulated insulin secretion. The results of the present study provide a novel avenue for the prevention and treatment of diabetes and its complications.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC5704267.xml
SHA-256: 0c169f0828e64175fa432b07f13f121cd402b2789360f2788f697ba9861bff41

Frozen fulltext excerpts:
```json
[]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0032

Case: heldout_v1_004
Ambiguity: MEDIUM

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "GSIS",
    "glucose-stimulated insulin secretion"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_004",
  "context_qualifiers": [
    "pancreatic beta cells"
  ],
  "frozen": true,
  "measurement_property_endpoint": "GSIS / glucose-stimulated secretion",
  "measurement_target": "insulin secretion",
  "object": "glucose-stimulated insulin secretion",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "GLP-1 receptor activation increases glucose-stimulated insulin secretion in pancreatic beta cells.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "generic insulin abundance or basal insulin expression is not equivalent to GSIS"
  ],
  "scientific_proposition_target_id": "heldout_v1_004:scientific_proposition:v1",
  "subject": "GLP-1 receptor activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Structural basis for GLP-1 receptor activation by LY3502970, an orally active nonpeptide agonist.",
  "pmid": "33177239",
  "pmcid": "PMC7703558",
  "doi": "10.1073/pnas.2014879117"
}
```

Abstract:
Glucagon-like peptide-1 receptor (GLP-1R) agonists are efficacious antidiabetic medications that work by enhancing glucose-dependent insulin secretion and improving energy balance. Currently approved GLP-1R agonists are peptide based, and it has proven difficult to obtain small-molecule activators possessing optimal pharmaceutical properties. We report the discovery and mechanism of action of LY3502970 (OWL833), a nonpeptide GLP-1R agonist. LY3502970 is a partial agonist, biased toward G protein activation over β-arrestin recruitment at the GLP-1R. The molecule is highly potent and selective against other class B G protein-coupled receptors (GPCRs) with a pharmacokinetic profile favorable for oral administration. A high-resolution structure of LY3502970 in complex with active-state GLP-1R revealed a unique binding pocket in the upper helical bundle where the compound is bound by the extracellular domain (ECD), extracellular loop 2, and transmembrane helices 1, 2, 3, and 7. This mechanism creates a distinct receptor conformation that may explain the partial agonism and biased signaling of the compound. Further, interaction between LY3502970 and the primate-specific Trp33 of the ECD informs species selective activity for the molecule. In efficacy studies, oral administration of LY3502970 resulted in glucose lowering in humanized GLP-1R transgenic mice and insulinotropic and hypophagic effects in nonhuman primates, demonstrating an effect size in both models comparable to injectable exenatide. Together, this work determined the molecular basis for the activity of an oral agent being developed for the treatment of type 2 diabetes mellitus, offering insights into the activation of class B GPCRs by nonpeptide ligands.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7703558.xml
SHA-256: 7fcf7890544c5c1310cd85b57c6533ae310b31580aca57f3edc97d3a4625170b

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 1,
    "text": "The glucagon-like peptide-1 receptor (GLP-1R) is a member of the class B family of peptide hormone G protein–coupled receptors (GPCRs). The hallmark structural and functional feature of these receptors is a large N-terminal extracellular domain (ECD) (1). The ECD is a globular structure forming trilayer α-β-βα folds that are stabilized by three conserved pairs of cysteine disulfide bonds. These domains play a critical role in class B receptor activation by recognizing the ligand in the initial binding event (1). For the GLP-1R, high-resolution cryoelectron microscopy (cryo-EM) studies show the ECD structure is in an extended open conformation where multiple interactions with the C terminus of GLP-1 occur along a peptide-binding groove (2). These interactions allow the N terminus of GLP-1 to access a deep pocket, thereby rearranging the helical bundle and affecting transmembrane movement to enable interaction with the G protein. This activation mechanism is remarkably efficient as very low concentrations of ligand are needed to elicit an endogenous or a therapeutic response."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "glucose-stimulated insulin secretion",
      "insulin secretion"
    ],
    "paragraph_index": 2,
    "text": "Physiologically, upon nutrient ingestion by feeding, GLP-1 is released from intestinal l-cells into the circulation at concentrations in the low picomolar range (5 to 15 pmol/L) (3). These levels of GLP-1 help activate pancreatic β-cell GLP-1R to enhance glucose-stimulated insulin secretion, part of the incretin effect. Therapeutically, the GLP-1 mimetic exenatide was the first GLP-1R agonist approved for the treatment of type 2 diabetes mellitus (T2DM) (4, 5). Exenatide is equipotent with native GLP-1 for activating the GLP-1R (6) and displays beneficial effects on glucose control and body weight reduction at plasma concentrations in the 40 to 70 pmol/L range (7, 8). Similarly, other highly potent GLP-1R agonists, including liraglutide (9), dulaglutide (10), and semaglutide (11), are approved T2DM medications, each with proven cardiovascular health benefits (12). While these medicines provide improved treatment outcomes for patients, all of them are large–molecular weight peptide-based agents that require administration by subcutaneous (s.c.) injection."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 3,
    "text": "An important advance in GLP-1 therapy is the recent development of a coformulated tablet of semaglutide with the absorption enhancer sodium N-(8-[2-hydroxybenzoyl] amino) caprylate for oral delivery (13). Although oral bioavailability is less than 1% (14), this approach is therapeutically feasible because of the strong potency of peptide agonists for GLP-1R activation. However, the approved doses of oral semaglutide (brand name Rybelsus) do not achieve the higher drug exposures required to deliver equivalent glucose and body weight–lowering efficacy observed with injectable semaglutide (brand name Ozempic) (14–16). Further, the dosing regimen for oral semaglutide is restrictive for patients since drug absorption is significantly affected by food and fluid in the stomach (17). Specifically, the tablet must be administered after overnight fasting with a proscribed volume of water and at least 30 min before consumption of breakfast or other medicines (14). As an alternative approach, nonpeptide agonists could offer more standard drug formulations with simpler dosing practices, which would be especially beneficial for T2DM patients who often require additional daily medications."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 4,
    "text": "Historically, several groups have attempted to discover small-molecule activators of the GLP-1R, including positive allosteric modulators and compounds with agonist properties. Various chemotypes have been reported, such as series of quinoxalines (18, 19), sulfonylthiophenes (20), pyrimidines (21), phenylalanine derivatives (22), Boc-5 (23), and azoanthracene and oxadiazoanthracene derivatives (24–27). Although this collection of molecules indicated that nonpeptide ligands can modulate GLP-1R activity, these compounds evidently lack potency and pharmacokinetic properties that would be necessary to achieve an efficacy profile similar to that of peptide-based GLP-1R drugs. Therefore, it was hypothesized that small molecules cannot make sufficient contacts throughout the peptide-binding pocket to potently activate the GLP-1R. Here, we challenge this notion by reporting the discovery of a unique ECD-driven binding mechanism for LY3502970, an orally bioavailable nonpeptide agonist of the GLP-1R. This mechanism provides a potent pharmacological profile in vitro and in vivo, supporting the promise of an orally administered GLP-1R agonist drug."
  },
  {
    "matched_frozen_surfaces": [
      "GLP1R",
      "GLP-1R"
    ],
    "paragraph_index": 5,
    "text": "Small-molecule activators of the GLP-1R were identified using a screening method that detects compound-induced expression of a urokinase-type plasminogen activator in LLC-PK1 cells (28) expressing the human GLP-1R. Multiple cycles of traditional structure activity relationship work were conducted to optimize affinity and drug-like properties that enabled the discovery of OWL833 (LY3502970) (Fig. 1A) (29). Pharmacological studies using HEK293 cells expressing various densities of the human GLP-1R revealed that LY3502970 is highly potent at stimulating GLP-1R-induced cAMP accumulation with partial agonist activity relative to native GLP-1 (Fig. 1 B and C and SI Appendix, Table S1). Further, no detectable recruitment of GLP-1R-mediated β-arrestin was observed for LY3502970 (Fig. 1 B and C), a feature that may enhance GLP-1R-induced glucose lowering and body weight reduction (30, 31). Although the biased pharmacology is reminiscent of that observed for the nonpeptide ligand TT-OAD2 (32), the potency and efficacy of LY3502970 to stimulate GLP-1R-mediated cAMP accumulation in cell lines expressing different densities of the receptor are far greater than TT-OAD2 (SI Appendix, Fig. S1A and Table S1). LY3502970 showed no activity on other class B GPCRs (SI Appendix, Fig. S1B), and strikingly, the compound was also inactive on the mouse (Fig. 1D) and other species of the GLP-1R (SI Appendix, Fig. S1C). Therefore, experiments in mice expressing the human GLP-1R were employed to investigate the in vivo efficacy of LY3502970 (33). In these studies, overnight-fasted animals were orally a"
  },
  {
    "matched_frozen_surfaces": [
      "GLP1R",
      "GLP-1R"
    ],
    "paragraph_index": 6,
    "text": "Pharmacology and structural analysis of LY3502970 in complex with GLP-1R/GsiN18/Nb35/scFv16. (A) Chemical structure of LY3502970 (molecular weight: 882.96, formula: C48H48F2N10O5). Moieties that are discussed in the cryo-EM structural analysis are highlighted in colored boxes. (B and C) The signal transduction pharmacology of LY3502970 and GLP-1(7-36) was determined. Human GLP-1R density-dependent pharmacology of ligands was quantified by measuring the potency and efficacy for cAMP accumulation at increasing levels of receptor density (high, medium, low). Functional potency and efficacy for β-arrestin recruitment using enzyme fragment complementation was determined. Representative concentration response curves are presented. Summarized data with statistics are presented in SI Appendix, Table S1. (D) LY3502970 does not stimulate cAMP accumulation in HEK293 cells expressing the mouse GLP-1R. Data are presented as the mean ± SD of three independent experiments. (E) Mice expressing the human GLP-1R (n = 5 mice/group) were fasted overnight and orally administered vehicle or LY3502970 (0.1 to 10 mg/kg). Five hours later, animals received an intraperitoneal (i.p.) injection of glucose (2 g/kg). As a control group, one cohort was dosed with a s.c. injection of exenatide (1 nmol/kg) 1 h prior to receiving the i.p. glucose. For all mice, the circulating concentration of glucose over various time points was measured using glucometers. Each dose of LY3502970 reduced the glucose excursion AUC versus vehicle (P < 0.05; one-way ANOVA followed by the Dunnett’s test). (F) Similar studies we"
  }
]
```

Fields fulltext was expected to resolve:
["context"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0041

Case: heldout_v1_005
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "resolved osimertinib identity",
    "resistant/sensitive or equivalent response contrast",
    "AXL activity/expression perturbation functionally relevant to resistance"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_005",
  "context_qualifiers": [
    "EGFR-mutant non-small-cell lung cancer"
  ],
  "frozen": true,
  "measurement_property_endpoint": "resistant/sensitive treatment-response contrast",
  "measurement_target": "osimertinib treatment response",
  "object": "osimertinib resistance",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "AXL activation contributes to osimertinib resistance in EGFR-mutant non-small-cell lung cancer.",
  "relation_family": "contributes_to",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "generic AXL expression in lung cancer without treatment response is insufficient"
  ],
  "scientific_proposition_target_id": "heldout_v1_005:scientific_proposition:v1",
  "subject": "AXL activation",
  "therapy": "osimertinib"
}
```

Publication:
```json
{
  "title": "Patient-derived cell-based pharmacogenomic assessment to unveil underlying resistance mechanisms and novel therapeutics for advanced lung cancer.",
  "pmid": "36717865",
  "pmcid": "PMC9885631",
  "doi": "10.1186/s13046-023-02606-3"
}
```

Abstract:
A pharmacogenomic platform using patient-derived cells (PDCs) was established to identify the underlying resistance mechanisms and tailored treatment for patients with advanced or refractory lung cancer.
Drug sensitivity screening and multi-omics datasets were acquired from lung cancer PDCs (n = 102). Integrative analysis was performed to explore drug candidates according to genetic variants, gene expression, and clinical profiles.
PDCs had genomic characteristics resembled with those of solid lung cancer tissues. PDC molecular subtyping classified patients into four groups: (1) inflammatory, (2) epithelial-to-mesenchymal transition (EMT)-like, (3) stemness, and (4) epithelial growth factor receptor (EGFR)-dominant. EGFR mutations of the EMT-like subtype were associated with a reduced response to EGFR-tyrosine kinase inhibitor therapy. Moreover, although RB1/TP53 mutations were significantly enriched in small-cell lung cancer (SCLC) PDCs, they were also present in non-SCLC PDCs. In contrast to its effect in the cell lines, alpelisib (a PI3K-AKT inhibitor) significantly inhibited both RB1/TP53 expression and SCLC cell growth in our PDC model. Furthermore, cell cycle inhibitors could effectively target SCLC cells. Finally, the upregulation of transforming growth factor-β expression and the YAP/TAZ pathway was observed in osimertinib-resistant PDCs, predisposing them to the EMT-like subtype. Our platform selected XAV939 (a WNT-TNKS-β-catenin inhibitor) for the treatment of osimertinib-resistant PDCs. Using an in vitro model, we further demonstrated that acquisition of osimertinib resistance enhances invasive characteristics and EMT, upregulates the YAP/TAZ-AXL axis, and increases the sensitivity of cancer cells to XAV939.
Our PDC models recapitulated the molecular characteristics of lung cancer, and pharmacogenomics analysis provided plausible therapeutic candidates.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9885631.xml
SHA-256: a42d59ad55588e23faeda77694f1503390d7421a7f61b1750f93500a20dac6a0

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 18,
    "text": "To identify the molecular features related to EGFR-TKI therapeutics, we categorized therapeutic groups from 27 PDC samples. We categorized these patients into four groups (Fig. 5A): (1) BASELINE, PDCs acquired from EGFR-mutated patients that did not receive any treatment; (2) POST1, PDCs without EGFR T790M mutation, acquired after disease progression to the first-line use of first- or second-generation EGFR-TKIs; (3) POST2, PDCs with EGFR T790M, acquired from patients after first- or second-generation EGFR-TKI treatment; and (4) POST3, T790M-positive PDCs, acquired after disease progression to second-line use of the third-generation TKI osimertinib. To identify gene regulation according to these four treatment groups, we identified upregulated DEGs (P < 0.01) for each group and associated pathways using limma and GSEA (P < 0.1 )[38, 43]. Additionally, we collected known EGFR-TKI resistance pathway gene sets: MAPK, PI3K-AKT, JAK-STAT, Wnt β-catenin, plasminogen activation, neuroendocrine activation, YAP/TAZ, MET, HER2, RAS, ERK, KRAS, and TAM (TYRO3-AXL-MERTK) family genes [13, 14, 43–46]. Resistance pathway scores were calculated using GSVA for each PDC. The score difference of the four therapeutics groups was evaluated using the Wilcoxon rank-sum test [34]."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 20,
    "text": "The generation of osimertinib-resistant cell lines and experiments are described in Additional file 1 (Supplementary methods)."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 29,
    "text": "PDC samples could be classified into four molecular subtypes using gene expression profile by NMF clustering. To extrapolate the clinical characteristics for each subtype, we interrogated patient clinical profile encompassing histologic type, survival, smoking, and EGFR-TKI therapy record (Fig. 2 and Table 1). To uncover regulatory program for each molecular subtype, variant enrichment, and pathway regulation scores were assessed from multi-omics profile. In brief, subtype C1 was associated with a good outcome shown in Fig. 2A, and was activated in inflammatory and IL6-JAK-STAT3 signaling pathways; subtype C2 was associated with a modest outcome, dominance of TP53/EGFR wild-type, upregulation of epithelial-to-mesenchymal transition (EMT), and enrichment of osimertinib-resistant group (POST3) PDCs; subtype C3 was associated with the worst outcome, long-term smoking males, SCLC, TP53 hotspot mutation, MYC activation, and fasten G2M checkpoint; by contrast, subtype C4 exhibited the best survival, frequent TP53 non-hotspot mutation, the dominance of EGFR-TKI TARGET mutation, and NOTCH signaling activation (Fig. 2A, B). We also demonstrated the survival significance corresponding to C1–C4 subtype gene sets using additional transcriptome datasets (n = 1587; see Fig. S1A-B in Additional file 3 and Table S3 in Additional file 2). Upregulation of the C3 gene set concurrently exhibited the worst outcomes (P < 0.001 and hazard ratio [HR] = 2.6). When additionally demonstrating from known up-regulated genes of embryonic stem cell, we could observe the activation of human embryonic stem"
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 32,
    "text": "To interrogate drug candidates for variants, we tested the difference in drug responses of single and co-occurrent mutation cases (P < 0.005 and |log2 FC| < 0.2; Fig. 3A). Co-mutated cases were also explored using the Fisher’s exact test (P < 0.25; see Additional file 3, Fig. S3). Unexpectedly, EGFR-TARGET mutated PDCs showed a relatively modest response to three EGFR-TKIs (afatinib P = 0.17, gefitinib P = 0.19, osimertinib P = 0.08). To uncover EGFR-mutated cells’ molecular features interfering with the EGFR-TKI response, we dissected TKI TARGET mutations according to our four molecular subtypes (Fig. 3B). The C4 EGFR-dominant subtype was the most sensitive to all EGFR-TKIs, and the C1 inflammatory subtype also showed an especially good response to afatinib and osimertinib. Mutated cases (n = 2) of the C3 stemness subtype was insufficient for statistical test. Finally, mutated cases (n = 6) of the C2 EMT-like subtype did not respond to any EGFR-TKIs. Additionally, both T790Maq and NOSaq (EGFR R776G and I744M with L858R) PDCs were TKI-sensitive. In the EGFR NOS type mutations, G719A was observed, and it comprised 11.5% among the NOS mutations in previous NSCLC study, and patient-derived xenografts demonstrated that the mutation was resistant to osimertinib [48]. The remaining NOS mutations excluded exon 18–21 and had a low possibility of finding a structure-based therapeutic target [48]. Therefore, we concluded that the remaining NOS group mutations were not targetable by EGFR-TKIs. Especially, EGFR TARGET mutated PDCs classified to EMT-like subtype exhibited low response t"
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 39,
    "text": "Among our PDCs, we identified 27 EGFR-TKI-treated cases with corresponding NGS results (independently obtained in the clinic using tissue samples). As described in methods, we these patients into four groups (Fig. 5A). Primarily, POST3 samples (86%) were enriched in the C2 EMT-like subtype (Table 1). EGFR mutation-calling failure was observed in the clinical tumor biopsy NGS record of some patients from which BASELINE (n = 2) and POST2 (n = 1) PDCs were derived. The mutation-calling failure likely originated from differences in the platform between the clinical biopsy and laboratory PDC testing. Moreover, TP53 non-hotspot mutations were present in all of the POST2 PDCs and were markedly absent in POST3 PDCs. EGFR T790Maq was identified in only POST2 PDCs (Fig. 5B red asterisk); interestingly, BRAF mutations highly co-occurred with EGFR T790Maq mutations (Fig. 5B and Additional file 3, Fig. S3). Thus, our PDC models significantly reflected EGFR mutation, acquisition, and extinction status according to EGFR-TKI therapies.Fig. 5Genomic profile and drug sensitivity of PDCs, and functional validation using cell lines. A Therapeutic groups were categorized into two arms. The first arm was BASELINE (yellow) to POST1 (light green). The second was BASELINE to POST2 (dark green) to POST3 (orange). B Heatmap presenting the mutation profile, RNA subtype, and tumor mutation burden (TMB) of each group. In the POST1 group, the red asterisk indicates the EGFR double mutation including T790M. C Heatmap of the DEGs for the four groups. DEGs and pathways (GSEA P < 0.1) for each group are deno"
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 40,
    "text": "Genomic profile and drug sensitivity of PDCs, and functional validation using cell lines. A Therapeutic groups were categorized into two arms. The first arm was BASELINE (yellow) to POST1 (light green). The second was BASELINE to POST2 (dark green) to POST3 (orange). B Heatmap presenting the mutation profile, RNA subtype, and tumor mutation burden (TMB) of each group. In the POST1 group, the red asterisk indicates the EGFR double mutation including T790M. C Heatmap of the DEGs for the four groups. DEGs and pathways (GSEA P < 0.1) for each group are denoted on the right. D Two scatter plots of scores extracted from EGFR-TKI resistance pathway gene pairs. ERBB2 and MET were upregulated in the POST2 group (dotted circle), and YAP/TAZ-AXL activated in the POST3 group (dotted circle). R indicates Pearson’s correlation coefficient, and the P value was acquired using the Wilcoxon rank-sum test from the AUC values. E Volcano plot to test drug sensitivity for each group. The x-axis is log2 fold change (FC) and the y-axis is P-value. F Drug response curves based on the viability of H1975, H1975_OR3, and OR4 cells treated with osimertinib. G Bar plots of YAP1 and its target gene expressions. Fold increases (x-axis) in mRNA expression in each gene (y-axis) were assessed using RT-PCR in H1975, H1975_OR3, and OR4 cells. H The protein level expression assessment in three cells using western blot analysis. I Cell migration across the transmembrane. Cell morphology images are shown from three cases. The bar plot indicates the average number of migrating cells (y-axis) for each condition (x-"
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0048

Case: heldout_v1_006
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "altered venetoclax sensitivity",
    "viability/apoptosis response to venetoclax",
    "combination-response evidence",
    "source-equivalent drug-response contrast"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_006",
  "context_qualifiers": [
    "acute myeloid leukemia"
  ],
  "frozen": true,
  "measurement_property_endpoint": "drug-response / viability / apoptosis contrast",
  "measurement_target": "venetoclax sensitivity",
  "object": "venetoclax",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "BRD4 inhibition increases sensitivity to venetoclax in acute myeloid leukemia.",
  "relation_family": "increases_sensitivity_to",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "BRD4 effects on AML growth without venetoclax response are insufficient",
    "BET inhibitor is search-use only unless intervention authority is resolved"
  ],
  "scientific_proposition_target_id": "heldout_v1_006:scientific_proposition:v1",
  "subject": "BRD4 inhibition",
  "therapy": "venetoclax"
}
```

Publication:
```json
{
  "title": "Preclinical efficacy of targeting epigenetic mechanisms in AML with 3q26 lesions and EVI1 overexpression.",
  "pmid": "38086946",
  "pmcid": "PMC12122007",
  "doi": "10.1038/s41375-023-02108-3"
}
```

Abstract:
AML with chromosomal alterations involving 3q26 overexpresses the transcription factor (TF) EVI1, associated with therapy refractoriness and inferior overall survival in AML. Consistent with a CRISPR screen highlighting BRD4 dependency, treatment with BET inhibitor (BETi) repressed EVI1, LEF1, c-Myc, c-Myb, CDK4/6, and MCL1, and induced apoptosis of AML cells with 3q26 lesions. Tegavivint (TV, BC-2059), known to disrupt the binding of nuclear β-catenin and TCF7L2/LEF1 with TBL1, also inhibited co-localization of EVI1 with TBL1 and dose-dependently induced apoptosis in AML cell lines and patient-derived (PD) AML cells with 3q26.2 lesions. TV treatment repressed EVI1, attenuated enhancer activity at ERG, TCF7L2, GATA2 and MECOM loci, abolished interactions between MYC enhancers, repressing AML stemness while upregulating mRNA gene-sets of interferon/inflammatory response, TGF-β signaling and apoptosis-regulation. Co-treatment with TV and BETi or venetoclax induced synergistic in vitro lethality and reduced AML burden, improving survival of NSG mice harboring xenografts of AML with 3q26.2 lesions.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12122007.xml
SHA-256: d4b63b11de0239853f5c717ccb778e9a9764cc6db5145f1ff514a3b1a4622105

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BRD4",
      "venetoclax"
    ],
    "paragraph_index": 2,
    "text": "A previous report had highlighted that CML blast crisis cells express high β-catenin levels, and knockdown of β-catenin and its related co-transcription factor LEF1 (lymphoid enhancer factor 1) was shown to attenuate EVI1 levels (36,37). Consistent with this, two tandem LEF1-β-catenin binding sites are present upstream of EVI1 which are bound by LEF1 (37). We previously reported that treatment with tegavivint (TV) disrupts the binding of nuclear β-catenin to the scaffold proteins TBL1/R1 (Transducin Beta Like 1 X-Linked/TBL1X Receptor 1) complexed to TCF7L2 (Transcription Factor 7 Like 2, TCF4), a member of LEF1 family of transcription factors, which reduced the nuclear β-catenin levels and inhibited targets of the transcriptional complex, including c-Myc (37,38). This resulted in growth inhibition and apoptosis of AML stem progenitor cells (38). A previous report had demonstrated that, due to increased BRD4 (Bromodomain Containing 4) occupancy on the rearranged GATA2 enhancer driving EVI1 overexpression, treatment with a BET protein inhibitor (BETi) represses EVI1 and induces loss of viability of EVI1 overexpressing AML cells (17). Related to this, our previous studies had also demonstrated that treatment with TV overcomes the non-genetic mechanism of tolerance-resistance to BETi, by inhibiting emergence of c-Myc re-expression in BETi-tolerant/resistant AML cells and restoring their sensitivity to BETi (39). Taken together, and based on the rationale generated by these reports, we determined here effects of TV on active chromatin, the transcriptome and protein expressions "
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 8,
    "text": "We first confirmed the in vitro lethal activity of a pan-BET protein inhibitor, OTX015, on AML cell lines (MUTZ-3, UCSD-AML1, OCI-AML20, HNT-34, AML191, AML194 and AML219) as well as in PD AML cells harboring inv(3q26) or t(3:3) and overexpressing EVI1 (1,39,40). Fig. S1A depicts the results of FISH and cytogenetics analyses of AML191, AML194 and AML219 cells, whereas Fig. S1B shows the oncoplot of the genetic alterations in PD AML cells. Fig. 1A demonstrates that treatment with OTX015 dose-dependently induced lethality in the AML cell lines, with AML191 showing less sensitivity than AML-194 cells. HNT-34, UCSD-AML1 and OCI-AML20 cells exhibited intermediate sensitivity. The lethal activity of OTX015 was associated with significant repression of mRNA of MECOM, LEF1, KIT, MYB and MYC but increased expression of HEXIM1 (Fig. 1B and S1C) (39). OTX015 treatment also concomitantly reduced the protein expressions of EVI1, CDK4/6, c-Myb, c-Myc and LEF1, while increasing protein levels of HEXIM1, BRD4, p21, CD11b and cleaved PARP (Fig. 1C, S1D and S1E). Exposure to OTX015 also induced greater loss of viability in PD AML cells harboring inv(3q26) or t(3:3) (mean values, n = 11), as compared to the AML cells lacking it (mean values, n = 8) (p < 0.05) (Fig. 1D and S1F). Since β-catenin acts as the co-factor for LEF1 and reduction in nuclear β-catenin levels would reduce LEF1, and potentially EVI1 levels, we next determined effects of TV, previously documented to attenuate nuclear β-catenin levels (38), on viability and associated gene-expression perturbations in AML cell lines and PD "
  },
  {
    "matched_frozen_surfaces": [
      "BRD4",
      "venetoclax"
    ],
    "paragraph_index": 13,
    "text": "We next conducted, in UCSD-AML1 transduced with Cas9, a CRISPR screen with a previously reported, targeted, domain-specific gRNAs library against epigenetic regulators (42). The screen revealed, among other ‘druggable’ targets, BRD4 as a dependency (Fig. S7A and S7B). Guided by this and based on the observation that TV treatment reduced SE-driven c-Myc and BCL2 levels in LSCs (Fig. 5D), we next determined whether co-treatment with TV and BETi would exert superior lethal activity in AML cells with inv(3)/t(3;3). Fig. 6A and 6B show that co-treatment with TV and OTX015 synergistically induced apoptosis in AML191 cells, with delta synergy scores of >1 by the ZIP method. This was associated with greater reduction in protein levels (by immunoblot analysis), in cell lysates, of EVI1, c-Myc, c-Myb, RUNX1, PU.1, CDK6 and c-KIT, as well as in anti-apoptotic proteins MCL-1, BCL2, and Bcl-xL, with upregulation of BIM, p21 and p27, in AML191 cells (Fig. 6C). Combined treatment with relatively lower concentrations of TV (20 to 50 nM) and OTX015 (250 to 500 nM) also yielded delta synergy scores of > 1 in AML194, UCSD-AML1, OCI-AML20, MUTZ3 and HNT34 cells (Fig. 6D). Notably, in 6 samples of PD AML cells with inv(3)/t(3;3), co-treatment with 30 nM or less of TV and OTX015 (100 to 500 nM) also synergistically induced apoptosis (Fig. 6E). In contrast, treatment of three normal CD34+ hematopoietic progenitor cells (HPCs) with TV or OTX015 alone induced less than 15% loss of viability, and their co-treatment exerted sub-additive lethal effects (Fig. S7C). We next determined the effect of TV a"
  },
  {
    "matched_frozen_surfaces": [
      "venetoclax"
    ],
    "paragraph_index": 14,
    "text": "We next determined the in vivo anti-leukemia efficacy of TV and/or OTX015 in aggressive, flank or tail-vein infused, xenograft models of AML cells with inv(3)/t(3;3) in immune-depleted NSG mice. These models were transduced with Luciferase/GFP for bioluminescence imaging. First, cohorts of mice were injected in the flank with AML 191 cells (in a 1:1 suspension of Matrigel) and tumors were measured once a week, beginning 3 weeks after injection. Mice were treated for 4 weeks with vehicle control, or with TV or OTX015 alone, or co-treated with TV and OTX015. The dose of each drug employed here was previously determined to be safe (18,23,47). Whereas monotherapy with TV delayed tumor growth, co-treatment with TV and OTX015 was significantly superior in delaying and suppressing AML growth compared to vehicle or each drug alone (Fig. 7A and S8). Consistent with this, co-treatment with TV and OTX015 was significantly superior in improving the survival of the mice up to > 1.5 cm of tumor growth, when mice had to be euthanized (Fig. 7B). Indeed, co-treatment with TV and OTX015 yielded a plateau in the survival curve for up to 70 days with 100% of mice in the cohort surviving, compared to none in the other cohorts (p < 0.01) (Fig. 7B). Although the tail-vein infused model of AML191 cells was rapidly lethal, the effects on AML burden could still be assessed and showed significantly greater reduction in AML burden, following co-treatment with TV and OTX015 compared to each drug alone (Fig. 7C). We next determined the anti-AML efficacy of TV and/or OTX015 against a separate, tail vein "
  },
  {
    "matched_frozen_surfaces": [
      "BRD4",
      "venetoclax"
    ],
    "paragraph_index": 17,
    "text": "It is noteworthy that the gRNAs for BRD4 and EP300 were enriched in a CRISPR screen in AML cells with inv(3) involving 3q26, while partial depletion of EVI1 via CRISPR knockout sensitized AML cells to BETi. These observations, coupled with the findings that in AML cells harboring inv(3) and EVI1 overexpression treatment with BETi, as well as with TV, reduced EVI1, c-Myb, c-Myc, CDK4/6 and MCL1, support and explain why co-treatment with BETi and TV exerts synergistic in vitro lethal activity and in vivo efficacy in models of AML cells harboring inv(3)/t(3;3). This combination also induced synergistic in vitro lethality in AML cells with atypical MECOM locus translocations, including t(3;8) and t(3;21), which are also associated with EVI1 and c-Myc expression (17). Moreover, since the HAT CBP/p300 is also involved in MYB regulated EVI1 expression (46), the CRISPR screen findings also explain the synergistic lethality we observed here in AML cells with inv(3)/t(3;3) due to co-treatment with TV and the CBP/p300 inhibitor GNE-049. Resistance to the BCL2 inhibitor venetoclax in AML setting has been attributed to upregulation of MCL1 and Bcl-xL following treatment with venetoclax or venetoclax-based anti-AML therapies (50). Treatment with TV and a pan-BET inhibitor not only repressed EVI1 and c-Myc levels but also reduced protein levels of MCL1 and Bcl-xL contributing to the observed in vitro synergistic lethality and superior in vivo efficacy of co-treatment with TV and venetoclax in AML cells harboring inv(3)/t(3;3). This is schematically represented in Fig. S9. The marked reduc"
  },
  {
    "matched_frozen_surfaces": [
      "venetoclax"
    ],
    "paragraph_index": 18,
    "text": "If past clinical experience with targeted therapies that have yielded incremental improvement in clinical outcome in AML is to be the guide, then findings presented here underscore that, at safe doses further in vivo interrogation of the combination of TV and BETi, with or without venetoclax, in AML with inv(3)/t(3;3) is warranted (50). AML-initiating, stem/progenitor cells have been reported to be enriched in the minimal and measurable residual disease (MRD) state after achieving a complete remission of AML (51). Therefore, findings presented here are promising that, in AML harboring inv(3)/t(3;3) with EVI1 overexpression, TV treatment attenuates the core transcriptional regulatory circuitry, reduces AML stemness score and depletes phenotypically characterized AML stem/progenitor cells. These findings also strongly support future development and in vivo testing of TV-based combinations highlighted here in the clinical setting of AML with inv(3)/t(3;3) in MRD positive clinical remission."
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "context", "therapy"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0051

Case: heldout_v1_007
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "dendritic spine density",
    "dendritic spine number"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_007",
  "context_qualifiers": [
    "hippocampal neurons"
  ],
  "frozen": true,
  "measurement_property_endpoint": "spine density / spine number",
  "measurement_target": "dendritic spines",
  "object": "dendritic spine density",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "BDNF increases dendritic spine density in hippocampal neurons.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "neurite length, neuronal survival, synapse-marker abundance or generic plasticity are not automatically equivalent",
    "TrkB/NTRK2 does not replace BDNF as subject"
  ],
  "scientific_proposition_target_id": "heldout_v1_007:scientific_proposition:v1",
  "subject": "BDNF",
  "therapy": null
}
```

Publication:
```json
{
  "title": "KCC2 Regulates Dendritic Spine Formation in a Brain-Region Specific and BDNF Dependent Manner.",
  "pmid": "30169756",
  "pmcid": "PMC6188549",
  "doi": "10.1093/cercor/bhy198"
}
```

Abstract:
KCC2 is the major chloride extruder in neurons. The spatiotemporal regulation of KCC2 expression orchestrates the developmental shift towards inhibitory GABAergic drive and the formation of glutamatergic synapses. Whether KCC2's role in synapse formation is similar in different brain regions is unknown. First, we found that KCC2 subcellular localization, but not overall KCC2 expression levels, differed between cortex and hippocampus during the first postnatal week. We performed site-specific in utero electroporation of KCC2 cDNA to target either hippocampal CA1 or somatosensory cortical pyramidal neurons. We found that a premature expression of KCC2 significantly decreased spine density in CA1 neurons, while it had the opposite effect in cortical neurons. These effects were cell autonomous, because single-cell biolistic overexpression of KCC2 in hippocampal and cortical organotypic cultures also induced a reduction and an increase of dendritic spine density, respectively. In addition, we found that the effects of its premature expression on spine density were dependent on BDNF levels. Finally, we showed that the effects of KCC2 on dendritic spine were dependent on its chloride transporter function in the hippocampus, contrary to what was observed in cortex. Altogether, these results demonstrate that KCC2 regulation of dendritic spine development, and its underlying mechanisms, are brain-region specific.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6188549.xml
SHA-256: e7245af1d3d34f4d66d8cd1ad47f4dab8144587aa6d41b70d4de4e66c9b2ce03

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "dendritic spine",
      "spine density"
    ],
    "paragraph_index": 2,
    "text": "KCC2 is a potassium-chloride cotransporter, the only member of the Cation Chloride Cotransporter family that is almost exclusively expressed in neurons (Kaila, Price, et al. 2014). The increase in KCC2 expression during development is responsible for the shift of GABAergic drive towards more inhibitory activity, by decreasing intracellular [Cl−] (Ben-Ari et al. 1989; Chudotvorova et al. 2005; Fiumelli et al. 2005; Lee et al. 2005). In addition, it has been suggested that KCC2 can modulate glutamatergic synapse development and function, via ion-transport independent mechanisms (Li et al. 2007; Gauvain et al. 2011; Fiumelli et al. 2013; Chevy et al. 2015). For example, removing KCC2 in immature cortical neurons prevented spine maturation altogether, leading to an increase of filopodia protrusions (Li et al. 2007). Conversely, removing KCC2 in mature hippocampal neurons, after spine formation and when KCC2 expression reached its plateau, did not affect spine density but reduced the efficacy of excitatory synapses, through an alteration of AMPA receptor aggregation (Gauvain et al. 2011; Chevy et al. 2015). Interestingly, these effects were not due to reduction of transporter activity, but to altered interactions of KCC2 with the cytoskeleton (Li et al. 2007; Gauvain et al. 2011). Consistent with these findings, premature expression of KCC2 induced by in utero electroporation of its cDNA in cortical pyramidal cells caused a long-lasting increase in dendritic spine density through a mechanism that was independent of its ion transporter function (Fiumelli et al. 2013). All togethe"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor",
      "spine density"
    ],
    "paragraph_index": 3,
    "text": "Here, we report that KCC2 subcellular localization in pyramidal neurons during the first postnatal week was significantly different in the CA1 region of the hippocampus and the somatosensory cortex. We further found that premature expression of KCC2 by targeted in utero electroporation caused opposite effects on spine density in the 2 regions and that KCC2-induced spine loss in the hippocampus was dependent on its transporter activity. Finally, we showed that increasing the levels of Brain Derived Neurotrophic Factor (BDNF), a potent regulator of KCC2 expression and activity in the immature brain (Ludwig et al. 2011; Puskarjov et al. 2015), was sufficient to block the spine density increase induced by KCC2 premature expression in cortical pyramidal neurons."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 6,
    "text": "For organotypic slice cultures, at least 3–4 slices per animal were pooled in a sample, in order to have enough proteins from whole lysates. Each experimental group included 3–5 animals. Membranes were probed with the following primary antibodies: anti-KCC2 1:1000 (rabbit polyclonal IgG; Cat. no. 07-432, Millipore), 1:200 anti-BDNF (cat#N-20: sc-546, Santa-Cruz Biotechnology, Inc.), anti-glyceraldehyde-3-phosphate dehydrogenase 1:4000 (GAPDH, mouse monoclonal IgG; Cat. no. AM4300; Applied Biosystems) and anti-β dystroglycan 1:3000 (rabbit polyclonal IgG, Cat no. ab43125, Abcam). Specificity of BDNF antibody was verified using tissue from a BDNF−/− mouse and a wild-type littermate (data not shown). All samples were run simultaneously. Bands were quantified using Image J software. The intensity of KCC2 and BDNF bands were normalized over the intensity of the GAPDH band for whole lysates or of the β dystroglycan band for membrane fractions, in the same lane (internal loading control)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 7,
    "text": "Brains were perfused with saline (0.9% NaCl) followed by 4% paraformaldehyde/phosphate buffer, pH 7.4, then cryoprotected in 30% sucrose/PBS, and frozen in Tissue Tek. Brains were sectioned (80 μm thick for in utero electroporation experiment, 40 μm for immunostaining of KCC2) using a cryostat (Leica). Slices were blocked in 10% NGS and 0.3% Triton for 2 h at room temperature, and incubated overnight at 4 °C in 5% NGS, 0.1% Triton and the following primary antibodies—NeuN, 1:400 (mouse monoclonal, Cat. no. MAB377 Millipore); KCC2, 1:200 (rabbit polyclonal, Cat. no. 07-432 Millipore); GFP, 1:500 (chicken polyclonal, Cat. no. Ab13970 Abcam). The following secondary antibodies were used: anti-mouse Alexa 633-conjugated goat IgG and anti-rabbit Alexa 488-conjugated goat IgG (1:400; Molecular Probes, Invitrogen) or Alexa 488 goat anti-chicken IgY H&L (1:500, Cat. no. Ab150169 Abcam). NeuN staining was used to unequivocally identify the CA1 region in hippocampal slices. GFP immunostaining was used to enhance GFP signal so we could reliably detect thin spines in all imaged cells. For the quantification of KCC2 expression and localization in vivo, we imaged the somatosensory cortex (SSCx) and the CA1 hippocampal region in 3–4 sections/animal. Confocal stacks were acquired using a Leica SP8 confocal microscope and a ×63 (glycerol, NA 1.3) objective and a z step of 0.5μm. The classification of the KCC2-positive neurons to groups with and without signal in the plasmalemma was done manually relying on the detectable fluorescence band on the periphery of the cell. To quantify KCC2 expre"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "dendritic spine"
    ],
    "paragraph_index": 8,
    "text": "Slice culture preparation was essentially as described in Chattopadhyaya et al. (2004). Mouse pups at postnatal day 4 (P4) for cortical slices and at P6 for hippocampal slices were decapitated, and brains were rapidly removed and immersed in ice-cold culture medium (containing MEM, 20% horse serum, 1 mM glutamine, 13 mM glucose, 1 mM CaCl2, 2 mM MgSO4, 0.5 μm/mL insulin, 30 mM HEPES, 5 mM NaHCO3, and 0.001% ascorbic acid). Coronal brain slices of hippocampus or cortex, 400 μm thick, were cut with a Chopper (Stoelting, Wood Dale, IL) into ice-cold culture medium. Slices were then placed on transparent Millicell membrane inserts (Millipore, Bedford, MA), usually 3–5 slices/insert, in 30 mm Petri dishes containing 0.75 mL of culture medium. Finally, they were incubated in a humidified incubator at 34 °C with a 5% CO2-enriched atmosphere, and the medium was changed 3 times per week. All procedures were performed under sterile conditions. Constructs to be transfected were incorporated into “bullets” made using 1.6 μm gold particles coated with 30 μg of each of the plasmids of interest. These bullets were used to biolistically transfect slices by gene gun (Bio-Rad, Hercules, CA) at high pressure (180 Pa). Cultures were biolistically tranfected with either pCI-KCC2wt-IRES-eGFP or pCI-KCC2 C568A-IRES-eGPF together with pCI-tdTomato or pCI-GFP, from equivalent postnatal day (EP) 6 to EP20. We found that the colocalization of GFP and tdTomato signals was 100% when cultures were shot with pCI-KCC2wt-IRES-eGFP or pCI-KCC2 C568A-IRES-eGPF and pCI-tdTomato. Therefore, in parallel experim"
  },
  {
    "matched_frozen_surfaces": [
      "spine density"
    ],
    "paragraph_index": 12,
    "text": "Spine density, spine morphology and spine length were analyzed and quantified in 3D using Neurolucida software (MicroBrightField), as described in Awad et al. (2016). We classified spines as mushroom spines, identified by a clearly distinguishable enlargement of the head of the spine (compared with the neck); stubby spines, identified as structures with equal thickness between head and neck (minimum 0.3 μm thick); thin spines as long and thin protrusions lacking a clearly defined head (maximum of 0.3 μm thick). Values for animals belonging to the same experimental group were not statistically different and were pooled. All quantification was done blind to the treatment."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0052

Case: heldout_v1_007
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "dendritic spine density",
    "dendritic spine number"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_007",
  "context_qualifiers": [
    "hippocampal neurons"
  ],
  "frozen": true,
  "measurement_property_endpoint": "spine density / spine number",
  "measurement_target": "dendritic spines",
  "object": "dendritic spine density",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "BDNF increases dendritic spine density in hippocampal neurons.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "neurite length, neuronal survival, synapse-marker abundance or generic plasticity are not automatically equivalent",
    "TrkB/NTRK2 does not replace BDNF as subject"
  ],
  "scientific_proposition_target_id": "heldout_v1_007:scientific_proposition:v1",
  "subject": "BDNF",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Voluntary exercise and caloric restriction enhance hippocampal dendritic spine density and BDNF levels in diabetic mice.",
  "pmid": "19280661",
  "pmcid": "PMC2755651",
  "doi": "10.1002/hipo.20577"
}
```

Abstract:
Diabetes may adversely affect cognitive function, but the underlying mechanisms are unknown. To investigate whether manipulations that enhance neurotrophin levels will also restore neuronal structure and function in diabetes, we examined the effects of wheel running and dietary energy restriction on hippocampal neuron morphology and brain-derived neurotrophic factor (BDNF) levels in db/db mice, a model of insulin resistant diabetes. Running wheel activity, caloric restriction, or the combination of the two treatments increased levels of BDNF in the hippocampus of db/db mice. Enhancement of hippocampal BDNF was accompanied by increases in dendritic spine density on the secondary and tertiary dendrites of dentate granule neurons. These studies suggest that diabetes exerts detrimental effects on hippocampal structure, and that this state can be attenuated by increasing energy expenditure and decreasing energy intake.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC2755651.xml
SHA-256: a998e51f51f7009b10d1f81f110f32844d4402552590ce45b6eb6c4cd500d952

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "dendritic spine",
      "spine density"
    ],
    "paragraph_index": 2,
    "text": "Dendritic spines are the primary sites of excitatory neurotransmission in the adult brain. Although previous studies have shown reductions in hippocampal synaptic density in insulin deficient diabetes (Martínez-Tellez et al., 2005; Zhou et al., 2007), far less is known about dendritic changes in the hippocampus of insulin resistant rodents. Using a diet-induced insulin resistance model, we have demonstrated reductions in dendritic spine density in hippocampal area CA1 (Stranahan et al., 2008c). Other studies have shown reductions in presynaptic marker expression in whole-hippocampal homegenates from genetic models of insulin resistance (Ahima et al., 1999). However, no studies to date have characterized dendritic spine density or neuronal morphology in the dentate gyrus of the hippocampus in insulin resistant diabetes."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor"
    ],
    "paragraph_index": 3,
    "text": "The consequences of diabetes for hippocampal neuronal structure are qualitatively similar to the effects of restricting brain-derived neurotrophic factor (BDNF) signaling. BDNF levels in the hippocampus are responsive to alterations in glucose levels (Anson et al., 2003; Duan et al., 2003), and BDNF plays a role in cellular metabolism (Burkhalter et al., 2003; Yeo et al., 2004). BDNF is also particularly abundant in the dentate gyrus, relative to the CA1 subfield (Friedman et al., 1991). Functionally, dentate gyrus BDNF signaling determines antidepressant efficacy, suggesting a role in anxiety and mood regulation (Adachi et al., 2008). This indicates that correlated alterations in dentate gyrus BDNF signaling and neuronal structure may be associated with the changes in anxiety-like behavior that have been reported in rodent models of insulin resistance (Asakawa et al., 2003)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 4,
    "text": "Voluntary wheel running and caloric restriction increase levels of BDNF in the hippocampus (Mattson et al., 2004a; Mattson et al., 2004b; Neeper et al., 1996; Ding et al., 2006) and enhance peripheral metabolism. Accumulating evidence suggests that the enhancement of peripheral metabolism is accompanied by alterations in central metabolic markers, with consequences for neuronal function (Vaynman et al., 2006; Gomez-Pinilla et al., 2008). Mice selected for high levels of wheel running have improved peripheral metabolism and exhibit greater exercise-induced upregulation of hippocampal BDNF (Johnson et al., 2003). This ‘metabotrophic hypothesis’ for the effects of exercise and caloric restriction on hippocampal structure and biochemistry has potential relevance for the treatment and prevention of neurodegenerative disease."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "dendritic spine",
      "spine density"
    ],
    "paragraph_index": 5,
    "text": "The coincident roles of BDNF in energy metabolism and spinogenesis prompted us to intially characterize differences in hippocampal neuronal morphology in an animal with deficient metabolic function. The db/db mouse carries a mutation that inactivates the leptin receptor, producing an animal that is obese and insulin resistant (Hummel et al., 1966). We observed reduced hippocampal BDNF and loss of dendritic spines in db/db mice, and therefore investigated the consequences of wheel running and caloric restriction – two ethologically relevant manipulations of energy availability. These manipulations enhanced dendritic spine density and hippocampal BDNF expression in wild type mice, and partially reversed abnormalities in db/db mice. These findings suggest that the adverse effects of diabetes on hippocampal structural plasticity can be ameliorated by increasing energy expenditure and decreasing energy intake."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 14,
    "text": "Homogenates were centrifuged at 14,000 rpm for 15 min (4°C), and supernatants were used for ELISA analysis according the manufacturer’s instructions (Promega Corp., Madison, WI). Briefly, ninety-six-well plates were coated with a mouse monoclonal BDNF antibody overnight. Samples (300 μg protein) were added in duplicate onto each plate and serial dilutions of BDNF standard (0–500 pg/ml) were added to generate a standard curve. Plates were incubated for 2 hours, washed five times in Tris-buffered saline with Tween-20 (TBST), and reacted for an additional 2 hours in a solution containing a rabbit polyclonal BDNF antibody. Wells were washed five times with TBST, and a hydrogen peroxide solution was added together with a peroxidase substrate. Reactions were stopped by adding 1N hydrochloric acid and the absorbance was measured at 450 nm."
  },
  {
    "matched_frozen_surfaces": [
      "spine density"
    ],
    "paragraph_index": 15,
    "text": "For Golgi impregnation we used a commercially available kit (FD Neurotechnologies kit #SS201) according to the manufacturer’s instructions. Following two weeks incubation in Golgi-Cox solution, the tissue was sectioned on the transverse plane (100 μm) using a Vibratome. After visualizing impregnated cells, the sections were dehydrated in increasing concentrations of ethanol, cleared in Histoclear, and coverslipped under Permount. Cells were selected for analysis as described (Stranahan et al., 2007). Briefly, cells were required to exhibit a fully impregnated cell body, and dark brown or black dendrites, with sufficient separation from other labeled cells, and no apparent severed dendrites. Dendritic segments selected for analysis of spine density were on second-or third-order dendrites."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0061

Case: heldout_v1_008
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "cellular glucose uptake",
    "2-deoxyglucose uptake",
    "2-DG uptake"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_008",
  "context_qualifiers": [
    "skeletal muscle cells / myotubes"
  ],
  "frozen": true,
  "measurement_property_endpoint": "cellular glucose uptake",
  "measurement_target": "glucose uptake",
  "object": "glucose uptake",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "AMPK activation increases glucose uptake in skeletal muscle cells or myotubes.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "GLUT4 abundance/translocation alone does not automatically satisfy glucose uptake"
  ],
  "scientific_proposition_target_id": "heldout_v1_008:scientific_proposition:v1",
  "subject": "AMPK activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "Diverse Inhibitors of De Novo Purine Synthesis Promote AICAR-Induced AMPK Activation and Glucose Uptake in L6 Myotubes.",
  "pmid": "40793247",
  "pmcid": "PMC12341450",
  "doi": "10.1002/biof.70037"
}
```

Abstract:
Methotrexate, an immunosuppressant and anticancer drug, promotes glucose uptake and lipid oxidation in skeletal muscle via activation of AMP-activated protein kinase (AMPK). Methotrexate promotes AMPK activation by inhibiting 5-aminoimidazole-4-carboxamide ribonucleotide (ZMP) formyltransferase/inosine monophosphate (IMP) cyclohydrolase (ATIC), which converts ZMP, an endogenous purine precursor and an active form of the pharmacological AMPK activator AICAR, to IMP during de novo purine synthesis. In addition to methotrexate, inhibition of purine synthesis underpins the therapeutic effects of a number of commonly used immunosuppressive, anticancer, and antimicrobial drugs, raising the question of whether activation of AMPK in skeletal muscle could be a recurrent feature of these drugs. Using L6 myotubes, we found that AICAR-induced AMPK activation and glucose uptake were enhanced by inhibitors of the conversion of IMP to GMP (mycophenolate mofetil) or of IMP to AMP (alanosine) as well as by indirect inhibitors of human (trimetrexate) and bacterial ATIC (sulfamethoxazole). 6-Mercaptopurine, which inhibits the conversion of IMP to GMP and AMP, activated AMPK, increased glucose uptake, and suppressed insulin signaling, but did not enhance the effect of AICAR. As determined by measuring oxygen consumption rate, none of these agents suppressed mitochondrial function. Overall, our results indicate that IMP metabolism is a gateway for the modulation of AMPK and its metabolic effects in skeletal muscle cells.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12341450.xml
SHA-256: 0f287dee9d08c6cebf75dab7e2e163532c8055eb0b845c29b67d939ff3d28e4b

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "glucose uptake"
    ],
    "paragraph_index": 1,
    "text": "Pharmacological activation of AMP‐activated protein kinase (AMPK) 1 in skeletal muscle has emerged as a promising strategy for increasing glucose disposal, reducing insulin resistance, and alleviating hyperglycaemia in type 2 diabetes [1, 2]. Methotrexate, an immunosuppressant and antineoplastic drug [3, 4], promotes glucose uptake and lipid oxidation in skeletal muscle via activation of AMPK [5], alleviates glucose dysregulation in diabetic [6] and obese mice [7], and protects patients with rheumatoid and psoriatic arthritis against diabetes [8, 9]. Since methotrexate stimulates AMPK and its metabolic effects by inhibiting purine synthesis [5, 10, 11], we assumed that other inhibitors of purine metabolism, including commonly used immunosuppressant and antineoplastic drugs [12], might have a similar effect. By stimulating AMPK, inhibitors of purine metabolism, which are often used to treat inflammatory diseases and other conditions associated with glucose dysregulation [8, 12, 13, 14, 15, 16], could provide additional therapeutic benefit, especially over those immunosuppressants and antineoplastics that increase the risk of diabetes [17, 18]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 2,
    "text": "In skeletal muscle, methotrexate promotes AMPK activation, glucose uptake, and lipid oxidation induced by 5‐aminoimidazole‐4‐carboxamide ribonucleotide (ZMP) [5] (Figure 1A). ZMP is both an endogenous precursor of inosine monophosphate (IMP) in the de novo purine synthesis pathway [20, 21, 22, 23] and the active (phosphorylated) form of a widely used experimental AMPK activator, 5‐aminoimidazole‐4‐carboxamide ribofuranoside (AICAR) [24, 25, 26] (Figure 1A). As an AMP analogue, ZMP binds to AMPK and activates it directly [24, 26, 27], but its concentrations in skeletal muscle are physiologically low and may remain below the threshold for AMPK activation even in the presence of AICAR [5, 28, 29]. Methotrexate increases ZMP concentrations and facilitates AMPK activation by inhibiting 5‐aminoimidazole‐4‐carboxamide ribonucleotide formyltransferase/inosine monophosphate cyclohydrolase (ATIC) [5, 10, 30, 31], an enzyme that catalyzes the conversion of ZMP to IMP in the de novo purine synthesis pathway [22, 23]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation"
    ],
    "paragraph_index": 3,
    "text": "Once formed, IMP is used for the de novo synthesis of GMP or AMP (Figure 1A). Mycophenolate mofetil, an immunosuppressant, and 6‐mercaptopurine, an antineoplastic and immunosuppressant drug, inhibit IMP dehydrogenase (IMPDH) [19, 32, 33, 34], which catalyzes the first, rate‐limiting step, in the synthesis of GMP from IMP. 6‐Mercaptopurine also inhibits adenylosuccinate synthetase (ADSS) and adenylosuccinate lyase (ADSL) [32], which catalyze the synthesis of AMP from IMP. Inhibition of IMPDH by mycophenolic acid (the active form of mycophenolate mofetil) increased ZMP levels in cancer cells [35], suggesting that inhibitors of GMP and/or AMP synthesis suppress ZMP clearance and facilitate AMPK activation, mimicking the inhibition of ATIC by methotrexate [31]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "In the present study, we asked whether inhibitors of GMP (mycophenolate mofetil) [19, 34], AMP (alanosine) [41], or GMP and AMP synthesis (6‐mercaptopurine) [32, 33] and indirect inhibitors of human (trimetrexate) [30] or bacterial ATIC (sulfamethoxazole and trimethoprim) [40] mimic effects of methotrexate and promote AMPK activation and glucose uptake in cultured myotubes. Their effects on insulin signaling and mitochondrial respiration were also assessed."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 14,
    "text": "Glucose uptake was determined by measuring the uptake of tritium (3H)‐labeled 2‐deoxy‐glucose (2DG) as described [11]. Cells were washed with HEPES‐buffered saline (HBS: 140 mM NaCl, 20 mM HEPES, 5 mM KCl, 2.5 mM MgCl2, 1 mM CaCl2, pH 7.4 (adjusted with NaOH)), incubated in HBS with 10 μM 2DG (unlabelled) and 1 μCi/mL 2‐[1,2‐3H]‐DG for 10 min at 37°C, washed with cold PBS with 25 mM glucose, and lysed with 0.04% (w/v) SDS in water. Cell lysates were then analyzed for protein content with BCA protein assay or mixed with liquid scintillation cocktail and analyzed for radioactivity with MicroBeta TriLux scintillation counter (PerkinElmer). The amount of 2DG in samples was determined from the radioactivity of samples using a standard (known amount of 2‐[1,2‐3H]‐DG) and is expressed in pmol of 2DG/min/mg of proteins."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "glucose uptake"
    ],
    "paragraph_index": 18,
    "text": "Assessment of sensitivity of L6 cells to inhibitors of purine metabolism. A: Purine metabolism and AMPK. The purine precursor ZMP is an AMPK activator. Methotrexate was shown to promote fatty acid oxidation (FAO) and glucose uptake via activation of AMPK in skeletal muscle tissue or cells [3, 19]. Intermediates: 5,10‐CH2‐THF, N5,N10‐methylene THF; 10‐CHO‐THF, N10‐Formyl‐THF; AMP, adenosine monophosphate; DHF, dihydrofolate; dUMP, deoxyuridine monophosphate; dTMP, deoxythymidine monophosphate; FGAR, formylglycinamide ribonucleotide; GAR, glycinamide ribonucleotide; GMP, guanosine monophosphate; Hx, hypoxanthine; IMP, inosine monophosphate; PRA, phosphoribosylamine; PRPP, 5‐phosphoribosyl‐1‐pyrophosphate; SAICAR, N‐succinyl‐5‐aminoimidazole‐4‐carboxamide ribonucleotide; THF, tetrahydrofolate; Xan, xanthine; ZMP, 5‐aminoimidazole‐4‐carboxamide ribonucleotide. Enzymes: ACC, acetyl‐coenzyme A carboxylase; ADSL, adenylosuccinate lyase; ADSS, adenylosuccinate synthetase; AMPK, AMP‐activated protein kinase; ATIC, 5‐aminoimidazole‐4‐carboxamide ribonucleotide formyltransferase/inosine monophosphate cyclohydrolase; DHFR, dihydrofolate reductase; GART, glycinamide ribonucleotide formyltransferase; GMPS, GMP synthetase; GPAT, glutamine phosphoribosylpyrophosphate amidotransferase; IMPDH, IMP dehydrogenase; TS, thymidylate synthetase; XDH, xanthine oxidase. Inhibitors: ALA, alanosine; ALO, allopurinol; FAO, fatty acid oxidation; MMF, mycophenolate mofetil; MP, mercaptopurine; MTX, methotrexate; TMP, trimethoprim; TMX, trimetrexate. “P” on AMPK and ACC indicates phosphorylation. (B, C) L"
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:

### Packet heldout_rrpv1_0062

Case: heldout_v1_008
Ambiguity: HIGH

ScientificPropositionTargetV1:
```json
{
  "acceptable_endpoint_evidence": [
    "cellular glucose uptake",
    "2-deoxyglucose uptake",
    "2-DG uptake"
  ],
  "artifact_schema_version": "ScientificPropositionTargetV1",
  "case_id": "heldout_v1_008",
  "context_qualifiers": [
    "skeletal muscle cells / myotubes"
  ],
  "frozen": true,
  "measurement_property_endpoint": "cellular glucose uptake",
  "measurement_target": "glucose uptake",
  "object": "glucose uptake",
  "primary_evidence_required": true,
  "primary_proposition_meaning": "AMPK activation increases glucose uptake in skeletal muscle cells or myotubes.",
  "relation_family": "increases",
  "retrieval_membership_grants_compatibility": false,
  "scientific_boundaries": [
    "GLUT4 abundance/translocation alone does not automatically satisfy glucose uptake"
  ],
  "scientific_proposition_target_id": "heldout_v1_008:scientific_proposition:v1",
  "subject": "AMPK activation",
  "therapy": null
}
```

Publication:
```json
{
  "title": "CaMKK2 is not involved in contraction-stimulated AMPK activation and glucose uptake in skeletal muscle.",
  "pmid": "37380024",
  "pmcid": "PMC10362367",
  "doi": "10.1016/j.molmet.2023.101761"
}
```

Abstract:
The AMP-activated protein kinase (AMPK) gets activated in response to energetic stress such as contractions and plays a vital role in regulating various metabolic processes such as insulin-independent glucose uptake in skeletal muscle. The main upstream kinase that activates AMPK through phosphorylation of α-AMPK Thr172 in skeletal muscle is LKB1, however some studies have suggested that Ca2+/calmodulin-dependent protein kinase kinase 2 (CaMKK2) acts as an alternative kinase to activate AMPK. We aimed to establish whether CaMKK2 is involved in activation of AMPK and promotion of glucose uptake following contractions in skeletal muscle.
A recently developed CaMKK2 inhibitor (SGC-CAMKK2-1) alongside a structurally related but inactive compound (SGC-CAMKK2-1N), as well as CaMKK2 knock-out (KO) mice were used. In vitro kinase inhibition selectivity and efficacy assays, as well as cellular inhibition efficacy analyses of CaMKK inhibitors (STO-609 and SGC-CAMKK2-1) were performed. Phosphorylation and activity of AMPK following contractions (ex vivo) in mouse skeletal muscles treated with/without CaMKK inhibitors or isolated from wild-type (WT)/CaMKK2 KO mice were assessed. Camkk2 mRNA in mouse tissues was measured by qPCR. CaMKK2 protein expression was assessed by immunoblotting with or without prior enrichment of calmodulin-binding proteins from skeletal muscle extracts, as well as by mass spectrometry-based proteomics of mouse skeletal muscle and C2C12 myotubes.
STO-609 and SGC-CAMKK2-1 were equally potent and effective in inhibiting CaMKK2 in cell-free and cell-based assays, but SGC-CAMKK2-1 was much more selective. Contraction-stimulated phosphorylation and activation of AMPK were not affected with CaMKK inhibitors or in CaMKK2 null muscles. Contraction-stimulated glucose uptake was comparable between WT and CaMKK2 KO muscle. Both CaMKK inhibitors (STO-609 and SGC-CAMKK2-1) and the inactive compound (SGC-CAMKK2-1N) significantly inhibited contraction-stimulated glucose uptake. SGC-CAMKK2-1 also inhibited glucose uptake induced by a pharmacological AMPK activator or insulin. Relatively low levels of Camkk2 mRNA were detected in mouse skeletal muscle, but neither CaMKK2 protein nor its derived peptides were detectable in mouse skeletal muscle tissue.
We demonstrate that pharmacological inhibition or genetic loss of CaMKK2 does not affect contraction-stimulated AMPK phosphorylation and activation, as well as glucose uptake in skeletal muscle. Previously observed inhibitory effect of STO-609 on AMPK activity and glucose uptake is likely due to off-target effects. CaMKK2 protein is either absent from adult murine skeletal muscle or below the detection limit of currently available methods.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10362367.xml
SHA-256: 155b601f01d00862881920555f600384dd911c21882a124390d719b8dcf23cac

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase"
    ],
    "paragraph_index": 1,
    "text": "AMP-activated protein kinase (AMPK) is a vital energy sensor which functions to maintain cellular homeostasis through coordinating metabolic pathways in response to energetic stresses (e.g., contractions, hypoxia, mitochondrial poisoning) [1,2]. AMPK exists as heterotrimeric complexes comprised of catalytic α-subunits, regulatory β-subunits, and γ-subunits. There are multiple genes encoding two α-isoforms (α1/α2), two β-isoforms (β1/β2), and three γ-isoforms (γ1/γ2/γ3). The expression of AMPK isoforms varies among different cell types and tissues, with α1, β1, and γ1 being the most ubiquitously expressed. Assays of immunoprecipitated AMPK isoforms in mouse skeletal muscle revealed that the α2-containing complexes (α2β2γ1, α2β2γ3, α2β1γ1) account for ∼90% and ∼70% of the total AMPK trimers in glycolytic extensor digitorum longus (EDL) and oxidative soleus muscle, respectively [3]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 2,
    "text": "AMPK heterotrimers are active when a threonine residue (Thr172) within the activation loop of the α-subunit kinase domain is phosphorylated [4]. The α-Thr172-phosphorylated/activated form of AMPK can be maintained by the binding of AMP or ADP to the cystathionine β-synthase domains of the γ subunit [5,6]. Moreover, AMP can increase AMPK activity further through an allosteric mechanism [7]. In contrast, ATP antagonizes the effects of AMP and ADP, and this forms the basis by which AMPK can respond to cellular fluctuations of the AMP:ATP and ADP:ATP ratios during times of energy demand and maintain ATP at a constant level."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 3,
    "text": "The major upstream kinases phosphorylating α-Thr172 are Liver kinase B 1 (LKB1) and Ca2+/calmodulin-dependent protein kinase kinase 2 (CaMKK2) [8]. In skeletal muscle, we and others have provided genetic evidence using muscle-specific LKB1 knock-out (mLKB1 KO) mouse models that LKB1 is the primary upstream kinase to activate AMPK [[9], [10], [11]]. We and others also showed that LKB1 is required for muscle glucose uptake in response to strenuous contractions or pharmacological treatments that increase intracellular levels of AMP or its mimetic ZMP [[11], [12], [13]]. Although activity of α2-AMPK is ablated [10,11,13], α1-AMPK activity was largely [10,13] or residually [11] detectable in skeletal muscle tissues from mLKB1 KO mice. Some studies reported that mLKB1 KO mice retained an ability to activate α1-AMPK in skeletal muscle in response to treatment with 5-aminoimidazole-4-carboxamide riboside (AICAR, a cellular ZMP-raising pro-drug) and electrically-stimulated contractions ex vivo [10] or treadmill exercise in vivo [13], suggesting that there might be an alternative kinase regulating α1-AMPK."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "Both CaMKK1 and CaMKK2 isoforms were initially demonstrated to activate AMPK in cell-free assays [14]. However, subsequent studies revealed a predominant role for CaMKK2 as a physiological upstream kinase of AMPK in particular cell types (e.g., T cells, neuronal, and endothelial cells) that predominantly express α1-AMPK (reviewed in [8,15,16]). The pharmacological inhibition of CaMKK2 predominantly relies on the use of 7-Oxo-7h-benzimidazo-[2,1-a]benz[de]isoquinoline-7-one-3-carboxylic acid (known as STO-609), which inhibits CaMKK2 activity 5–10 fold more effectively than CaMKK1 activity in cell-free assays (IC50 value = ∼1 μM) [[17], [18], [19], [20], [21]]. In perfused rat hindlimb in vivo, STO-609 (5 μM) resulted in a significant inhibition of contraction-stimulated AMPK activation and glucose uptake in skeletal muscle [22]. However, in incubated mouse skeletal muscles ex vivo STO-609 (5 μM) inhibited contraction- stimulated AMPK activation and glucose uptake in one study [23] whereas in another study STO-609 (∼2.7 μM) had no effect on muscle glucose uptake or AMPKα (Thr172) phosphorylation [24]. While the on-target effects of STO-609 are compelling when using cells expressing STO-609-resistant CaMKK mutants [25], careful examinations have revealed that it also inhibits several other protein kinases with a similar potency to CaMKKs [19,20,26]. Notably, STO-609 inhibits AMPK with an IC50 of 1.7 μM in cell-free assays [19], which raises concerns regarding the interpretation of experiments studying the physiological roles of the CaMKK2-AMPK signaling pathway in intact cells"
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "In the current study, we aimed to address these limitations and establish whether CaMKK2 functions as an upstream activator of AMPK in response to contractions and mediates contraction-stimulated glucose uptake in skeletal muscle. To this end, we employed a recently developed potent and selective CaMKK2 inhibitor alongside a structurally related but inactive compound [28], as well as CaMKK2 KO mice."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 13,
    "text": "Heterotrimeric human AMPK FLAG-α2β1γ1 and FLAG-α2β2γ1, as well as human FLAG-CaMKK1 and FLAG-CaMKK2, were produced in mammalian cells as described [33,34]. For AMPK expression, the cells were triply transfected at 60% confluency using FuGene HD (Roche Applied Science) and 1 μg of pcDNA3 plasmid expression constructs for AMPK FLAG-α2, β1-Myc or β2-Myc, and HA-γ1. For CaMKK1 and CaMKK2 expression, the cells were transfected with either 1 μg of pcDNA3 FLAG-CaMKK1 or FLAG-CaMKK2 plasmid. After 48 h, the transfected cells were harvested by rinsing with ice-cold PBS, followed by rapid lysis using 500 μl of lysis buffer."
  }
]
```

Fields fulltext was expected to resolve:
["scientific proposition compatibility", "endpoint evidence and measurement", "context and biological-unit fit"]

ADJUDICATION
relevance_state:
matched_target_components:
mismatched_target_components:
fulltext_resolved_fields:
remaining_unresolved_fields:
contaminant_class:
rationale:
confidence:
reviewer_type:
