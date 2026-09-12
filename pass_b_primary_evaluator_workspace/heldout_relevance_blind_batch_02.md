# Held-out PASS B — relevance review

Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.
All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.
Do not calculate partial or running metrics.

Allowed relevance_state: DIRECTLY_RELEVANT, PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED, RELATED_BUT_WRONG_PROPOSITION, WRONG_ENDPOINT, WRONG_ENTITY, WRONG_EVIDENCE_MODE, WRONG_THERAPY, TOPIC_ONLY, INSUFFICIENT_SOURCE_EVIDENCE

### Packet heldout_rrpv1_0003

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
  "title": "P2RY13 Exacerbates Intestinal Inflammation by Damaging the Intestinal Mucosal Barrier via Activating IL-6/STAT3 Pathway.",
  "pmid": "35982893",
  "pmcid": "PMC9379400",
  "doi": "10.7150/ijbs.74304"
}
```

Abstract:
The pathogenesis of ulcerative colitis (UC) is unclear, while genetic factors have been confirmed to play an important role in its development. P2RY13 is a G protein-coupled receptor (GPCRs), which are involved in the pathogenesis of inflammation and immune disorders. According to GEO database analysis, we first observed that the expression of P2Y13 was increased in UC patients. Therefore, we sought to determine the role of P2Y13 in the development of colitis. Our data showed that P2RY13 was highly expressed in the inflamed intestinal tissues of UC patients. In mice, pharmacological antagonism of P2Y13 can significantly attenuate the intestinal mucosal barrier disruption. In LPS-induced NCM460 cell, knockdown or pharmacological inhibition of P2RY13 increased the expression of intestinal tight junction protein and reduced apoptosis. In addition, we found that the effect of P2Y13 on colitis is related to the activation of the IL-6/STAT3 pathway. Activation of P2Y13 increases IL-6 expression and promotes STAT3 phosphorylation and nuclear transport. Deletion of the STAT3 gene in the intestinal epithelial cells of mice significantly mitigated the exacerbation of colitis due to P2Y13 activation. Thus, P2Y13 can aggravate intestinal mucosal barrier destruction by activating the IL-6/STAT3 pathway. P2Y13 might be a potential drug target for UC.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9379400.xml
SHA-256: 5bbc1bb0a00ebf03070549d0531ba068d1f97ffd9dc903e3ab69cbccf7d93aa6

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 3,
    "text": "P2RY13 is a Gi protein-coupled receptor encoded by 354 amino acids. It is highly sensitive to ADP but can be activated by ADP and ATP 15. Gene deletion or drug inhibition of P2RY13 can relieve asthma via inhibiting IL-33 and HMGB1 release 11. MRS2211, an antagonist of P2RY13, inhibits LPS-induced IL-6 production in KUP5 cells and has the potential to downregulate hepatic inflammation 16. Evidence reveals the pivotal role of P2RY13 in inflammation and immune dysregulation. However, the contribution of P2RY13 to the development of IBD remains unclear."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 4,
    "text": "In this study, the Gene Expression Synthesis (GEO) dataset showed that P2RY13 was upregulated in the intestinal tissues of patients with UC. Furthermore, we found that MRS2211-induced inhibition of P2RY13 activity significantly alleviated dextran sulfate sodium (DSS)-induced colitis. Our study demonstrated that P2RY13 played a key role in mediating UC development through disruption of the intestinal epithelial barrier via IL-6/STAT3 pathway activation."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 6,
    "text": "Animal experiments were approved by the Animal Care and Use Committee of Renmin Hospital of Wuhan University (PR China; approval number: 20181001). STAT3-deficient mice in IEC (STAT3△IEC) were produced by crossing STAT3 fl/fl (fl/fl) mice with Villin-Cre mice (GemPharmetech CO., Ltd, Nanjing, China). C57BL/6J WT mice were obtained from GemPharmetech CO., Ltd."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 10,
    "text": "Total protein was extracted from tissues and cells using the lysis buffer (50 mM Tris-HCl pH 7.4,1% NP-40, 0.5% Na-deoxycholate, 0.1% SDS,150 mM NaCl, 2 mM EDTA, 50 Mm NaF) with protease inhibitor. Extract nuclear proteins from cultured cells using a Nuclear and Cytoplasmic Protein Extraction Kit (P0027, Beyotime) according to manufacturer's instructions. The protein was carried out by 10% sodium dodecyl sulfate polyacrylamide gel electrophoresis (SDS-PAGE) and then transferred to the PVDF membrane (Bio-Rad Laboratories, Hercules, CA, USA). The membrane was sealed with 5% skim milk powder for 2h and then incubated at 4° in TBST diluted primary antibody for 8-12h. The membranes were incubated with TBST diluted secondary antibodies at room temperature for 1h. ChemiDocTMXRS+ system (BIO-RAD, USA), was used to detect protein signal. The primary antibodies used in this study: Bax (#50599-2-Ig,proteintech), STAT3 (#124H6,CST), P-STAT3 (#D3A7,CST), P2RY13 (#APR-017,Alomone labs), ZO-1 (#ab276131, abcam), LaminB (#12987-1-AP, proteintech), β-actin (#66009-1-Ig, proteintech), occluding (#91131,CST), Bcl-2 (#26593-1-AP, proteintech) and GAPDH (#60004-1-Ig, proteintech)."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 11,
    "text": "Paraffin-embedded mouse intestinal tissue was cut into 3 μm slices. The sections were stained by immunohistochemistry, using an UltraSensitive™ SP (mouse/rabbit) IHC kit (Maxib, Fuzhou, China), according to the manufacturer's instructions. AB-PAS was performed using an AB-PAS staining kit (Solarbio.G1285, Solarbio) according to the manufacturer's instructions. For IHC,primary antibodies against the following targets were used: ZO-1 (#ab276131, abcam), MUC-2 (#ab272692, abcam), P2RY13 (#APR-017, Alomone labs), STAT3 (#124H6, CST)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 19,
    "text": "To further confirm that the promoting effect of P2RY13 on UC development, we next assessed the effect of P2RY13 pharmacological inhibition on the development of DSS-induced colitis. In our study, the mice treated with MRS2211 (specific inhibitor of P2RY13) exhibited a slower slower weight loss (Figure 3A), a lower Disease activity index (Figure 3B), significantly inhibited cecal edema and colon shortening (Figure 3C and 3F) and a lower histological score (Figure 3E), while MRS2211 alone has little influence on mice. MRS2211 treatment alleviated inflammation, epithelial damage and ulceration caused by DSS (Figure 3D). In addition, the mRNA expression of inflammatory cytokines IL-6, IL-1β and TNF-α was reduced in mice treated with MRS2211+ DSS, compared with mice treated with DSS, especially IL-6 expression, and the expression of mRNA encoding the IL-10 was increased (Figure 3G). These results demonstrate that activation of P2RY13 can exacerbate DSS-induced colitis."
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

### Packet heldout_rrpv1_0004

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
  "title": "Astrocytic DLL4-NOTCH1 signaling pathway promotes neuroinflammation via the IL-6-STAT3 axis.",
  "pmid": "39390606",
  "pmcid": "PMC11468415",
  "doi": "10.1186/s12974-024-03246-w"
}
```

Abstract:
Under neuroinflammatory conditions, astrocytes acquire a reactive phenotype that drives acute inflammatory injury as well as chronic neurodegeneration. We hypothesized that astrocytic Delta-like 4 (DLL4) may interact with its receptor NOTCH1 on neighboring astrocytes to regulate astrocyte reactivity via downstream juxtacrine signaling pathways. Here we investigated the role of astrocytic DLL4 on neurovascular unit homeostasis under neuroinflammatory conditions. We probed for downstream effectors of the DLL4-NOTCH1 axis and targeted these for therapy in two models of CNS inflammatory disease. We first demonstrated that astrocytic DLL4 is upregulated during neuroinflammation, both in mice and humans, driving astrocyte reactivity and subsequent blood-brain barrier permeability and inflammatory infiltration. We then showed that the DLL4-mediated NOTCH1 signaling in astrocytes directly drives IL-6 levels, induces STAT3 phosphorylation promoting upregulation of astrocyte reactivity markers, pro-permeability factor secretion and consequent blood-brain barrier destabilization. Finally we revealed that blocking DLL4 with antibodies improves experimental autoimmune encephalomyelitis symptoms in mice, identifying a potential novel therapeutic strategy for CNS autoimmune demyelinating disease. As a general conclusion, this study demonstrates that DLL4-NOTCH1 signaling is not only a key pathway in vascular development and angiogenesis, but also in the control of astrocyte reactivity during neuroinflammation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11468415.xml
SHA-256: 100497287d5754b4b800b20a05486b7abc4669af4683eca6f6c3b08506df0cdc

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 6,
    "text": "Interestingly, activation of the NOTCH1-STAT3 axis in EAE has been shown to control the production of inflammatory cytokines by reactive astrocytes via the long non-coding (lnc) RNA Gm13568, which has also been implicated in MS pathogenesis. Precisely, knockdown of the endogenous lncRNA Gm13568 remarkably inhibits the NOTCH1 expression, astrocytosis, and the phosphorylation of STAT3 as well as the production of inflammatory cytokines and chemokines (IL-6, TNF-α, IP-10) in IL-9-reactive astrocytes. More importantly, inhibiting Gm13568 with lentiviral vector in astrocytes ameliorates significantly inflammation and demyelination in EAE mice, therefore delaying the EAE process [13]. Moreover, the NOTCH1-STAT3 pathway has similarly been identified as an effector of inflammation-induced differentiation of neurotoxic A1 astrocytes in a model of spinal cord injury (SCI) and glial scar formation [23, 24]."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 9,
    "text": "We first tested the role of astrocytic DLL4 on neurovascular unit homeostasis under neuroinflammatory conditions. We then probed for downstream effectors of the DLL4-NOTCH1 axis and targeted these for therapy in two models of CNS inflammatory disease. Here, we demonstrate that astrocytic DLL4 is upregulated during neuroinflammation, both in mice and humans, driving astrocyte reactivity and subsequent blood-brain barrier permeability and inflammatory soluble factor and immune cell infiltration. We then show that the DLL4-mediated NOTCH1 signaling in astrocytes directly drives IL-6 levels, induces STAT3 phosphorylation promoting upregulation of astrocyte reactivity markers, pro-permeability factor secretion and consequent blood-brain barrier destabilization. Finally we reveal that blocking DLL4 with antibodies improves EAE symptoms in mice, identifying a potential novel therapeutic strategy for CNS autoimmune demyelinating disease."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 10,
    "text": "In summary, we report here for the first time that the DLL4-NOTCH1 axis acts as a key driver of astrocyte reactivity during neuroinflammation via upregulation of the IL-6-STAT3-TYMP/VEGFA signaling pathway, leading to disruption of the neurovascular unit, increased immune infiltration into the CNS parenchyma and worsened neuropathology. More generally, this study demonstrates that DLL4-NOTCH1 signaling is not only a key pathway in vascular development and angiogenesis [27], but also in the control of astrocytic reactivity during neuroinflammation."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "interleukin-6"
    ],
    "paragraph_index": 27,
    "text": "Transcriptional profiling of isolated astrocyte lysates from EAE induced Dll4ACKOC and control littermates showed that 1558 genes were downregulated in EAE induced Dll4ACKOC mice while 874 genes were upregulated (Supplemental Fig. 2, A). Notably, among the downregulated genes, a wide cohort of transcripts linked to reactive astrocyte markers (Fig. 3, H). Specifically, this approach identified, among others, Vim (vimentin) and Serpina3n transcripts as downregulated in astrocyte samples from EAE induced Dll4ACKOC mice (Fig. 3, H). Importantly, these two factors, like all the genes highlighted in the heatmap (Fig. 3, H), have been identified as markers of astrocytic reactivity in the international consensus published in 2021 in the journal nature neuroscience [28]. The pro-inflammatory cytokine Il-6 (interleukin-6) transcripts are also downregulated in astrocyte samples from EAE induced Dll4ACKOC mice (Fig. 3, H). Surprisingly, Gfap transcripts weren’t modulated in astrocyte samples from EAE induced Dll4ACKOC mice (cf. transcriptional profiling of isolated astrocyte lysate full table, additional file 1). However, in examining VIM and GFAP protein expression by western blot, in spinal cord lysates from Freund adjuvant and EAE induced Dll4ACKOC mice compared to control littermates; we showed that both factors are downregulated in Dll4ACKOC mice (Fig. 3I-K). Moreover, in examining VIM and GFAP protein expression by immunofluorescence on spinal cord sections from EAE-induced Dll4ACKOP mice and control littermates and from EAE-induced Dll4ACKOC mice and control littermates, we conf"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 31,
    "text": "Fig. 4DLL4-NOTCH1 signaling in reactive astrocytes promotes IL-6 transcription via a direct interaction with NICD. (A) Notch1ACKOC mice and control mice induced with EAE were scored daily according to a widely-used 5-point scale (EAE scoring: 1 limp tail; 2 limp tail and weakness of hind limb; 3 limp tail and complete paralysis of hind legs; 4 limp tail, complete hind leg and partial front leg paralysis). Statistical significance was determined by using a 2 ways Anova test followed by the Holm-Sidak’s multiple comparisons test, (*: p ≤ 0.05; **: p ≤ 0.01; ***: p ≤ 0.001 ****: p ≤ 0.0001). (Notch1ACKOC n = 15, WT n = 16). (B) NA were cultured until confluence and treated with IL-1β 10ng/mL for 24 h. A Chromatin Immuno-Precipitation (ChiP) was then performed on NA lysates using NICD antibody versus IgG controls to pull-down. IL-6 DNA expression level was then quantified by PCR. (C-G) NA were cultured until 70% confluence. They were then transduced with an empty lentivirus (6.21 108 PFU/mL) versus a DLL4-expressing lentivirus (4.14 108 PFU/mL) and harvested 24 h post transduction (n = 11). (C) HES1, (D) HEY1, (E) HEY2, (F) IL-6 and (G) DLL4 expression were quantified by qRT-PCR. β-ACTIN was used as a reference. Statistical significance was determined by using a Mann-Whitney U test"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 32,
    "text": "DLL4-NOTCH1 signaling in reactive astrocytes promotes IL-6 transcription via a direct interaction with NICD. (A) Notch1ACKOC mice and control mice induced with EAE were scored daily according to a widely-used 5-point scale (EAE scoring: 1 limp tail; 2 limp tail and weakness of hind limb; 3 limp tail and complete paralysis of hind legs; 4 limp tail, complete hind leg and partial front leg paralysis). Statistical significance was determined by using a 2 ways Anova test followed by the Holm-Sidak’s multiple comparisons test, (*: p ≤ 0.05; **: p ≤ 0.01; ***: p ≤ 0.001 ****: p ≤ 0.0001). (Notch1ACKOC n = 15, WT n = 16). (B) NA were cultured until confluence and treated with IL-1β 10ng/mL for 24 h. A Chromatin Immuno-Precipitation (ChiP) was then performed on NA lysates using NICD antibody versus IgG controls to pull-down. IL-6 DNA expression level was then quantified by PCR. (C-G) NA were cultured until 70% confluence. They were then transduced with an empty lentivirus (6.21 108 PFU/mL) versus a DLL4-expressing lentivirus (4.14 108 PFU/mL) and harvested 24 h post transduction (n = 11). (C) HES1, (D) HEY1, (E) HEY2, (F) IL-6 and (G) DLL4 expression were quantified by qRT-PCR. β-ACTIN was used as a reference. Statistical significance was determined by using a Mann-Whitney U test"
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

### Packet heldout_rrpv1_0013

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
  "title": "Multiple Cathepsins Promote Pro-IL-1β Synthesis and NLRP3-Mediated IL-1β Activation.",
  "pmid": "26195813",
  "pmcid": "PMC4530060",
  "doi": "10.4049/jimmunol.1500509"
}
```

Abstract:
Sterile particles induce robust inflammatory responses that underlie the pathogenesis of diseases like silicosis, gout, and atherosclerosis. A key cytokine mediating this response is IL-1β. The generation of bioactive IL-1β by sterile particles is mediated by the NOD-like receptor containing a pyrin domain 3 (NLRP3) inflammasome, although exactly how this occurs is incompletely resolved. Prior studies have found that the cathepsin B inhibitor, Ca074Me, suppresses this response, supporting a model whereby ingested particles disrupt lysosomes and release cathepsin B into the cytosol, somehow activating NLRP3. However, reports that cathepsin B-deficient macrophages have no defect in particle-induced IL-1β generation have questioned cathepsin B's involvement. In this study, we examine the hypothesis that multiple redundant cathepsins (not just cathepsin B) mediate this process by evaluating IL-1β generation in murine macrophages, singly or multiply deficient in cathepsins B, L, C, S and X. Using an activity-based probe, we measure specific cathepsin activity in living cells, documenting compensatory changes in cathepsin-deficient cells, and Ca074Me's dose-dependent cathepsin inhibition profile is analyzed in parallel with its suppression of particle-induced IL-1β secretion. Also, we evaluate endogenous cathepsin inhibitors cystatins C and B. Surprisingly, we find that multiple redundant cathepsins, inhibited by Ca074Me and cystatins, promote pro-IL-1β synthesis, and to our knowledge, we provide the first evidence that cathepsin X plays a nonredundant role in nonparticulate NLRP3 activation. Finally, we find cathepsin inhibitors selectively block particle-induced NLRP3 activation, independently of suppressing pro-IL-1β synthesis. Altogether, we demonstrate that both small molecule and endogenous cathepsin inhibitors suppress particle-induced IL-1β secretion, implicating roles for multiple cathepsins in both pro-IL-1β synthesis and NLRP3 activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4530060.xml
SHA-256: 3d46f0845c183ebed95bf8657fbf1f797c2b2232355b26e0d834b520c4089d30

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 1,
    "text": "Sterile particles induce robust inflammatory responses that underlie the pathogenesis of many diseases. These pathogenic particles are diverse, and include silica (1–4), which causes silicosis, monosodium urate (5), the etiologic agent in gout, and cholesterol crystals (CC) (6, 7), which are thought to contribute to the pathogenesis of atherosclerosis. Importantly, the sterile inflammatory response and resultant diseases caused by these particles all involve signaling through the interleukin-1 receptor, IL-1R1 (8, 9). While IL-1R1 can be stimulated by either of two cytokines, IL-1α or IL-1β, it has been shown that IL-1β plays a pivotal role in disease pathogenesis (10) because it not only directly stimulates IL-1R1-dependent inflammatory signaling, but is also needed for the secretion of IL-1α from cells (11). Therefore, it is important to understand the exact mechanisms underlying the generation and secretion of active IL-1β. However, this process is still incompletely understood and the focus of the present report."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "The generation of biologically active IL-1β is highly regulated and usually proceeds in two distinct steps (12, 13). The first step (Signal 1 or “priming”) is initiated when cells such as macrophages are stimulated by certain cytokines, pathogen-associated molecular patterns (PAMPs), or danger-associated molecular patterns (DAMPs). Signal 1 leads to the nuclear translocation of NF-κB, which then stimulates the synthesis of biologically inactive pro-IL-1β and, among other things, NOD-like receptor containing a pyrin domain 3 (NLRP3), a protein important for IL-1β activation. The second step (Signal 2 or “activation”) induces the formation of a multimolecular complex, known as the inflammasome. Inflammasomes are composed of a sensor protein, an adaptor protein, apoptosis-associated speck-like protein containing a CARD (ASC), and an executioner protease, caspase-1. Each inflammasome sensor detects distinct stimuli, thereby initiating multimerization and activating caspase-1, which then cleaves pro-IL-1β and facilitates the secretion of bioactive mature IL-1β. Among the known inflammasomes, the NLRP3 inflammasome is unique. While all inflammasomes rely on the availability of a newly-synthesized pool of pro-IL-1β, basal levels of NLRP3 itself are limiting, making priming especially critical for de novo NLRP3 transcription and subsequent activation (14, 15). Moreover, the NLRP3 inflammasome is the exclusive mediator of IL-1β activation in response to sterile particles (1–7)."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 3,
    "text": "While the NLRP3 inflammasome is located in the cytosol, how this intracellular complex senses the presence of extracellular particles has been of considerable interest. It has been shown that internalization of particles by phagocytosis is a first essential step in activating the NLRP3 inflammasome (2). Multiple mechanisms have been proposed as to how particles in phagosomes then lead to NLRP3 inflammasome activation, including lysosomal membrane disruption (LMD) (2, 3, 6, 7, 13, 16–29), potassium efflux (1, 4, 7, 21, 29–37), and the generation of reactive oxygen species (ROS) (1, 27, 29, 30, 32, 36, 38–40), among various other mechanisms (Reviewed (12)). All of these pathways may contribute to this process. In support of the LMD model, it has been shown that particles like silica, CC and the adjuvant alum can cause LMD (2, 6, 7), leading to the leakage of the lysosomal cysteine protease cathepsin B into the cytosol, where this protease is thought to activate NLRP3 through an as yet undescribed mechanism. Consistent with this model, particle-induced activation of the NLRP3 inflammasome is blocked by inhibitors of lysosomal acidification (cathepsins are optimally active in acidic conditions) and inhibitors of cathepsin B. However, the requirement for cathepsin B in this process is controversial."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "A role for cathepsin B in NLRP3 activation is supported by a number of studies showing that Ca074Me, an inhibitor reported to be specific for cathepsin B, suppresses IL-1β activation induced by particulate and non-particulate stimuli (2, 7, 17, 20, 21, 25–29, 41–46). However, despite a few subsequent studies showing that cathepsin B or L-deficient macrophages show partial impairment of this response (6, 25, 41), several follow-up studies have found that responses are intact in these same mutant cells (31, 42, 47). Thus, it has become unclear whether the efficacy of Ca074Me is really a result of cathepsin B inhibition, or whether this is an off-target effect. Indeed, there are there are several reports demonstrating that Ca074Me inhibits other cathepsins as well (48–52). Therefore, one hypothesis proposed to explain the discrepancy between Ca074Me and genetic models is that multiple cathepsins, which are a highly conserved family of proteases, play redundant roles in NLRP3 activation (53). Redundancy of cathepsins B and L has been demonstrated in a mouse model, where deficiency of both results in neonatal mortality, while deficiency of either alone does not (54). Similar redundancy also been observed in mouse cancer models showing upregulation of cathepsin X when cathepsin B is knocked out (55). However, the role of redundant cathepsins has not been examined in the context of NLRP3 activation and remains an open question."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "Here, we utilize genetic inactivation of multiple cathepsins, together with exogenous and endogenous inhibitors of these proteases, and an activity-based probe to investigate the role of cathepsins in NLRP3-dependent particle-induced IL-1β secretion. This analysis reveals that multiple cathepsins indeed contribute to IL-1β secretion. Surprisingly, our data also demonstrate that cathepsins contribute, not only to the inflammasome-mediated cleavage of pro-IL-1β into mature IL-1β (Signal 2), but also, to the priming step of pro-IL-1β synthesis (Signal 1). In addition, we found a unique role for cathepsin X in nigericin-induced NLRP3 activation, a protease not previously implicated in the IL-1 response. Together, these data clarify the contribution of cathepsins to particle-induced IL-1β responses and define a previously unappreciated role for cathepsins and their inhibitors in regulating pro-IL-1β synthesis. In doing so, this study provides insight into the mechanistic regulation of IL-1β production and points to cathepsins as unique therapeutic targets for controlling particle-induced sterile inflammatory responses."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "Antibodies for Western Blots were against mouse IL-1β (R&D Systems), caspase-1 p10 (sc-514; Santa Cruz Biotechnology), NLRP3 (Cryo2; Enzo Life Sciences), β-actin (C4; Santa Cruz Biotechnology) and GAPDH (6C5; EMD Millopore). ELISA kits were purchased for mouse IL-1β (BD Biosciences), pro-IL-1β and TNF-α (eBioscience). Ultrapure LPS was from Salmonella minnesota (Invivogen). Poly(deoxyadenylic-deoxythymidylic) acid and nigericin were purchased from Sigma-Aldrich (St. Louis, MO). Silica crystals (MIN- U-SIL 15) were obtained from U.S. Silica (Frederick, MD). Cholesterol crystals were synthesized by acetone supersaturation and cooling (6), Alum (Imject alum adjuvant; a mixture of aluminum hydroxide and magnesium hydroxide) was from Pierce Biotechnology, and Leu-Leu-OMe-HCl was from Chem-Impex International. ZVAD-FMK and Ca-074-Me were from Enzo Life Sciences and K777 was initially gifted to us by Stephanie A. Robertson and James H. McKerrow at UCSF, and further stocks obtained through services from the NHLBI’s SMARTT Program. Lipofectamine 2000, RNAiMax and all siRNA smart pools were from Life Technologies and Endoporter was from Gene Tools."
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

### Packet heldout_rrpv1_0014

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
  "title": "Zinc depletion regulates the processing and secretion of IL-1β.",
  "pmid": "24481454",
  "pmcid": "PMC4040701",
  "doi": "10.1038/cddis.2013.547"
}
```

Abstract:
Sterile inflammation contributes to many common and serious human diseases. The pro-inflammatory cytokine interleukin-1β (IL-1β) drives sterile inflammatory responses and is thus a very attractive therapeutic target. Activation of IL-1β in sterile diseases commonly requires an intracellular multi-protein complex called the NLRP3 (NACHT, LRR, and PYD domains-containing protein 3) inflammasome. A number of disease-associated danger molecules are known to activate the NLRP3 inflammasome. We show here that depletion of zinc from macrophages, a paradigm for zinc deficiency, also activates the NLRP3 inflammasome and induces IL-1β secretion. Our data suggest that zinc depletion damages the integrity of lysosomes and that this event is important for NLRP3 activation. These data provide new mechanistic insight to how zinc deficiency contributes to inflammation and further unravel the mechanisms of NLRP3 inflammasome activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4040701.xml
SHA-256: 53067d56eabf730b9bfed6bdb1d6ceec93f7a82069ae86dfa0ce026b56c5a6fc

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 1,
    "text": "Inflammation is a protective host response required for resistance to infection. However, inflammation that occurs in response to tissue injury in the absence of pathogen is considered sterile, and can contribute to damage.1 Sterile inflammation is driven by the pro-inflammatory cytokines of the interleukin-1 (IL-1) family.1 IL-1β is a master cytokine central to the damaging inflammatory response in a range of major human diseases.2 For this reason, understanding the mechanisms of IL-1β production is a crucial area of research that may lead to the identification of new therapeutic targets and therapies. IL-1β is produced by macrophages as a 31-kDa precursor called pro-IL-1β. Pro-IL-1β is expressed in response to pathogen-associated molecular patterns or damage-associated molecular patterns (DAMPs) that bind to pattern recognition receptors (PRRs) on the macrophage to upregulate pro-inflammatory gene expression.3, 4 Pro-IL-1β is inactive and remains intracellular until a further pathogen-associated molecular pattern or DAMP stimulation activates cytosolic PRRs, often of the NOD-like receptor family, to form large multi-protein complexes called inflammasomes.5 These complexes consist of the PRR, pro-caspase-1, and depending upon the PRR, an adaptor protein called ASC (apoptosis-associated speck-like protein containing a caspase recruitment domain), that interact via homotypic interactions between caspase activation and recruitment and pyrin (PYD) domains.5 Of the inflammasomes identified to-date, the best characterised and most relevant to sterile inflammatory responses is fo"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "We reported previously an interaction between Zn2+ and caspase-1-dependent processing and release of IL-1β.15 A brief 15 min incubation of lipopolysacharide (LPS)-primed peritoneal macrophages with the Zn2+ chelator TPEN (N,N,N',N'-Tetrakis-(2–pyridylmethyl) ethylenediamine) inhibits IL-1β release in response to NLRP3 inflammasome agonists ATP and nigericin.15 However, here we have discovered that sustained Zn2+ depletion acts as a stimulus for the NLRP3 inflammasome. These data provide valuable insights into regulation of the NLRP3 inflammasome, and the mechanisms through which Zn2+ deficiency may contribute to inflammatory disease."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "We have previously reported that brief (15 min) incubation of LPS-primed mouse peritoneal macrophages with TPEN completely inhibits ATP- and nigericin-induced caspase-1 activation and secretion of IL-1β.15 We discovered that this was probably due to an inhibition of the pannexin-1 hemichannel. To test whether these data are relevant to inflammation in vivo, adult C57BL/6 mice were injected intraperitoneally (i.p.) with LPS (5 mg/kg) followed by TPEN (1 or 10 mg/kg) 1 h later, with peritoneal lavages recovered 3 h following TPEN administration. Levels of IL-1β and of another pro-inflammatory cytokine, IL-6, in the lavage fluid were analysed by ELISA. In contrast to our previous in vitro data,15 TPEN in vivo was pro-inflammatory, increasing the levels of both IL-1β and IL-6 (Figures 1a and b)."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "We therefore asked the question whether, in contrast to our report on the effects of short-term TPEN treatment on NLRP3 inflammasome activation,15 sustained Zn2+ depletion with TPEN could activate IL-1β processing and release. To test whether sustained (4 h) Zn2+ depletion modifies the production and secretion of IL-1β directly, we treated cultured mouse primary peritoneal macrophages with TPEN (0–10 μM) or dimethyl sulfoxide (DMSO; 0–0.5%) for 4 h and measured the levels of IL-1β in cell lysates and culture supernatants by ELISA. Under these conditions TPEN did not induce significant expression or release of IL-1β (data not shown). After priming cultured macrophages with LPS (1 μg/ml, 2 h), TPEN treatment (10 μM, 4 h) induced the release of mature (17 kDa) IL-1β (Figure 2aii, iii), and caused cell death (Figure 2ai). This is consistent with models of NLRP3-inflammasome-dependent IL-1β secretion where an initial priming stimulus is required to induce the expression of pro-IL-1β and the PRR NLRP3.16 The effect of TPEN on cell death and IL-1β processing and release was specific to a depletion of Zn2+ as 4 h incubation with selective copper (TTM, ammonium tetrathiomolybdate) or iron (SIH, salicylaldehyde isonicotinoyl hydrazone) chelators had no effect on either parameter (Figure 2a). The addition of ZnCl2 (50 μM) to TPEN-treated LPS-primed macrophage cultures reduced cell death and inhibited IL-1β release (Figure 2b). Another Zn2+ chelator (DTPA, diethylenetriaminepentaacetic acid17) also induced the release of IL-1β (Figure 2c). We confirmed that the addition of TPEN quenche"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "To investigate the mechanism through which TPEN induced IL-1β release, we initially investigated whether release was dependent upon caspase-1 or caspase-8. TPEN induces tumour cell death by causing the degradation of X-linked inhibitor of apoptosis protein (XIAP),18, 19 and inhibitor of apoptosis protein inhibitors induce IL-1β processing via both NLRP3/caspase-1 and caspase-8-dependent mechanisms.20 Once activated caspase-8 can cleave pro-IL-1β directly at the same site as caspase-1, and induce secretion of the mature form.20, 21 Cell death can also induce the release of IL-1β from macrophages that is dependent upon caspase-8, but is independent of inflammasomes.22 Thus, we investigated whether TPEN-induced IL-1β processing and secretion were dependent on caspase-1 or caspase-8. Treatment of LPS-primed primary peritoneal macrophages with TPEN resulted in the loss of XIAP and an activation of caspase-8 (Figure 3ai). The extracellular Zn2+ chelator DTPA and the Zn2+ ionophore pyrithione also induced a loss of XIAP and an activation of caspase-8 (Figure 3ai, ii). TPEN treatment also induced activation of caspase-1, as seen by the appearance of the active caspase-1 subunit (10 kDa) in TPEN-treated culture supernatants (Figure 3aiii). This activation of caspase-1 was inhibited by the addition of 1 μM ZnPyr confirming the Zn2+ dependence of this effect. Thus, from these data it is clear that Zn2+ depletion activated both caspase-1 and caspase-8. To determine which of these caspases were involved in TPEN-induced IL-1β processing and release, we used selective caspase-1 and caspas"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 7,
    "text": "Caspase-1 activation is regulated by multi-protein complexes called inflammasomes. The NLRP3 inflammasome is generally regarded as a sensor of sterile injury, and given that TPEN is a sterile stimulus we hypothesised that TPEN-induced IL-1β release occurred through activation of the NLRP3 inflammasome. We reported recently that PP1/PP2A phosphatase inhibitors such as calyculin A (CA) and okadaic acid are potent inhibitors of multiple inflammasomes.23 Incubation of LPS-primed primary peritoneal macrophages with 10 or 50 nM CA completely inhibited TPEN-induced IL-1β processing and release (Figure 4a), consistent with our previous observations on inflammasome inhibition.23 To test the involvement of NLRP3, we incubated LPS-primed peritoneal macrophages with the NLRP3 inflammasome inhibitor glyburide,24 which also significantly inhibited TPEN-induced IL-1β release (Figure 4b). When treated with TPEN, macrophages from NLRP3 KO mice secreted significantly less IL-1β compared with WT macrophages, although cell death responses were not affected (Figure 4c). Likewise, macrophages isolated from ASC KO mice also secreted significantly less IL-1β than WT in response to TPEN (Figure 4d). Together, these data strongly suggest that Zn2+ depletion activates the processing and secretion of IL-1β, which is at least partially via a NLRP3-inflammasome/caspase-1-dependent pathway."
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

### Packet heldout_rrpv1_0023

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
  "title": "Oxy210, a Semi-Synthetic Oxysterol, Inhibits Profibrotic Signaling in Cellular Models of Lung and Kidney Fibrosis.",
  "pmid": "36678611",
  "pmcid": "PMC9862207",
  "doi": "10.3390/ph16010114"
}
```

Abstract:
Oxy210, a semi-synthetic oxysterol derivative, displays cell-selective inhibition of Hedgehog (Hh) and transforming growth factor beta (TGF-β) signaling in epithelial cells, fibroblasts, and macrophages as well as antifibrotic and anti-inflammatory efficacy in models of liver fibrosis. In the present report, we examine the effects of Oxy210 in cellular models of lung and kidney fibrosis, such as human lung fibroblast cell lines IMR-90, derived from healthy lung tissue, and LL97A, derived from an idiopathic pulmonary fibrosis (IPF) patient. In addition, we examine the effects of Oxy210 in primary human renal fibroblasts, pericytes, mesangial cells, and renal tubular epithelial cells, known for their involvement in chronic kidney disease (CKD) and kidney fibrosis. We demonstrate in fibroblasts that the expression of several profibrotic TGF-β target genes, including fibronectin (FN), collagen 1A1 (COL1A1), and connective tissue growth factor (CTGF) are inhibited by Oxy210, both at the basal level and following TGF-β stimulation in a statistically significant manner. The inhibition of COL1A1 gene expression translated directly to significantly reduced COL1A1 protein expression. In human primary small airway epithelial cells (HSAECs) and renal tubular epithelial cells, Oxy210 significantly inhibited TGF-β target gene expression associated with epithelial-mesenchymal transition (EMT). Oxy210 also inhibited the proliferation of fibroblasts, pericytes, and mesangial cells in a dose-dependent and statistically significant manner.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9862207.xml
SHA-256: 56482fa37b0c05b2c82733f336093125aa3822000f33cfce1b7c3fa90f789dec

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 2,
    "text": "Myofibroblasts are specialized fibrotic cells with contractile properties, characterized by overexpression of alpha-smooth muscle actin, chemotactic factors, and increased rates of cell proliferation [2]. Myofibroblasts are often derived from quiescent fibroblast progenitors in the connective tissues that migrate toward sites of injury when stimulated by various paracrine and autocrine factors [3]. However, in a profibrotic environment with repeated tissue injury, other cell types, such as resident epithelial cells or pericytes, may transdifferentiate and assume myofibroblast-like characteristics, expanding the pool of cells with fibrotic potential [4]. Activation and proliferation of myofibroblasts in pro-fibrotic lesions sets off cascading fibrotic events, such as over-production and accumulation of extracellular matrix (EM) components, including non-fibrillar collagens, hyaluronan, FN, and matricellular proteins, such as tenascins, thrombospondins, osteopontin and periostin [5]. Activation and proliferation of myofibroblasts and other cell types contributing to fibrosis are universally driven by profibrotic cellular signaling, i.e., growth factors, cytokines, and chemokines released in the local tissue microenvironment [6], a process that can even be further increased in the presence of EM and matricellular proteins, such as thrombospondin 1. These profibrotic signals include, most prominently, TGF-β signaling and several factors induced by TGF-β signaling, such as platelet-derived growth factor (PDGF) and CTGF [6]. In addition, contributions of other signaling pathways "
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 3,
    "text": "Oxysterols are oxidized derivatives of cholesterol, known for wide-ranging biological activities that differ from those of cholesterol itself. Oxysterols, either naturally occurring or man-made, can be activators or inhibitors of cellular signaling. At MAX BioPharma, we strive to identify novel drug candidates among semi-synthetic oxysterol derivatives, following cycles of design, synthesis, and biological testing, an approach that we have termed Oxysterol Therapeutics®. During such studies, we discovered Oxy210, a synthetic oxysterol derivative, as a dual inhibitor of Hh and TGF-β signaling in cell cultures of A549 human lung epithelial cancer cells and NIH3T3 mouse fibroblast cells [21]. With respect to liver fibrosis, we characterized Oxy210 as an orally bioavailable drug candidate with antifibrotic properties, exhibited in vitro, in primary human hepatic stellate cells (HSCs), and in vivo, using the humanized APOE*3-Leiden.CETP mouse model of NASH [22]. In the NASH mouse model, oral administration of Oxy210 formulated in mouse food was well-tolerated over 16 weeks of continuous dosing and ameliorated several hallmarks of NASH, including hepatic inflammation, fibrosis, apoptosis, and lipid deposition in a dose-dependent manner, resulting in improved hepatic function ([22] and unpublished results). Given the potential for pro-inflammatory side effects associated with the systemic inhibition of TGF-β signaling, we were initially surprised to find that Oxy210 exerted anti-inflammatory effects in the liver, adipose tissue [23], and plasma of the mice, evidenced by reduced in"
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "COL1A1",
      "collagen I",
      "type I collagen"
    ],
    "paragraph_index": 4,
    "text": "Fibrosis can be understood as an imbalance between EM deposition and degradation, including the unbalanced production and breakdown of extracellular collagen. Among various collagen subtypes, COL1A1 protein is the major component of type I collagen and by far the most abundant collagen present in human scar tissue. As such, COL1A1 can be considered a reliable biomarker in lung [24] and kidney [25] fibrosis and its reduction or removal in scar tissue may be therapeutically helpful. Lung myofibroblasts, stimulated by TGF-β and other profibrotic factors, are considered central mediators of the pathological fibrotic EM accumulation, including collagen, FN, and CTGF, all TGF-β target genes known for their pivotal roles in fibrosis [26]. We employed the IMR-90 cells, a human lung fibroblast cell line derived from healthy fetal lung tissue, to study the effect of Oxy210 on the expression of pro-fibrotic genes. As shown in Figure 1A,B, Oxy210 treatment inhibited the baseline expression of FN1 and COL1A1 as well as the TGF-β-induced expression of FN1, COL1A1, and CTGF, respectively, in a dose-dependent and statistically significant manner. Among the genes stimulated by TGF-β, the expression of COL1A1 appears to be more sensitive to inhibition by Oxy210 compared to FN1 and CTGF (Figure 1A,B). The effect of Oxy210 on cellular COL1A1 protein expression was also examined using ELISA. As shown in Figure 1C, treatment of IMR-90 cells with 5 μM Oxy210 resulted in a significant decrease in basal and TGF-β stimulated COL1A1 protein expression (measured by ELISA in cell lysate). The reduction"
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "COL1A1"
    ],
    "paragraph_index": 5,
    "text": "We have previously hypothesized that Oxy210 through simultaneous inhibition of both Hh and TGF-β signaling pathways may be therapeutically more effective compared to selective inhibitors of the Hh or TGF-β pathways alone [21,22]. To separate individual contributions of Hh and TGF-β signaling to responses in profibrotic gene expression, LL97A cells were studied in the presence or absence of TGF-β induction, and treated with HPI-1, a selective inhibitor of Gli transcription factors [30] and/or SB-431542 (SB), a selective TGFβRI/ALK5 inhibitor [31]. As shown in Figure 2, expression of ACTA2, COL1A1, and FN, was significantly suppressed by either HPI-1 or SB, with or without TGF-β stimulation, suggesting that profibrotic responses may be partially regulated by both signaling pathways. Combination treatments of HPI-1 and SB, with or without TGF-β stimulation, suppressed profibrotic gene expression below basal levels, hinting at possible synergy in this inhibition between Hh/Gli and TGF-β signaling. HPI-1 and SB treatment alone, in the presence of TGF-β stimulation, did not reduce profibrotic gene expression below baseline. Hence, the effect of Oxy210 on profibrotic gene expression in LL97A cells may resemble the combination treatment of HPI-1 and SB."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 6,
    "text": "Fibroblasts proliferation and differentiation occur in response to prolonged tissue injury as well as chronic inflammation and activated lung fibroblasts are characterized by enhanced proliferation [32]. To examine the effect of Oxy210 on the proliferation of pulmonary fibroblasts in vitro, cell counting experiments were conducted in the presence of increasing concentrations of Oxy210 using the IMR-90 and LL97A cells. Treatment of cells with Oxy210 resulted in the inhibition of proliferation with an IC50 of 1.6 ± 0.17 μM for IMR-90 cells and 2.5 ± 1.3 μM for LL97A cells (Figure 1B and Figure 3A). It is noteworthy that culturing of various fibroblastic and non-fibroblastic cells, including pulmonary fibroblasts, HSCs, and pericytes, on plastic tissue culture plates can result in an activated state and enhanced proliferative activity [33,34,35]. These states are inhibited by Oxy210, evidenced in this report by the inhibition of baseline expression of activation markers ACTA2 and COL1A1 in both lung fibroblasts employed in our studies (Figure 1E,G)."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 7,
    "text": "Repetitive injuries to the alveolar epithelium as well as inappropriate responses of airway epithelial cells to such injuries may contribute significantly to disease development and progression in IPF. This suggests that airway epithelial cells, such as small airway epithelial (HSAE) cells, could add fibrogenic potential through EMT stimulated via profibrotic signaling (e.g., TGF-β, Hh, Notch, and Wnt signaling) or hypoxia [36,37,38]. EMT is a patho-physiological process through which, in various diseases, epithelial cells acquire the phenotype of mesenchymal cells and express EM molecules that contribute to fibrosis [39,40]. EMT is orchestrated on the transcriptional level by the upregulation of a network of transcription factors, including SNAIL and TWIST, that directly repress epithelial genes and upregulate mesenchymal gene markers [41]. The source of myofibroblasts contributing to IPF is not completely understood. However, pulmonary epithelial cells undergoing EMT can reportedly play a role in creating a profibrotic environment in the lung even if they themselves do not account for a significant source of myofibroblasts in IPF [42]. Oxy210 significantly inhibited TGF-β-stimulated expression of the mesenchymal markers CTGF, matrix metalloproteinase 2 (MMP2), ACTA2, and N-cadherin (N-CAD) (Figure 4) and partially reversed the TGF-β-induced reduction in the epithelial marker E-cadherin (E-CAD) (Figure 4). In addition, TGF-β-induced the expression of IL-6 by HSAE cells, an effect that was inhibited to below basal levels by Oxy210 (Figure 4). It is noteworthy that IL-6 has "
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

### Packet heldout_rrpv1_0024

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
  "title": "SPARC Is Highly Expressed in Young Skin and Promotes Extracellular Matrix Integrity in Fibroblasts via the TGF-β Signaling Pathway.",
  "pmid": "37569556",
  "pmcid": "PMC10419001",
  "doi": "10.3390/ijms241512179"
}
```

Abstract:
The matricellular secreted protein acidic and rich in cysteine (SPARC; also known as osteonectin), is involved in the regulation of extracellular matrix (ECM) synthesis, cell-ECM interactions, and bone mineralization. We found decreased SPARC expression in aged skin. Incubating foreskin fibroblasts with recombinant human SPARC led to increased type I collagen production and decreased matrix metalloproteinase-1 (MMP-1) secretion at the protein and mRNA levels. In a three-dimensional culture of foreskin fibroblasts mimicking the dermis, SPARC significantly increased the synthesis of type I collagen and decreased its degradation. In addition, SPARC also induced receptor-regulated SMAD (R-SMAD) phosphorylation. An inhibitor of transforming growth factor-beta (TGF-β) receptor type 1 reversed the SPARC-induced increase in type I collagen and decrease in MMP-1, and decreased SPARC-induced R-SMAD phosphorylation. Transcriptome analysis revealed that SPARC modulated expression of genes involved in ECM synthesis and regulation in fibroblasts. RT-qPCR confirmed that a subset of differentially expressed genes is induced by SPARC. These results indicated that SPARC enhanced ECM integrity by activating the TGF-β signaling pathway in fibroblasts. We inferred that the decline in SPARC expression in aged skin contributes to process of skin aging by negatively affecting ECM integrity in fibroblasts.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10419001.xml
SHA-256: 7b045e6c7ebaeaaa716e4e352bb27f18b642b5a4698c0eb4741fe38cb143c1ee

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 3,
    "text": "Transforming growth factor-β (TGF-β) is a multifunctional cytokine involved in physiological processes such as growth, differentiation, and proliferation in several cell types [18,19]. TGF-β activates receptor-regulated mothers against decapentaplegic (R-SMADs) by binding to TGF-β receptors (TGFBRs), then induces collagen synthesis and suppresses MMPs [20,21]. SPARC can activate TGF-β signaling by interacting with TGF-β receptor type 2 (TGFBR2) that induces SMAD2 phosphorylation [22,23,24]. Moreover, TGF-β can stimulate the expression of SPARC in fibroblasts, keratinocytes, smooth muscle, and endothelial cells [25,26,27,28]."
  },
  {
    "matched_frozen_surfaces": [
      "type I collagen"
    ],
    "paragraph_index": 4,
    "text": "SPARC also promotes and reduces ECM integrity [14,29]. We quantified SPARC in young and elderly sun-protected skin and analyzed its effects on type I collagen and MMP-1 at the protein and mRNA levels in two-dimensional (2D) and 3D cultured human fibroblasts to determine the capacity of SPARC to modulate the ECM in human skin. We explored and validated the molecular mechanism through which SPARC regulates type I collagen and MMP-1 expression in fibroblasts. We also assessed differentially expressed genes (DEGs) and significantly changing gene ontologies (GOs) by SPARC in fibroblasts. Our results suggested that SPARC plays a role in intrinsic skin aging via ECM regulation."
  },
  {
    "matched_frozen_surfaces": [
      "collagen I"
    ],
    "paragraph_index": 5,
    "text": "We analyzed ultraviolet (UV)-protected buttock skin tissues from young and elderly individuals using quantitative RT-PCR and immunohistochemical (IHC) staining to identify age-related changes in SPARC in human skin. Levels of SPARC mRNA and IHC-stained protein were both significantly lower in elderly, than in young skin tissues (Figure 1A,B). We also detected SPARC signals particularly in the basal layer of the epidermis, and in fibroblasts and endothelial cells of the dermis. Moreover, a significant decrease in collagen intensity was observed in elderly human skin tissues when compared with young tissues (Supplementary Figure S1)."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "type I collagen"
    ],
    "paragraph_index": 6,
    "text": "We used western blotting to analyze the expression of type I collagen and MMP-1 in foreskin fibroblasts incubated with or without SPARC. We expressed a recombinant SPARC polypeptide by constructing a vector expressing human SPARC with a C-terminal His tag and stably transfecting it into HEK293 cells. His-tagged SPARC was purified from the conditioned medium of cells overexpressing the SPARC polypeptide by affinity chromatography using Ni2+-NTA resin (Supplementary Figure S2). Treatment with SPARC (0–8 μg/mL) resulted in a dose-dependent up-regulation of type I collagen and down-regulation of MMP-1. Notably, saturation was observed at a concentration of 2 μg/mL SPARC or higher (Figure 2A). In addition, SPARC (2 μg/mL) increased type I collagen and decreased MMP-1 secretion in fibroblasts to levels almost similar to those in cells incubated with TGF-β1 (3 ng/mL) (Figure 2B)."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1",
      "type I collagen"
    ],
    "paragraph_index": 7,
    "text": "We explored whether changes in the secretion of type I collagen and MMP-1 induced by SPARC were regulated at the mRNA level. The results of conventional and quantitative RT-PCR analyses showed that SPARC significantly increased levels of COL1A1 and COL1A2 mRNA and decreased those of MMP-1 mRNA in fibroblasts (Figure 3)."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1",
      "type I collagen"
    ],
    "paragraph_index": 8,
    "text": "We confirmed the effects of SPARC on ECM integrity by analyzing changes in SPARC-induced type I collagen and MMP-1 expression in fibroblasts embedded in a collagen matrix (3D culture) to mimic the dermis in vivo. Immunofluorescence (IF) staining of fibroblasts using antibodies specific to the N-terminal pro-peptide of type I collagen (COL1A1) and three-quarter fragment of type I collagen (Type I collagen cleavage site) revealed that SPARC treatment led to increased synthesis of type I collagen and decreased degradation of type I collagen (Figure 4). The synthesized type I procollagen was observed in the perinuclear region, likely corresponding to the endoplasmic reticulum (ER), while the degraded type I collagen was detected in the pericellular area. These data strongly indicate the critical role of SPARC in maintaining ECM integrity within the dermis of the skin."
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

### Packet heldout_rrpv1_0033

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
  "title": "Maternal GLP-1 receptor activation inhibits fetal growth.",
  "pmid": "38197791",
  "pmcid": "PMC11193516",
  "doi": "10.1152/ajpendo.00361.2023"
}
```

Abstract:
Glucagon-like peptide 1 (GLP-1) regulates food intake, insulin production, and metabolism. Our recent study demonstrated that pancreatic α-cells-secreted (intraislet) GLP-1 effectively promotes maternal insulin secretion and metabolic adaptation during pregnancy. However, the role of circulating GLP-1 in maternal energy metabolism remains largely unknown. Our study aims to investigate systemic GLP-1 response to pregnancy and its regulatory effect on fetal growth. Using C57BL/6 mice, we observed a gradual decline in maternal blood GLP-1 concentrations. Subsequent administration of the GLP-1 receptor agonist semaglutide (Sem) to dams in late pregnancy revealed a modest decrease in maternal food intake during initial treatment. At the same time, no significant alterations were observed in maternal body weight or fat mass. Notably, Sem-treated dams exhibited a significant decrease in fetal body weight, which persisted even following the restoration of maternal blood glucose levels. Despite no observable change in placental weight, a marked reduction in the placenta labyrinth area from Sem-treated dams was evident. Our investigation further demonstrated a substantial decrease in the expression levels of various pivotal nutrient transporters within the placenta, including glucose transporter one and sodium-neutral amino acid transporter one, after Sem treatment. In addition, Sem injection led to a notable reduction in the capillary area, number, and surface densities within the labyrinth. These findings underscore the crucial role of modulating circulating GLP-1 levels in maternal adaptation, emphasizing the inhibitory effects of excessive GLP-1 receptor activation on both placental development and fetal growth.NEW & NOTEWORTHY Our study reveals a progressive decline in maternal blood glucagon-like peptide 1 (GLP-1) concentration. GLP-1 receptor agonist injection in late pregnancy significantly reduced fetal body weight, even after restoration of maternal blood glucose concentration. GLP-1 receptor activation significantly reduced the placental labyrinth area, expression of some nutrient transporters, and capillary development. Our study indicates that reducing maternal blood GLP-1 levels is a physiological adaptation process that benefits placental development and fetal growth.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11193516.xml
SHA-256: 0c7a74ba323ff9789ed0a5386f936e5c6b9524e5a736963ee6e86b110442a4c4

Frozen fulltext excerpts:
```json
[]
```

Fields fulltext was expected to resolve:
["context", "relation"]

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

### Packet heldout_rrpv1_0034

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
  "title": "GLP-1 Receptor Activation Abrogates β-Cell Dysfunction by PKA Cα-Mediated Degradation of Thioredoxin Interacting Protein.",
  "pmid": "31708773",
  "pmcid": "PMC6824261",
  "doi": "10.3389/fphar.2019.01230"
}
```

Abstract:
Glucagon-like peptide 1 receptor (GLP-1R) agonist (Exendin-4) is a well-known agent used to improve β-cell dysfunctions via protein kinase A (PKA), but the detailed downstream molecular mechanisms are still elusive. We have now found that PKA Cα mediated- TXNIP phosphorylation and degradation played a vital role in the β-cell protective role of exendin-4. After PKA activator (Exendin-4 or FSK) treatment, PKA Cα could directly interact with TXNIP by bimolecular fluorescence complementation and Co-IP assays in INS-1 cells. And PKA Cα overexpression decreased TXNIP level, whereas TXNIP level was largely increased in PKA Cα-KO β-cells by CRISPR-Cas9. Interestingly, TXNIP overexpression or PKA Cα-KO has impaired β-cell functions, including loss of insulin secretion and activation of inflammation. PKA Cα directly phosphorylated TXNIP at Ser307 and Ser308 positions, leading to its degradation via activation of cellular proteasome pathway. Consistent with this observation, TXNIP (S307/308A) mutant resisted the degradation effects of PKA Cα. However, exendin-4 neither affected TXNIP level in TXNIP (S307/308A) mutant overexpressed β-cells nor in PKA Cα-KO β-cells. Moreover, exendin-4 treatment reduced the inflammation gene expression in TXNIP overexpressed β-cells, but exendin-4 treatment has no effect on the inflammation gene expression in TXNIP (S307/308A) overexpressed β-cells. In conclusion, our study reveals the integral role of PKA Cα/TXNIP signaling in pancreatic β-cells and suggests that PKA Cα-mediated TXNIP degradation is vital in β-cell protective effects of exendin-4.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6824261.xml
SHA-256: 4008f9a31f0764a682d7d007cba1e7eadf576a6ba846db5f51d6cd13e5c56e7d

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "insulin secretion"
    ],
    "paragraph_index": 3,
    "text": "Exendin-4, the anti-diabetic drug, could improve β-cell dysfunctions and apoptosis in a PKA-dependent manner under ER stress condition (Cunha et al., 2009; Yusta et al., 2006). PKA is a serine/threonine kinase formed by a dimer of two regulatory (R) subunits and two catalytic (C) subunits, but the holoenzyme is inactive because the R subunits bind with C subunits and only the C subunits have the ability to phosphorylate PKA substrates after disassociation with R subunit (Lester et al., 1997). There are four types of R subunits (RIα, RIβ, RIIα, and RIIβ) and two types of C subunits (C-α and C-β). RIα or RIβ subunits construct the type I PKA, and RIIα or RIIβ subunits construct the Type II PKA holoenzymes. Type I PKA is activated at a lower cAMP level compared with type II PKA. In β-cells, type I and type II PKA could be detected (Shibasaki et al., 2014). Interestingly, the acute phase of insulin secretion was increased and blood glucose was effective control in PKA Cα subunit knock in mice (Kaihara et al., 2013), so PKA Cα was overexpressed or knocked out throughout this study. Also, a previous study demonstrated that exendin-4 or forskolin (FSK) treatment could largely decrease the high glucose-induced TXNIP level in pancreatic β-cells (Shao et al., 2010). These observations raise the possibility that PKA could mediate TXNIP level under ER stress condition in response to exendin-4 treatment."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 4,
    "text": "Considering ER stress could directly activate inflammation through TXNIP, whether ER stress-activated inflammation could be modulated by exendin-4 is still unclear. Here, we found that activation of PKA has largely reduced TXNIP level and inflammation under ER stress condition. Moreover, PKA Cα could directly interact with TXNIP and lead to its degradation. PKA Cα/TXNIP signaling was thus found to lead to a vital function in the effects of exendin-4. In conclusion, our study was an exploratory study and provided a missing link between GLP-1R, PKA Cα and TXNIP."
  },
  {
    "matched_frozen_surfaces": [
      "GSIS"
    ],
    "paragraph_index": 9,
    "text": "GSIS assay was performed as our previous report (Zhang et al., 2013; Yao et al., 2015). Briefly speaking, INS-1 cells were pre–incubated with KRB buffer contained 0.2% BSA for 2 h, followed by incubation in KRB buffer containing glucose (16.8 mM) with indicated compounds for 2 h. Then, the supernatant was collected and insulin concentration was detected by the Insulin High Range Kit (Cisbio, Billerica, France)."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1 receptor"
    ],
    "paragraph_index": 28,
    "text": "ER stress induces TXNIP expression, which in turn activates inflammasomes and finally β-cell death (Ortsater and Sjoholm, 2007; Oslowski et al., 2012). Whereas, ER stress could be alleviated by exendin-4 (GLP-1 receptor agonist) via PKA activation in pancreatic β-cells (Kim et al., 2010). In order to confirm these results, we thus treated INS-1 cells with thapsigargin (THAP), an ER stress inducer, to observe the effect of exendin-4 or FSK on β-cell viability, because exendin-4 or FSK both could activate PKA. Similar to the previous results, exendin-4 ( Figure 1A ) or FSK ( Figure 1B ) treatment could statistically significantly improve ER stress-induced β-cell death. Considering ER stress-induced inflammation is the cause of β-cell death (Oslowski et al., 2012), we evaluated the effects of FSK on IL1-β level. As shown in Figure 1C , THAP largely enhanced IL1-β transcription, which was reduced in the presence of exendin-4 or FSK. Therefore, we wanted to know whether the anti-inflammation effect was dependent on PKA. After PKA activation was inhibited by H89, a PKA inhibitor, IL1-β, was at the same level under ER stress condition with or without exendin-4 or FSK treatment. Moreover, H89 could not induce more IL-1β expression under ER stress, which excluded the possibility that the inhibition of PKA has other downstream effects that increase the IL-1β expression. The results indicated that PKA played a key role in the protective effect of exendin-4 or FSK."
  },
  {
    "matched_frozen_surfaces": [
      "GSIS"
    ],
    "paragraph_index": 39,
    "text": "Deletion of PKA Cα enhances TXNIP level in β-cells. (A) Three designed sgRNAs were inserted into LentiV2 plasmid. These plasmids were transfected into INS-1 cells, and the TXNIP protein level was detected using WB (n = 3). (B) Single PKA Cα-KO β-cell was screened out using 96-well plate and the PKA Cα gene was sequenced in WT and PKA Cα-KO cells. Red sequence indicates GGG in the CRISPR -Cas9 sgRNA design and the green sequence indicates the whole sgRNA sequence. (C) EYFP vector or EYFP- PKA Cα plasmids were transfected into WT or PKA Cα-KO INS-1 cells separately for 24 h. THAP was added to the indicated cells. TXNIP and PKA Cα were analyzed using WB (n = 3). (D) WT or PKA Cα-KO INS-1 cells were treated with THAP, FSK or H89 for 2 h. TXNIP and PKA Cα were analyzed using WB (n = 3). (E) WT or PKA Cα-KO INS-1 cells were treated with THAP, and GSIS assay was performed as described in materials and methods (n = 3). (F) The mRNA level of IL-1β and IL-6 were analyzed in WT or PKA Cα-KO INS-1 cells by qRT-PCR (n = 3). Bars represent the mean ± SEM of independent samples. Significant difference in expression between groups as labeled was analyzed by one-way ANOVA, corrected for multiple comparisons with the Bonferroni test. (ns indicates no statistically significant, ** indicates P value < 0.01, *** indicates P value < 0.001)."
  },
  {
    "matched_frozen_surfaces": [
      "glucose-stimulated insulin secretion",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 40,
    "text": "It is widely reported that TXNIP overexpression has direct links with glucotoxicity, insulin secretion, β-cell inflammation and cell death (Chen et al., 2008; Reich et al., 2012). We thus evaluated the ability of glucose-stimulated insulin secretion (GSIS) in PKA Cα-KO cells. It was shown that insulin secretion was statistically significantly down regulated in PKA Cα-KO β-cells compared with WT β-cells in the presence of 16.8 mM glucose ( Figure 4E ). Moreover, insulin concentration reduced about 64.8% and 81% in WT β-cells and PKA Cα-KO β-cells under ER stress condition, respectively ( Figure 4E ). These data indicated that the TXNIP level was enhanced in PKA Cα-KO β-cells, thereby impairing insulin secretion. Furthermore, the inflammation level was evaluated in PKA Cα-KO β-cells. Compared to the WT β-cells, there were statistically significantly enhanced transcriptional levels of pro-inflammatory cytokines, such as IL-1β and IL-6 in PKA Cα-KO β-cells ( Figure 4F )."
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "relation"]

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

### Packet heldout_rrpv1_0042

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
  "title": "ZDHHC11-mediated AXL palmitoylation promotes osimertinib resistance in non-small-cell lung cancer.",
  "pmid": "41150710",
  "pmcid": "PMC12595455",
  "doi": "10.1073/pnas.2502778122"
}
```

Abstract:
Receptor tyrosine kinase pathway rewiring represents a fundamental mechanism underlying acquired resistance to EGFR tyrosine kinase inhibitors in EGFR-mutant non-small-cell lung cancer (NSCLC). While posttranslational modifications facilitate aberrant activation of bypass signaling networks, the specific contribution of ZDHHC palmitoyl acyltransferase-mediated palmitoylation remains poorly characterized. Here, ZDHHC11-mediated palmitoylation contributes to osimertinib resistance in EGFR-mutant NSCLC. Patient samples, along with in vitro and in vivo functional studies, indicated that ZDHHC11 upregulation reduces the sensitivity of tumor cells to osimertinib by promoting malignant phenotype. Mechanistically, we establish AXL receptor tyrosine kinase as the critical substrate. ZDHHC11 catalyzes AXL palmitoylation at Cys869, inducing plasma membrane retention and constitutive activation. This triggers downstream PI3K-AKT signaling, with AXL knockout alleviating the effect of ZDHHC11-driven resistance. Crucially, pharmacological inhibition ZDHHC11-mediated palmitoylation with the broad-spectrum palmitoylation inhibitor 2-bromopalmitate effectively augmented the antitumor effects of osimertinib. Collectively, ZDHHC11 regulates osimertinib resistance in a palmitoylation-dependent manner. Targeting the ZDHHC11-AXL axis may provide a promising therapeutic strategy for the treatment of osimertinib-resistant EGFR-mutant NSCLC patients with high ZDHHC11 expression.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12595455.xml
SHA-256: dcbfdf0bb0c0c85e2f0fbe6813ea0b976cfad2c3b70dd2618a6b63f3fa54673a

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 1,
    "text": "Non-small-cell lung cancer (NSCLC) represents a paradigm for genotype-directed cancer therapy (1). Epidermal growth factor receptor (EGFR)-activating mutations occur in about 10 to 15% of Caucasian and up to 50% of East Asian NSCLC patients (2), conferring sensitivity to EGFR tyrosine kinase inhibitors (TKIs) (3). Osimertinib, a third-generation irreversible EGFR–TKI, selectively targets both EGFR-activating mutations (e.g., exon 19 deletions/L858R) and T790M resistance mutations in advanced NSCLC (4). However, acquired resistance invariably develops, with limited therapeutic options postresistance. Currently, osimertinib resistance is believed to be acquired via various mechanisms, including mutation of EGFR-C797S, activation of a bypass pathway, and histological transformation, such as small-cell lung cancer transformation (5–7). Notably, data showing that only approximately 10 to 15% of first-line osimertinib-treated patients exhibit on-target resistance mechanisms, suggesting that the cause of resistance to osimertinib treatment may be more complex (8, 9). Critically, the specific molecular alterations responsible for tumor progression are unknown in approximately 40 to 50% of patients with no identifiable genotypic alterations (10, 11). Thus, investigation of the mechanisms underlying osimertinib resistance is essential to achieve better clinical outcomes for patients with EGFR-mutant NSCLC."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 2,
    "text": "Palmitoylation is the reversible posttranslational modification of proteins with a 16-carbon palmitate that serves as a critical mechanism to regulate protein subcellular localization and function (12, 13). According to several palmitoylome studies available in the SwissPalm database, as many as 78 of the 299 validated cancer driver proteins, such as EGFR–TKI resistance-related Ras, EGFR, and JAK1, can be palmitoylated (14). Currently, the catalytic enzymes responsible for the palmitoylation of most proteins remain unclear. In human cells, the thioesterification of palmitate to cysteine residues (S-palmitoylation) is catalyzed by 23 zinc-finger Asp-His-His-Cys (ZDHHC) domain-containing protein acyltransferases (PATs), also known as ZDHHCs (15). Emerging evidence suggests that aberrant ZDHHC activity and fluctuations in palmitoylation levels are vital determinants of various malignant phenotypes in tumorigenesis, including sustained cell proliferation, activation of metastasis, induction of angiogenesis, and drug resistance (16–18). In lung adenocarcinoma, elevated ZDHHC5 is involved in modulating the cancer stem cell–related palmitoylated protein INCENP (19). ZDHHC9 plays a tumor-promoting role in regulating PD-L1 stability by palmitoylation (20). In addition, ZDHHC11 is found on chromosome 5 in a small region of recurrent amplification (21). These results suggest that individual ZDHHC enzymes can act in a substrate-specific manner. Although the role of the ZDHHC-palmitoylation protein in osimertinib resistance in NSCLC remains largely unknown, advances in our knowledge of "
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "AXL activation",
      "osimertinib"
    ],
    "paragraph_index": 3,
    "text": "AXL, a receptor tyrosine kinase (RTK), is positioned upstream of a wide array of intracellular oncogenic signaling pathways and participates in various biological processes (22). High expression of AXL in various types of cancer, including lung cancer, is reportedly associated with poor prognosis (23). Notably, AXL has been found to be overexpressed more frequently in patients with EGFR-activating mutations than in those with wild-type (WT) EGFR in NSCLC (24), implying that AXL may be a potential therapeutic target to address the issue of cancer drug resistance. Increasing evidence has demonstrated that the activation of AXL induces intrinsic or acquired resistance to osimertinib in EGFR-mutant NSCLC cells and that the addition of AXL inhibitors in combination with other targeted agents can overcome TKI resistance (25, 26). Mechanistically, multiple pathways triggered by AXL are involved in resistance to EGFR–TKIs, including the MAPK/ERK and PI3K–AKT signaling pathways (27). In addition, AXL can promote EGFR-induced signaling by binding to EGFR and other members of the HER family (e.g., MET and PDGFR), contributing to preventing the effects of some RTK inhibitors (28). These pieces of evidences place AXL not only as a key mediator of EGFR–TKI resistance in tumors but also as an important component of the EGFR-RTK cellular survival network. However, how AXL can be continuously activated on the plasma membrane of resistant cells remains largely unclear. Crucially, the therapeutic effects of AXL axis inhibitors alone are not yet satisfactory. Thus, the mechanism underlying the"
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "This study delineates the critical role of ZDHHC11-mediated palmitoylation in osimertinib resistance. We establish that ZDHHC11 directly modulates EGFR-mutant cell sensitivity through S-palmitoylation of AXL RTK. This posttranslational modification drives AXL plasma membrane localization and constitutive activation, triggering PI3K–AKT signaling cascades that ultimately promote malignant phenotypes under osimertinib treatment. Our findings demonstrate that ZDHHC11 is a promising target whose inhibition may prevent or overcome resistance to osimertinib in individuals with EGFR-mutant NSCLC."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 5,
    "text": "To assess ZDHHCs’ clinical relevance in NSCLC progression and osimertinib resistance, the Cancer Genome Atlas (TCGA) Pancancer genomic datasets were queried. We first noted that ZDHHC11 amplification frequency was highest in lung adenocarcinoma (about 13% of 511, cBioPortal-sourced TCGA_LUAD samples) and was particularly enriched in NSCLC samples harboring oncogenic EGFR mutations (Fig. 1A). Consistent with ZDHHC11 location in the recurrently amplified 5p13.33 locus (21) (SI Appendix, Fig. S1A), NSCLC exhibited the highest ZDHHC11 amplification frequency among cancers analyzed in two independent studies (Fig. 1B and SI Appendix, Fig. S1B). According to analysis of the RNA sequencing of NSCLC samples in the TCGA datasets, we noted a trend toward higher ZDHHC11 mRNA levels with its amplification as compared to those without detectable genetic aberrations (SI Appendix, Fig. S1 C and D). Immunohistochemistry (IHC) of 90 NSCLC specimens confirmed cytoplasmic ZDHHC11 overexpression in tumors compared with paired normal tissues (Fig. 1C and SI Appendix, Fig. S1E). High ZDHHC11 expression (++; +++) correlated with larger tumor size, poorer histologic grade, and lymph node metastasis (SI Appendix, Table S1). Patients with poor differentiation or lymph node metastasis exhibited elevated ZDHHC11 levels (Fig. 1D), while survival analysis of 62 NSCLC smokers (Kaplan–Meier Plotter) showed poorer overall survival with high ZDHHC11 expression (Fig. 1E). To further validate these clinical findings, we performed CRISPR-Cas9 screening systematically knocking out all 23 ZDHHC palmitoyl acyltra"
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 6,
    "text": "The clinical significance of ZDHHC11 aberrations in NSCLC patients. (A) Frequency of ZDHHC amplification and diagram of ZDHHC11 and EGFR gene alterations across 511 samples (cBioPortal-sourced TCGA_LUAD). (B) Frequency of genomic ZDHHC11 alterations in patients with NSCLC (n = 10,528) obtained from cBioPortal (TCGA pancancer atlas studies). (C) The protein levels of ZDHHC11 in 90 paired adjacent nontumor tissues and NSCLC tumor tissues were determined via IHC staining. (D) Relative protein levels of ZDHHC11 in 90 clinical samples with or without poor histologic grade and metastasis status. (E) Curves of 62 NSCLC smoker in which the best cutoff level of ZDHHC11 was selected were used to depict survival time. All the data were derived from the Kaplan–Meier plotter and analyzed via the subset of TCGA. (F) PC9 OR cells were transfected with the indicated ZDHHC-KO constructs for 72 h before being treated with a series of osimertinib doses for 48 h. The IC50 values of osimertinib in each group were detected via CCK-8 assay and are shown as the mean ± SD of three independent experiments. The red dashed line represents the IC50 value of the negative control. (G) Venn diagram displaying genes whose expression was upregulated in osimertinib-resistant cells. Data obtained from GEO datasets (GSE146850, GSE165019, and GSE193258). (H) Immunoblot analysis of ZDHHC11 in PC9, PC9 OR, H1975, and H1975 OR cells. β-actin was used as a loading control."
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "therapy"]

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

### Packet heldout_rrpv1_0049

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
  "title": "BET protein proteolysis targeting chimera (PROTAC) exerts potent lethal activity against mantle cell lymphoma cells.",
  "pmid": "28663582",
  "pmcid": "PMC12856936",
  "doi": "10.1038/leu.2017.207"
}
```

Abstract:
Bromodomain extraterminal protein (BETP) inhibitors transcriptionally repress oncoproteins and nuclear factor-κB (NF-κB) target genes that undermines the growth and survival of mantle cell lymphoma (MCL) cells. However, BET bromodomain inhibitor (BETi) treatment causes accumulation of BETPs, associated with reversible binding and incomplete inhibition of BRD4 that potentially compromises the activity of BETi in MCL cells. Unlike BETi, BET-PROTACs (proteolysis-targeting chimera) ARV-825 and ARV-771 (Arvinas, Inc.) recruit and utilize an E3-ubiquitin ligase to effectively degrade BETPs in MCL cells. BET-PROTACs induce more apoptosis than BETi of MCL cells, including those resistant to ibrutinib. BET-PROTAC treatment induced more perturbations in the mRNA and protein expressions than BETi, with depletion of c-Myc, CDK4, cyclin D1 and the NF-κB transcriptional targets Bcl-xL, XIAP and BTK, while inducing the levels of HEXIM1, NOXA and CDKN1A/p21. Treatment with ARV-771, which possesses superior pharmacological properties compared with ARV-825, inhibited the in vivo growth and induced greater survival improvement than the BETi OTX015 of immune-depleted mice engrafted with MCL cells. Cotreatment of ARV-771 with ibrutinib or the BCL2 antagonist venetoclax or CDK4/6 inhibitor palbociclib synergistically induced apoptosis of MCL cells. These studies highlight promising and superior preclinical activity of BET-PROTAC than BETi, requiring further in vivo evaluation of BET-PROTAC as a therapy for ibrutinib-sensitive or -resistant MCL.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12856936.xml
SHA-256: 8c59319e39706f175d1d777669177db8b7121ff167cb28e943f6e0e8c115f1f5

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 1,
    "text": "Mantle Cell Lymphoma (MCL) exhibits pathogenetic mutations or deletion of RB1, ATM and p53, deletion of INK4a/ARF, as well as copy number gains of MYC, CDK4 and BCL2 1–3. Activated B cell receptor (BCR) signaling, and the ensuing downstream pro-growth and pro-survival NFkB activity, is also a notable feature of MCL4,5. Collectively, the genetic alterations and ensuing deregulated signaling and activity of transcription factors, including c-MYC and NFkB, creates the MCL-specific ‘transcriptome’ that promotes growth and survival of MCL cells 6,7. Ibrutinib, a covalent inhibitor of Bruton’s tyrosine kinase (BTK), exhibits unprecedented single-agent activity in relapsed/refractory MCL, however approximately 40% of patients demonstrate primary refractory/resistant disease with a one-year survival rate of only 22% 8–10. Mutations in CARD11/IKBKB/TRAF2/BIRC3/NIK or the C481S mutation in BTK, despite ibrutinib treatment, sustain the classical or alternative NFkB signaling and transcriptional activity, thereby conferring resistance to ibrutinib in MCL 11–13. We previously reported that the BET protein (BETP) bromodomain inhibitors (BETis), which disrupt the binding of BRD4 with acetylated chromatin, inhibit the in vitro growth and induce apoptosis of cultured and patient-derived (PD) primary MCL cells 14. This was associated with BETi-mediated attenuation of c-MYC, BCL2, CDK4/6 as well as of NFkB target gene expressions, including cIAP2, XIAP, cFLIP, TNFAIP3, BCl-xL, IL10, TNFα and BTK. Concomitantly, BETi treatment induced HEXIM1, p21, p27 and NOXA levels in MCL cells 14. However, "
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 2,
    "text": "BET PROTACs (proteolysis targeting chimera) ARV-825 and ARV-771 (Arvinas, Inc.) are hetero-bifunctional compounds, in which a small molecule BETP-binding moiety (OTX015/JQ1) is connected to the E3 ligase cereblon-binding moiety (pomalidomide) or VHL (Von Hippel-Lindau)-binding moiety, respectively, through a short alkyl linker19–21. The BETi OTX015 and the third-generation immunomodulatory drug (Imid) pomalidomide are currently under clinical investigation 22, 23. BET-PROTACs form a ternary complex with BETPs and the E3 ligase (cereblon or VHL), in which the BETPs are positioned in a spatially favorable presentation to promote their ubiquitylation by the E3 ligases, thereby inducing subsequent proteasomal degradation which results in prolonged and profound depletion of BETPs including BRD4 19–21. Unlike BETis such as JQ1 or OTX015, BET-PROTACs are catalytically active at sub-stoichiometric concentrations, and facilitate multiple rounds of BETP degradation 19, 20. Here, we compared the anti-MCL activity of the novel BET-PROTACs (ARV-825 and ARV-771) that degrade BRD4 with the BETi OTX015 against cultured and primary MCL cells. At equimolar concentrations ARV-825 and ARV-771 were more potent than the BETi OTX015 in inducing apoptosis of cultured and primary MCL cells, including the ibrutinib-resistant MCL cells, while relatively sparing the CD19+ normal B and CD34+ hematopoietic progenitor cells. Whereas OTX015 treatment increased, BET-PROTACs markedly attenuated (> 90%) the levels of BRD4 in the MCL cells. BET-PROTAC treatment also caused greater and more sustained depletion"
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 9,
    "text": "We first compared the effect of treatment with the equimolar concentrations of the BET-PROTACs ARV-771 and ARV-825 versus BETi OTX015 on the levels of BET proteins BRD4 and BRD2 in the MCL Mino cells. As has been previously demonstrated in Burkitt’s Lymphoma (BL) cells lines 19, in contrast to OTX015 which caused significant (p <0.05) accumulation and increased levels of BRD4 protein, treatment with ARV-771 and ARV-825 caused marked depletion of the levels of BRD4 and BRD2 in Mino and Z138 cells (Figure 1A, 1B and Supplemental Figure S2A). Similar effects were observed in two additional MCL cell lines, MAVER-1 and Granta-519 (Supplemental Figure S2B and S2C). Treatment with the BETi JQ1 also induced BRD4 levels in the MCL cells (data not shown). Confocal immunofluorescent microscopy has also demonstrated that treatment with BET-PROTAC depletes whereas BETi treatment increases the nuclear expression of BRD4 26. We also assessed BRD4 levels in the MCL cells treated with equimolar (1.0 μM) concentrations of ARV-825 or ARV-771 versus OTX015 for 24 hours, followed by washout of each compound, re-suspension and incubation of the cells for an additional 24 hours in drug-free medium. As shown in Figure 1B, compared to the high expression of BRD4 in the OTX015-treated post-washout cells, prior treatment with ARV-825 or ARV-771 caused a sustained depletion of BRD4 and BRD2 in the post-washout cells. Similar effects of ARV-825 or ARV-771 was also observed on BRD2 levels in Mino cells (data not shown). Whereas treatment with OTX015 increased, exposure to equimolar concentration of ARV-"
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 12,
    "text": "We also determined the effects of treatment with BET-PROTAC on protein expressions, utilizing specific and validated antibodies coupled to a reverse phase protein array (RPPA) 26,29,30. The heat maps in Supplemental Figure S8A show the changes in expression (in triplicate) of those proteins that exhibited a > 1.25-fold increase or decrease in their expression and p < 0.05 (relative to the untreated cells), following treatment of Mino cells with either 500 nM of the BET-PROTAC ARV-825 or ARV-771 for 18 hours, respectively. BET-PROTACs depleted BRD4 levels as well as down and up regulated proteins, with ARV-771 demonstrating greater effect than ARV-825 (Supplemental Figure S8A, Supplemental Table S8). ARV-771 treatment markedly down regulated p-S6, p-Rb, (surrogate for CDK4/6 down-regulation) c-Myc, c-RAF and c-IAP2, whereas the protein levels of DNA damage-associated γ-H2AX (H2AX p-S140) as well as of cleaved caspase 3 and 7 were up regulated (Supplemental Figure S8B and S8C, Supplemental Table S9). Similar treatment with OTX015 (500 nM for 18 hours) yielded perturbations of lesser magnitude than the BET-PROTACS in MCL cells (Supplemental Figure S8D, S8E and S8F, Supplemental Table S10). Western analyses were conducted to further confirm the greater effects of the BET-PROTACs versus OTX015 on the protein levels in the MCL Mino and Z138 cells. At 10-fold lower concentrations (100 nM) than OTX015 (1000 nM), treatment with ARV-771 or ARV-825 caused greater depletion of c-Myc, Bcl-xL, cyclin D1, CDK4, XIAP, p-BTK and BTK (Figure 5A and 5B). Similar effects were observed in Grant"
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 13,
    "text": "Following documentation of engraftment of luciferase-transduced ibrutinib-resistant Z138 cells into pre-irradiated NSG mice (Supplemental Figure S10), we also compared the effects of treatment with ARV-771, a BET-PROTAC with superior in vivo pharmacology compared to ARV-825, which recruits the E3 ligase VHL (Von Hippel Lindau) to degrade BETPs, versus OTX015 or vehicle control on the MCL burden and survival of the mice. Figure 6A (box and whisker plot) demonstrates that treatment with ARV-771 (30 mg/kg) was more effective than OTX015 in reducing the bioluminescence due to the MCL cells in the NSG mice, as determined 14 days after engraftment of the MCL cells. Notably, compared to OTX015, treatment with ARV-771 (30 mg/kg) was significantly more effective in improving the median and overall survival of the NSG mice, as depicted in the Kaplan Meier plot in Figure 6B (p = 0.0023). Whereas treatment with 50 mg/kg of OTX015 appreciably reduced the weight of the NSG mice, treatment with ARV-771 had an insignificant effect on their weight (p = 0.16) (data not shown). Notably, following a daily treatment with ARV-771 (30 mg/kg) for 5 days (daily x 5 days) also resulted in the in vivo depletion of the levels of BRD4, BRD2 and c-Myc in the Z138 xenograft cells from the spleen and bone marrow of the engrafted NSG mice (Figure 6C)."
  },
  {
    "matched_frozen_surfaces": [
      "venetoclax"
    ],
    "paragraph_index": 14,
    "text": "Next, we determined the activity of co-treatment with ARV-771 or OTX015 and ibrutinib or the BCL2 inhibitor, venetoclax against the cultured ibrutinib-sensitive MCL Mino and JeKo-1 cells. Co-treatment with ARV-771 or OTX015 and ibrutinib or venetoclax synergistically induced apoptosis of the cultured MCL Mino and JeKo-1 cells, with combination indices below 1.0, utilizing the isobologram analyses (Figure 7A and 7B and Supplemental Figure S11) 25. Importantly, co-treatment with ARV-771 or OTX015 and venetoclax or the CDK4/6 inhibitor palbociclib exerted synergistic lethality against ibrutinib-resistant Z138 and Mino/Persister cells (Supplemental Figure S12, Supplemental Figure S13, and Figure 7C). These combinations also induced synergistic apoptosis of the PD, primary MCL cells (Figure 7D). These findings suggest that the combinations of ARV-771 or OTX015 and ibrutinib or venetoclax may be synergistically active against ibrutinib-sensitive, whereas the combinations of ARV-771 or OTX015 and venetoclax or palbociclib may be highly effective against ibrutinib-resistant MCL cells."
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "relation", "therapy"]

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

### Packet heldout_rrpv1_0053

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
  "title": "BDNF enhances quantal neurotransmitter release and increases the number of docked vesicles at the active zones of hippocampal excitatory synapses.",
  "pmid": "11404410",
  "pmcid": "PMC2806848",
  "doi": "10.1523/JNEUROSCI.21-12-04249.2001"
}
```

Abstract:
Brain-derived neurotrophic factor (BDNF) is emerging as a key mediator of activity-dependent modifications of synaptic strength in the CNS. We investigated the hypothesis that BDNF enhances quantal neurotransmitter release by modulating the distribution of synaptic vesicles within presynaptic terminals using organotypic slice cultures of postnatal rat hippocampus. BDNF specifically increased the number of docked vesicles at the active zone of excitatory synapses on CA1 dendritic spines, with only a small increase in active zone size. In agreement with the hypothesis that an increased docked vesicle density enhances quantal neurotransmitter release, BDNF increased the frequency, but not the amplitude, of AMPA receptor-mediated miniature EPSCs (mEPSCs) recorded from CA1 pyramidal neurons in hippocampal slices. Synapse number, independently estimated from dendritic spine density and electron microscopy measurements, was also increased after BDNF treatment, indicating that the actions of BNDF on mEPSC frequency can be partially attributed to an increased synaptic density. Our results further suggest that all these actions were mediated via tyrosine kinase B (TrkB) receptor activation, established by inhibition of plasma membrane tyrosine kinases with K-252a. These results provide additional evidence of a fundamental role of the BDNF-TrkB signaling cascade in synaptic transmission, as well as in cellular models of hippocampus-dependent learning and memory.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC2806848.xml
SHA-256: 670b119aed76aa5037cee1f10e06727818f98482ccf43f28a254d4167e315fcc

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

### Packet heldout_rrpv1_0054

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
  "title": "Miniature synaptic transmission and BDNF modulate dendritic spine growth and form in rat CA1 neurones.",
  "pmid": "14500767",
  "pmcid": "PMC2343578",
  "doi": "10.1113/jphysiol.2003.052639"
}
```

Abstract:
The refinement and plasticity of neuronal connections require synaptic activity and neurotrophin signalling; their specific contributions and interplay are, however, poorly understood. We show here that brain-derived neurotrophic factor (BDNF) increased spine density in apical dendrites of CA1 pyramidal neurones in organotypic slice cultures prepared from postnatal rat hippocampal slices. This effect was observed also in the absence of action potentials, and even when miniature synaptic transmission was inhibited with botulinum neurotoxin C (BoNT/C). There were, however, marked differences in the morphology of individual spines induced by BDNF across these different levels of spontaneous ongoing synaptic activity. During both normal synaptic transmission, and when action potentials were blocked with TTX, BDNF increased the proportion of stubby, type-I spines. However, when SNARE-dependent vesicular release was inhibited with BoNT/C, BDNF increased the proportion of thin, type-III spines. Our results indicate that BDNF increases spine density irrespective of the levels of synaptic transmission. In addition, miniature synaptic transmission provides sufficient activity for the functional translation of BDNF-triggered spinogenesis into clearly defined morphological spine types, favouring those spines potentially responsible for coordinated Ca2+ transients thought to mediate synaptic plasticity. We propose that BDNF/TrkB signalling represents a mechanism of expression of both morphological and physiological homeostatic plasticity in the hippocampus, leading to a more efficient synaptic information transfer across widespread levels of synaptic activity.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC2343578.xml
SHA-256: b669a3b844a0fe77e27c846e7139e92b1133992aece03f998f644004cc1da973

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

### Packet heldout_rrpv1_0063

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
  "title": "Insulin-independent stimulation of skeletal muscle glucose uptake by low-dose abscisic acid via AMPK activation.",
  "pmid": "31996711",
  "pmcid": "PMC6989460",
  "doi": "10.1038/s41598-020-58206-0"
}
```

Abstract:
Abscisic acid (ABA) is a plant hormone active also in mammals where it regulates, at nanomolar concentrations, blood glucose homeostasis. Here we investigated the mechanism through which low-dose ABA controls glycemia and glucose fate. ABA stimulated uptake of the fluorescent glucose analog 2-NBDG by L6, and of [18F]-deoxy-glucose (FDG) by mouse skeletal muscle, in the absence of insulin, and both effects were abrogated by the specific AMPK inhibitor dorsomorphin. In L6, incubation with ABA increased phosphorylation of AMPK and upregulated PGC-1α expression. LANCL2 silencing reduced all these ABA-induced effects. In vivo, low-dose oral ABA stimulated glucose uptake and storage in the skeletal muscle of rats undergoing an oral glucose load, as detected by micro-PET. Chronic treatment with ABA significantly improved the AUC of glycemia and muscle glycogen content in CD1 mice exposed to a high-glucose diet. Finally, both acute and chronic ABA treatment of hypoinsulinemic TRPM2-/- mice ameliorated the glycemia profile and increased muscle glycogen storage. Altogether, these results suggest that low-dose oral ABA might be beneficial for pre-diabetic and diabetic subjects by increasing insulin-independent skeletal muscle glucose disposal through an AMPK-mediated mechanism.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6989460.xml
SHA-256: 20e7361a133a16f08e45c3dd4880194db17f0e399eed68ebdace834f70098431

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 3,
    "text": "Several lines of evidence indicate that ABA is a new and important player in mammalian glycemic control. Nanomolar ABA stimulates insulin-independent glucose uptake by murine adipocytes in vitro by increasing the expression and plasmamembrane translocation of the glucose transporter GLUT4, also the target of insulin3,8. Plasma ABA increases after an oral glucose load in healthy humans, but not in subjects with type 2 diabetes (T2D), or with gestational diabetes (GDM). In the latter case, the resolution of the diabetic state that follows childbirth is accompanied by the restoration of a normal ABA response to oral glucose9. ABA stimulates the glucose-independent release of GLP-1 from enteroendocrine cells in vitro and the increase of plasma GLP-1 in fasted rats10. Finally, low-dose oral ABA reduces glycemia and also insulinemia in rats and in healthy humans undergoing a glucose load7."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "The fact that ABA administration reduces both glycemia and insulinemia suggested that the mechanism underlying the glycemia-lowering action of low-dose ABA in vivo could depend on the stimulation of peripheral glucose uptake7. The identification of a second hormone beside insulin capable of stimulating muscle glucose uptake would bear significant consequences in clinical conditions where insulin deficiency or insulin resistance reduce glucose tolerance."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "The aim of this study was, (i) to explore the effect of ABA in the absence of insulin on myocyte glucose uptake in vitro and ex vivo; (ii) to investigate the effect of a single low-dose ABA administration on muscle glucose disposal in vivo by micro-PET, and (iii) to verify whether low-dose ABA improves glucose tolerance in hypoinsulinemic mice."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 6,
    "text": "Previous studies had shown that ABA stimulated glucose uptake by murine 3T3-L1 preadipocytes in the absence of insulin, by increasing the expression and the plasmamembrane translocation of the insulin-sensitive glucose transporter GLUT4 via a PI3K/Akt-dependent pathway3,8. In skeletal muscle, GLUT4 translocation to the plasmamembrane and glucose transport are known to be stimulated by AMPK11. Expression of the ABA receptor LANCL2 in L6 was preliminarily confirmed by Western blot, which also showed presence of closely related LANCL1, though at lower levels, as confirmed by RT-PCR (not shown). The effect of ABA on glucose transport was thus explored on rat L6 myoblasts, in the absence or presence of the AMPK inhibitor dorsomorphin. Nanomolar ABA stimulated uptake of the fluorescent glucose analog 2-NBDG in serum-starved L6 myoblasts, confirming previous results obtained with radioactive glucose3; this effect was abrogated when cells were preincubated with 1 µM dorsomorphin (Fig. 1a, light grey bar). Addition of 100 nM insulin stimulated NBDG uptake in serum-starved L6 cells, quantitatively similarly to 100 nM ABA (approx. 3-fold) and pre-incubation of the cells for 30 min with 100 nM wortmannin, a specific PI3K inhibitor, reduced NBDG uptake to values similar to those measured in untreated control cells, similarly to what observed in ABA-treated cells pre-incubated with dorsomorphin (not shown). Thus, the mechanism through which ABA stimulates NBDG uptake in L6 is AMPK-dependent and different from the one of insulin. ABA-stimulated NBDG uptake was significantly reduced by sil"
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 7,
    "text": "Glucose uptake in rat L6 myoblasts and in murine muscle incubated with ABA: effect of AMPK inhibition and LANCL2 silencing. (a) Serum-starved rat L6 myoblasts were: (i) pre-incubated for 30 min without (control) or with the AMPK inhibitor dorsomorphin (1 µM), or (ii) transiently transfected with scramble (siRNA-SCR) or LANCL2-targeting siRNA (siRNA-L2), then incubated without (control) or with 100 nM ABA, without or with 1 µM dorsomorphin, for 30 min and uptake of the fluorescent glucose analog 2-NBDG was measured after 10 min incubation with the dye. Results are expressed as fluorescence relative to control (mean ± SD from at least 3 experiments; *p = 0.001 relative to control, #p = 0.002 relative to ABA, **p = 0.001 relative to siRNA-SCR without ABA, $p = 0.002 relative to siRNA-SCR + ABA). Inset: a representative Western blot of LANCL2 expression in siRNA-SCR vs. siRNA-L2 cells. (b) Ligand Tracer analysis of FDG uptake by L6 cells stably infected with a scramble (shRNA-SCR, upper panel) or with a LANCL2-targeting shRNA (shRNA-L2, lower panel). Cells were pre-incubated with or without 100 nM ABA for 1 hour before being placed in the Ligand Tracer device. Cytochalasin B and Phloretin were added at time zero of the Ligand Tracer analysis (cyto-phlo). Representative traces are shown on the left and mean ± SD values from 3 experiments are shown on the right. Inset: a representative Western blot of LANCL2 expression in shRNA-SCR vs. shRNA-L2 cells. *p < 0.03 relative to control. (c) Freshly isolated samples of femoral quadriceps (~100 mg) were pre-incubated, or not (control) w"
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 8,
    "text": "In order to obtain a higher extent of LANCL2 silencing and to explore the time-course of glucose uptake, a different experimental approach was undertaken. L6 cells were infected with lentiviral particles expressing either shRNA-SCR (control cells) or shRNA-L2 (shRNA-L2 cells). After puromycin selection, shRNA-L2 cells showed a > 95% reduction of LANCL2 mRNA levels by Real Time PCR and a > 90% reduction of protein levels (by Western blot) compared with control cells (inset to Fig. 1b). Using the Ligand Tracer device, [18F]-deoxy-glucose (FDG) uptake in shRNA-L2 L6 cells was measured in real-time and compared with that of control cells, shRNA-SCR, incubated with or without ABA. ABA increased FDG uptake in shRNA-SCR cells approximately 1.7-fold compared with untreated cells (Fig. 1b, upper panel) and LANCL2 silencing reduced the ABA-induced stimulation of FDG uptake (Fig. 1b, lower panel). In the presence of cytochalasin B and phloretin, FDG uptake was similarly abrogated in control (cyto-phlo Fig. 1b), as well as in ABA-treated cells (not shown), indicating that the FDG uptake measured was indeed the result of glucose transport. Finally, a 10-minute pre-incubation of shRNA-SCR cells with 0.2 mM Indinavir (a GLUT4-specific inhibitor of glucose transport) reduced the effect of ABA on FDG uptake in L6 cells by 93 ± 5%, confirming that stimulation by ABA of glucose transport occurs via GLUT4 (not shown)."
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

### Packet heldout_rrpv1_0064

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
  "title": "Methotrexate promotes glucose uptake and lipid oxidation in skeletal muscle via AMPK activation.",
  "pmid": "25338814",
  "pmcid": "PMC5703413",
  "doi": "10.2337/db14-0508"
}
```

Abstract:
Methotrexate (MTX) is a widely used anticancer and antirheumatic drug that has been postulated to protect against metabolic risk factors associated with type 2 diabetes, although the mechanism remains unknown. MTX inhibits 5-aminoimidazole-4-carboxamide ribonucleotide formyltransferase/inosine monophosphate cyclohydrolase (ATIC) and thereby slows the metabolism of 5-aminoimidazole-4-carboxamide-1-β-D-ribofuranosyl-5'-monophosphate (ZMP) and its precursor AICAR, which is a pharmacological AMPK activator. We explored whether MTX promotes AMPK activation in cultured myotubes and isolated skeletal muscle. We found MTX markedly reduced the threshold for AICAR-induced AMPK activation and potentiated glucose uptake and lipid oxidation. Gene silencing of the MTX target ATIC activated AMPK and stimulated lipid oxidation in cultured myotubes. Furthermore, MTX activated AMPK in wild-type HEK-293 cells. These effects were abolished in skeletal muscle lacking the muscle-specific, ZMP-sensitive AMPK-γ3 subunit and in HEK-293 cells expressing a ZMP-insensitive mutant AMPK-γ2 subunit. Collectively, our findings underscore a role for AMPK as a direct molecular link between MTX and energy metabolism in skeletal muscle. Cotherapy with AICAR and MTX could represent a novel strategy to treat metabolic disorders and overcome current limitations of AICAR monotherapy.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC5703413.xml
SHA-256: 68671a57ff651791593874b05f50144c276bb9ba3845bb4fc6bb48649a08ce7a

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "AMPK activation"
    ],
    "paragraph_index": 2,
    "text": "MTX has several pharmacological targets, including 5-aminoimidazole-4-carboxamide ribonucleotide formyltransferase / inosine monophosphate cyclohydr3olase (ATIC) (11). ATIC is essential for the conversion of 5-aminoimidazole-4-carboxamide-1-β-D-ribofuranosyl-5’-monophosphate (ZMP) to inosine monophosphate in the final two steps of the de novo purine synthesis pathway. Thus, congenital ATIC deficiency or MTX therapy elevates intracellular ZMP content and excretion of its metabolites (6, 12, 13). The purine precursor ZMP is also an AMP-mimetic and activates the AMP-activated protein kinase (AMPK) (14). AMPK is a heterotrimeric serine-threonine kinase, composed of the catalytic α and non-catalytic β and γ subunits (15). ZMP binds to the AMP-binding sites on the γ subunits (16), and this is required for its ability to activate AMPK (17). AMPK plays a role in maintaining energy homeostasis and is currently a target for the treatment of type 2 diabetes (18–20). Thus, MTX might mitigate metabolic impairments by promoting ZMP-stimulated AMPK activation in key organs controlling glucose homeostasis."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 3,
    "text": "AMPK activation increases glucose uptake, fatty acid oxidation and mitochondrial biogenesis, which helps to ameliorate different aspects of metabolic dysregulation, including hyperglycemia and insulin resistance (19). MTX could promote ZMP accumulation and AMPK activation by suppressing ATIC, which is expressed and active in skeletal muscle (21, 22). ZMP is also the active metabolite of the pharmacological AMPK activator 5-aminoimidazole-4-carboxamide-1-β-D-ribofuranoside (AICAR) (14). AICAR therapy promotes favorable metabolic reprogramming in skeletal muscle of sedentary (23) and diabetic (ob/ob) mice (24). However, a relatively high threshold for AMPK activation (25), in conjunction with poor bioavailability (26), limits the usefulness of AICAR in the treatment of type 2 diabetes (27). MTX may enhance AICAR-stimulated AMPK activation in skeletal muscle by suppressing ATIC-mediated ZMP clearance and overcome this problem."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "Here, we show that MTX markedly reduces the threshold for AICAR-stimulated AMPK activation and potentiates glucose uptake and lipid oxidation in skeletal muscle. Thus, co-therapy with AICAR and MTX could represent a novel strategy to treat metabolic disorders and overcome current limitations of AICAR mono-therapy."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 5,
    "text": "Antibodies against phospho-AMPKα (Thr172) and phospho-ACC (Ser79) were from Cell Signaling Technology (Beverly, MA), the antibody against ATIC was from Sigma-Aldrich (Stockholm, Sweden), the GLUT4 antibody was from Millipore (Temecula, CA), and the antibody against GAPDH was from Santa Cruz Biotechnology (Santa Cruz, CA). ECL reagent and the protein molecular weight marker were from GE Healthcare (Uppsala, Sweden). BCA Protein Assay kit was from Pierce (Rockford, IL), and PVDF Immobilon-P membrane from Millipore (Bedford, MA). Cell culture materials were from Costar (Täby, Sweden). [9-10(n)-3H]-palmitic acid and [1,2-3H]-2-deoxy-D-glucose were from Perkin-Elmer. All other reagents, unless otherwise specified, were of analytical grade and obtained from Sigma-Aldrich (Stockholm, Sweden)."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 8,
    "text": "L6 myotubes were incubated in αMEM (w/o nucleosides) with or without 5 µM MTX for 16 hours prior to the experiment. For fatty acid oxidation, myotubes were serum-starved for 4 hours and then incubated with or without MTX (5 µM) and/or AICAR (0.2 or 2 mM) for 5 hours in αMEM, supplemented with 0.2% BSA, 20 µM cold palmitate and 0.5 µCi/ml [3H]-palmitic acid. Palmitate oxidation was determined by measuring the amount of 3H2O in cell culture media. Non-metabolized palmitate was adsorbed to charcoal and removed by centrifugation (16,000 rpm, 15 minutes). For glucose uptake, L6 myotubes were incubated with or without MTX (5 µM) and/or AICAR (0.2 mM or 2 mM) in serum-free αMEM (w/o nucleosides) for 5 hours. Myotubes were then washed with HBS (140 mM NaCl, 20 mM Hepes, 5 mM KCl, 2.5 mM MgSO4, 1 mM CaCl2, pH 7.4) and subsequently incubated in HBS supplemented with 10 µM 2-deoxy-D-glucose and 0.75-1 µCi/ml [1,2-3H]-2-deoxy-D-glucose for 10 minutes. Nonspecific glucose transport was assessed in the presence of 10 µM cytochalasin B. Myotubes were then washed with ice-cold stop solution (25 mM glucose, 0.9% (w/v) NaCl) and lysed in 0.03% (w/v) SDS. Radioactivity was measured in cell lysates by liquid scintillation counting."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 9,
    "text": "This study was approved by the Regional Animal Ethical Committee (Stockholm, Sweden). AMPK-γ3 knock-out (AMPK-γ3-/-) mice were bred onto a C57BL/6 genetic background and have been thoroughly characterized (28). Prior to all experiments, AMPK-γ3-/- and wild-type mice were fasted for 4 hours before being anesthetized with Avertin (0.02 ml/g i.p.)."
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
