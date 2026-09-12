# Held-out PASS B — relevance review

Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.
All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.
Do not calculate partial or running metrics.

Allowed relevance_state: DIRECTLY_RELEVANT, PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED, RELATED_BUT_WRONG_PROPOSITION, WRONG_ENDPOINT, WRONG_ENTITY, WRONG_EVIDENCE_MODE, WRONG_THERAPY, TOPIC_ONLY, INSUFFICIENT_SOURCE_EVIDENCE

### Packet heldout_rrpv1_0005

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
  "title": "Ouabain Suppresses IL-6/STAT3 Signaling and Promotes Cytokine Secretion in Cultured Skeletal Muscle Cells.",
  "pmid": "33101052",
  "pmcid": "PMC7544989",
  "doi": "10.3389/fphys.2020.566584"
}
```

Abstract:
The cardiotonic steroids (CTS), such as ouabain and marinobufagenin, are thought to be adrenocortical hormones secreted during exercise and the stress response. The catalytic α-subunit of Na,K-ATPase (NKA) is a CTS receptor, whose largest pool is located in skeletal muscles, indicating that muscles are a major target for CTS. Skeletal muscles contribute to adaptations to exercise by secreting interleukin-6 (IL-6) and plethora of other cytokines, which exert paracrine and endocrine effects in muscles and non-muscle tissues. Here, we determined whether ouabain, a prototypical CTS, modulates IL-6 signaling and secretion in the cultured human skeletal muscle cells. Ouabain (2.5-50 nM) suppressed the abundance of STAT3, a key transcription factor downstream of the IL-6 receptor, as well as its basal and IL-6-stimulated phosphorylation. Conversely, ouabain (50 nM) increased the phosphorylation of ERK1/2, Akt, p70S6K, and S6 ribosomal protein, indicating activation of the ERK1/2 and the Akt-mTOR pathways. Proteasome inhibitor MG-132 blocked the ouabain-induced suppression of the total STAT3, but did not prevent the dephosphorylation of STAT3. Ouabain (50 nM) suppressed hypoxia-inducible factor-1α (HIF-1α), a modulator of STAT3 signaling, but gene silencing of HIF-1α and/or its partner protein HIF-1β did not mimic effects of ouabain on the phosphorylation of STAT3. Ouabain (50 nM) failed to suppress the phosphorylation of STAT3 and HIF-1α in rat L6 skeletal muscle cells, which express the ouabain-resistant α1-subunit of NKA. We also found that ouabain (100 nM) promoted the secretion of IL-6, IL-8, GM-CSF, and TNF-α from the skeletal muscle cells of healthy subjects, and the secretion of GM-CSF from cells of subjects with the type 2 diabetes. Marinobufagenin (10 nM), another important CTS, did not alter the secretion of these cytokines. In conclusion, our study shows that ouabain suppresses the IL-6 signaling via STAT3, but promotes the secretion of IL-6 and other cytokines, which might represent a negative feedback in the IL-6/STAT3 pathway. Collectively, our results implicate a role for CTS and NKA in regulation of the IL-6 signaling and secretion in skeletal muscle.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7544989.xml
SHA-256: a0fb9819abc7164117a92c1d22372ec958f82609248e83f47024e5442c81e489

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "interleukin-6"
    ],
    "paragraph_index": 2,
    "text": "Cardiotonic steroids, whose endogenous secretion is believed to be regulated by the sympathoadrenergic system, the adrenocorticotropic hormone, and angiotensin II (Laredo et al., 1995, 1997; Bauer et al., 2005), may have an important role in regulation of Na+ homeostasis, arterial blood pressure, as well as the stress and immune responses (Foey et al., 1997; Fedorova et al., 2001; Berendes et al., 2003; Blaustein et al., 2012; Cavalcante-Silva et al., 2017). As estimated by an ouabain immunoassay, plasma concentrations of CTS are markedly increased during exercise (Bauer et al., 2005), but their physiological role under these conditions has not been established. Contracting skeletal muscles secrete interleukin-6 (IL-6) and a plethora of other cytokines (aka myokines), which regulate the immune system and metabolic pathways in skeletal muscle and other metabolic organs, thus contributing to acute and chronic adaptations to exercise (Pedersen and Febbraio, 2012; Egan and Zierath, 2013; Pedersen, 2019). Skeletal muscles are therefore a major source as well as an important site of cytokine action during exercise. Here, we asked whether CTS might alter signaling and the secretion of IL-6 in skeletal muscle cells."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 5,
    "text": "Skeletal muscles contain a major pool of NKA in the body (Clausen, 1996, 2010) and are therefore an important target for CTS (Glantz et al., 1976; Kjeldsen et al., 1985; Harashima et al., 1988). However, only limited data regarding the role of CTS in skeletal muscle is available. In mice, infusion of the CTS-binding antibody increases transport activity of NKA during muscle contractions, which demonstrates that CTS might be involved in acute regulation of NKA (Radzyukevich et al., 2009). In cultured skeletal muscle cells and isolated skeletal muscle, ouabain stimulates the glycogen synthesis (Clausen, 1965; Kotova et al., 2006a, b), suggesting a role for CTS and NKA in regulation of skeletal muscle metabolism (Pirkmajer and Chibalin, 2016). Interestingly, recent data suggest that circulating ouabain may regulate NKA in skeletal muscle and oppose depolarization of the sarcolemma due to muscle disuse or exposure to lipopolysaccharide (Kravtsova et al., 2020). Clearly, the role of CTS in skeletal muscle needs to be dissected in more detail. Using primary human skeletal muscle cells we examined whether and how CTS modulate the IL-6/STAT3 signaling. We also determined whether ouabain and marinobufagenin modulate the secretion of IL-6 and other muscle-derived cytokines."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 6,
    "text": "Cell culture flasks and plates were from Sarstedt or TPP. Advanced MEM, GlutaMAX, MEM vitamin solution, DMEM, fetal bovine serum (FBS), trypsin-EDTA, pen strep (5000 units/ml of penicillin and 5000 μg/ml of streptomycin), fungizone (250 μg/ml of amphotericin B), gentamicin (10 mg/ml), Pierce BCA Protein Assay Kit, Pierce Enhanced Chemiluminescence (ECL) Western Blotting Substrate, High-Capacity cDNA Reverse Transcription Kit, TaqMan Universal Master Mix and TaqMan gene expression assays for IL-6 (Hs00174131_m1), HIF1A (Hs00153153_m1), ARNT/HIF1β (Hs00231048_m1), ATP1A1 (Hs00167556_m1), ATP1A2 (Hs00265131_m1), ATP1A3 (Hs00958036_m1), and actin-β (ACTB, Hs99999903_m1), PPIA (Hs99999904_m1), 18S rRNA (Hs99999901_s1), rat ATP1A1 (Rn01533986_m1), rat ATP1A2 (Rn00560789_m1), rat ATP1A3 (Rn00560813_m1) and rat ACTB (4352931E) were from Thermo Fisher Scientific. PCR plates, PCR plate sealing films, 4–12% Criterion XT Bis-Tris polyacrylamide gels, XT MES electrophoresis buffer and goat anti-rabbit or anti-mouse IgG - horseradish peroxidase conjugate were from Bio-Rad. Amersham ECL Full-Range Rainbow Molecular Weight Markers were from GE Healthcare Life Sciences. Polyvinylidene fluoride (PVDF) membrane was from Merck Millipore. CP-BU NEW X-ray films were form AGFA HealthCare. RNeasy Plus Mini Kit was from Qiagen. E.Z.N.A. HP Total RNA Kit was from Omega Bio-Tek. Recombinant human IL-6 was from PeproTech and antibody against IL-6 receptor was from Roche (tocilizumab, RoActemra). Proteasome inhibitor MG-132, ouabain octahydrate, puromycin, and all other reagents, unless otherwise speci"
  },
  {
    "matched_frozen_surfaces": [
      "STAT3",
      "phospho-STAT3"
    ],
    "paragraph_index": 7,
    "text": "Target proteins were detected using primary antibodies against phospho-STAT3 (Tyr705) (Cell Signaling #9145), STAT3 (Cell Signaling #4904), phospho-ERK1/2 (Thr202/Tyr204) (Cell Signaling #4370 or #9101), ERK1/2 (Cell Signaling #4695), phospho-4E-BP1 (Thr37/46) (Cell Signaling #2855), 4E-BP1 (Cell Signaling #9644), α1-subunit of NKA (Upstate #05-369), phospho-Src (Tyr527) (Cell Signaling #2105), phospho-S6 ribosomal protein (Ser235/236) (Cell Signaling #2211), S6 ribosomal protein (Cell Signaling #2217), phospho-p70S6K (Thr389) (Cell Signaling #9205), phospho-Akt (Ser473) (Cell Signaling #4060), total Akt (Cell Signaling #4691), HIF-1α (Novus Biologicals #NB100-449), HIF-1β/ARNT (Cell Signaling #5537)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 14,
    "text": "Total RNA was extracted with RNeasy Plus Mini Kit or E.Z.N.A. HP Total RNA Kit and reverse transcribed to cDNA with High-Capacity cDNA Reverse Transcription Kit. The quantitative real-time polymerase chain reaction (qPCR) was performed on 7500 Real-Time PCR System (Applied Biosystems, Thermo Fisher Scientific) using TaqMan Universal Master Mix and TaqMan gene expression assays. The endogenous controls (reference genes) were actin-β (ACTB), cyclophilin (PPIA), and 18S rRNA. ACTB was the endogenous control for the gene silencing (of HIF-1α and/or HIF-1β) experiment. To estimate effects of ouabain on IL-6 and NKAα1 mRNA the geometric mean of three endogenous controls (ACTB mRNA, PPIA mRNA, and 18S rRNA) was used for normalization. Efficiency of PCR was estimated with the LinRegPCR software (Ramakers et al., 2003; Ruijter et al., 2009)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 17,
    "text": "STAT3, a transcription factor, is activated (phosphorylated) in skeletal muscle by IL-6 and exercise (Trenerry et al., 2007; Pedersen and Febbraio, 2008). To determine whether ouabain modulates IL-6 signaling in skeletal muscle cells, we treated myotubes with 50 nM ouabain for 20 h in Advanced MEM, supplemented with 2% FBS. This was followed by a 4-h treatment with 50 nM ouabain and/or 100 μg/ml tocilizumab in serum-free Advanced MEM. Myotubes were stimulated with 50 ng/ml IL-6 (Figures 1A–D) during the last 15 min. Ouabain decreased the abundance of the α1-subunit of NKA (NKAα1) (Figure 1A) and STAT3 (Figure 1B). The basal and the IL-6-stimulated phosphorylation of STAT3 (Tyr705) were also reduced by ouabain (Figures 1C,D). Tocilizumab, an antibody against the α-subunit (IL-6Rα) of the oligomeric IL-6 receptor (IL-6Rα/gp130), blocked the IL-6-stimulated phosphorylation of STAT3 without significantly altering its basal phosphorylation (Figures 1C,D) or the abundance of STAT3 (Figure 1B)."
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

### Packet heldout_rrpv1_0006

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
  "title": "Correlation of IL-6 and JAK2/STAT3 signaling pathway with prognosis of nasopharyngeal carcinoma patients.",
  "pmid": "34165442",
  "pmcid": "PMC8266356",
  "doi": "10.18632/aging.203186"
}
```

Abstract:
IL-6 is reported to be the main upstream activator, instead of the downstream target of JAK2/STAT3. This study is intended to explore the correlation of IL-6 and JAK2/STAT3 signaling pathway with clinicopathological features and prognosis in nasopharyngeal carcinoma (NPC). First, NPC tissues and normal nasopharyngeal epithelial tissues were obtained from 117 NPC patients. Next, we detected expression levels of IL-6 in serum and those of STAT3, p-STAT3, JAK2, p-JAK2 and CyclinD1 in tissues. A follow-up was conducted in all the patients and the survival was analyzed. To verify the correlation of IL-6 and JAK2/STAT3 pathway, CNE-1 and SUNE1 NPC cells were interpreted with IL-6 and JAK2/STAT3 signaling pathway inhibitor AG490 to detect cell viability, migration and invasion. We observed thatIL-6 increased in serum of NPC patients. The expressions of IL-6, STAT3, p-STAT3, JAK2, p-JAK2 and CyclinD1 in NPC tissues were higher and correlated with TNM stage and lymph node metastasis (LNM). Survival rates were reduced in patients with positive expressions of IL-6, STAT3, p-STAT3, JAK2, p-JAK2 and CyclinD1. LNM and positive expressions of IL-6 and p-STAT3 were risk factors for poor prognosis of NPC. Besides, recombinant human IL-6 promoted cell proliferation, invasion and migration while AG490 inhibited cell proliferation, invasion and migration in CNE-1 and SUNE1 NPC cells. The results demonstrated that increased IL-6 expression and the activated JAK2/STAT3 signaling pathway had effects on prognosis and reduced the survival time in NPC patients, which provide a potential target for the treatment of NPC.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC8266356.xml
SHA-256: 9c3d042657bfc01bb2f5482a56eed84d0fd6d6cd6c87b8f13bc939865099d006

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 2,
    "text": "Inflammatory mediators, including TNF-α, IL-6, TGF-β, and IL-10, have been widely incriminated in chronic inflammation and the progression of cancers [16–17]. The pathological feature of NPC tumor microenvironment (TME) is that it releases a large amount of inflammatory messengers such as cytokines (TNF-α, IL-6), which causes immune cell infiltration and promotes tumorigenesis [18]. IL-6 is a pleiotropic cytokine that regulates cell proliferation and inhibits apoptosis and has been proven to overexpress in many types of tumors, such as colon, liver, breast, brain tumor and NPC; furthermore, IL-6 activates multiple pro-proliferation and anti-survival proteins to stimulate growth of tumor cells [19–21]. By binding to its cognate receptor on the cell membrane (IL-6R), IL-6 transduces their signals via membrane-bound glycoprotein 130 (gp130) mostly to indicate transducers and activators of transcription 3 (STAT3) [22, 23]. After stimulation by IL-6, the gp130 forms a dimmer and activates the Janus-activated kinase (JAK1, JAK2 and Tyk2) signal transducer and activator of transcription (JAK/STAT) signaling pathway, especially STAT3 [24]. The JAK/STAT signaling pathway is the main pathway of IL-6, which is constitutively activated by IL-6 and frequently observed in a variety of human cancers, including NPC [25–27]. IL-6 promotes NPC migration of bystander tumor cells by IL-6R/JAK/STAT3 pathway [28]. JAK2/STAT3 signaling pathway plays a critical role in the occurrence and development of tumor cells [29]. STAT3 will be activated by JAK2 when cells receive the pro-proliferative stimu"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 5,
    "text": "The concentration of IL-6 in serum was measured, respectively using ELISA Kit (ZhongShan JohnKing Pharmaceutical Co., Zhongshan, China) according to the manufacturer’s instructions. An enzyme-labeling plate was placed at room temperature for 30 min, and 100 μl standard samples were then added into 6 wells. Each well was supplemented with 100 μl serum samples. Then each well was added with 50 μl enzyme-labeling solution and placed at room temperature for 90 min. Subsequently, the plate was washed 5 times (10–20 s every time). Each well was added with 50 μl A solution and 50 μl B solution as substrates and incubated for 15 min in the dark. Then 50 μl stop solution was added into each well to terminate the reaction. The optical density (OD450 nm) value of each well was measured by the microplate reader (Thermo Fisher Scientific, Carlsbad, CA, USA)"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 6,
    "text": "The NPC tissues and normal nasopharyngeal epithelial tissues were collected, fixed with 10% formaldehyde, paraffin-embedded and cut into sections (4 μm). The sections were incubated at 65°C for 30 min, deparaffinized, hydrated and washed 3 times with double distilled water. Sections were soaked in 3% H2O2 for 15 min and washed 3 times with phosphate-buffered saline (PBS, 0.01 mol/L). Then sections were soaked in citrate buffer, boiled for 15 min and fully cooled. The sections were washed 3 times again with PBS and incubated with rabbit anti-human primary antibodies IL-6 (Cat# ab6672, 1:500, Abcam, Cambridge, MA, USA), JAK (Cat# ab39636, 1:100, Abcam, Cambridge, MA, USA), p-JAK (Cat# ab32101, 1:100, Abcam, Cambridge, MA, USA), STAT3 (Cat# 119352, 1:600, Abcam, Cambridge, MA, USA), p-STAT3 (Cat# ab76315, 1:100, Abcam, Cambridge, MA, USA) and CyclinD1 (Cat# ab134175, 1:100, Abcam, Cambridge, MA, USA) overnight in the refrigerator at 4°C. After being washed with PBS 3 times, the sections were incubated with HRP-conjugated secondary antibodies (1:5,000; cat. no.S A00004-10, Proteintech Group, Inc.) for 20 min at 37°C and then incubated with SP solution at 37°C for 20 min. Then, the sections were stained with diaminobenzidine (DAB) (Maxim Biotechnology Company, Fuzhou, Fujian, China) and re-stained with hematoxylin. After dehydration and mounting, the sections were viewed using a microscope Olympus BX51 (Olympus Optical Co., Ltd, Tokyo, Japan). Staining cells usually presented brownish yellow granules. The staining intensity of cells was scored as follows: uncolored or not obviou"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "interleukin-6",
      "STAT3"
    ],
    "paragraph_index": 8,
    "text": "Abbreviations: RT-qPCR: reverse transcription quantitative polymerase chain reaction; IL-6: interleukin-6; STAT3: Signal transducers and activators of transcription 3; JAK2: Janus kinase 2; GAPDH: glyceraldehyde-3-phosphate dehydrogenase."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 9,
    "text": "The NPC tissues and normal tissues were washed with PBS, added with cell lysates containing with protease inhibitors, shaken at 4°C for 5 min and centrifuged at 4°C for 10 min at the rate 37100 × g. The proteins were extracted from the supernatant by using Qproteome Mammalian Protein Prer kit (QIAGEN, GmbH, Germany). Proteins (50 μg) were obtained for sodium dodecyl sulfate-polyacrylamide gel electrophoresis (SDS-PAGE) and then moved to nitrocellulose membranes. Following blocking with skimmed milk and incubated overnight with the following primary antibody IL-6 (Cat# ab9324, 0.4 μg/ml, Abcam, Cambridge, MA, USA), JAK (Cat# ab205223, 1: 500, Abcam, Cambridge, MA, USA), p-JAK (Cat# ab32101, 1: 1000, Abcam, Cambridge, MA, USA), STAT3 (Cat# 119352, 1:600, Abcam, Cambridge, MA, USA), p-STAT3 (Cat# ab76315, 1:2000, Abcam, Cambridge, MA, USA) and CyclinD1 (Cat# ab134175, 1: 10000, Abcam, Cambridge, MA, USA). After washing with tris-buffered saline solution containing Tween 20 (TBST) 4 times (10 min every time), the membranes were incubated with IRDye™ 700DX-labeled IgG (LI-COR Bioscience, NE, USA) antibody (dilution 1:1000, Upstate, NY, USA) at room temperature for 1 h, washed by TBST 4 times and developed with the substrates. The data were analyzed by LabWorks Image Acquisition and Analysis Software (UVP, Inc., Upland, CA, USA) to obtain the relative protein concentration."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 11,
    "text": "NPC CNE-1 cells and SUNE1 cells were obtained from Shanghai Institute of Cell Bank. The CNE-1 cells and SUNE1 cells were inoculated into a RPMI 1640 culture medium with 10% fetal bovine serum (FBS) and 1% penicillin-streptomycin in an incubator with 5% CO2 at 37°C. Subculture (1:3) was carried out when cell confluence reached 90%. The cells in logarithmic growth phase were placed on a 6 well-plate (1 × 105 cells/well, 3 ml nutrient fluid each well) and the following experiment was carried out when cell confluence reached 50% to 70%. AG490, which is used to selectively inhibit JAK/Stat-3 activation, inhibits the activation of Stat-3 by selectively blocking JAK2 [36]. AG490 could also inhibit cell proliferation and induce cell apoptosis by blocking the activation of JAK2 mediated by IL-6 [37]. The CNE-1 cells and SUNE1 cells were grouped into five groups: blank group (equal volume of culture medium), NC group (equal density of dimethyl sulfoxide (DMSO) culture medium), IL-6 group (100 ng/mL recombinant human IL-6 culture medium, Peprotech, Rocky Hill, NJ, USA) [38], AG490 group (50 uM JAK2/STAT3 signaling pathway inhibitor AG490, Alexis, Philadelphia, PA, USA; [39], and IL-6 + AG490 group (100 ng/mL recombinant human IL-6 + 50 uM AG490)."
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

### Packet heldout_rrpv1_0015

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
  "title": "Propionibacterium acnes Induces IL-1β secretion via the NLRP3 inflammasome in human monocytes.",
  "pmid": "23884315",
  "pmcid": "PMC4116307",
  "doi": "10.1038/jid.2013.309"
}
```

Abstract:
Propionibacterium acnes induction of inflammatory responses is a major etiological factor contributing to the pathogenesis of acne vulgaris. In particular, the IL-1 family of cytokines has a critical role in both initiation of acne lesions and in the inflammatory response in acne. In this study, we demonstrated that human monocytes respond to P. acnes and secrete mature IL-1β partially via the NLRP3-mediated pathway. When monocytes were stimulated with live P. acnes, caspase-1 and caspase-5 gene expression was upregulated; however, IL-1β secretion required only caspase-1 activity. P. acnes induced key inflammasome genes including NLRP1 and NLPR3. Moreover, silencing of NLRP3, but not NLRP1, expression by small interfering RNA attenuated P. acnes-induced IL-1β secretion. The mechanism of P. acnes-induced NLRP3 activation and subsequent IL-1β secretion was found to involve potassium efflux. Finally, in acne lesions, mature caspase-1 and NLRP3 were detected around the pilosebaceous follicles and colocalized with tissue macrophages. Taken together, our results indicate that P. acnes triggers a key inflammatory mediator, IL-1β, via NLRP3 and caspase-1 activation, suggesting a role for inflammasome-mediated inflammation in acne pathogenesis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4116307.xml
SHA-256: 35bc7228f7bc239f7db5775a87db34fb678f259920abea67eab3b9a8b2736ff9

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "Propionibacterium acnes which resides in pilosebaceous follicles in both acne and non-acne subjects, plays a key role in eliciting host inflammatory responses that are thought to be essential for the pathogenesis and responsible for the clinical manifestation of acne vulgaris (Bojar and Holland, 2004). P. acnes contributes to the inflammatory nature of acne by inducing innate immune cells to secrete pro-inflammatory cytokines including TNF-α, IL-6, IL-8 and IL-12 (Kim et al., 2002). The IL-1 family of cytokines has been implicated as an initiator and a key player in the pathogenesis of acne (Ingham et al., 1992). IL-1β has been shown to be a potent inducer of proinflammatory cytokines IL-6 and IL-8 in sebocytes suggesting a potential role in diseases of the pilosebaceous unit such as acne (Mastrofrancesco et al., 2010). Our laboratory and others have previously demonstrated that P. acnes induces inflammatory cytokines and metalloproteinases (MMPs) in part through Toll-like receptor (TLR)-2 (Jalian et al., 2008; Kim et al., 2002)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "Nucleotide Oligomerization Domain (NOD) like receptors (NLRs), are an important class of cytosolic pattern recognition receptors sensing microbial molecules and danger signals and triggering inflammation and anti-microbial responses (Martinon and Tschopp, 2005). NLRs are a part of inflammasome complexes, which are a central component for regulation of IL-1β maturation and secretion (Martinon et al., 2002). Involvement of inflammasome complexes in inducing inflammatory responses in skin diseases, including psoriasis and Staphylococcus infection, has been recently demonstrated (Dombrowski et al., 2011; Miller et al., 2007; Murphy et al., 2000). However, the involvement of inflammasome activation in P. acnes-induced inflammation remains elusive. Therefore, we have investigated the role of inflammasome activation in IL-1β regulation in human monocytes in response to P. acnes."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "Our previous studies showed that P. acnes induces the inflammatory cytokines IL-8 and IL-12 in human monocytes (Kim et al., 2002). In order to determine whether P. acnes induces IL-1β in primary human monocytes, we obtained monocytes from normal subjects and exposed them to live P. acnes at various MOIs (0.1, 0.5 and 1.0) for 24 hours and the expression of IL-1β mRNA was determined by qRT-PCR. P. acnes induced IL-1β gene expression by 100-200 fold in comparison to media control over a range of MOI (p<0.01, Fig. 1a). The induction of pro-IL-1p protein was determined by western blot analysis of cell lysates, confirming the upregulation of pro-IL-1β (31kD) when cells were stimulated with live P. acnes (Fig. 1b). In addition, secretion of mature IL-1β following stimulation with P. acnes was significantly induced (4,000-5,000 pg/ml) over a range of MOI (p<0.01) (Fig. 1c)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "It has been shown that several bacterial components are critical activators of TLR2-mediated response (Lamkanfi et al., 2009a; Mariathasan et al, 2006; Sutterwala et al., 2006). Our previous studies showed that TLR2 mediates P. acnes induction of innate immune response in monocytes by inducing IL-8 and Il-12 production; however, whether TLR2 pathway is specifically involved in IL-1β regulation in the presence of P. acnes is not clear yet. Using TLR2 blocking Ab, we show that P. acnes induction of IL-1β is suppressed by approximately 50% at mRNA (Fig. 1d) and 40% at protein/secreted (Fig. 1e) levels respectively, indicating that TLR2 is at least partially but not soley involved in IL-1β induction."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "In order to determine other factors/pathways in addition to TLR2 that mediate P. acnes induction of IL-1β, we studied inflammasome complex involved in inducing innate immune response. Since mature IL-1β requires proteolytic cleavage by inflammatory caspases, we examined the expression of two caspases, caspase-1 and caspase-5 involved in inflammation (Martinon and Tschopp, 2007). We found that monocytes stimulated with P. acnes significantly induced the mRNA expression of both caspase-1 and caspase-5, by approximately 5-fold and 6-fold respectively, in comparison to cells cultured in media alone (p<0.01) (Fig. 2a)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 7,
    "text": "In order to determine whether caspase-1 and/or caspase-5 played a role in P. acnes-induced IL-1β secretion, we performed inhibitor studies. Monocytes were pre-treated with either Z-YVAD-FMK or Z-WED-FMK, specific inhibitors of caspase-1 and caspase-5, respectively, prior to stimulation with live P. acnes. IL-1β secretion following P. acnes stimulation was inhibited in a concentration-dependent manner by the caspase-1 inhibitor, Z-YVAD-FMK (p<0.01, p<0.05) (Fig. 2b). In contrast, there was no significant change in IL-1β secretion in the presence of the caspase-5 specific inhibitor (Fig. 2c). In comparison, P. acnes induced IL-6 in the presence of both caspase-1 and caspase-5 inhibitors (supplementary data, Fig 1) suggesting that specific induction of IL-1β by P. acnes is dependent on caspase-1."
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

### Packet heldout_rrpv1_0016

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
  "title": "Brucella abortus nitric oxide metabolite regulates inflammasome activation and IL-1β secretion in murine macrophages.",
  "pmid": "30919410",
  "pmcid": "PMC7484905",
  "doi": "10.1002/eji.201848016"
}
```

Abstract:
NLRP3 inflammasome is a protein complex crucial to caspase-1 activation and IL-1β and IL-18 maturation. This receptor participates in innate immune responses to different pathogens, including the bacteria of genus Brucella. Our group recently demonstrated that Brucella abortus-induced IL-1β secretion involves NLRP3 inflammasome and it is partially dependent on mitochondrial ROS production. However, other factors could be involved, such as P2X7-dependent potassium efflux, membrane destabilization, and cathepsin release. Moreover, there is increasing evidence that nitric oxide acts as a modulator of NLRP3 inflammasome. The aim of this study was to unravel the mechanism of NLRP3 inflammasome activation induced by B. abortus, as well as the involvement of bacterial nitric oxide (NO) as a modulator of this inflammasome pathway. We demonstrated that NO produced by B. abortus can be used by the bacteria to modulate IL-1β secretion in infected murine macrophages. Additionally, our results suggest that B. abortus-induced IL-1β secretion depends on a P2X7-independent potassium efflux, lysosomal acidification, cathepsin release, mechanisms clearly associated to NLRP3 inflammasome. In summary, our results help to elucidate the molecular mechanisms of NLRP3 activation and regulation during an intracellular bacterial infection.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7484905.xml
SHA-256: ff684c384dfb72ef119024b029b0beee5cd4f3cefbacc8d60a62aa96cb21ce52

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
    "text": "Over the past years, inflammasomes gained attention by their role on defense against pathogens and in the development of metabolic, neurodegenerative and autoinflammatory diseases as well as in cancer [1]. Inflammasomes are multiprotein platforms which control maturation of the proinflammatory cytokines interleukin-1β (IL-1β) and IL-18 [2]. Several inflammasomes have been identified, and most of them include either receptors of the NOD-like receptor family of proteins (e.g. NLRP3, NLRP1 and NLRPC4) or AIM receptors (AIM2 inflammasome). However, the NLRP3 is by far the most studied inflammasome [3, 4]. NLRP3 pathway requires at least two signals: the first is provided by microbial molecules or endogenous cytokines and leads to the upregulation of NLRP3 and pro-IL-1β through the activation of the transcription factor NF-κB; the second signal is provided by diverse stimuli, such as pathogen or damage-associated molecular patterns (PAMPs or DAMPs, respectively), triggering the assembly of the NLRP3 inflammasome and multimerization of the adaptor molecule ASC [5]. However, the molecular interactions that engage the NLRP3 inflammasome in response to such distinct stimuli are still unclear. Recently, it has been shown that sodium (Na+) influx and most notably potassium (K+) efflux via purinergic receptor P2X7 are events related to NLRP3 inflammasome activation induced by bacterial toxins and particulate matter [6, 7]. A second model proposed that NLRP3 acts as a cell stress sensor, activated by reactive oxygen species (ROS) generated in spatial and temporal proximity to the inflam"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "Increasing evidence has shown that NLRP3 inflammasome activation is important for host defense and effective pathogen clearance against microbial infections [10]. Previous reports have shown that the immune responses against Gram-positive bacteria such as Staphylococcus aureus or Listeria monocytogenes requires NLRP3 activation, the same is not true for Salmonella typhimurium or Francisella tularensis (Gram-negative bacteria) [11]. However, some Gram-negative enteropathogens, such as enterohemorrhagic Escherichia coli (EHEC) and Citrobacter rodentium, induce NLRP3 inflammasome activation in bone marrow-derived macrophages in a Toll-IL-1 receptor (TIR)-domain-containing adapter-inducing interferon-β (TRIF)-dependent pathway [12]. Furthermore, Neisseria gonorrhoeae induces a cathepsin B-dependent NLRP3 inflammasome activation and cell death [13]. Experiments with macrophages infected with Paracoccidioides brasiliensis also showed that endosomal-lysosomal acidification is a mechanism involved in NLRP3 inflammasome activation [14]. Brucella abortus is a facultative intracellular gram-negative cocobacillus, causative agent of brucellosis in humans and livestock. In humans, it causes undulant fever, endocarditis, arthritis and osteomyelitis; in livestock, it leads to abortion and infertility, resulting in significant economical losses [15, 16]. Our group published recently that IL-1β secretion in macrophages infected with Brucella abortus was partially dependent on mitochondrial ROS. Moreover, infected NLRP3 knockout (KO) macrophages secreted lower levels of IL-1β than wild-type "
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "To deal with host immune response, some bacteria have evolved diverse strategies to manipulate inflammasome activation in host cells [18]. Legionella pneumophila, for example, controls ASC levels to manipulate inflammasome, apoptosome and NF-κB pathways, establishing the necessary environment for its replication within human monocytes [19]. The protein RipA from Francisella tularensis inhibits IL-1β, IL-18 and TNF-α secretion in macrophages to evade host immunity; mice infected with mutants for RipA produced higher levels of inflammatory cytokines when compared to the wild-type bacteria [20]. It was recently described that nitric oxide (NO) negatively regulates IL-1β processing, through inhibition of NLRP3 inflammasome assembly in cells infected with Mycobacterium tuberculosis [21]. In humans, Mycobacterium bacilli reside in granulomas, structures which may limit the availability of oxygen. Under these conditions, there is an increased expression of genes involved in denitrification, a energy-yelding metabolic process which converts nitrate (NO3−) to inert nitrogen gas (N2), with NO as a intermediate metabolite [22, 23]. However, the hypothesis of IL-1β production being modulated by Mycobacterium NO has not been tested yet. Recently, genomic analysis has revealed that members of the genus Brucella also possess denitrifying genes in their genomes [24, 25], and this raises the hypothesis of Brucella NO as a regulator of NLRP3-dependent IL-1β, since it has been shown that genes involved in denitrification regulate Brucella virulence in mice [26]."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "In the present study, we investigated the cellular and molecular mechanisms involved in NLRP3 activation during B. abortus infection. Most importantly, we demonstrated that NO produced by B. abortus is a modulator of NLRP3-dependent IL-1β production and acts as an evasion strategy used by this pathogen to avoid proper host innate immune responses."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "The NLRP3 inflammasome can be activated by a variety of stimuli, including extracellular ATP, microbial toxins (e.g., nigericin), and crystalline particles, all converging on potassium efflux [27]. Previous studies have reported that potassium efflux is important in caspase-1 activation, IL-1β processing, and cell death and NLRP3 activation is inhibited by high extracellular [K+] [6, 28]. To test whether potassium efflux is involved in B. abortus-induced NLRP3 inflammasome activation, two defined inhibitors were used to treat B. abortus-infected BMDMs, glibenclamide (a selective inhibitor for ATP-dependent potassium channels) and KCl (since high extracellular concentrations of K+ prevent NLRP3 activation). Addition of increasing concentrations of glibenclamide and KCl to macrophages prior to bacterial infection reduced IL-1β secretion in a dose-dependent manner (Fig 1A and 1B) without significant changes in TNF-α (Figs 1C and 1D), an inflammasome-independent cytokine. Moreover, Western blot analysis showed that treatment of BMDMs with glibenclamide and KCl prior to B. abortus infection does not significantly affect pro-IL-1 β and pro-caspase-1 levels but it results in a decrease in secreted IL-1β and caspase-1 mature forms (Fig 1E). These results suggest that potassium efflux induces a NLRP3-dependent caspase-1 activation and IL-1β secretion in B. abortus-infected BMDM."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "The occurrence of extracellular ATP is considered a signal for the immune system, particularly during an inflammatory response. It is sensed by P2X receptors, whose activation by ATP opens a cation-specific channel and alters the ionic environment of the cell activating several pathways including the inflammasome [29]. Moreover, studies suggest that P2X7R opening causes a drastic change in K+ homeostasis which has an important role in caspase-1 activation and NLRP3-dependent IL-1β release [30, 31]. Therefore, we investigate the potential role of P2X7R in the IL-1β secretion induced by B. abortus in macrophages using two different approaches: first, by preincubating BMDMs with A740003 (a selective P2X7 purinoceptor antagonist) before infecting with B. abortus, and secondly, by quantifying IL-1β secretion in infected P2X7 knockout cells. As shown in the Fig 2A, IL-1β secretion in B. abortus-infected cells was not affected by the presence of the inhibitor, even when tested at higher concentrations (50 μM). As a control, cells were preincubated with A740003 at the highest concentration tested and then stimulated with LPS plus ATP. As expected, the presence of the inhibitor was sufficient to abolish IL-1β secretion. Moreover, no differences in cytokine secretion were observed between wild-type and P2X7R KO BMDMs, when infected with the bacteria (Fig 2B). The results suggest that P2X7R does not play an essential role in B. abortus-induced IL-1β secretion."
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

### Packet heldout_rrpv1_0025

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
  "title": "Oxidative exposure impairs TGF-β pathway via reduction of type II receptor and SMAD3 in human skin fibroblasts.",
  "pmid": "24550076",
  "pmcid": "PMC4082581",
  "doi": "10.1007/s11357-014-9623-6"
}
```

Abstract:
Exposure to oxidants results in cellular alterations that are implicated in aging and age-associated diseases. Here, we report that brief, low-level oxidative exposure leads to long-term elevation of cellular reactive oxygen species (ROS) levels and oxidative damage in human skin fibroblasts. Elevated ROS impairs the transforming growth factor-β (TGF-β) pathway, through reduction of type II TGF-β receptor (TβRII) and SMAD3 protein levels. This impairment results in reduced expression of connective tissue growth factor (CTGF/CCN2) and type I collagen, which are regulated by TGF-β. Restoration of TβRII and SMAD3 together, but not separately, reinstates TGF-β signaling and increases CTGF/CCN2 and type I collagen levels. Treatment with the anti-oxidant N-acetylcysteine reduces ROS elevation and normalizes TGF-β signaling and target gene expression. These data reveal a novel linkage between limited oxidant exposure and altered cellular redox homeostasis that results in impairment of TGF-β signaling. This linkage provides new insights regarding the mechanism by which aberrant redox homeostasis is coupled to decline of collagen production, a hallmark of human skin aging.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4082581.xml
SHA-256: 09a3138f65bb15383970a4dcd148116ffcb840f825bb668e0236a00069a5d246

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

### Packet heldout_rrpv1_0026

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
  "title": "Effects of Tenascin C on the Integrity of Extracellular Matrix and Skin Aging.",
  "pmid": "33217999",
  "pmcid": "PMC7698786",
  "doi": "10.3390/ijms21228693"
}
```

Abstract:
Tenascin C (TNC) is an element of the extracellular matrix (ECM) of various tissues, including the skin, and is involved in modulating ECM integrity and cell physiology. Although skin aging is apparently associated with changes in the ECM, little is known about the role of TNC in skin aging. In this study, we found that the Tnc mRNA level was significantly reduced in the skin tissues of aged mice compared with young mice, consistent with reduced TNC protein expression in aged human skin. TNC-large (TNC-L; 330-kDa) and -small (TNC-S; 240-kDa) polypeptides were observed in conditional media from primary dermal fibroblasts. Both recombinant TNC polypeptides, corresponding to TNC-L and TNC-S, increased the expression of type I collagen and reduced the expression of matrix metalloproteinase-1 in fibroblasts. Treatment of fibroblasts with a recombinant TNC polypeptide, corresponding to TNC-L, induced phosphorylation of SMAD2 and SMAD3. TNC increased the level of transforming growth factor-β1 (TGF-β1) mRNA and upregulated the expression of type I collagen by activating the TGF-β signaling pathway. In addition, TNC also promoted the expression of type I collagen in fibroblasts embedded in a three-dimensional collagen matrix. Our findings suggest that TNC contributes to the integrity of ECM in young skin and to prevention of skin aging.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7698786.xml
SHA-256: 1c86907d73fc45c7217daf97ed01078dd271d3e4309da74d10a492aad06ca377

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "collagen I",
      "type I collagen"
    ],
    "paragraph_index": 4,
    "text": "TNC is known to upregulate the expression of type I collagen in foreskin fibroblasts and hepatic stellate cells [16,17]. The expression of TNC is elevated in collagen diseases [16] that are characterized by inflammation, autoimmune attack, and vascular damage and often leads to fibrosis [18]. Patients with increased TNC levels show a higher incidence of diffuse cutaneous systemic sclerosis, severe thickened skin, and probability of pulmonary fibrosis compared to those with normal levels."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "type I collagen"
    ],
    "paragraph_index": 5,
    "text": "Transforming growth factor-β (TGF-β) upregulates collagens and downregulates matrix metalloproteinases (MMPs), the major enzymes involved in degrading collagens and ECM components, and also contributes to the prevention of collagen loss in aged human skin [19]. TNC deficiency attenuates TGF-β-mediated fibrosis following immune-mediated chronic hepatitis [20] or acute lung injury [21]. TNC induces activation of hematopoietic stem cells mediated by TGF-β1 and α9β1 integrin, thereby elevating type 1 collagen production and promoting cell migration [17]. TNC also activates the TGF-β signaling pathway and induces the expression of type I collagen, at least in fibrotic lesions."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "collagen I",
      "type I collagen"
    ],
    "paragraph_index": 6,
    "text": "Previous studies suggest that TNC is implicated in collagen biosynthesis and is relevant to TGF-β signaling in fibroblasts. However, the role of TNC in normal skin, particularly during aging, has not been studied. In the present study, we investigated the expression of TNC in skin tissues from young and aged mice and humans by reverse transcription-polymerase chain reaction (RT-PCR) and histological analysis. The major forms of TNC that are expressed in human primary dermal fibroblasts were also analyzed. Next, the major forms of human TNC were ectopically expressed, and the effect of recombinant TNC polypeptides on the secretion of type I collagen and MMP-1 in foreskin fibroblasts was analyzed. We then analyzed the molecular mechanism of TNC-induced upregulation of type I collagen. In addition, the effect of TNC on the synthesis of type I collagen was validated in fibroblasts cultured in a three-dimensional (3D) collagen matrix. Based on our findings, we suggest that TNC is an important molecule that maintains the ECM integrity and prevents and attenuates skin aging."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "type I collagen"
    ],
    "paragraph_index": 10,
    "text": "We next analyzed whether TNC could induce changes in the expression of type I collagen and MMP-1 in foreskin fibroblasts. Cells were treated with recombinant human TNC-2201 and TNC-1564 polypeptides as well as TGF-β1 (as a positive control). Both recombinant TNC polypeptides as well as TGF-β1 caused a significant increase in type I collagen and a significant decrease in MMP-1 at the protein level (Figure 2C). The two TNC isoforms, however, showed no difference in the increase of type I collagen level and the decrease of MMP-1 level (Figure 2C). Therefore, a recombinant TNC-2201 polypeptide was used for further analysis of TNC."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "COL1A1"
    ],
    "paragraph_index": 11,
    "text": "The mRNA levels of COL1A1, COL1A2, and MMP-1 with or without TNC treatment were analyzed in foreskin fibroblasts by conventional and quantitative RT-PCR. As expected, COL1A1 and COL1A2 mRNA levels were significantly upregulated following treatment with TNC as well as TGF-β1 (Figure 3). However, MMP-1 mRNA level was decreased following TNC treatment, although the difference was not statistically significant (Figure 3)."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "type I collagen"
    ],
    "paragraph_index": 12,
    "text": "To elucidate whether the TNC-mediated induction of type I collagen expression involves TGF-β signaling pathway, we analyzed the activation of representative R-SMADs, SMAD2, and SMAD3 in foreskin fibroblasts following TNC treatment. Treatment with TNC (2 µg/mL) as well as TGF-β1 (3 ng/mL) increased the phosphorylation of SMAD2 and SMAD3 (Figure 4A). Next, the effect of SB431542, an inhibitor of TGF-β receptor type I, was examined on TNC-induced SMAD2 activation in foreskin fibroblasts. Treatment with SB431542 abolished SMAD2 phosphorylation induced by TNC and severely impaired TGF-β1-induced phosphorylation (Figure 4B). In addition, SB431542 inhibited TNC-induced type I collagen secretion, whereas it restored TNC-mediated suppression of MMP-1 secretion (Figure 4C). These results demonstrate that TNC induces type I collagen expression via activation of TGF-β receptors and R-SMADs."
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

### Packet heldout_rrpv1_0035

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
  "title": "Pancreatic GLP-1 receptor activation is sufficient for incretin control of glucose metabolism in mice.",
  "pmid": "22182839",
  "pmcid": "PMC3248276",
  "doi": "10.1172/JCI42497"
}
```

Abstract:
Glucagon-like peptide-1 (GLP-1) circulates at low levels and acts as an incretin hormone, potentiating glucose-dependent insulin secretion from islet β cells. GLP-1 also modulates gastric emptying and engages neural circuits in the portal region and CNS that contribute to GLP-1 receptor-dependent (GLP-1R-dependent) regulation of glucose homeostasis. To elucidate the importance of pancreatic GLP-1R signaling for glucose homeostasis, we generated transgenic mice that expressed the human GLP-1R in islets and pancreatic ductal cells (Pdx1-hGLP1R:Glp1r-/- mice). Transgene expression restored GLP-1R-dependent stimulation of cAMP and Akt phosphorylation in isolated islets, conferred GLP-1R-dependent stimulation of β cell proliferation, and was sufficient for restoration of GLP-1-stimulated insulin secretion in perifused islets. Systemic GLP-1R activation with the GLP-1R agonist exendin-4 had no effect on food intake, hindbrain c-fos expression, or gastric emptying but improved glucose tolerance and stimulated insulin secretion in Pdx1-hGLP1R:Glp1r-/- mice. i.c.v. GLP-1R blockade with the antagonist exendin(9-39) impaired glucose tolerance in WT mice but had no effect in Pdx1-hGLP1R:Glp1r-/- mice. Nevertheless, transgenic expression of the pancreatic GLP-1R was sufficient to normalize both oral and i.p. glucose tolerance in Glp1r-/- mice. These findings illustrate that low levels of endogenous GLP-1 secreted from gut endocrine cells are capable of augmenting glucoregulatory activity via pancreatic GLP-1Rs independent of communication with neural pathways.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3248276.xml
SHA-256: ece2d7ffcef7043b42b1b5bbf3e41af24172546d1eb36942312f89705eae7955

Frozen fulltext excerpts:
```json
[]
```

Fields fulltext was expected to resolve:
["evidence_mode", "context"]

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

### Packet heldout_rrpv1_0036

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
  "title": "Glucagon-like peptide 1 receptor induced suppression of food intake, and body weight is mediated by central IL-1 and IL-6.",
  "pmid": "24048027",
  "pmcid": "PMC3791711",
  "doi": "10.1073/pnas.1306799110"
}
```

Abstract:
Glucagon-like peptide 1 (GLP-1), produced in the intestine and the brain, can stimulate insulin secretion from the pancreas and alleviate type 2 diabetes. The cytokine interleukin-6 (IL-6) may enhance insulin secretion from β-cells by stimulating peripheral GLP-1 production. GLP-1 and its analogs also reduce food intake and body weight, clinically beneficial actions that are likely exerted at the level of the CNS, but otherwise are poorly understood. The cytokines IL-6 and interleukin 1β (IL-1β) may exert an anti-obesity effect in the CNS during health. Here we found that central injection of a clinically used GLP-1 receptor agonist, exendin-4, potently increased the expression of IL-6 in the hypothalamus (11-fold) and the hindbrain (4-fold) and of IL-1β in the hypothalamus, without changing the expression of other inflammation-associated genes. Furthermore, hypothalamic and hindbrain interleukin-associated intracellular signals [phosphorylated signal transducer and activator of transcription-3 (pSTAT3) and suppressor of cytokine signaling-1 (SOCS1)] were also elevated by exendin-4. Pharmacologic disruption of CNS IL-1 receptor or IL-6 biological activity attenuated anorexia and body weight loss induced by central exendin-4 administration in a rat. Simultaneous blockade of IL-1 and IL-6 activity led to a more potent attenuation of exendin-4 effects on food intake. Mice with global IL-1 receptor gene knockout or central IL-6 receptor knockdown showed attenuated decrease in food intake and body weight in response to peripheral exendin-4 treatment. GLP-1 receptor activation in the mouse neuronal Neuro2A cell line also resulted in increased IL-6 expression. These data outline a previously unidentified role of the central IL-1 and IL-6 in mediating the anorexic and body weight loss effects of GLP-1 receptor activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3791711.xml
SHA-256: 70358c22f556dbbe965da3398b7599fca7ea3a580eac2b73863465dcfcd59a05

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

### Packet heldout_rrpv1_0043

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
  "title": "AXL/CDCP1/SRC axis confers acquired resistance to osimertinib in lung cancer.",
  "pmid": "35643725",
  "pmcid": "PMC9148303",
  "doi": "10.1038/s41598-022-12995-8"
}
```

Abstract:
Osimertinib, a third-generation EGFR-TKI, has nowadays been applied to non-small cell lung cancer harboring activated EGFR mutation with or without T790M, but ultimately develop resistance to this drug. Here we report a novel mechanism of acquired resistance to osimertinib and the reversal of which could improve the clinical outcomes. In osimertinib-resistant lung cancer cell lines harboring T790M mutation that we established, expression of multiple EGFR family proteins and MET was markedly reduced, whereas expression of AXL, CDCP1 and SRC was augmented along with activation of AKT. Surprisingly, AXL or CDCP1 expression was induced by osimertinib in a time-dependent manner up to 3 months. Silencing of CDCP1 or AXL restored the sensitivity to osimertinib with reduced activation of SRC and AKT. Furthermore, silencing of both CDCP1 and AXL increased the sensitivity to osimertinib. Either silencing of SRC or dasatinib, a SRC family kinase (SFK) inhibitor, suppressed AKT phosphorylation and cell growth. Increased expression of AXL and CDCP1 was observed in refractory tumor samples from patients with lung cancer treated with osimertinib. Together, this study suggests that AXL/SFK/AKT and CDCP1/SFK/AKT signaling pathways play some roles in acquired osimertinib resistance of non-small cell lung cancer.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9148303.xml
SHA-256: 27fbea191b20c29d8d0e6c0f69be9ece40bf331e85cd6d1dd7b4e57cb1fc39bf

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 1,
    "text": "Treatment with first and second generation epidermal growth factor receptor-tyrosine kinase inhibitors (EGFR-TKIs), such as gefitinib, erlotinib, and afatinib, has contributed to therapeutic responses of patients with lung cancer and treatment-naïve oncogenic and activated mutant EGFR (mutEGFR)1–3. However, most patients ultimately develop acquired resistance to EGFR-TKIs and approximately 60% of such recurrent patients harbor a secondary resistant EGFR mutation involving T790M4,5. Osimertinib has been further developed by selective targeting of mutEGFR T790M, and is highly effective in patients with T790M-mediated resistant tumors6,7. Osimertinib demonstrates robust objective response rates and prolonged progression-free survival in treatment-naïve mutEGFR patients with advanced non-small cell lung cancer (NSCLC) as a first-line treatment8."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 2,
    "text": "However, the acquisition of a secondary EGFR mutation, C797S, has been reported in refractory tumors of patients with EGFR T790M-mediated resistance to gefitinib or erlotinib when treated with osimertinib9,10. Further, either loss or maintenance of the EGFR T790M mutation has been observed in tumors displaying acquired resistance to osimertinib when patients were previously treated with first or second generation EGFR-TKIs11,12. On the other hand, off-target genetic mutational alterations involving KRAS, BRAF, PIK3CA, PTEN, CTNNB1, TSC2, RET, and FGFR3 are associated with acquired resistance to osimertinib11–16. Other off-target mechanisms for osimertinib resistance include gene amplification and/or enhanced expression of HER2, MET, FGFR, MAPK1, AKT3 and AXL, and activation of SRC family kinase (SFK)/focal adhesion kinase (FAK) and Sonic Hedgehog (SHH)14,16–19. Among these pleiotropic mechanisms for drug resistance to EGFR-TKIs, activation of AXL via AXL kinase often confers EGFR-TKI resistance in lung cancer cells in vitro20 and in patients21, and a combination of osimertinib with a multikinase inhibitor cabozantinib of VEGFR, MET, and AXL overcomes resistance in vitro22. However, which mechanism or biomarker may play a greater role in the appearance of osimertinib resistant tumors is not fully understood."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 3,
    "text": "To further develop potent therapeutic strategies to overcome osimertinib resistance, we should elucidate which mechanisms could be closely associated with acquisition of osimertinib resistance, and also which drugs could be useful to overcome osimertinib resistance in progressive lung cancer. In this study, we established osimertinib-resistant (OR) cell lines from lung cancer H1975 cells harboring mutEGFR and T790M after chronic exposure to osimertinib in culture. Acquired resistance to osimertinib is induced by off-target SRC activation in close collaboration with enhanced expression of AXL and Cub domain-containing protein 1 (CDCP1), and activation of AKT. We discuss how a novel bypass pathway involving the AXL/CDCP1/SRC/AKT signaling is activated during acquired resistance to osimertinib, and also how this osimertinib resistance can be overcome."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "We independently established two OR cell lines, OR1 and OR2, from parental H1975 cells harboring L858R and T790M in EGFR by stepwise selection following exposure to osimertinib. OR1 and OR2 exhibited approximately 300-fold higher resistance to osimertinib than the parental H1975 cells, when they exhibited only three to fourfold higher resistance to afatinib but not erlotinib (Table 1). KRAS mutation and a representative osimertinib resistance-related mutation (C797S) in the tyrosine kinase domain of EGFR were not detected in either OR cell line.Table 1Cytotoxicity of erlotinib, afatinib or osimertinib in H1975 and osimertinib-resistant cell lines.Cell linesEGFR mutationsSelected drugIC50 (µmol/L)aErlotinibAfatinibOsimertinibH1975L858R + T790M5.48 (1.00)0.21 (1.00)0.014 (1.00)H1975/OR1Osimertinib6.30 (1.15)0.94 (4.48)4.0 (286)H1975/OR2Osimertinib6.97 (1.27)0.66 (3.14)4.04 (289)aThe relative resistance, defined as the IC50 value divided by the IC50 value of the parental cells, is shown in parentheses."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 5,
    "text": "Cytotoxicity of erlotinib, afatinib or osimertinib in H1975 and osimertinib-resistant cell lines."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 7,
    "text": "OR1 and OR2 displayed markedly reduced expression of EGFR, HER2, HER3, and MET as well as their phosphorylated forms as compared to H1975 cells (Fig. 1a). Among downstream signaling molecules of growth factor receptors, pAKT expression was increased, whereas pSTAT3 expression was reduced, in both OR1 and OR2 cells as compared to H1975 (Fig. 1a). OR1 and OR2 showed markedly decreased expression of E-cadherin and β-catenin as compared to H1975 (Fig. 1b). Osimertinib suppressed phosphorylation of EGFR and ERK1/2 in OR1 and OR2 as H1975 at similar levels. However, phosphorylation of AKT was not affected in OR cells (Fig. 1c).Figure 1Osimertinib-resistant cell lines, OR1 and OR2, show reduced EGFR expression with constitutive activation of AKT. (a) Western blot analysis of EGFR and other molecules in lysates of H1975, OR1 and OR2 cells. (b) Western blot analysis of E-cadherin and β-catenin in lysates of H1975, OR1 and OR2 cells. (c) Expression levels of EGFR and other molecules analyzed after treatment with various doses of osimertinib for 6 h. (d) mRNA expression levels of 9 SFK genes by microarray analysis. Relative-fold changes (OR1 or OR2 vs H1975 cells) are presented with expression levels of each gene in H1975 cells normalized to 1.0. NULL, no significant expression."
  }
]
```

Fields fulltext was expected to resolve:
["therapy"]

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

### Packet heldout_rrpv1_0050

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
  "title": "Superior efficacy of cotreatment with BET protein inhibitor and BCL2 or MCL1 inhibitor against AML blast progenitor cells.",
  "pmid": "30647404",
  "pmcid": "PMC6333829",
  "doi": "10.1038/s41408-018-0165-5"
}
```

Abstract:
First-generation bromodomain extra-terminal protein (BETP) inhibitors (BETi) (e.g., OTX015) that disrupt binding of BETP BRD4 to chromatin transcriptionally attenuate AML-relevant progrowth and prosurvival oncoproteins. BETi treatment induces apoptosis of AML BPCs, reduces in vivo AML burden and induces clinical remissions in a minority of AML patients. Clinical efficacy of more potent BETis, e.g., ABBV-075 (AbbVie, Inc.), is being evaluated. Venetoclax and A-1210477 bind and inhibit the antiapoptotic activity of BCL2 and MCL1, respectively, lowering the threshold for apoptosis. BETi treatment is shown here to perturb accessible chromatin and activity of enhancers/promoters, attenuating MYC, CDK6, MCL1 and BCL2, while inducing BIM, HEXIM1, CDKN1A expressions and apoptosis of AML cells. Treatment with venetoclax increased MCL1 protein levels, but cotreatment with ABBV-075 reduced MCL1 and Bcl-xL levels. ABBV-075 cotreatment synergistically induced apoptosis with venetoclax or A-1210477 in patient-derived, CD34+ AML cells. Compared to treatment with either agent alone, cotreatment with ABBV-075 and venetoclax was significantly more effective in reducing AML cell-burden and improving survival, without inducing toxicity, in AML-engrafted immune-depleted mice. These findings highlight the basis of superior activity and support interrogation of clinical efficacy and safety of cotreatment with BETi and BCL2 or MCL1 inhibitor in AML.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6333829.xml
SHA-256: 433547017f1e1e72e10dc935bb1e148bea45c1a964fbbe8976de609de3f7fb9c

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 1,
    "text": "The bromodomain extra-terminal (BET) protein (BETP) BRD4 interacts with transcription factors as well as cofactors, including mediator protein complex, lysine methyltransferase NSD3, arginine demethylase JMJD6, and pTEFb (a heterodimer of CDK9 and cyclin T), to regulate RNA pol II (RNAP2)-mediated transcript elongation1–4. BRD4 promotes pTEFb-mediated phosphorylation of serine 2 in the heptad repeats within the CTD of RNAP2, as well as of the negative transcription elongation factors, NELF and Sept5, which induces promoter-proximal pause release of RNAP2 and RNA transcript elongation4–6. This has been shown to occur at the enhancers and promoters of oncogenes that promote growth and survival of cancer cells, including acute myeloid leukemia (AML) stem-progenitor cells2,6–9. Consistent with this, knockdown of BRD4 by RNAi, or disruption of its binding to acetylated chromatin by BET inhibitors (BETi) leads to lethality in AML blast progenitor cells (BPCs), associated with down regulation of AML-relevant progrowth and prosurvival oncogenes1,2,10–13. BETis, including JQ1 and OTX015, have been documented to reduce AML burden and improve survival of mice engrafted with human AML BPCs11–13. Whereas treatment with BETi was shown to induce clinical responses in AML, refractoriness to BETi therapy and resistance with disease progression is uniformly observed14–16. This has prompted the development and testing of more potent and effective BETis, e.g., ABBV-07516–20. Since BETi treatment attenuated expressions of several BCL2 family of antiapoptotic proteins11–13,21, to further lower t"
  },
  {
    "matched_frozen_surfaces": [
      "venetoclax",
      "ABT-199"
    ],
    "paragraph_index": 2,
    "text": "BCL2, Bcl-xL, and MCL1 are members of multi-BCL-2 homology (BH) domain (BH1−BH4) containing family of antiapoptotic proteins22,23. They bind proapoptotic BCL2 family members BAX and BAK (containing BH1, BH2, and BH3) and BH3 domain-only proapoptotic activator proteins, to inhibit intrinsic mitochondria-induced pathway of apoptosis22–24. The first, highly selective BCL2 inhibitor venetoclax (ABT-199) binds specifically to BCL2 and displaces BH3 domain-only proteins to trigger BAX/BAK-mediated mitochondria-induced apoptosis of cancer, including AML cells25,26. Venetoclax treatment alone showed anti-AML in vivo efficacy in the mouse xenograft models26,27. Although effective in inducing clinical remissions in AML, innate or acquired resistance to venetoclax alone is commonly observed28. The best predictor of sustained response to venetoclax is the lack of readily accessible resistance mechanisms provided by Bcl-xL and MCL128. In venetoclax-resistant cells, increased MCL1 and/or Bcl-xL levels was observed29. Preclinically, dual targeting of BCL2 and MCL1, but not either alone, was also shown to prolong survival of AML or lymphoma bearing mice30,31. Combining venetoclax with other anti-AML drugs such as cytarabine or DNA hypomethylating agent has yielded higher remission rates32,33. However, a full assessment of their clinical efficacy has not been conducted. In present studies we determined the effects of the BETi on cis-regulatory DNA elements and on mRNA and protein expressions of AML-relevant oncoproteins, including MYC, BCL2, Bcl-xL, MCL1, and CDK6. We also determined whethe"
  },
  {
    "matched_frozen_surfaces": [
      "BRD4",
      "ABT-199"
    ],
    "paragraph_index": 3,
    "text": "In vivo grade ABBV-075 and ABT-199 for mouse xenograft experiments were kindly provided by AbbVie, Inc. In vitro grade A-1210477 (Catalog No. S7790), ABBV-075 (Catalog No. S8400) and ABT-199 (Catalog No. S8048) were purchased from Selleck Chemicals (Houston, TX) and utilized for in vitro experiments. All compounds were prepared as 10 mM stocks in 100% dimethyl sulfoxide (DMSO) and frozen at −80 °C in 5–10 µL aliquots to allow for single use, thus avoiding multiple freeze-thaw cycles that could result in compound decomposition and loss of activity. Anti-BRD4 (RRID:AB_2620184) antibody was obtained from Bethyl Labs (Montgomery, TX). Anti-c-Myc (RRID: AB_1903938), anti-HEXIM1 (Cat #12604), anti-p21 (RRID: AB_823586), anti-p-Histone H2AX (Ser139) (RRID: AB_2118010), anti-Bcl-xL (RRID: AB_10695729), anti-BAX (RRID:AB_2744530), anti-BAK (RRID:AB_2290287), anti-Cleaved PARP (RRID:AB_331426), anti-BIM (RRID:AB_1030947) and anti-MCL1 (RRID:AB_2281980) antibodies were obtained from Cell Signaling Technologies (Beverly, MA). Anti-CDK6 (RRID: AB_10610066), anti-Bcl2 (RRID: AB_626733), Alexa488-conjugated anti-BAX(6A7) (RRID:AB_626728) and anti-β-Actin (RRID: AB_626630) antibodies were obtained from Santa Cruz Biotechnologies (Santa Cruz, CA). Anti-BAK(NT) (RRID:AB_310159) antibody was obtained from Millipore Sigma (Burlington, MA)."
  },
  {
    "matched_frozen_surfaces": [
      "ABT-199"
    ],
    "paragraph_index": 8,
    "text": "Untreated or drug-treated cells were stained with Annexin V-FITC (Pharmingen, San Diego, CA) and TO-PRO-3 iodide (Life Technologies, Carlsbad, CA) and the percentages of apoptotic cells were determined by flow cytometry. To analyze in vitro synergism between ABBV-075 and ABT-199 or A-1210477 or synergy between A-1210477 and ABT-199, cells were treated with in vitro grade single agents and combinations for 48 h and the percentages of annexin V-positive, apoptotic cells were determined by flow cytometry. The combination index (CI) for each drug combination was calculated by median dose effect and isobologram analyses (assuming mutual exclusivity) utilizing the commercially available software Compusyn. CI values of less than 1.0 represent a synergistic interaction of the two drugs in the combination. The CI values were input into GraphPad V7.0 to create Box and Whisker plots of the range of the CI values for each cell line and drug combination."
  },
  {
    "matched_frozen_surfaces": [
      "ABT-199"
    ],
    "paragraph_index": 10,
    "text": "All animal studies were performed under a protocol approved by the IACUC at M.D. Anderson Cancer Center, an AAALAC-accredited institution. To determine the in vivo effects of ABT-199 and/or ABBV-075 on leukemia progression and engraftment, 2 million MOLM13/GFP-Luc cells were injected with a 26-gauge needle into the lateral tail vein of 4–6-week-old female NOD-scid IL2Rgammanull (NSG, Stock number 005557 (RRID:IMSR_JAX:005557); The Jackson Laboratory, Bar Harbor, ME) mice (n = 7) which had received a preconditioning dose of radiation (2.5 Gy) 24 h prior to injection of cells. All the mice were monitored for 4 days and imaged to document engraftment. Mice were randomly assigned to treatment cohorts. Following this, mice were treated daily with vehicle (10% ethanol, 30% PEG400, 60% Phosal 50), 50 mg/kg of ABT-199 (by oral gavage, daily × 5 days per week), 1 mg/kg of ABBV-075 (by oral gavage, daily × 5 days per week) or ABBV-075 + ABT-199 for 2 weeks. Mice were injected with 75 mg/kg of d-Luciferin and imaged once per week by Xenogen camera to monitor disease status and treatment efficacy. Mice that became moribund or experienced hind limb paralysis were euthanized according to the approved IACUC protocol. Investigators were not blinded to the experimental conditions; however, veterinarians and veterinary staff assisting in determining when euthanasia was required were blinded to the experimental conditions of the study. The survival of the mice is represented by a Kaplan-Meier plot. The variance between cohorts was similar. To determine the antileukemia effects of ABBV-075 and"
  },
  {
    "matched_frozen_surfaces": [
      "BRD4"
    ],
    "paragraph_index": 14,
    "text": "Utilizing RNA-Seq analysis, we also determined the impact of BETi-induced perturbations in accessible chromatin on mRNA expressions in the AML SET2 cells. Figure 1d shows the up- or down-regulated mRNA expressions in BETi-treated vs. untreated AML cells. Whereas HEXIM1 and CDKN1A (p21) mRNA levels were induced, mRNA levels of MYC, CDK6, BCL2L1 (Bcl-xL), BCL2, and PIM1 were downregulated. We next confirmed by qPCR analysis whether the more potent BETi ABBV-075 induces similar mRNA perturbations in AML cells, including patient-derived (PD) CD34+ AML BPCs. As shown in Fig. 2a−d, ABBV-075 treatment attenuated MYC, BCL2, Bcl-xL, and CDK6, while inducing HEXIM1 and p21 mRNA levels in MV4-11, OCI-AML5, MOLM13, and PD CD34+ AML BPCs. Genetic alterations detected by NextGen sequencing (NGS) of an AML-associated 28-gene panel, conducted in the AML cell lines, is presented in Fig. S2A. Utilizing a reversed phase protein array (RPPA) and Western analyses, we next determined the effect of ABBV-075 on protein expressions in AML BPCs. Figure S2B demonstrates the heat map of perturbations in protein levels by the RPPA analysis, showing increase in 29 and reduction in 55 protein expressions, following treatment of MV4-11 cells with ABBV-075 for 16 h. As shown in Fig. S2C, among the log2-fold-altered protein levels, proteins involved in cell signaling, cell cycle, and transcription regulators were inhibited, while protein expressions involved in DNA damage response, cell cycle arrest, and cell death were increased. Western analyses confirmed that treatment with ABBV-075 attenuated protein ex"
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "context", "relation", "therapy"]

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

### Packet heldout_rrpv1_0055

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
  "title": "Essential role for vav Guanine nucleotide exchange factors in brain-derived neurotrophic factor-induced dendritic spine growth and synapse plasticity.",
  "pmid": "21880903",
  "pmcid": "PMC3183742",
  "doi": "10.1523/JNEUROSCI.0685-11.2011"
}
```

Abstract:
Brain-derived neurotrophic factor (BDNF) and its cognate receptor, TrkB, regulate a wide range of cellular processes, including dendritic spine formation and functional synapse plasticity. However, the signaling mechanisms that link BDNF-activated TrkB to F-actin remodeling enzymes and dendritic spine morphological plasticity remain poorly understood. We report here that BDNF/TrkB signaling in neurons activates the Vav family of Rac/RhoA guanine nucleotide exchange factors through a novel TrkB-dependent mechanism. We find that Vav is required for BDNF-stimulated Rac-GTP production in cortical and hippocampal neurons. Vav is partially enriched at excitatory synapses in the postnatal hippocampus but does not appear to be required for normal dendritic spine density. Rather, we observe significant reductions in both BDNF-induced, rapid, dendritic spine head growth and in CA3-CA1 theta burst-stimulated long-term potentiation in Vav-deficient mouse hippocampal slices, suggesting that Vav-dependent regulation of dendritic spine morphological plasticity facilitates normal functional synapse plasticity.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3183742.xml
SHA-256: df47d6ebc180dbabaffffae8e7dd698ccb41fcbb7dc468fec423ba3e02548868

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

### Packet heldout_rrpv1_0056

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
  "title": "Astrocytic FABP7 Alleviates Depression-Like Behaviors of Chronic Unpredictable Mild Stress Mice by Regulating Neuroinflammation and Hippocampal Spinogenesis.",
  "pmid": "40331773",
  "pmcid": "PMC12057550",
  "doi": "10.1096/fj.202403417RR"
}
```

Abstract:
Fatty acid binding protein 7 (FABP7) is prominently expressed in astrocytes and is a critical regulator of inflammatory responses. Accumulating evidence suggests that FABP7 is crucial in neuropsychological disease through the modulation of spinogenesis. Nonetheless, the impact of FABP7 on depressive disorders and the underlying mechanisms is not fully understood. Here, we investigated the antidepressant properties of FABP7 using the chronic unpredictable mild stress (CUMS)-induced model of depression and possible mechanisms. Our results revealed that depressive-like behavior induced by CUMS was associated with decreased levels of FABP7 protein in the hippocampus (HP). Furthermore, the overexpression of FABP7 in the HP mitigated the depressive-like behavior and increased the expression of its downstream target caveolin-1 (Cav-1). FABP7 overexpression in the HP specifically regulates the expression of the astrocyte marker protein GFAP, as well as the blood-brain barrier (BBB)-associated proteins AQP4, CLDN-5, occludin, and LRP1. Notably, the CUMS-induced upregulation of the pro-inflammatory factors IL-1β and IL-6 was also significantly reversed by FABP7 overexpression in the HP. This intervention also led to increased levels of postsynaptic proteins, including PSD95 and GluA1, as well as an increase in brain-derived neurotrophic factor (BDNF) and enhanced neuronal dendritic spine density. The findings indicate that FABP7 exerts antidepressant-like properties by inhibiting inflammation, regulating spinogenesis, and modulating BBB-related proteins.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12057550.xml
SHA-256: 8593949ea1a4b08a376530335893b1782ef2665ee88e5bb95f86f286083830c7

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "dendritic spine"
    ],
    "paragraph_index": 2,
    "text": "Astrocytes, the most plentiful and pervasive glial cells in the brain, play an essential function in sustaining brain homeostasis. Extensive research has demonstrated that astrocytes are involved in depressive behaviors through diverse mechanisms, including participation in the nervous system's inflammatory responses [4, 5], modulation of synaptic plasticity [6], and the construction and preservation of the blood–brain barrier (BBB) [7]. The astrocyte‐abundant brain‐type fatty acid binding protein, FABP7, serves as an intracellular transporter of fatty acid. This small molecular protein, with a molecular weight of 14 kDa, is highly expressed in astrocytes and functions to regulate inflammatory responses. FABP7‐knockout (FABP7‐KO) in mice led to an increase in the mRNA levels of IL‐17 and TNF‐α within the lesioned regions in a mouse model of multiple sclerosis (MS) [8]. Additionally, FABP7 regulates neurogenesis [9, 10], spinogenesis [11], and astrocyte proliferation [12, 13]. In the medial prefrontal cortex (mPFC), the lack of FABP7 in astrocytes leads to aberrant dendritic morphology and reduces the density of dendritic spines on pyramidal neurons [11]. Collectively, this literature shows that FABP7 is intimately connected with the pathological and physiological mechanisms underlying neurodegenerative diseases and neuropsychiatric disorders [14, 15, 16, 17]."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 12,
    "text": "Total protein was extracted with RIPA lysate containing 1% PMSF from hippocampal tissue (n = 6). Following the execution of 10%–15% SDS‐PAGE, targeted proteins were transferred to polyvinylidene fluoride (PVDF) membranes, which were incubated with the listed primary antibodies at 4°C overnight: FABP7 (1:1000, rabbit monoclonal; CST, Danvers, MA, USA, #13347); Cav‐1 (1:1000, rabbit monoclonal; CST, #3267); AQP4 (1:1000, mouse monoclonal; Santa Cruz Biotechnology, CA, USA, #sc‐32739); CLDN‐5 (1:1000; mouse monoclonal; Thermo Fisher Scientific, Waltham, MA, USA, #35‐2500); occludin (1:1000, mouse monoclonal; Thermo Fisher Scientific, #33‐1500); LRP1 (1:2000, rabbit monoclonal; Abcam, Cambridge, UK, #ab92544); GFAP (1:1000, mouse monoclonal; CST, #3670); BDNF (1:1000, rabbit polyclonal; ABclonal, Wuhan, China, #A16229); PSD95 (1:1000, mouse monoclonal; Abcam, #ab192757); GluA1 (1:2000, rabbit polyclonal; Abcam, #ab109450); Synapsin (1:1000, rabbit polyclonal; Abcam, #ab64581); NeuN (1:1000, mouse monoclonal; Abcam, #ab104224); IL‐1β (1:1000, rabbit polyclonal; Abcam, #ab2105); IL‐6 (1:1000, rabbit polyclonal; Proteintech, Wuhan, China, #21865‐1‐AP); or β‐actin (1:2000, mouse monoclonal; Transgen Biotech, Beijing, China, #HC201). After washing with TBST (TBS containing 0.1% Tween‐20), the membrane was incubated with secondary antibodies (Anti‐rabbit: 1:3000, ZSBG‐Bio, Beijing, China, #ZB2301; or anti‐mouse: 1:3000, ZSBG‐Bio, #ZB2305) for 1 h at room temperature. After washing with TBST, the developer (WBKLS0500, Millipore) was uniformly dripped onto the membrane, and the analysi"
  },
  {
    "matched_frozen_surfaces": [
      "dendritic spine",
      "spine density",
      "spine number"
    ],
    "paragraph_index": 14,
    "text": "The procedures for Golgi‐Cox staining follow a previous report published by this research group [31]. After the behavioral experiment, whole brains (n = 3) were removed after cardiac perfusion with normal saline and immersed in Golgi‐Cox reagent for 2 days at room temperature, which consisted of 200 mL 5% potassium dichromate solution (Sinopharm Chemical Reagent Co. Ltd., Shanghai, China), 200 mL 5% mercuric chloride solution (Tongren Chemical Plant, Tongren, Guizhou, China), 160 mL 5% potassium chromate solution (Tianjin BASF Chemical Trade Co. Ltd., Tianjin, China), and 400 mL double distilled water (ddH2O). The treatment was replaced with a new Golgi‐Cox reagent solution and continued for 14 days at normal temperature. After that, the brain tissues were transferred in a sucrose solution gradient (10%, 20%, and 30%) at 4°C. Sections of 200 μm thickness were obtained on adherent slides using a vibrating slicer and dried at room temperature away from light. The staining steps included alkalinization with ammonia for 60 min, fixation with fixative (consisted of 1.25% potassium dichromate solution, 0.115% mercuric chloride solution) for 30 min, gradient dehydration with ethanol (50%, 70%, 95%, 100%, and again 100%, for 1 min at each concentration), and xylene for 4 min (repeated three times). Finally, the slices were covered with neutral gum (HUSHI, 10004160) and dried at room temperature. Dendrites with a clear structure and less intersection with other dendrites were photographed using a microscope 100× oil lens. Dendritic spine density is expressed as the dendritic spine n"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 23,
    "text": "Effects of CUMS on inflammation and spinogenesis‐related proteins. (A–E) Representative western blots for GFAP (A), IL‐1β (B), IL‐6 (B), NeuN (C), BDNF (D), PSD95 (E), GluA1 (E), and synapsin (E) in the HP. (F–M) Quantitative analysis of GFAP (F), IL‐1β (G), IL‐6 (H), NeuN (I), BDNF (J), PSD95 (K), GluA1 (L), and synapsin (M) proteins in the HP. Data were presented as mean ± SEM (n = 5‐6) and normalized to the control group (CON) for analysis. Student's t test, *p < 0.05, **p < 0.01, ***p < 0.001."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor"
    ],
    "paragraph_index": 25,
    "text": "Inhibition of spinogenesis is one of the mechanisms that produces depressive‐like behavior. The number of neurons, levels of neurotrophic factors, and synaptic‐related proteins are all related indicators of spinogenesis. To investigate the impact of CUMS on spinogenesis in HP, the protein levels of NeuN, brain‐derived neurotrophic factor (BDNF), and the synapse‐associated proteins PSD95, GluA1, and synapsin were measured. NeuN protein expression was not significantly changed in the HP after CUMS compared to control treatments (t (10)=0.9956, p = 0.3429; Figure 2C,I), while BDNF levels were significantly reduced (t (10)=3.063, p < 0.05; Figure 2D,J). Similarly, the expression of synapse‐associated proteins PSD95 (t (10)=5.915, p < 0.001; Figure 2E,K) and GluA1 (t (9)=3.795, p < 0.01; Figure 2E,L) was reduced in HP after CUMS, while synapsin protein expression was not significantly changed (t (10)=2.181, p = 0.0541; Figure 2E,M)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 32,
    "text": "In the initial experiment presented here, CUMS caused a decrease in spinogenesis in HP. However, the influence of FABP7 overexpression in HP on spinogenesis in CUMS mice remains to be explored. Therefore, the protein expression levels of NeuN (F CUMS(1,20) = 0.1959, p = 0.6628; F FABP7(1,20) = 1.851, p = 0.1888; F CUMS×FABP7(1,20) = 1.631, p = 0.2162; Figure 6A,D), BDNF (F CUMS(1,20) = 1.279, p = 0.2714; F FABP7(1,20) = 1.546, p = 0.2281; F CUMS×FABP7(1,20) = 8.064, p < 0.05; Figure 6B,E), and the synapse‐related proteins PSD95 (F CUMS(1,20) = 14.35, p < 0.01; F FABP7(1,20) = 14.98, p < 0.01; F CUMS×FABP7(1,20) = 2.62, p = 0.1212; Figure 6C,F), GluA1 (F CUMS(1,20) = 13.48, p < 0.01; F FABP7(1,20) = 22.42, p < 0.001; F CUMS×FABP7(1,20) = 16.59, p < 0.001; Figure 6C,G), and synapsin (F CUMS(1,20) = 1.208, p = 0.2848; F FABP7(1,20) = 0.6569, p = 0.4272; F CUMS×FABP7(1,20) = 4.518, p < 0.05; Figure 6C,H) in HP were examined by Western blotting. Tukey's HSD showed that after FABP7 overexpression in HP, the protein expression of BDNF (p < 0.05), PSD95 (p < 0.01), and GluA1 (p < 0.001) in HP of the CUMS‐treated mice showed a notable increase, while NeuN (p = 0.9339) and synapsin (p = 0.8856) remained unchanged."
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

### Packet heldout_rrpv1_0065

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
  "title": "Rosmarinic Acid, a Rosemary Extract Polyphenol, Increases Skeletal Muscle Cell Glucose Uptake and Activates AMPK.",
  "pmid": "28991159",
  "pmcid": "PMC6151814",
  "doi": "10.3390/molecules22101669"
}
```

Abstract:
Skeletal muscle is a major insulin-target tissue and plays an important role in glucose homeostasis. Impaired insulin action in muscles leads to insulin resistance and type 2 diabetes mellitus. 5' AMP-activated kinase (AMPK) is an energy sensor, its activation increases glucose uptake in skeletal muscle and AMPK activators have been viewed as a targeted approach in combating insulin resistance. We previously reported AMPK activation and increased muscle glucose uptake by rosemary extract (RE). In the present study, we examined the effects and the mechanism of action of rosmarinic acid (RA), a major RE constituent, in L6 rat muscle cells. RA (5.0 µM) increased glucose uptake (186 ± 4.17% of control, p < 0.001) to levels comparable to maximum insulin (204 ± 10.73% of control, p < 0.001) and metformin (202 ± 14.37% of control, p < 0.001). Akt phosphorylation was not affected by RA, while AMPK phosphorylation was increased. The RA-stimulated glucose uptake was inhibited by the AMPK inhibitor compound C and was not affected by wortmannin, an inhibitor of phosphoinositide 3-kinase (PI3K). The current study shows an effect of RA to increase muscle glucose uptake and AMPK phosphorylation. RA deserves further study as it shows potential to be used as an agent to regulate glucose homeostasis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6151814.xml
SHA-256: 955b0ef1cf67a2fa48c3f1b0b9d1a72cb2f760b62dd625cd83cbba1cbf60cd0e

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "glucose uptake"
    ],
    "paragraph_index": 2,
    "text": "AMP-activated protein kinase (AMPK) is a serine/threonine kinase that has a potential to regulate blood glucose levels. As an energy sensor, AMPK is activated by increased AMP/ATP ratio and/or via activation of its upstream kinases, liver kinase B1 (LKB1) and calmodulin dependent protein kinases (CaMKKs) [8,9]. Muscle AMPK is activated through muscle contraction/exercise [8]. Several compounds including metformin [10], thiazolidineones [11] and polyphenols such as resveratrol [12] and naringenin [13] are also known to activate AMPK and increase muscle glucose uptake. In recent years, AMPK activators have been recognized as a promising pharmacological intervention for the prevention and treatment of T2DM [8,9,14,15,16,17,18]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 3,
    "text": "Rosemary (Rosmarinus officinalis L.) is an aromatic evergreen plant endemic to the Mediterranean region and South America that is reported to exhibit antioxidant, anticancer and antimicrobial effects [19,20]. In addition, beneficial effects have been reported in regards to lipid metabolism and plasma glucose levels [21,22,23,24,25,26]. Previous studies by our group examined the effects of rosemary extract (RE) [27] on skeletal muscle cells and found a significant increase in glucose uptake and AMPK activation. In vivo studies demonstrated that administration of RE decreased plasma glucose levels in streptozotocin-induced diabetic mice [21], rats [23,25,26], alloxan-induced diabetic rabbits [22], and in genetic [24] and dietary [26,28,29] animal models of obesity and insulin resistance. RE is composed of various polyphenols with carnosic acid (CA) and rosmarinic acid (RA) being the most abundant in regards to concentration [30]. It is therefore possible that the beneficial effects observed with RE administration may be due to the action of a specific polyphenol. We recently found a significant increase in muscle cell glucose uptake and activation of AMPK by CA [31]."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "In the present study, we focused on RA and examined its direct effect on muscle cell glucose uptake, and investigated the signaling molecules that may be involved."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "We reported previously that glucose uptake was significantly increased in L6 muscle cells by 5 μg/mL of RE [27]. Additionally, previous studies have indicated that RA is one of the major constituents found in RE [30], and therefore we examined the levels of RA present in the RE that was extracted in our lab and utilized previously [27]. To this end, we performed high-performance liquid chromatography (HPLC) and a representative chromatograph is shown in Figure 1A. The retention time of the peak which corresponds to RA from the standard was utilized to determine the presence of RA in the extract. The area under the peak corresponding to the RA present in the extract was used to quantify the relative amount of RA. Our data demonstrate that RE contained 13.39 ± 0.23% RA. Based on these values and the molecular weight of RA (MW: 360.13 g/mol), we calculated the concentration of RA in media containing 5 μg/mL of RE, a concentration that elicited maximal stimulation of glucose uptake in our previous study [27], and found that the corresponding concentration of RA is 2.0 μM. We then went on to investigate whether RA at a concentration of 2.0 μM would have any effect on the glucose uptake. However, we wished to obtain a dose-response curve and for this reason we used additional concentrations."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 6,
    "text": "L6 muscle cells were differentiated in α-Minimal Essential Medium (α-MEM) containing 2% (v/v) Fetal bovine serum (FBS), as previously described [12,13,27]. Myotubes were incubated with 0.1, 0.5, 2, 5 or 10 μM RA for 4 h (Figure 1B). RA at 0.1 and 0.5 μM did not increase glucose uptake (105 ± 4.80% of control and 114 ± 3.96% of control respectively, both p > 0.05). However, higher concentration of RA resulted in a dose-dependent increase in glucose uptake. Significant stimulation of glucose uptake was seen at 2 μM RA (127 ± 4.04% of control, p < 0.01), and maximum stimulation was seen at 5 μM RA (186 ± 7.31% of control, p < 0.001) (Figure 1). It should be noted that higher concentration of RA (10 μM) also stimulated glucose uptake (181 ± 7.88% of control, p < 0.001) without any changes in cell morphology or cell toxicity assessed by microscopic examination."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 7,
    "text": "We further investigated if the effect of RA on glucose uptake is time-dependent. Fully differentiated myotubes were incubated with 5 μM RA for 0.25, 0.5, 1, 2, 4, 6, 12 or 24 h (Figure 2). Significant stimulation was seen after 2 h of RA exposure (126.6 ± 3.32% of control, p < 0.01) while maximum stimulation was observed after 4 h of exposure (186 ± 7.38% of control, p < 0.001) (Figure 2). Longer exposure time of 12 and 24 h to RA also significantly stimulated glucose uptake (166 ± 4.00% of control and 167 ± 2.00% of control, respectively, both p < 0.001) (Figure 2)."
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

### Packet heldout_rrpv1_0066

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
  "title": "Palmitoleic acid (n-7) increases white adipocytes GLUT4 content and glucose uptake in association with AMPK activation.",
  "pmid": "25528561",
  "pmcid": "PMC4364637",
  "doi": "10.1186/1476-511X-13-199"
}
```

Abstract:
Palmitoleic acid was previously shown to improve glucose homeostasis by reducing hepatic glucose production and by enhancing insulin-stimulated glucose uptake in skeletal muscle. Herein we tested the hypothesis that palmitoleic acid positively modulates glucose uptake and metabolism in adipocytes.
For this, both differentiated 3 T3-L1 cells treated with either palmitoleic acid (16:1n7, 200 μM) or palmitic acid (16:0, 200 μM) for 24 h and primary adipocytes from mice treated with 16:1n7 (300 mg/kg/day) or oleic acid (18:1n9, 300 mg/kg/day) by gavage for 10 days were evaluated for glucose uptake, oxidation, conversion to lactate and incorporation into fatty acids and glycerol components of TAG along with the activity and expression of lipogenic enzymes.
Treatment of adipocytes with palmitoleic, but not oleic (in vivo) or palmitic (in vitro) acids, increased basal and insulin-stimulated glucose uptake and GLUT4 mRNA levels and protein content. Along with uptake, palmitoleic acid enhanced glucose oxidation (aerobic glycolysis), conversion to lactate (anaerobic glycolysis) and incorporation into glycerol-TAG, but reduced de novo fatty acid synthesis from glucose and acetate and the activity of lipogenic enzymes glucose 6-phosphate dehydrogenase and ATP-citrate lyase. Importantly, palmitoleic acid induction of adipocyte glucose uptake and metabolism were associated with AMPK activation as evidenced by the increased protein content of phospho(p)Thr172AMPKα, but no changes in pSer473Akt and pThr308Akt. Importantly, such increase in GLUT4 content induced by 16:1n7, was prevented by pharmacological inhibition of AMPK with compound C.
In conclusion, palmitoleic acid increases glucose uptake and the GLUT4 content in association with AMPK activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4364637.xml
SHA-256: a1c11050c1524752e462214e2856ee32da1b58470887b275ec55ae0fed3c9c6f

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 2,
    "text": "Glucose uptake in adipocytes is carried out independently of insulin by specific glucose transporters (GLUTs) namely GLUT1 and GLUT5 located in the plasma membrane that display low efficiency of transport for the hexose [5]. In the presence of insulin, however, glucose uptake in adipocytes is drastically enhanced (by 10–20 fold) after translocation and fusion of intracellular vesicles containing GLUT4 to the plasma membrane [6, 7] induced by activation of the canonical insulin receptor substrate (IRS) - phosphoinositide 3-kinase (PI3K) - Akt pathway [7–9]. In addition to translocation, insulin through the very same IRS-PI3K-Akt pathway also modulates GLUT4 protein content [10, 11]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "glucose uptake"
    ],
    "paragraph_index": 3,
    "text": "Another intracellular signaling pathway that plays an important role in the regulation of glucose uptake in adipocytes is the AMP-activated protein kinase (AMPK) [12, 13], a heterotrimeric protein that is activated by the lower ATP/AMP ratio commonly found in situations of higher energy demand. Upon its activation, AMPK promotes GLUT4 translocation to the plasma membrane and glucose uptake independently of insulin [8, 13–15]. Along with translocation, AMPK also positively modulates GLUT4 transcription and protein levels [16]."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "Evidences accumulated over the years have shown that fatty acids, according to the carbon chain length and number of double bounds, have the ability to affect rates of glucose uptake through the modulation of above-mentioned intracellular signaling pathways [17]. Indeed, saturated long-chain fatty acids such as palmitic (16:0) and stearic (18:0) acids were shown to impair glucose uptake [18, 19], whereas monounsaturated n-7 palmitoleic acid (16:1n7) was found to improve glucose uptake by affecting insulin responsivity [20]. More specifically to latter, palmitoleic acid, which is synthesized by the desaturation of palmitic acid (16:0) catalyzed by the stearoyl-CoA desaturase 1 (SCD-1), was shown to improve glucose homeostasis by enhancing Akt activation and plasma membrane GLUT1 and GLUT4 protein content in skeletal muscle [20–22] and by reducing hepatic esteatosis and improving insuling signaling in the liver [20, 23]. Furthermore, palmitoleic acid was also shown to protect pancreatic β-cells from the deleterious effects of palmitic acid [24, 25] and to increase lipolysis and the content of the major lipases ATGL and HSL in adipose tissue [26]."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "In the present study, we tested the hypothesis that, similarly to skeletal muscle, palmitoleic acid is an important modulator of glucose uptake and metabolism in adipocytes. For this, adipocytes were evaluated for glucose uptake and metabolism after treatment with palmitoleic acid. Putative mechanisms underlying palmitoleic acid actions in adipocytes were also investigated."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 8,
    "text": "3 T3-L1 preadipocytes were cultured in DMEM containing 10% calf serum and penicillin/streptozotocin at 1% until confluence. After 2–3 days post-confluence, differentiation was induced by a cocktail composed of dexamethasone (1 μM), isobutylmethylxanthine (0.5 mM) and insulin (1.67 μM). After 48 h, medium was replaced by DMEM with 10% FBS containing 0.41 μM insulin [28]. Differentiated 3 T3-L1 cells (6 days after cocktail) were incubated either with vehicle (ethanol 0.05%), or palmitic acid (16:0, 200 μM) or palmitoleic acid (16:1n7, 200 μM). Because 3 T3-L1 cells are abundant in palmitoleic acid, a dose of fatty acids slightly higher than that commonly found in plasma of rodents and humans was chosen to challenge these cells in vitro. As evaluated by membrane integrity and DNA fragmentation (data not shown), this dose of fatty acid is not cytotoxic or deleterious to 3 T3-L1. After 18 h of treatment, cells were washed with PBS and starved from serum and insulin in the presence of fatty acids for 6 h. Treatment with palmitoleic acid for 24 h induced a significant increase in 3 T3-L1 palmitoleic acid content, without affecting cell levels of palmitic, stearic, oleic, and vaccenic acids [26]. AMPK inhibition was achieved by treatment with 6-[4-(2-Piperidin-1-ylethoxy)phenyl]-3-pyridin-4-ylpyrazolo[1,5-a]pyrimidine (Compound C, 20 μM in DMSO) to the medium containing fatty acids, for 24 h. All reagents and drugs were purchased from Sigma Chemical Company (St. Louis, MO, USA)."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 15,
    "text": "For GLUT1 and GLUT 4 total protein content analysis, 3 T3-L1 cells were homogenized and processed in buffer composed in mM: 10 Tris–HCl, 1 EDTA and 250 sucrose, 7.4 pH and centrifuged at 1,000 × g for 15 minutes at 4°C [32, 33]. For the analysis of other proteins, 3 T3-L1 cells were homogenized and processed in buffer composed in mM: 50 HEPES, 40 NaCl, 50 NaF, 2 EDTA, 10 sodium pyrophosphate, 10 sodium glycerophosphate, 2 sodium orthovanadate, 1% Triton-X100, and EDTA-free protease inhibitors. Identical amounts of protein aliquots of 3 T3-L1 lysates cells were resolved on Nupage gradient gels (4-12%, Life Technologies) and transferred to nitrocellulose membranes. After blockage with 5% milk for 1 h, membranes were incubated overnight at 4°C with the following primary antibodies: GLUT 1 (#07-1401), GLUT4 (#07-1404) (Millipore, Billerica, MA, USA) or Akt (#9685S), phosphoSer473 Akt (#4060S), phosphoThr308 Akt (#4056), AMPKα (#2532) and phosphoThr172 AMPKα (#2531) (Cell Signaling, Beverly, MA, USA) or GAPDH (G9545, Sigma) in 5% milk (1:1000). After washing, membranes were subsequently incubated with appropriated peroxidase-conjugated secondary antibody (1:5000) for 1 h and developed using the ECL enhanced chemiluminescence substrate (GE Healthcare Life Sciences, Björkgatan, Uppsala). Densitometric analyses were performed using the ImageJ software (National Institutes of Health, Bethesda, MD)."
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
