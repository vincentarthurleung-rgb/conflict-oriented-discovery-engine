# Held-out PASS B — relevance review

Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.
All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.
Do not calculate partial or running metrics.

Allowed relevance_state: DIRECTLY_RELEVANT, PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED, RELATED_BUT_WRONG_PROPOSITION, WRONG_ENDPOINT, WRONG_ENTITY, WRONG_EVIDENCE_MODE, WRONG_THERAPY, TOPIC_ONLY, INSUFFICIENT_SOURCE_EVIDENCE

### Packet heldout_rrpv1_0007

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
  "title": "Curcumin Alleviates Epidermal Psoriasis-Like Dermatitis and IL-6/STAT3 Pathway of Mice.",
  "pmid": "37675183",
  "pmcid": "PMC10478781",
  "doi": "10.2147/CCID.S423922"
}
```

Abstract:
To further investigate why curcumin (CUR) can attenuate psoriasis-like dermatitis of mice.
Sixteen mice were randomized into four groups. The control group used carrier cream, and the model and the CUR group were applied with topical 5% imiquimod in the naked mice skin once a day for 6 days (62.5 mg/day/mice). Meanwhile, the control and model mice were given the same dose of saline by oral means, while mice in the CUR groups received oral drug doses of 50 and 100 mg/kg once a day for 6 days, respectively. CUR could largely improve imiquimod-induced lesions of mice. By using the ELISA and qPCR, we found that the protein and mRNA levels of epidermal TNF-α and IL-6 were inhibited by CUR. The phosphorylation levels of STAT3 and its downstream associated protein levels (eg, Cyclin D1, Bcl-2 and Pim1) in skin tissues of different groups were also inhibited by CUR. Furthermore, the results of immunohistochemistry also showed the repressed effect of CUR for the expression of TNF-α, IL-6 and p-STAT3 in psoriasis-like lesions of mice.
CUR can effectively ameliorate the featured lesions of psoriasis mice, which may be closely associated with the involvement of IL-6/STAT3 signaling.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10478781.xml
SHA-256: 051df120e6b7e6b6f1307513c53889ecfe9ca234633eaa749f607ff531ed5133

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 1,
    "text": "Psoriasis is a chronic, repeated inflammatory disorder involved by multiple factors.1 The common clinical manifestations of psoriasis are inflammation erythema, covered with silver-white scales, locally or widely distributed throughout the body.2 The patients of psoriasis vulgaris are much common in the human populations worldwide.3 Because of the long course and easy recurrence of psoriasis, it seriously disturbed the mental and physical health of patients.4,5 As a multifunctional cytokine, the expression of IL-6 at psoriatic lesions is significantly elevated and involved in the development of psoriasis. STAT3, one of the major effector mediators of IL-6, is an important regulator of cell proliferation and is essential for the pathogenesis and development of psoriasis. Therefore, IL-6/STAT3 pathway is of great importance in psoriasis pathogenesis.6 Nowadays, the pathogenic mechanism of psoriasis has not been fully understood, and there are no specific drugs to prevent the recurrence of psoriasis in clinical practice. The main therapy method of psoriasis is to alleviate the disease and delay the recurrence. Therefore, finding new drugs and new drug targets for psoriasis will be critical for the ameliorating psoriasis."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 3,
    "text": "Curcuma longa is an important component extracted from Chinese herbal medicine rhizoma curcumae longae. It can be used to treat many diseases, such as neck and shoulder pain, rheumatic diseases, irregular menstruation and other diseases, and has the functions of blood ventilation, detumescence and pain relief.11 Curcumin (CUR), a plant polyphenol, is the main component of Curcuma longa, its chemical formula is C21H20O6 (Figure 1).12 It is reported that CUR has a promising application, including antioxidant, free radical scavenging, anti-virus, inhibiting tumor growth, analgesic treatment of rheumatism, anti-inflammatory, and protection of important organ functions, etc., which showed a good application prospect in the treatment of diseases,13,14 and has become a hot drug in scientific research of various disciplines. Previous reports have confirmed that CUR could prohibit the proliferation of human keratinocyte cell line (HaCaT) and induce apoptosis,15 but whether IL/STAT3 is involved in the process is still not fully studied. Therefore, the therapeutic mechanism of CUR for psoriasis deserves further study. Figure 1(A) The morphology changes of the lesion skin in psoriasis mice. I, Control; II, Model; III, Cur 50 mg/kg; IV, Cur 100 mg/kg. The selected pictures were typical skin lesions in each group, N=4 per group."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "phospho-STAT3"
    ],
    "paragraph_index": 6,
    "text": "Curcumin (purity > 98%) (Shanghai, Yuanye) and 5% imiquimod cream (Sichuan, Mingxin) were obtained from Chinese manufacturers. Vaseline was purchased from Shanghai Shangxi Weikang Pharmaceutical Co., Ltd. (Shanghai, China). Mouse TNF-α (3511-1A-6) ELISA kit was purchased from Mabtech (Sweden). IL-6 (KA3344) ELISA kit was purchased from Abnova (USA). Stat3 (124H6, #9139), phospho Stat3 (Tyr705, #9131) and cyclin D1 (92G2, #2978) were purchased from Cell Signaling Technology. Bcl-2 (C-2, sc-7382) and Pim-1 (12H8, sc-13513) antibody were gained from Santa Cruz Biotechnology. IL-6 (ab6672) antibody was purchased from Abcam."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 12,
    "text": "After ending the experiment, harvest the skin tissues from back sections of mice, stored at −80°C before use. The epidermal protein levels of TNF-α, IL-6 and p-STAT3 were examined according to the advice of the ELISA kit. RNA isolation and mRNA amplification were processed by the advice of manufacturing kit. Broken tissue was added to Trizol (Beyotime) for mixed concussion for full RNA extraction. Subsequently, the extracted RNA was reverse-transcribed into cDNA with the PrimeScriptTM reagent kit (Beyotime). Lastly, qPCR was continued to operate by the real-time PCR system. The whole process to be performed was as described previously.18 GAPDH mRNA was an endogenous control for all experiments. All the primer sequences we used are showed in Table 1.Table 1All Sequences of the Primers Used in This ExperimentNameForward Primer (5’ → 3’)Reverse Primer (5’ → 3’)IL-6GGCGGATCGGATGTTGTGATGGACCCCAGACAATCGGTTGTNF-αCGCCTTGGATTGACAAACCCTTCCGTGTTCCTACCCGAPDHAATGGATTTGGACGCATTGGTTTTGCACTGGTACGTGTTGAT"
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 15,
    "text": "The protein expression of Stat3 (1:1000), phosphor-Stat3 (1:1000), cyclin D1 (1:1000), Bcl-2 (1:500) and Pim1 (1:500) in lesion skins was assayed by Western blot. The lesion skin samples were lysate by RIPA lysis buffer (P0013B, Beyotime) through electric grinder on ice bath. Forty milligrams of lesion skin with 160μL of precooled RIPA lysis buffer, homogenized in ice bath, centrifuged at 4°C, 950 g for 6 min. The upper suspension was collected and assessed by the BCA kit (P0012, Beyotime). Take 50μg of protein samples that will run by 12% SDS-PAGE electrophoresis gel. Subsequently, the indicated protein was moved to a pre-trimmed PVDF membrane for antibody incubation. Finally, the indicated proteins were imaged on the device (ChemiScope 6000) via the light-emitting solution."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 16,
    "text": "The 6μm thickness section was prepared as the process of “Histopathological analysis” description. The primary antibody was incubated with the dilution ratio of 1:500 for TNF-α, p-STAT3, and 1:250 for IL-6 at 4°C (no less than 8h), respectively, which was followed by immersion with specific goat anti-mouse antibody at 24 °C for 50 min. The main procedures were as previous showed.18 The magnification of acquired images was 200× in specific device (AttoStar® 4800A)."
  }
]
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

### Packet heldout_rrpv1_0008

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
  "title": "CAA-derived IL-6 induced M2 macrophage polarization by activating STAT3.",
  "pmid": "37127625",
  "pmcid": "PMC10152707",
  "doi": "10.1186/s12885-023-10826-1"
}
```

Abstract:
Tumor-associated macrophages (TAMs) are the most abundant types of immune cells in the tumor microenvironment (TME) of breast cancer (BC). TAMs usually exhibit an M2 phenotype and promote tumor progression by facilitating immunosuppression. This study aimed to investigate the effect of CAA-derived IL-6 on macrophage polarization in promoting BC progression.
Human BC samples and adipocytes co-cultured with 4T1 BC cells were employed to explore the properties of CAAs. The co-implantation of adipocytes and 4T1 cells in mouse tumor-bearing model and tail vein pulmonary metastasis model were constructed to investigate the impact of CAAs on BC malignant progression in vivo. The functional assays, qRT-PCR, western blotting assay and ELISA assay were employed to explore the effect of CAA-derived IL-6 on macrophage polarization and programmed cell death protein ligand 1 (PD-L1) expression.
CAAs were located at the invasive front of BC and possessed a de-differentiated fibroblast phenotype. CAAs facilitated the malignant behaviors of 4T1 cells in vitro, and promoted 4T1 tumor growth and pulmonary metastasis in vivo. The IHC staining of both human BC specimens and xenograft and the in vitro experiment indicated that CAAs could enhance infiltration of M2 macrophages in the TME of 4T1 BC. Furthermore, CAA-educated macrophages could enhance malignant behaviors of 4T1 cells in vitro. More importantly, CAAs could secret abundant IL-6 and thus induce M2 macrophage polarization by activating STAT3. In addition, CAAs could upregulate PD-L1 expression in macrophages.
Our study revealed that CAAs and CAA-educated macrophages enhanced the malignant behaviors of BC. Specifically, CAA-derived IL-6 induced migration and M2 polarization of macrophages via activation STAT3 and promoted macrophage PD-L1 expression, thereby leading to BC progression.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10152707.xml
SHA-256: 69c7f1b08818e231cf6f4fddb3502115a530b4d3aa6570ddbac913278fb544d9

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 2,
    "text": "Adipocytes are the cell type with the largest proportion in the mesenchymal stroma of BC. Studies have shown that TAMs play an essential role in the interplay between adipocytes and BC cells [8]. Adipocytes in the vicinity of BC tissue can be converted into cancer-associated adipocytes (CAAs), which promote cancer cell proliferation, enhance angiogenesis and change the extracellular matrix by secreting various cytokines such as IL-6, hepatocyte growth factor (HGF) and chemokine (C–C motif) ligand 2 (CCL2), playing an active role in the process of tumorigenesis and progression [9]. Among them, CCL2 is a common macrophage chemokines and induces M2-type macrophage differentiation, thus promoting BC progression and metastasis [10]. In addition, CAAs can secrete lactate and adenosine accumulated in the TME, and these metabolites have been shown to further induce macrophage to polarize towards M2-type [11, 12]."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "p-STAT3"
    ],
    "paragraph_index": 3,
    "text": "IL-6 mediates chronic inflammation and provides a favorable microenvironment for tumor growth. Studies have shown that circulating levels of IL-6 are correlated with the aggressive characteristics of BC patients and could lead to a worse prognosis in BC patients [13]. It was reported that IL-6 promoted the polarization of monocytes into M2-type macrophages, further enhancing the invasiveness of BC [14]. IL-6 is a strong activator of STAT3. When IL-6 binds to IL-6R and the co-receptor gp130, it activates STAT3 and the activated p-STAT3 is rapidly transferred to the nucleus, thereby activating the inflammatory cascade and oncogenic pathways [15]. STAT3 was proven to induce polarization of M2-type macrophages in ovarian cancer [16]. In gastric cancer, IL-6/STAT3 signaling could promote M2 macrophage differentiation [17]. IL-6-dependent activation of STAT3 is of importance in the progression of multiple tumors, including BC."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 20,
    "text": "According to the manufacturer's introduction, mouse IL-6 ELISA kits (Invitrogen, CA, USA) were used to measure the secretion levels of IL-6 in mouse serum of CAAs group and the control group, and CAA-CM and the control medium."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 22,
    "text": "Human BC specimens were collected to explore the morphological characteristics of CAAs. The results of the H&E staining indicated that CAAs were located at the invasive front of the tumor (Fig. 1A). It was apparent that CAAs were smaller in diameter compared to the normal mammary adipocytes (NAs) (Fig. 1A-B). Mature adipocytes were obtained by adipogenic induction of 3T3-L1 cells, and presented large and round lipid droplets, as confirmed by oil red o staining (Fig. 1C). To validate the de-differentiation features of CAAs, CAAs were acquired by co-culture of mature adipocytes with 4T1 cells in a transwell system. It was found that CAAs were decreased in size and were elongated in shape similar to fibroblasts with dispersed and small lipid droplets, compared to the mature 3T3-L1 adipocytes (Fig. 1C-E). In the analysis of adipocyte-specific gene expression, the expression levels of mature adipocyte markers C/EBP-α, PPAR-γ, and Adipoq mRNA were remarkably decreased, and preadipocyte markers HSL and α-SMA, and pro-inflammatory IL-6 were remarkably increased in CAAs, compared with the mature 3T3-L1 adipocytes (Fig. 1F). Taken together, these results suggested that mature adipocytes could be changed into CAAs in contact with adjacent BC cells and presented a de-differentiation phenotype, which accorded with the earlier observations [19–21].Fig. 1CAAs presented an alteration phenotype. A Representative images of H&E-stained adipocytes in human BC samples, including CAAs located at the invasive front of BC (red arrow) and normal mammary adipocytes, 100 × . B The cell diameters of C"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 23,
    "text": "CAAs presented an alteration phenotype. A Representative images of H&E-stained adipocytes in human BC samples, including CAAs located at the invasive front of BC (red arrow) and normal mammary adipocytes, 100 × . B The cell diameters of CAAs and NAs in human BC samples were evaluated with the Image J software (n = 11). C Mature 3T3-L1 adipocytes were gained by the adipogenic-induced differentiation of 3T3-L1. The lipid droplets and cell morphology of mature 3T3-L1 adipocytes were observed by Oil red O staining. D CAAs were achieved by co-culture of mature 3T3-L1 adipocytes with 4T1 cells in a transwell system for 3 days. The lipid droplets and cell morphology of CAAs were checked by Oil red O staining. E The number of lipid contents was determined by extracting Oil red O with isopropanol and examining the optical density (OD) of Oil red O at 510 nm. F The mRNA expression levels of mature adipocyte-markers (C/EBP-α, PPAR-γ, and Adipoq), preadipocyte-markers (HSL and α-SMA), and pro-inflammatory IL-6 in 3T3-L1 adipocytes and CAAs detected by qRT-PCR. Scale bar, 100 μm. *P < 0.05, **P < 0.01, ***P < 0.001"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 28,
    "text": "To further study the effect of CAAs on macrophages in the TME of 4T1 BC, we examined the expression of the M2 macrophage marker CD206 in human BC specimens, xenograft model and 4T1 cells. In human BC samples, CD206 expression tend to be more abundant at the invasive front of BC than in the normal adipose presented by IHC and IF assay, indicating more infiltration of M2 type macrophages at the invasive front of BC (Fig. 4A-B). The IHC assay further confirmed that the expression of CD206, as well as IL-6, was enhanced in the xenograft of CAAs group compared to the control group (Fig. 4C). The IF results showed more CD206 and CD68 co-localized M2 type macrophages in the xenograft of CAAs group (Fig. 4D).Fig. 4CAAs enhanced infiltration of M2 macrophages in the TME of 4T1 BC. A Representative IHC images of CD206 at the tumor invasive front compared to the normal breast adipose tissue. B Representative IF images presented the co-expression of CD206 and CD68 at the tumor invasive front compared to the normal breast adipose tissue. C Representative IHC images of IL-6 and CD206 in the xenografts of the control group or the CAAs group. D Representative IF images presented the co-expression of CD206 and CD68 in the xenografts of the control group or the CAAs group. E The migration capability of RAW 264.7 cells was measured by the transwell migration assay treated with the control medium, CAA-CM, AD-CM, and 4T1-CM, respectively, and (F) the migrated cells were stained with crystal violet and further quantified by checking OD values at 590 nm. G The mRNA expression levels of M2 macroph"
  }
]
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

### Packet heldout_rrpv1_0017

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
  "title": "Zika virus infection induces host inflammatory responses by facilitating NLRP3 inflammasome assembly and interleukin-1β secretion.",
  "pmid": "29317641",
  "pmcid": "PMC5760693",
  "doi": "10.1038/s41467-017-02645-3"
}
```

Abstract:
Zika virus (ZIKV) infection is a public health emergency and host innate immunity is essential for the control of virus infection. The NLRP3 inflammasome plays a key role in host innate immune responses by activating caspase-1 to facilitate interleukin-1β (IL-1β) secretion. Here we report that ZIKV stimulates IL-1β secretion in infected patients, human PBMCs and macrophages, mice, and mice BMDCs. The knockdown of NLRP3 in cells and knockout of NLRP3 in mice inhibit ZIKV-mediated IL-1β secretion, indicating an essential role for NLRP3 in ZIKV-induced IL-1β activation. Moreover, ZIKV NS5 protein is required for NLRP3 activation and IL-1β secretion by binding with NLRP3 to facilitate the inflammasome complex assembly. Finally, ZIKV infection in mice activates IL-1β secretion, leading to inflammatory responses in the mice brain, spleen, liver, and kidney. Thus we reveal a mechanism by which ZIKV induces inflammatory responses by facilitating NLRP3 inflammasome complex assembly and IL-1β activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC5760693.xml
SHA-256: 687128adfa4d6f9c805c4ea64dda695e3e194bcc6604c718db904e82f249c890

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "The host innate immune system detects viral infection by recognizing molecular patterns14. The best-characterized viral sensors are pattern-recognition receptors, including Toll-like receptors15, RIG-I-like receptors16, NOD-like receptors (NLRs)17 and C-type lectin receptors18. The NLRs are involved in the assembly of large protein complexes known as inflammasomes, which are involved in the innate immune response to pathogens19. Inflammasomes consist of a cytoplasmic sensor molecule (such as NACHT, LRR, and PYD domain-containing protein 3 (NLRP3)), the adaptor protein (apoptosis-associated speck-like protein containing caspase recruitment domain (ASC)), and the effecter protein (pro-Caspase-1). NLRP3 and ASC promote pro-Casp-1 cleavage to generate the active subunits p22 and p20, leading to the maturation and secretion of interleukin-1β (IL-1β)20. IL-1β plays crucial roles in inflammatory responses, instructs adaptive immune responses by inducing expression of immunity-associated genes, and facilitates lymphocyte recruitment to the site of infection21,22."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "Here we reveal a mechanism by which ZIKV infection induces host inflammatory responses by facilitating the NLRP3 inflammasome assembly and IL-1β secretion. Clinical investigations, animal analyses, and cellular studies show that ZIKV induces IL-1β secretion by activating the NLRP3 inflammasome. Interestingly, ZIKV NS5 directly binds NLRP3 to facilitate the assembly of NLRP3 inflammasome complex by forming a sphere-like structure of NS5–NLRP3–ASC. Moreover, ZIKV induces considerable inflammatory responses in the brain, spleen, liver, and kidney of infected mice. Thus we report a function of ZIKV NS5 in regulating the NLRP3 inflammasome and reveal a mechanism by which ZIKV induces host inflammatory and immune responses."
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "ZIKV first appeared in South China in 2016 with at least 22 infected cases reported, most of them imported23,24. Here we initially showed that IL-1β levels in the sera of ZIKV-infected patients (n = 11) were higher than those in healthy individuals (n = 13) (Fig. 1a), suggesting that ZIKV infection is associated with IL-1β secretion. The correlation between ZIKV infection and IL-1β secretion was evaluated in A129 mice deficient in type I receptors25. In the blood of infected mice, the viral titers peaked at 2 days postinfection and then declined (Fig. 1b), and in the sera of infected mice, the IL-1β levels increased rapidly until 4 days postinfection and decreased thereafter (Fig. 1c), demonstrating that ZIKV induces IL-1β production and secretion.Fig. 1The effects of ZIKV infection on IL-1β production and secretion. a IL-1β levels in the sera of patients (n = 11) and healthy individuals (n = 13) was determined by ELISA. Data shown are means ± s.e.m; *P < 0.05 (two-tailed Student's t-test). b, c Six-week-old A129 mice (n = 7; 4 males and 3 females) were infected with ZIKV (5 × 105 PFU) for 0, 2, 4, and 6 days. Viral titers in the blood were determined by RT-PCR (b). IL-1β levels in the sera were determined by ELISA (c). Data shown are whiskers: min.–max.; *P < 0.05, ***P < 0.0001 (one-way ANOVA with Tukey’s post-hoc test). d–g PBMCs isolated from healthy individuals were treated with LPS (1 µg/ml) for 6 h or 2 μM Nigericin for 2 h or infected with ZIKV at an MOI = 1 for 24, 36, or 48 h or for 48 h at an MOI = 0.1, 0.5, or 1. IL-1β and GAPDH mRNAs were quantified by RT-PCR ("
  },
  {
    "matched_frozen_surfaces": [
      "IL-1β"
    ],
    "paragraph_index": 5,
    "text": "The effects of ZIKV infection on IL-1β production and secretion. a IL-1β levels in the sera of patients (n = 11) and healthy individuals (n = 13) was determined by ELISA. Data shown are means ± s.e.m; *P < 0.05 (two-tailed Student's t-test). b, c Six-week-old A129 mice (n = 7; 4 males and 3 females) were infected with ZIKV (5 × 105 PFU) for 0, 2, 4, and 6 days. Viral titers in the blood were determined by RT-PCR (b). IL-1β levels in the sera were determined by ELISA (c). Data shown are whiskers: min.–max.; *P < 0.05, ***P < 0.0001 (one-way ANOVA with Tukey’s post-hoc test). d–g PBMCs isolated from healthy individuals were treated with LPS (1 µg/ml) for 6 h or 2 μM Nigericin for 2 h or infected with ZIKV at an MOI = 1 for 24, 36, or 48 h or for 48 h at an MOI = 0.1, 0.5, or 1. IL-1β and GAPDH mRNAs were quantified by RT-PCR (d, f). IL-1β levels were determined by ELISA (e and g). h–m THP-1 macrophages were treated with 2 μM Nigericin for 2 h, infected with ZIKV at an MOI = 1 for 24, 36, and 48 h or for 48 h at an MOI = 0.1, 0.5, and 1. IL-1β and GAPDH mRNAs were quantified by RT-PCR (h, j). IL-1β levels were determined by ELISA (i, k). Mature IL-1β (p17) and cleaved Casp-1 (p22/p20) in supernatants or pro-IL-1β and pro-Casp-1 in lysates were determined by western blot (l, m). n, o BMDCs prepared from C57BL/6 mice bone marrow were stimulated by LPS (1 µg/ml) for 6 h or 2 μM Nigericin for 30 min or infected with ZIKV for 48 h at an MOI = 0.1, 0.5, and 1. Pro-IL-1β and GAPDH mRNAs were quantified by RT-PCR (n). IL-1β levels in supernatants were determined by ELISA (o). The numb"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "IL-1β"
    ],
    "paragraph_index": 6,
    "text": "The effect of ZIKV on IL-1β activation was then determined. In human peripheral blood mononuclear cells (PBMCs), IL-1β mRNA expression (Fig. 1d, f) and protein secretion (Fig. 1e, g) were stimulated by lipopolysaccharides (LPS) and ZIKV. In phorbol-12-myristate-13-acetate (TPA)-differentiated THP-1 macrophages26, IL-1β mRNA was activated by ZIKV but not by Nigericin (an NLRP3 activator) (Fig. 1h, j), IL-1β secretion was induced by Nigericin and ZIKV (Fig. 1I, k), IL-1β maturation and Casp-1 cleavage in cell supernatants, and pro-IL-1β production in cell lysates were activated by Nigericin and ZIKV (Fig. 1l, m). Moreover, in bone marrow dendritic cells (BMDCs) differentiated from C57BL/6 mice, IL-1β mRNA and protein levels were induced by LPS+Nigericin and ZIKV (Fig. 1n, o). ZIKV RNA was expressed in infected PBMCs and THP-1 cells (Supplementary Fig. 1a–d), infectious ZIKV was detected in the cell supernatant of PBMCs and THP-1 cells (Supplementary Fig. 1e, f), ZIKV E protein was produced in THP-1 cells (Supplementary Fig. 1g), and ZIKV RNA was detected in mice BMDCs (Supplementary Fig. 1h), indicating that ZIKV is replicated well in the infected cells. Taken together, we demonstrate that ZIKV activates the production and secretion of IL-1β in infected patients and cultured cells."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 7,
    "text": "The activation of IL-1β is regulated by two pathways: the transcription of pro-IL-1β mRNA regulated by nuclear factor (NF)-κB and the procession of IL-1β mediated by Casp-119. In THP-1-differentiated macrophages, IL-1β secretion was stimulated by Nigericin and ZIKV, but this activation was repressed by VX-765 (Casp-1 inhibitor) (Fig. 2a). Similarly, IL-1β and Casp-1 cleavages were activated by Nigericin and ZIKV, but such activations were repressed by VX-765. However, the levels of pro-IL-1β and pro-Casp-1 proteins were not affected by VX-765 (Fig. 2b). These results suggest that Casp-1 is involved in ZIKV-induced activation of IL-1β.Fig. 2The role of NLRP3 inflammasome in regulation of ZIKV-induced IL-1β secretion. a, b THP-1 macrophages were treated with Casp-1 inhibitor VX-765 for 1 h or 2 μM Nigericin for 2 h or infected with ZIKV at an MOI = 1 for 24 h. c–f THP-1 cells stably expressing shRNAs targeting NLRP3, ASC, or Casp-1 were generated and treated with 2 µM Nigericin for 2 h (c, d) or infected with ZIKV at an MOI = 1 for 24 h (e and f). IL-1β levels in the supernatants were determined by ELISA (a, c, e). p17 and p22/p20 levels in the supernatants were determined by western blot (b, d, f, top). NLRP3, ASC, pro-Casp-1, pro-IL-1β, Casp-1, and GAPDH proteins in the lysates were determined by western blot (b, d, f, bottom). (g–i) BMDCs prepared from the bone marrow (g, h) or BMDMs prepared from bone marrow cells (i) of treated C57BL/6 WT mice and C57BL/6 NLRP3−/− mice were stimulated with LPS (1 µg/ml) for 6 h and 5 mM ATP for 30 min or infected with ZIKV for 24 h at an"
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

### Packet heldout_rrpv1_0018

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
  "title": "TLR-induced PAI-2 expression suppresses IL-1β processing via increasing autophagy and NLRP3 degradation.",
  "pmid": "24043792",
  "pmcid": "PMC3791747",
  "doi": "10.1073/pnas.1306556110"
}
```

Abstract:
The NOD-like receptor family, pyrin domain containing 3 (NLRP3) inflammasome, a multiprotein complex, triggers caspase-1 activation and maturation of the proinflammatory cytokines IL-1β and IL-18 upon sensing a wide range of pathogen- and damage-associated molecules. Dysregulation of NLRP3 inflammasome activity contributes to the pathogenesis of many diseases, but its regulation remains poorly defined. Here we show that depletion of plasminogen activator inhibitor type 2 (PAI-2), a serine protease inhibitor, resulted in NLRP3- and ASC (apoptosis-associated Speck-like protein containing a C-terminal caspase recruitment domain)-dependent caspase-1 activation and IL-1β secretion in macrophages upon Toll-like receptor 2 (TLR2) and TLR4 engagement. TLR2 or TLR4 agonist induced PAI-2 expression, which subsequently stabilized the autophagic protein Beclin 1 to promote autophagy, resulting in decreases in mitochondrial reactive oxygen species, NLRP3 protein level, and pro-IL-1β processing. Likewise, overexpressing Beclin 1 in PAI-2-deficient cells rescued the suppression of NLRP3 activation in response to LPS. Together, our data identify a tier of TLR signaling in controlling NLRP3 inflammasome activation and reveal a cell-autonomous mechanism which inversely regulates TLR- or Escherichia coli-induced mitochondrial dysfunction, oxidative stress, and IL-1β-driven inflammation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3791747.xml
SHA-256: a5b459f01bef8f993db906a04c4de2535af12f675e55a71f0642e9a2c865b4a4

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

### Packet heldout_rrpv1_0027

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
  "title": "Inhibition of intrahepatic monocyte recruitment by Cenicriviroc and extracellular matrix degradation by MMP1 synergistically attenuate liver inflammation and fibrogenesis in vivo.",
  "pmid": "39043893",
  "pmcid": "PMC11266417",
  "doi": "10.1038/s41598-024-67926-6"
}
```

Abstract:
The chemokine (CCL)-chemokine receptor (CCR2) interaction, importantly CCL2-CCR2, involved in the intrahepatic recruitment of monocytes upon liver injury promotes liver fibrosis. CCL2-CCR2 antagonism using Cenicriviroc (CVC) showed promising results in several preclinical studies. Unfortunately, CVC failed in phase III clinical trials due to lack of efficacy to treat liver fibrosis. Lack of efficacy could be attributed to the fact that macrophages are also involved in disease resolution by secreting matrix metalloproteinases (MMPs) to degrade extracellular matrix (ECM), thereby inhibiting hepatic stellate cells (HSCs) activation. HSCs are the key pathogenic cell types in liver fibrosis that secrete excessive amounts of ECM causing liver stiffening and liver dysfunction. Knowing the detrimental role of intrahepatic monocyte recruitment, ECM, and HSCs activation during liver injury, we hypothesize that combining CVC and MMP (MMP1) could reverse liver fibrosis. We evaluated the effects of CVC, MMP1 and CVC + MMP1 in vitro and in vivo in CCl4-induced liver injury mouse model. We observed that CVC + MMP1 inhibited macrophage migration, and TGF-β induced collagen-I expression in fibroblasts in vitro. In vivo, MMP1 + CVC significantly inhibited normalized liver weights, and improved liver function without any adverse effects. Moreover, MMP1 + CVC inhibited monocyte infiltration and liver inflammation as confirmed by F4/80 and CD11b staining, and TNFα gene expression. MMP1 + CVC also ameliorated liver fibrogenesis via inhibiting HSCs activation as assessed by collagen-I staining and collagen-I and α-SMA mRNA expression. In conclusion, we demonstrated that a combination therapeutic approach by combining CVC and MMP1 to inhibit intrahepatic monocyte recruitment and increasing collagen degradation respectively ameliorate liver inflammation and fibrosis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11266417.xml
SHA-256: 7c70650e13c4687d1f6b9c598c3b14013af4bc789128be3f8d56a8baf29fa34a

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "transforming growth factor beta"
    ],
    "paragraph_index": 2,
    "text": "During liver injury, damaged hepatocytes secrete pro-inflammatory factors that activates resident liver macrophages (Kupffer cells, KCs)4. Damaged hepatocytes and KCs secrete chemokines such as C–C motif chemokine ligand-2 (CCL2) that instigate the recruitment of circulating bone-marrow derived monocytes (Fig. 1). The recruited monocytes differentiate into inflammatory macrophages referred to as monocytes-derived macrophages (MoMFs) causing liver inflammation, and activation of hepatic stellate cells (HSCs) via transforming growth factor beta (TGF-β)5,6. HSCs following activation transdifferentiate into highly proliferative myofibroblasts that secretes excessive amounts of collagen-rich extracellular matrix (ECM) that disrupts the architecture and function of the liver7,8. Activated HSCs also stimulate monocyte recruitment by secreting CCL2 (Fig. 1). The involvement of the CCL2/CCR2 axis in the pathogenesis of liver disease has prompted extensive research into its potential as a therapeutic target. Several studies via genetic or pharmacological inactivation of CCR2 have demonstrated a significant reduction in monocyte infiltration and disease progression in different liver disease etiologies9–17. In addition to its extensively studied role in hepatic inflammation and monocyte recruitment, CCR2 is also expressed on HSCs and plays a pivotal role in hepatic fibrosis18. Owing to the crucial role of CCL2-CCR2 pathway in different liver diseases, Cenicriviroc (CVC), a CCR2/CCR5 antagonist have been investigated greatly in several preclinical with promising results14,15,19,20, and"
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "transforming growth factor beta"
    ],
    "paragraph_index": 3,
    "text": "Schematic showing the pathogenesis of liver fibrosis, and the combination treatment strategy (Cenicriviroc and Matrix Metalloproteinase 1, MMP1) to promote the resolution of liver fibrosis. During liver injury, injured hepatocytes secrete pro-inflammatory factors that activate liver resident Kupffer cells (KCs). Damaged hepatocytes and KCs secrete chemokines especially CCL2 that induces recruitment of CCR2-expressing monocytes via CCL2-CCR2 axis. Following recruitment, monocytes differentiate into macrophages referred to as monocytes-derived macrophages (MoMFs). KCs and MoMFs secrete pro-fibrogenic factors such as transforming growth factor beta (TGF-β) that activates hepatic stellate cells (HSCs). Activated HSCs stimulate monocyte recruitment by secreting CCL2 and produce excessive amounts of extracellular matrix proteins primarily collagen that leads to fibrosis development. Cenicriviroc (CVC, a CCR2/CCR5 antagonist) inhibits monocyte recruitment and thereby blunts TGF-β secretion and HSCs activation which further inhibit monocyte recruitment. MMP1 degrades collagen-rich ECM thereby inhibits HSCs activation and monocyte recruitment. The combination of CVC and MMP1 can potentially contribute to fibrosis resolution."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 7,
    "text": "For the transwell migration assay, mouse RAW macrophages (1 × 105 cells/100 µL) were seeded into the 24-well inserts with 5 µm polycarbonate membranes in RPMI medium supplemented with 100 ng/mL LPS (Sigma) and 10 ng/mL IFNγ (Peprotech, Thermo Fisher Scientific) to activate macrophages. 3T3 fibroblasts (3 × 105 cells/300 µL) were seeded in the lower chamber, where applicable. In the lower well containing 600 µL medium, 10 ng/mL CCL2 was added to induce transwell migration and 5 ng/mL TGF-β (Peprotech) was added, where applicable, to activate 3T3 fibroblasts and to induce transwell migration. CVC (10 µM) was added in the upper chamber while MMP1 (2 µg/mL) was added in the lower chamber. After 24 h of incubation, the upper wells were cleaned with a cotton swap to remove non-migrated cells. The migrated cells on the bottom side were washed 3 times with PBS and fixed for 20 min at RT with 4% formaldehyde in PBS. After fixation, cells were washed 3 times in PBS and permeabilized for 5 min in ice-cold methanol. Cells were again washed 3 times in PBS and membranes were cut out, put on a glass slide, mounted in DAPI containing mounting medium and representative images were captured at 10 × under a microscope. Nuclei were counted using ImageJ. 3T3 fibroblasts in the lower chamber were lysed with RNA lysis buffer and stored at − 80 °C for further analysis."
  },
  {
    "matched_frozen_surfaces": [
      "collagen I"
    ],
    "paragraph_index": 9,
    "text": "Liver tissues were harvested and transferred to Cryomatrix™ embedding resin, and snap-frozen in 2-methylbutane chilled on dry ice. Cryosections (6 µm) were cut using a Leica CM 1860 cryostat. The sections were air-dried until dry and fixed in acetone for 20 min at RT. Thereafter, tissue cryosections were rehydrated in PBS and incubated with the primary antibody i.e., Rat anti-mouse F4/80 (clone CI: A3-1, Bio-Rad); Rat anti-mouse CD11b (clone M1/70, BioLegend, Amsterdam, Netherlands); goat anti-mouse collagen-I antibody (cat. no. 1310-01, Southern Biotech, Birmingham, USA) at 4 °C overnight. Next day, sections were washed 3 times with PBS. Endogenous peroxidase activity was blocked by 0.3% H2O2 prepared in methanol for 30 min. Sections were washed 3 times with PBS and then incubated with horseradish peroxidase (HRP)-conjugated secondary antibodies i.e., rabbit anti-rat (Southern Biotech) or rabbit anti-goat (Thermo Fisher Scientific) for 1 h at RT. Thereafter, sections were washed 3 times with PBS and incubated with HRP-conjugated tertiary antibody (goat anti-rabbit, Dako, Agilent, CA, USA) for 1 h at RT and washed again 3 times with PBS. 3-Amino-9-ethylcarbazole (AEC) solution was freshly prepared by combining 4.5 mL MilliQ, 500 µL 1 M sodium acetate pH 5.5 and 250 µL AEC in dimethylformamide (DMF) (1 tablet per 2.5 mL DMF). This was filtered using a 4.5 µm nylon filter and lastly 5.2 µL 30% H2O2 was added to the AEC solution. When prepared, peroxidase activity was developed using AEC solution for 20 min at RT, and nuclei were counterstained with hematoxylin for 5 min. Afte"
  },
  {
    "matched_frozen_surfaces": [
      "collagen I"
    ],
    "paragraph_index": 12,
    "text": "Total RNA was extracted using GenElute Total RNA Miniprep Kit (Sigma) for 3T3 cells or SV total RNA isolation system (Promega Corporation, Fitchburg, WI, USA) for mouse liver tissues according to the manufacturer’s instructions. The RNA concentration was quantified using NanoDrop® ND-1000 Spectrophotometer (Thermo Scientific, Waltham, USA). Total RNA (1 µg) was reverse transcribed using iScript cDNA synthesis kit (Bio-Rad, Hercules, CA, USA) according to the manufacturer’s instructions. For quantitative real-time PCR, 20 ng cDNA was used for each PCR reaction and was performed with 2 × SensiMix SYBR and Fluorescein Kit (Bioline GmbH, QT615-05, Luckenwalde, Germany) and pre-tested and gene-specific primers (see Table 1), using a BioRad CXF-384 Real-Time PCR detection system (BioRad). Finally, cycle threshold (Ct) values were normalized to reference 18S ribosomal RNA (18S rRNA), and relative gene expression were calculated using the 2−ΔΔCt-method.Table 1Sequence of the primers used for quantitative real-time PCR.GeneSpeciesForward primerReverse primers18S rRNAMouseAACTTTCGATGGTAGTCGCCGTTCCTTGGATGTGGTAGCCGTTTAdgre (F4/80)MouseTGCATCTAGCAATGGACAGCGCCTTCTGGATCCATTTGAATNFαMouseGTCCCCAAAGGGATGAGAAGTGCTCCTCCACTTGGTGGTTTCollagen-IMouseTGACTGGAAGAGCGGAGAGTATCCATCGGTCATGCTCTCTActa2 (α-SMA)MouseACTACTGCCGAGCGTGAGATCCAATGAAAGATGGCTGGAA"
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 15,
    "text": "Previous studies have shown that CCL2 secreted by damaged hepatocytes, KCs and activated HSCs promote monocyte recruitment (Fig. 1). We therefore first evaluated if CCL2 and/or other chemokines secreted by fibroblasts without and with TGF-β activation potentiates macrophage recruitment using transwell migration assays. As can be seen in the schematic in Fig. 2A, we cultured macrophages in the upper transwell insert without CCL2, with CCL2, with 3T3 fibroblasts cultured in the lower chamber, with 3T3 fibroblasts and CCL2, with 3T3 fibroblasts and TGF-β, and with 3T3 fibroblasts, CCL2 and TGF-β. We observed that the CCL2 showed 4.7-fold increase in macrophage migration similar to 3T3 fibroblasts (about 4.9-fold) suggesting that 3T3 fibroblasts secrete chemokines that favor macrophage recruitment (Fig. 2B). Moreover, we observed that macrophage migration is strongly increased upon co-addition of CCL2 and 3T3 suggesting synergistic effect of CCL2 and 3T3 (Fig. 2B). Macrophage migration is further potentiated by 3T3 fibroblasts and TGF-β, while addition of CCL2 to 3T3 fibroblasts and TGF-β did not promote further migration suggesting that maximum macrophage recruitment is achieved by 3T3 fibroblasts and TGF-β (Fig. 2B). These results suggest that macrophage recruitment is indeed driven by CCL2 while TGF-β activated fibroblasts strongly potentiate macrophage recruitment via secretion of chemokines including CCL2 indicating the role of CCL2 and TGF-β activated fibroblasts in intrahepatic macrophage recruitment and in liver inflammation.Figure 2CCL2 and 3T3 fibroblasts with or with"
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

### Packet heldout_rrpv1_0028

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
  "title": "N-n-Butyl haloperidol iodide ameliorates liver fibrosis and hepatic stellate cell activation in mice.",
  "pmid": "33758354",
  "pmcid": "PMC8724321",
  "doi": "10.1038/s41401-021-00630-7"
}
```

Abstract:
N-n-Butyl haloperidol iodide (F2) is a novel compound that has antiproliferative and antifibrogenic activities. In this study we investigated the therapeutic potential of F2 against liver fibrosis in mice and the underlying mechanisms. Two widely used mouse models of fibrosis was established in mice by injection of either carbon tetrachloride (CCl4) or thioacetamide (TAA). The mice received F2 (0.75, 1.5 or 3 mg·kg-1·d-1, ip) for 4 weeks of fibrosis induction. We showed that F2 administration dose-dependently ameliorated CCl4- or TAA-induced liver fibrosis, evidenced by significant decreases in collagen deposition and c-Jun, TGF-β receptor II (TGFBR2), α-smooth muscle actin (α-SMA), and collagen I expression in the liver. In transforming growth factor beta 1 (TGF-β1)-stimulated LX-2 cells (a human hepatic stellate cell line) and primary mouse hepatic stellate cells, treatment with F2 (0.1, 1, 10 μM) concentration-dependently inhibited the expression of α-SMA, and collagen I. In LX-2 cells, F2 inhibited TGF-β/Smad signaling through reducing the levels of TGFBR2; pretreatment with LY2109761 (TGF-β signaling inhibitor) or SP600125 (c-Jun signaling inhibitor) markedly inhibited TGF-β1-induced induction of α-SMA and collagen I. Knockdown of c-Jun decreased TGF-β signaling genes, including TGFBR2 levels. We revealed that c-Jun was bound to the TGFBR2 promoter, whereas F2 suppressed the binding of c-Jun to the TGFBR2 promoter to restrain TGF-β signaling and inhibit α-SMA and collagen I upregulation. In conclusion, the therapeutic benefit of F2 against liver fibrosis results from inhibition of c-Jun expression to reduce TGFBR2 and concomitant reduction of the responsiveness of hepatic stellate cells to TGF-β1. F2 may thus be a potentially new effective pharmacotherapy for human liver fibrosis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC8724321.xml
SHA-256: 1d7148d531f154aca2cee7b78e15525cb4d80b3c8d5a620ed0930501886b319f

Frozen fulltext excerpts:
```json
[]
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

### Packet heldout_rrpv1_0037

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
  "title": "GLP-1 receptor agonist protects glucose-stimulated insulin secretion in pancreatic β-cells against lipotoxicity via PPARδ/UCP2 pathway.",
  "pmid": "41165809",
  "pmcid": "PMC12575910",
  "doi": "10.1007/s00018-025-05844-0"
}
```

Abstract:
Glucagon-like peptide 1 receptor agonists (GLP-1RAs) enhance glucose-stimulated insulin secretion (GSIS). Peroxisome proliferator-activated receptor δ (PPARδ) plays an essential role in mitochondrial function and glucose homeostasis. This study investigated the role of PPARδ in the protective effects of GLP-1RAs on pancreatic β-cells against lipotoxicity. C57BL/6J mice fed a high-fat diet (HFD) for 12 weeks were treated with exenatide (Exe), GW501516 (GW, a PPARδ agonist), saline, or dimethyl sulfoxide (DM) for 8 weeks, followed by phenotypic assessments. In vitro, mouse pancreatic β-cells (NIT-1 cells) were exposed to palmitic acid (PA), PA + exendin-4 (Ex-4), PA + GW, PA + GSK0660 (GSK, a PPARδ antagonist), or PA + Ex-4 + GSK. Compared to HFD mice treated with saline or DM, Exe and GW administration reduced fasting blood glucose, enhanced insulin secretion function and glucose tolerance, and upregulated PPARδ expression. NIT-1 cells treated with PA + Ex-4 and PA + GW showed enhanced GSIS capacity, increased PPARδ expression, decreased UCP2 expression and ADP/ATP ratio, and improved mitochondrial DNA content and mitochondrial membrane potential compared with those treated with PA alone, whereas the opposite results were observed in the PA + GSK group. In the PA + Ex-4 + GSK group, GSK attenuated the effects of Ex-4. PPARδ-knockout (KO) cells treated with PA exhibited similar changes to those treated with PA + GSK, and Ex-4 did not reverse these alterations. Moreover, Ex-4 failed to reverse mitochondrial function or GSIS in pancreatic β-cells with UCP2 overexpression despite an increase in PPARδ expression. Thus, GLP-1RA Exe/Ex-4 preserved GSIS against lipotoxicity in pancreatic β-cells by modulating mitochondrial function through the PPARδ/UCP2 axis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12575910.xml
SHA-256: 83cb1de94ebae30de3ae29cb051a3739ba5b09cacccb8dec909478f663de3fc4

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "insulin secretion"
    ],
    "paragraph_index": 1,
    "text": "Pancreatic β-cell function includes the synthesis, storage, and secretion of insulin in a pulsatile manner, which is essential in maintaining normal blood glucose levels [1]. Among these functions, pulsatile secretion is a hallmark of healthy β-cell activity [2]. Numerous factors influence the secretory function of pancreatic islet β-cells, with mitochondrial dysfunction being a significant contributor to the diminished insulin secretion capacity of these cells [3]. Alterations in mitochondrial dynamics [4], reactive oxygen species production [5], mitophagy [6], and mitochondrial-related gene expression, such as that of mitochondrial transcription factor A (Tfam) and uncoupling protein 2 (Ucp2) [7, 8], may underlie mitochondrial-induced β-cell failure."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 3,
    "text": "Our preliminary research indicated that hypoglycaemic agents, such as glucagon-like peptide-1 receptor agonists (GLP-1RAs), such as exenatide (Exe), can protect pancreatic β-cell function [20]; however, the underlying mechanisms remain unclear. Some studies have suggested that GLP-1RAs may exert beneficial effects by modulating mitochondrial function [21, 22]. Moreover, the GLP-1RA Exe can regulate the expression of PPARα and PPARγ [23, 24]. Nonetheless, whether GLP-1RAs can regulate PPARδ in a manner analogous to that of PPARα and PPARγ in pancreatic β-cells and whether GLP-1RAs influence mitochondrial function through PPARδ to further improve pancreatic β-cell function remain unclear."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 4,
    "text": "In the present study, we investigated the role of PPARδ in mediating the protective effects of the GLP-1RA Exe on the insulin secretory function of pancreatic β-cells. Additionally, we explored the involvement of mitochondrial function in this process."
  },
  {
    "matched_frozen_surfaces": [
      "glucose-stimulated insulin secretion",
      "insulin secretion"
    ],
    "paragraph_index": 6,
    "text": "After 8 weeks of treatment, intraperitoneal glucose tolerance (IPGTT), glucose-stimulated insulin secretion (IPIRT), and insulin tolerance (IPITT) tests were conducted as previously described [26, 27]. The glucose stimulation index was calculated as the ratio of insulin concentration at 15, 30, and 60 min after intraperitoneal glucose injection to the basal insulin concentration."
  },
  {
    "matched_frozen_surfaces": [
      "insulin secretion"
    ],
    "paragraph_index": 11,
    "text": "The mouse insulinoma β-cell line NIT-1 (CRL-2055, ATCC) was cultured in Ham’s F-12K medium (21127022, Gibco) supplemented with 15% (v/v) foetal bovine serum (10099141 C, Gibco). The insulin secretion characteristics of NIT-1 cells have been confirmed (Fig. S1). Palmitate (PA; P0500, Sigma-Aldrich) was solubilised in 10% fatty acid-free bovine serum albumin (BSA; 126575, Sigma-Aldrich)."
  },
  {
    "matched_frozen_surfaces": [
      "glucose-stimulated insulin secretion",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 17,
    "text": "After intervention or transfection, glucose-stimulated insulin secretion (GSIS) assay was performed. NIT-1 cells in 12-well plates were washed twice with PBS and preincubated in Krebs-Ringer bicarbonate buffer (KRBH; PH1832-B, Phygene) at 37 °C for 1 h. Cells were then sequentially stimulated first with KRBH buffer containing a low glucose concentration (2.8 mmol/L) for 1 h, followed by KRBH buffer containing a high glucose concentration (16.7 mmol/L) for 1 h. Supernatants were collected and insulin secretion levels were quantified using a mouse insulin ELISA kit (10-1247-01, Mercodia). Results were normalised to total protein concentration."
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode"]

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

### Packet heldout_rrpv1_0038

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
  "title": "Non-clinical and first-in-human characterization of ECC5004/AZD5004, a novel once-daily, oral small-molecule GLP-1 receptor agonist.",
  "pmid": "39495140",
  "pmcid": "PMC11701199",
  "doi": "10.1111/dom.16047"
}
```

Abstract:
GLP-1 receptor agonists (GLP-1 RAs) are proven therapies for type 2 diabetes mellitus (T2DM) and overweight or obesity. We performed non-clinical and first-in-human (FIH) evaluation of ECC5004/AZD5004, an oral small-molecule GLP-1 RA.
ECC5004 was profiled in cell lines overexpressing human GLP-1R, in glucose-stimulated insulin secretion (GSIS) assays in a human β-cell line and non-human primates (NHPs). To evaluate safety, ECC5004 was orally administered to NHPs for 9 months and a phase I, double-blind, placebo-controlled FIH study was conducted. This study evaluated single doses of ECC5004 (1-300 mg) in healthy volunteers, and multiple daily doses (5, 10, 30 and 50 mg) in patients with T2DM for 28 days.
ECC5004 bound to the hGLP-1R (IC50 = 2.4 nM) augmented cAMP signalling without β-arrestin-2 recruitment or receptor internalization. ECC5004 potentiated GSIS in both EndoC-βH5 cells (EC50 = 5.9 nM) and in vivo in NHPs (EC50 = 0.022 nM). Dose-dependent body weight changes compared to control were seen in the 9-month NHP toxicity study. In the first-in-human study, ECC5004 was well tolerated with no serious adverse events. Dose-dependent reductions in glucose and body weight were observed with a dose-proportional exposure at doses ≥25 mg.
ECC5004 engaged the GLP-1R across the therapeutic dose range tested and had a safety and tolerability profile consistent with other GLP-1 RAs, along with a pharmacokinetic profile compatible with once-daily oral dosing. These data support continued development of ECC5004 as a potential therapy for T2DM and overweight or obesity.
NCT05654831.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11701199.xml
SHA-256: fdb0c1d884c1a6a55ff24b22b3b80c5599fdda2cb63719815e33efb205654516

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "insulin secretion"
    ],
    "paragraph_index": 2,
    "text": "Glucagon‐like peptide‐1 receptor agonists (GLP‐1 RAs) are currently approved therapies for T2DM and overweight or obesity. 12 , 13 , 14 GLP‐1 RAs pharmacologically activate the glucagon‐like peptide‐1 receptor (GLP‐1R) to potentiate insulin secretion at high glucose levels, suppressing glucagon release and inhibiting gastric emptying and promoting satiety, leading to improved glycaemic control and reductions in body weight. 15 , 16"
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "glucose-stimulated insulin secretion",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 6,
    "text": "Details of all in vitro assays are described in Supplemental Methods. In brief, binding to the human GLP‐1R was assessed in a radioligand binding assay, where the compound competes with 125I‐GLP‐1(7‐36)NH2. The cAMP production upon activation of the human and cynomolgus GLP‐1R was measured using CisBio's HTRF cAMP Gs Dynamic range kit in different cell systems overexpressing respective receptors. β‐arrestin‐2 recruitment after stimulation of the human GLP‐1R was investigated using a commercially available assay from Eurofins (formerly DiscoverX, USA). Human GLP‐1R internalization was examined using an imaging assay in U2OS cells overexpressing Fluorogen Activating Protein β (FAPβ)‐tagged human GLP‐1R (SpectraGenetics). Glucose‐stimulated insulin secretion (GSIS) experiments were conducted in EndoC‐βH5 cells as described in Blanchi et al. 28"
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "insulin secretion"
    ],
    "paragraph_index": 15,
    "text": "The potency (IC50 or EC50) of ECC5004 was assessed in different cell systems (Figure 1 and Table S1). ECC5004 binds to the human GLP‐1R with a potency of 2.4 nM (Figure 1A). Downstream, signalling through cAMP was studied in two different human GLP‐1R‐overexpressing cell systems HEK293 and CHO‐K1 cells (Figure 1B,C), as well as in cell lines expressing mouse, rat and rabbit GLP‐1R, where ECC5004 was not active (data not shown). In the HEK293 cells, ECC5004 displayed a full agonist profile with a potency of 2.1 nM (Figure 1B). In the CHO‐K1 cAMP assay, ECC5004 acted as a partial agonist with an E max of 30% and an EC50 of 45 nM (Figure 1C). In contrast to GLP‐1(7‐36)NH2, which is a full agonist, ECC5004 does not demonstrate detectable β‐arrestin‐2 recruitment (Figure 1D). Similarly, GLP‐1(7‐36)NH2 internalizes the GLP‐1R, while GLP‐1R internalization is not observed in response to ECC5004 (Figure 1E). In EndoC‐βH5 cells, ECC5004 exhibits a dose‐dependent effect on potentiating insulin secretion at 11 mM glucose (EC50 = 5.9 nM; Figure 1F)."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "glucose-stimulated insulin secretion",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 16,
    "text": "In vitro profiling of ECC5004 on the hGLP‐1R. ECC5004 potently binds the human GLP‐1R (A) triggering downstream signalling through cAMP in HEK‐293 cells (B) and CHO‐K1 cells (C). Binding of ECC5004 to the receptor does not lead to β‐arrestin‐2 recruitment (D) or receptor internalization (E), while GLP‐1(7–36)NH2 potently activates both signalling events. ECC5004 concentration‐dependently potentiated insulin secretion at 11 mM glucose in EndoC‐βH5 cells (F). Curves are derived from three independent test occasions and error bars represent SEM for responses at each concentration, except for (A) and (B), where one representative curve is shown. Data from each assay are presented as percentage of the positive control used in the assay. Potency data and positive controls used are summarized in Table S1. GSIS, glucose‐stimulated insulin secretion."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 17,
    "text": "Before ECC5004 was evaluated in vivo in non‐human primates (NHPs), we assessed its potency in vitro in this species. ECC5004 exhibited a robust dose‐dependent effect on potentiating cAMP accumulation in a cell line overexpressing the cynomolgus GLP‐1R (EC50 7.7 nM; Figure 2A). PK studies in lean NHPs showed that after intravenous dosing, ECC5004 had a mean half‐life of 1.72 h (SD 0.405), mean plasma clearance of 14.4 mL/min/kg (SD 1.32) and mean volume of distribution of 0.651 L/kg (SD 0.138) (Figure 2B). Together, these data were used to set doses for the subsequent PD assessment of ECC5004 in obese NHPs."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "insulin secretion"
    ],
    "paragraph_index": 18,
    "text": "Pharmacokinetics (PK), pharmacodynamics (PD) and body weight change in non‐human primates (NHPs). ECC5004 showed a dose‐dependent effect on cAMP in a cell line overexpressing the cynomolgus GLP‐1R (A). ECC5004 presented a favourable PK profile with a half‐life of 1.72 ± 0.405 h (mean ± SD) and plasma clearance of 14.7 ± 1.32 mL/min/kg (mean ± SD) in lean NHPs following a single intravenous dose (0.5 mg/kg) (B). ECC5004 potentiated insulin secretion following an intravenous glucose tolerance tests in obese NHPs as exemplified by the effect on insulin following 33 μg/kg intravenous of ECC5004 compared to vehicle administered before the glucose bolus (0.5 g/kg) (C). From the insulin profiles measured following the six different doses of ECC5004 evaluated, an area under the concentration–time curve (AUC) was calculated for each dose and plotted against the corresponding free average exposure of ECC5004 (PK/PD plot) (D). From the PK/PD data, an in vivo potency of 0.022 nM (EC50) was estimated. ECC5004 dose‐dependently decreased body weight gain compared to control in low‐, mid‐ and high‐dose groups over time in both females and males, including 95% confidence interval (CIs) (shaded area) (E). Least squares mean (darker line) and 95% CI were obtained from a mixed models for repeated measures analysis. During the dose titration period from day −14 to day 0, the low‐ and mid‐dose groups received ECC5004 10 and 30 mg/kg/day, respectively. The high‐dose group was administered ECC5004 30 mg/kg/day for 14 days and 50 mg/kg/day from day 1 and beyond."
  }
]
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

### Packet heldout_rrpv1_0044

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
  "title": "AXL degradation in combination with EGFR-TKI can delay and overcome acquired resistance in human non-small cell lung cancer cells.",
  "pmid": "31043587",
  "pmcid": "PMC6494839",
  "doi": "10.1038/s41419-019-1601-6"
}
```

Abstract:
Acquired resistance to epidermal growth factor receptor-tyrosine kinase inhibitors (EGFR-TKIs) has been a major obstacle in the treatment of non-small cell lung cancer (NSCLC) patients. AXL has been reported to mediate EGFR-TKIs. Recently, third generation EGFR-TKI osimertinib has been approved and yet its acquired resistance mechanism is not clearly understood. We found that AXL is involved in both gefitinib and osimertinib resistance using in vitro and in vivo model. In addition, AXL overexpression was correlated with extended protein degradation rate. We demonstrate targeting AXL degradation is an alternative route to restore EGFR-TKIs sensitivity. We confirmed that the combination effect of YD, an AXL degrader, and EGFR-TKIs can delay or overcome EGFR-TKIs-driven resistance in EGFR-mutant NSCLC cells, xenograft tumors, and patient-derived xenograft (PDX) models. Therefore, combination of EGFR-TKI and AXL degrader is a potentially effective treatment strategy for overcoming and delaying acquired resistance in NSCLC.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6494839.xml
SHA-256: cc4d80331282747f2a19c1fcf3d226279582f77c51575df0be552d9a9d2a228d

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 1,
    "text": "Epidermal growth factor receptor (EGFR) mutation is one of the major driver oncogenes in non-small cell lung cancer (NSCLC) and most frequently found in Asian patients1–3. Although the first generation of EGFR tyrosine kinase inhibitors (TKIs), such as gefitinib and erlotinib, have led to improved prognoses for NSCLC patients, their long-term efficacy is questionable due to the emergence of acquired resistance within a year of treatment4,5. Recently, a third generation EGFR-TKIs osimertinib, a specific inhibitor of mutant EGFR, has been approved for clinical use. However, several resistance mechanisms were subsequently identified from patients’ samples including C797S and L718Q EGFR mutations, SCLC transformation, HER2 amplification, and MET amplification6. Although a number of agents have been suggested for development to target the L858R/T790M/C797S triple mutation of EGFR, alternative approaches to control resistance are needed and the use of drug combinations may benefit patients who do not respond to current treatment7,8."
  },
  {
    "matched_frozen_surfaces": [
      "AXL"
    ],
    "paragraph_index": 2,
    "text": "AXL is a receptor tyrosine kinase that belongs to the TAM family which consists of three members: Tyro3, MERTK, and AXL9. Dysregulation of TAM signaling has been reported to be associated with cancer, chronic inflammation, and autoimmune disease10. Among three TAM member, AXL, both growth arrest-specific gene 6 (GAS6)-dependent and (GAS6)-independent, can promote many downstream signaling pathways and transcription factors regulating cell survival, growth, EMT, metastasis, and tumor microenvironment in cancer cells11–13. Recently, AXL has been reported to play a role in drug resistance mechanisms for many anti-cancer drugs, as well as in ionizing radiation therapy for multiple cancers14–17. AXL receptor kinase inhibitors have shown profound effects in overcoming the acquired resistance to EGFR-TKIs in mesenchymal cancer cells, but their anti-proliferative effects as a single agent are very limited18. Since AXL is considered as an attractive target to overcome the resistance to EGFR-TKIs, several AXL kinase inhibitors, antibody drug conjugates and decoy receptors are currently under investigation in clinical trials for cancer treatment19–21."
  },
  {
    "matched_frozen_surfaces": [
      "AXL"
    ],
    "paragraph_index": 3,
    "text": "In this study, we determined that activation of the AXL in EGFR-TKIs resistant cells is associated with extended protein degradation of AXL. We further demonstrated the combining YD, an AXL degrader, and EGFR-TKI resulted in overcoming resistance in EGFR-TKIs resistant NSCLC cells also delaying the emergence of resistance in EGFR-TKI sensitive NSCLC cells using tumor xenograft, and PDX model."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "Gefitinib (CAS No. HY-50895) and Osimertinib (AZD-9291, CAS No. HY-15772) were purchased from MedChemExpress (NJ, USA). Cycloheximide (CAS No. 66-81-9) was purchased from A.G. Scientific (CA, USA). Yuanhuadine (YD; purity >98.5%) was isolated from a CHCl3-soluble fraction of the flowers of Daphne genkwa, as described previously22. All chemicals were dissolved in DMSO for in vitro experiments."
  },
  {
    "matched_frozen_surfaces": [
      "AXL"
    ],
    "paragraph_index": 5,
    "text": "Antibodies against C-terminal AXL (sc-1096), EGFR (sc-03), p-ERK (sc-7383), ERK (sc-94), MET (sc-10), β-actin (sc-47778) were obtained from Santa Cruz Biotechnology (Santa Cruz, CA, USA). p-AXL (#5724), p-EGFR (#2234), p-MET (#3077), p-Akt (#9271), Akt (#9272), p-p70S6 Kinase (#9205), p70S6 Kinase (#9202), p-SAPK/JNK (#9091), SAPK/JNK (#9252), and snail (#3879) were obtained from Cell Signaling Technology (Danvers, MA, USA)."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 6,
    "text": "Human non-small lung cancer cells HCC827, HCC827-gef, PC9, PC9-gef cells were a kind gift of Dr. Jae Cheol Lee and Dr. Jin Kyung Rho (Asan Medical Center, Seoul, Korea). HCC827-gef and PC9-gef cells were subcultured in the presence of 1 µM gefitinib. Resistant cell line HCC827-osi was generated in vitro by culturing HCC827 cells with escalating doses (0.001–0.5 μM) of osimertinib. All the cells were maintained in RPMI 1640 media supplemented with 10% Fetal Bovine Serum (FBS) and 1% antibiotics-antimycotics (AA) (PSF; 100 units/mL penicillin G sodium, 100 μg/mL streptomycin, and 250 ng/mL amphotericin B)."
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

### Packet heldout_rrpv1_0045

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
  "title": "Bidirectional coupling among EMT, AXL-RB1 signaling and lineage switch drives resistance to osimertinib and worse clinical outcomes in NSCLC.",
  "pmid": "42079213",
  "pmcid": "PMC13131775",
  "doi": "10.64898/2026.04.21.719547"
}
```

Abstract:
Acquired resistance to osimertinib remains a major barrier in EGFR-mutant lung adenocarcinoma (LUAD), and in many patients cannot be explained by secondary targetable mutations. This pattern highlights a central role for non-genetic plasticity programs, including epithelial-mesenchymal transition (EMT), drug tolerance, immune evasion, and lineage switch. Here, we used a systems-level framework to define how these processes are coordinated. We constructed a minimal gene regulatory network integrating core EMT regulators with AXL, RB1, PD-L1, and NF-κB, and analysed its emergent behaviour using dynamical simulations. The network resolved into two mutually inhibitory, self-reinforcing "teams": an epithelial/sensitive team centred on RB1, miR-200, miR-34, p53, and E-cadherin, and a mesenchymal/resistant team centred on ZEB1, SNAIL, AXL, PD-L1, and NF-κB. Simulations predicted a strong coupling between EMT and osimertinib resistance, which was validated across bulk transcriptomic datasets from NSCLC cell lines, EGFR-mutant patient cohorts, and perturbation experiments. Inducing EMT increased RB1-loss programs, whereas osimertinib exposure induced AXL and EMT programs, supporting bidirectional regulation and reinforcement. Single-cell and spatial transcriptomic analyses further showed that EMT, AXL, PD-L1 activity, and reduced RB1 signaling co-occur within tumors. Clinically, activation of individual axes such as EMT, RB1 loss, or PD-L1 upregulation was associated with worse outcomes, while combined activation produced markedly poorer survival than any single axis alone. Extending the network to incorporate lineage regulators further linked a partial LUAD-to-LUSC shift with EMT, RB1 loss, and resistance. Together, these findings identify a network topology that coordinates multiple plasticity programs driving osimertinib resistance and suggest that disrupting this cooperative architecture may offer a therapeutic strategy in EGFR-mutant LUAD.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC13131775.xml
SHA-256: 9f339d7b5b0a1beae31b97d84f45b11c47d41df12910d8ddf06b1229bbd5eb65

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 1,
    "text": "Lung cancer is the leading cause of cancer related mortality worldwide, with an estimated 1.8 million deaths, and low 5-year survival rate of 10–20% (1). Its two main histological types are non-small cell lung cancer (NSCLC) and small-cell lung cancer (SCLC). NSCLC accounts for 85% of lung cancer with lung adenocarcinoma (LUAD) being the most prevalent subtype (2). Mutations in epidermal growth factor receptor (EGFR) such as exon 19 deletion and exon 21 L858R substitutions are among the most well-characterized drivers of NSCLC, leading to constitutive activation of the receptor. EGFR tyrosine kinase inhibitors (EGFR-TKIs) are used to block EGFR activity, leading to improved clinical outcomes, but secondary mutations, T790M being the most prevalent one, led patients to develop resistance to first- and second-generation EGFR-TKIs such as erlotinib or gefitinib. Osimertinib, a third-generation EGFR-TKI, has redefined the standard of care for EGFR-mutant NSCLC, being effective against T790M-positive lung cancer (3). However, the emergence of acquired resistance to osimertinib limits its long-term efficacy and demands a better understanding of underlying mechanisms to improve the clinical management of NSCLC."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 2,
    "text": "While some genomic drivers of osimertinib resistance have been reported, such as EGFR C797S mutation, approximately 50% of patients exhibiting resistance lack any identifiable mutations, emphasizing the role of non-genetic cell adaptation in evading drug response (4). Therapeutic options for these patients with no targetable mutations remain quite limited. Many EGFR-independent mechanisms such as an epithelial-mesenchymal transition (EMT) (5), drug-tolerant persisters (DTPs) (6) and lineage switch to SCLC (7) or lung squamous cell carcinoma (LUSC) (8) have been implicated in enabling resistance to osimertinib. The loss of tumour suppressor gene RB1 is observed frequently in EGFR mutant LUAD undergoing lineage plasticity to SCLC, and associates with a mesenchymal cell-state (9). Similarly, the receptor tyrosine kinase AXL can confer resistance to both osimertinib and erlotinib (10,11). It has also been associated with EMT in NSCLC and its concurrent inhibition with osimertinib can prevent the growth and delay the relapse in NSCLC patient-derived xenografts (PDXs) (5,9,12). Clinical case reports have also proposed RB1 loss and lineage switch to enable acquired resistance to anti-PD-1 antibody treatment (13,14). Consistent observations have been made in the first-line treatment of EGFR-mutant NSCLC with osimertinib, where PD-L1 expression has been shown to be a negative prognostic factor, and PD-L1 expression > 50% was associated with up to two-fold risk of death or progression, suggesting the role of PD-L1 role in osimertinib resistance (13,15–17). However, the underlying mec"
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 3,
    "text": "Here, we integrate dynamical simulations of an underlying regulatory network with extensive analysis of bulk, single-cell and spatial transcriptomic data of osimertinib-treated or EMT-induced cells, to demonstrate that EMT activation, PD-L1 upregulation, reduced RB1 activity interconnected with osimertinib resistance can reinforce each other due to the presence of higher-order feedback loops in the network, forming two mutually inhibiting ‘teams’ of nodes. Perturbing one axis can drive coordinated changes along many other axes too. This coordinated expression of EMT, PD-L1, AXL and reduced RB1 activity – enabled by the ‘teams’ topology – is also observed in patient samples. Finally, we report that such coordinated activation of more than one axes – EMT, upregulation of AXL or PD-L1 and defective RB1 pathway activity – lead to worse clinical outcomes as compared to their individual roles, underscoring that such reinforcement can amplify the fitness of NSCLC cells under therapeutic stress. Our results suggest breaking these ‘teams’ of nodes as a network topology-driven potential therapeutic strategy."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "AXL activation",
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "We first identified a minimal gene regulatory network (GRN) that integrates the known interactions among key molecular players of EMT (ZEB1, SNAIL, miR-200, miR-34), AXL, RB1 and PD-L1 (Fig 1A). We first identified a minimal gene regulatory network (GRN) that integrates the known interactions among key molecular players of EMT (ZEB1, SNAIL, miR-200, miR-34), AXL, RB1 and PD-L1 (Fig 1A). AXL activation can enhance the survival of DTPs and its inhibition during either the initial or tolerant phases can delay tumour re-growth compared to osimertinib alone (10). Clinically, its high expression associates with a low response rate to EGFR-TKI, and GAS6-AXL signalling is upregulated in EGFR-treated patients presenting with residual disease (10,18). AXL can activate NF-κB signalling that can stabilize SNAIL (19), thus driving EMT. AXL also activates miR-34a that can repress EMT (20), while miR-34a can inhibit AXL, forming a negative feedback loop (18). SNAIL and miR-34 form a mutually inhibitory feedback loop (21), similar to that reported between ZEB1 and miR-200 family (22). RB1 can repress ZEB1 (23), thus RB1 loss can lead to induction of ZEB1 (24). Conversely, ZEB1 can inactivate RB1, forming yet another positive reciprocal loop (25). While wild-type p53 can inhibit NF-κB (26), NF-κB activates p53 in response to stress (27), constituting a negative feedback loop. Phosphorylated RB can suppress NF-κB transcriptional activity and its downstream targets such as PD-L1 (28); inactivation of RB can promote pro-inflammatory signals in many cancers (29). NF-κB can activate miR-192–5p ("
  },
  {
    "matched_frozen_surfaces": [
      "AXL"
    ],
    "paragraph_index": 5,
    "text": "These interactions can be represented in the form of an adjacency matrix (31), where each row depicts the source, each column denotes the target, and each cell can take 3 values: −1 (red) indicating an inhibition edge, +1 (blue) indicating an activation edge, and 0 (white) for no direct regulation (Fig 1B, left). The adjacency matrix can be then used to generate an influence matrix, where each cell denotes the net impact that one node (source) in the GRN has on another one (target), through multiple paths of varying lengths containing multiple activation and/or inhibition edges in each path (Fig 1B, right, S1A). Thus, the influence matrix captures long-range regulatory interactions in a GRN (31). The influence matrix for this GRN revealed the presence of two “teams” such that members within each team effectively activate one another, while those across the two teams effectively inhibit each other to varied extents. One ‘team’ comprises E-cadherin, p53, miR-200, miR-34 and RB1 – all of which are known to maintain or drive an epithelial phenotype (32–36). The other ‘team’ consists of ZEB1, PD-L1, SNAIL, AXL and NF-κB – all of which can drive a mesenchymal immunosuppressive cell-state (32,37–40). Next, we computed the team strength that is defined on a scale of 0 to 1 and quantifies the degree of separation between the two teams. The team strength for this influence matrix was found to be 0.49. Collectively, these observations suggested that this GRN topology is structured to enable the presence of two mutually inhibiting and self-reinforcing ‘teams’ of nodes that can drive mu"
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 6,
    "text": "Further, we simulated the dynamics of this GRN using RACIPE – a computational tool that simulates the emergent dynamics of a coupled set of ODEs representing a GRN over multiple initial conditions and biologically relevant kinetic parameter sets – to identify its different possible steady-states (41). We obtained over 25,000 unique steady state values across 10,000 parameter sets, indicating the prevalence of multi-stability (co-existence of different steady-states/phenotypes) as a feature of this GRN. Correlation heatmap of this ensemble of phenotypes shows the same ‘team’ structure as observed in the network topology, with miR-200 and RB1 on one team, and ZEB1 and AXL on the other team (Fig 1C). To decode the functional relevance for the steady-states, we calculated corresponding EMT scores ( (= ZEB1 + SNAIL – miR-34 – miR-200)/4 ) and resistance scores ( = (AXL – RB1)/2 ), given the antagonistic roles of EMT-inducing factors (ZEB1 and SNAIL) and EMT-inhibiting microRNAs (miR-200 and miR-34) in regulating EMT (21,42), and those of RB1 and AXL in driving osimertinib resistance (9,10). A normalized frequency histogram of EMT scores revealed trimodality, with two dominant peaks corresponding to epithelial and mesenchymal phenotypes. Similarly, the histogram of resistance scores showed two peaks corresponding to sensitive and resistance phenotypes (Fig 1D). To better visualise the various phenotypes enabled by this GRN, we projected the steady-states using principal component analysis (PCA) and observed that the epithelial cluster was more likely to be sensitive, and mesenchy"
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

### Packet heldout_rrpv1_0057

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
  "title": "Acupuncture alleviates CSDS-induced depressive-like behaviors by modulating synaptic plasticity in vCA1.",
  "pmid": "40225589",
  "pmcid": "PMC11984413",
  "doi": "10.7150/thno.106751"
}
```

Abstract:
Acupuncture (Acu) has been clinically validated as an effective treatment for depression. However, the underlying mechanism of Acu treatment's antidepressant effect remains unclear. Methods: We investigate the antidepressant effects of Acu treatment at the LR3 point in mice subjected to chronic social defeat stress (CSDS). GCaMP6m-based fiber-optic photometry was employed in the ventral CA1 (vCA1) regions for the first time to monitor Ca2+ transients in vivo during behavioral testing. Electrophysiological recordings were used to detect the activity and synaptic function of pyramidal neurons. Golgi staining was performed to measure the density of dendritic spines in the vCA1. Western blot analysis was conducted to quantify the expression levels of phosphorylated CaMKIIα, AMPA receptor protein (GluA1, GluA2), and brain-derived neurotrophic factor (BDNF) in the hippocampus. Results: Our findings indicated that Acu treatment significantly alleviated emotional deficits and restored the activity of pyramidal neurons, which were suppressed by CSDS. Acu treatment also reversed the decrease in spontaneous excitatory postsynaptic currents (sEPSCs), thereby enhancing glutamatergic transmission. Moreover, Acu treatment improved synaptic plasticity, as evidenced by increased dendritic spine density and restored expression levels of phosphorylated CaMKIIα, GluA1, GluA2 and BDNF. Conclusion: Collectively, these findings suggest that Acu treatment alleviates depressive-like behaviors induced by CSDS and enhances synaptic function in the vCA1 region, potentially through mechanisms involving increased AMPAR trafficking and BDNF expression.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11984413.xml
SHA-256: 7714ee5e544c7b82333d28be1161d074450893ee5c71f75ef284c5d73fa6683c

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor"
    ],
    "paragraph_index": 3,
    "text": "The hippocampus plays a crucial role in mood regulation and cognitive function, with its dysfunction being implicated in the pathophysiology of depression. In various chronic stress models, hippocampal pyramidal neurons exhibit apical dendritic atrophy, reduced density of postsynaptic spines and AMPA receptors (AMPARs), along with deficits in excitatory neurotransmission and long-term potentiation (LTP) 8-12. AMPARs are critical for synaptic plasticity, and abnormalities in their function or the proteins regulating their transport are associated with numerous neurological and psychiatric disorders 13. Stress reduces the expression of the GluA1 subunit of AMPARs in the ventral CA1 (vCA1) region, impairing AMPAR-mediated synaptic excitation 14. Additionally, prolonged exposure to socially frustrating stress leads to a reduction in excitatory postsynaptic currents in the prefrontal cortex and hippocampus, indicating a decline in functional plasticity at glutamatergic synapses 15-17. At the molecular level, brain-derived neurotrophic factor (BDNF) plays a crucial role in mediating synaptic plasticity, influencing neuronal morphology and physiology. It promotes neuronal growth, facilitates the formation and stabilization of synapses and enhances LTP 18. Chronic stress or early life stress significantly reduces BDNF levels in the hippocampus, leading to impaired synaptic plasticity and depression-like behavior 19,20."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 4,
    "text": "In this study, we employed the CSDS model to analyze Ca2+ signals simultaneously recorded in the vCA1 using fiber photometry and to examine their relationship with depression-like and social behaviors. We assessed changes in synaptic transmission using electrophysiology and measured the expression levels of GluA1, GluA2, CaMKIIα and BDNF levels in the vCA1. Our results suggest that acupuncture at LR3 elicits an antidepressant response by altering pyramidal neuronal activity, increasing AMPAR trafficking to the cell membrane, and enhancing BDNF expression."
  },
  {
    "matched_frozen_surfaces": [
      "spine density"
    ],
    "paragraph_index": 21,
    "text": "Golgi impregnation of whole brains was accomplished sing the FD Rapid Golgi Stain kit (FD NeuroTechnologies, PK401, USA). Coronal sections of 100 μm thickness were obtained using a vibratome (Leica VT1200S). The neurons were viewed with a 100x oil objective on an OLYMPUS IX73 upright light microscope. Tertiary or lesser order apical dendrites (≥ 10 μm) were chosen to determine spine density, the dendrites should be paralleling to imaging focal plane to the full extent for easier and better processing. Identification of spines was accomplished semi-automatically using ImageJ (https://imagej.nih.gov/ij/). For dendritic number, we counted basal branches emanating from the cell body manually. Spine density assessment were done under double-blind conditions."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 22,
    "text": "Proteins from hippocampus were extracted and protein concentration was determined by BCA method. 40 µg of protein was used for electrophoresis. The proteins were then separated by polyacrylamide gel electrophoresis and transferred onto a polyvinylidene fluoride (PVDF) membrane. After blocking the PVDF membrane with 5% skimmed milk powder for 2 h, p-GluA1 (Invitrogen, MA5-27975), p-GluA2 (Ser880) (absin, abs147627), p-CaMKIIa (Thr286) (Cell Signaling, 12716), BDNF (Thermo Scientific, 710306) and β-actin (Cell Signaling, 4970) were added as primary antibodies, and incubated at 4 ℃ overnight. Dilute the secondary antibody (Protein-tech, SA00001-2) and add to the incubation box. Incubate for 1.5 h at room temperature. The immunoblot was quantified using a very sensitive ECL chemiluminescent solution. Gray scale values of protein bands were evaluated using Image J software. β-actin was used as an internal standard."
  },
  {
    "matched_frozen_surfaces": [
      "dendritic spine",
      "spine density",
      "spine number"
    ],
    "paragraph_index": 31,
    "text": "Long-term chronic stress leads to changes in synaptic plasticity in brain regions related to emotions, including decreased complexity and density of neuronal dendrites and dendritic spines, as well as impaired synaptic plasticity 26-28. To visualize spine remodeling before and after CSDS and Acu treatment, we employed Golgi staining (Figure 5A). Data revealed that CSDS significant decreased spine number by approximately 24%, which were reversed after Acu treatment (Figure 5B). Furthermore, a strong negative correlation was observed between immobility time and dendritic spine density in vCA1 pyramidal neurons across the four groups in the FST (Figure 5C). These findings suggest that CSDS reduces unitary excitatory synaptic events by decreasing the number of excitatory synapses, an effect that can be reversed by Acu treatment."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 33,
    "text": "Moreover, stress significantly reduced BDNF expression in the hippocampus, leading to impaired synaptic plasticity. We further examined the expression levels of BDNF in hippocampus and observed a restorative effect of Acu treatment and found the proportional reduction of BDNF induced by CSDS was significantly reversed by Acu treatment (Figure 5G). The expression levels of BDNF showed positively correlated with the ratio of sucrose preference in the SPT (Figure 5J) and negatively correlated with immobility time in the TST (Figure S8C). We speculate that the mechanism by which Acu treatment enhances the plasticity of hippocampal pyramidal neurons may involve increased AMPAR trafficking to the cell membrane and enhanced BDNF expression."
  }
]
```

Fields fulltext was expected to resolve:
["relation"]

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

### Packet heldout_rrpv1_0058

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
  "title": "Microglial ERK-NRBP1-CREB-BDNF signaling in sustained antidepressant actions of (R)-ketamine.",
  "pmid": "34819637",
  "pmcid": "PMC9095473",
  "doi": "10.1038/s41380-021-01377-7"
}
```

Abstract:
(R,S)-ketamine elicits rapid-acting and sustained antidepressant actions in treatment-resistant patients with depression. (R)-ketamine produces longer-lasting antidepressant effects than (S)-ketamine in rodents; however, the precise molecular mechanisms underlying antidepressant actions of (R)-ketamine remain unknown. Using isobaric Tag for Relative and Absolute Quantification, we identified nuclear receptor-binding protein 1 (NRBP1) that could contribute to different antidepressant-like effects of the two enantiomers in chronic social defeat stress (CSDS) model. NRBP1 was localized in the microglia and neuron, not astrocyte, of mouse medial prefrontal cortex (mPFC). (R)-ketamine increased the expression of NRBP1, brain-derived neurotrophic factor (BDNF), and phosphorylated cAMP response element binding protein (p-CREB)/CREB ratio in primary microglia cultures thorough the extracellular signal-regulated kinase (ERK) activation. Furthermore, (R)-ketamine could activate BDNF transcription through activation of CREB as well as MeCP2 (methyl-CpG binding protein 2) suppression in microglia. Single intracerebroventricular (i.c.v.) injection of CREB-DNA/RNA heteroduplex oligonucleotides (CREB-HDO) or BDNF exon IV-HDO blocked the antidepressant-like effects of (R)-ketamine in CSDS susceptible mice. Moreover, microglial depletion by colony-stimulating factor 1 receptor (CSF1R) inhibitor PLX3397 blocked the antidepressant-like effects of (R)-ketamine in CSDS susceptible mice. In addition, inhibition of microglia by single i.c.v. injection of mannosylated clodronate liposomes (MCLs) significantly blocked the antidepressant-like effects of (R)-ketamine in CSDS susceptible mice. Finally, single i.c.v. injection of CREB-HDO, BDNF exon IV-HDO or MCLs blocked the beneficial effects of (R)-ketamine on the reduced dendritic spine density in the mPFC of CSDS susceptible mice. These data suggest a novel ERK-NRBP1-CREB-BDNF pathways in microglia underlying antidepressant-like effects of (R)-ketamine.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC9095473.xml
SHA-256: ac9946841d1ffecaf94af41feb828cbe3f6883d96afd8828151ed5b9654ca0f1

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor"
    ],
    "paragraph_index": 3,
    "text": "Mounting evidence suggests a key role of brain-derived neurotrophic factor (BDNF) in antidepressant-like effects of (R,S)-ketamine and its two enantiomers in rodents [2, 22–24, 41–44]. Shirayama et al. [45] reported that direct injection of BDNF in the hippocampus caused long-lasting (i.e., 10 days) antidepressant-like effects in rat learned helplessness model, suggesting a role of BDNF in the long-lasting antidepressant effects. However, the precise molecular mechanisms underlying the relationship between (R)-ketamine’s long-lasting antidepressant actions and BDNF signaling remain poorly understood."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 4,
    "text": "The isobaric Tags for Relative and Absolute Quantification (iTRAQ)-based proteomic technique has been widely used in proteomic workflows relative quantification [46]. The aim of this study was to identify the novel molecular mechanisms underlying long-lasting antidepressant-like effects of (R)-ketamine in rodents. Here, we conducted iTRAQ analysis of the medial prefrontal cortex (mPFC) of chronic social defeat stress (CSDS) susceptible mice treated with either (R)-ketamine or (S)-ketamine since mPFC is implicated in the antidepressant-like effects of (R,S)-ketamine and two enantiomers [27, 47, 48]. Here, we identified the nuclear receptor-binding protein 1 (NRBP1) as differentially expressed protein for two enantiomers. Furthermore, we investigated the role of NRBP1, upstream and downstream signaling such as the extracellular signal-regulated kinase (ERK), cAMP response element binding protein (CREB), and BDNF in the antidepressant-like effects of (R)-ketamine."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 7,
    "text": "Detailed information of the compounds including (R)-ketamine, (S)-ketamine, (2R,6R)-hydroxynorketamine [(2R,6R)-HNK], lipopolysaccharide (LPS), SL327 (ERA inhibitor), PLX3397 [colony-stimulating factor 1 receptor (CSF1R) inhibitor], mannosylated clodronate liposomes (MCLs), the antisense oligonucleotides and cRNA for targeting CREB or BDNF exon IV, and CREB-DNA/RNA heteroduplex oligonucleotides (HDO) or BDNF exon IV-HDO was shown in the Supplementary Information. Detailed information of cells cultures such as HEK293T, BV2 cells and primary microglia was also shown in the Supplementary Information."
  },
  {
    "matched_frozen_surfaces": [
      "dendritic spine"
    ],
    "paragraph_index": 10,
    "text": "We performed immunoprecipitation, quantitative real-time PCR, western blot, luciferase assay, ChIP assay, immunofluorescence staining, and dendritic spine analysis for in vitro and/or in vivo experiments (for details, see Supplementary Information)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 13,
    "text": "A computer-assisted generation of a protein-interaction database suggests that NRBP might bind to CREB [57]. The immunoprecipitation assay showed that NRBP1 and CREB bind to each other under physiological function and after (R)-ketamine (10 μM) or (S)-ketamine (10 μM) treatment (Fig. S2). However, the precise physiological function of the interaction of NRBP1 and CREB is unclear. We previously reported that ERK plays a role in the antidepressant-like effects of (R)-ketamine in CSDS model [30]. It is also known that phosphorylation of ERK could activate the transcription factor CREB, resulting in the regulation of BDNF transcription [58, 59]. Together, we have hypothesis that (R)-ketamine may activate the expression of BDNF though NRBP1 and ERK-CREB signaling. To address the hypothesis, we examined the relationship between NRBP1 and ERK-CREB. Western blot assay showed that siRNA-NRBP1 caused down-regulation of NRBP1 and the ratio of p-CREB/CREB in the BV2 cells, in a concentration dependent manner (Fig. S3A). Next, we examined the effects of ketamine enantiomers on the expression of NRBP1 and p-CREB/CREB ratio in the primary microglia. (R)-ketamine significantly increased the expression of NRBP1 and p-CREB/CREB ratio in the primary microglia, in a concentration dependent manner (Fig. S3B). In contrast, (S)-ketamine increased expression of NRBP1 at 1 μM and p-CREB/CREB ratio at 10 μM (Fig. S3B). (R)-ketamine was more potent than (S)-ketamine (Fig. S3B). To examine the role of ERK, we treated differential concentrations of ERK inhibitor SL327 for primary microglia. Western blo"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 14,
    "text": "It is reported that CREB functions as a transcription activator of BDNF via motif ahead of Bdnf exon IV [60, 61]. Here, we examined whether (R)-ketamine can promote BDNF expression by affecting Bdnf transcription through the activation of CREB. First, we analyzed the DNA sequences of the promoter regions in the mouse Bdnf exon IV by using luciferase assay. Both (R)-ketamine and (S)-ketamine could activate Bdnf exon IV promoter in HEK293T cells, in a concentration dependent manner (Fig. 1A). Interestingly, activation for Bdnf exon IV promoter by (R)-ketamine was more potent than (S)-ketamine (Fig. 1A). In contrast, (2R,6R)-HNK (the metabolite from (R)-ketamine) [28] did not activate Bdnf exon IV promoter whereas its parent compound (R)-ketamine significantly activated Bdnf exon IV promoter (Fig. S4). Furthermore, the mutation in this motif significantly attenuated the promoter activity by (R)-ketamine or (S)-ketamine (Fig. 1B). Moreover, activation of Bdnf exon IV promotor by (R)-ketamine was significantly blocked by siRNA-CREB, CREB-HDO, and BDNF exon IV-HDO (Fig. 1C, D).Fig. 1Effects of (R)-ketamine and (S)-ketamine on the BDNF activation.A, B The luciferase assay for BDNF exon IV promoter. A BDNF exon IV promoter activity in the HEK293T cells treated with (R)-ketamine (0.1, 1.0, and 10 μM) or (S)-ketamine (0.1, 1.0, and 10 μM). The data are the mean ± SEM (n = 6). **P < 0.01; ***P < 0.001 compared to vehicle group. $P < 0.05; $$P < 0.01; $$$P < 0.001 (one-way ANOVA). B BDNF exon IV promoter activity in the HEK293T cells treated with (R)-ketamine (10 μM) [or (S)-ketamine ("
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

### Packet heldout_rrpv1_0067

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
  "title": "AMPK activation through mitochondrial regulation results in increased substrate oxidation and improved metabolic parameters in models of diabetes.",
  "pmid": "24339975",
  "pmcid": "PMC3855387",
  "doi": "10.1371/journal.pone.0081870"
}
```

Abstract:
Modulation of mitochondrial function through inhibiting respiratory complex I activates a key sensor of cellular energy status, the 5'-AMP-activated protein kinase (AMPK). Activation of AMPK results in the mobilization of nutrient uptake and catabolism for mitochondrial ATP generation to restore energy homeostasis. How these nutrient pathways are affected in the presence of a potent modulator of mitochondrial function and the role of AMPK activation in these effects remain unclear. We have identified a molecule, named R419, that activates AMPK in vitro via complex I inhibition at much lower concentrations than metformin (IC50 100 nM vs 27 mM, respectively). R419 potently increased myocyte glucose uptake that was dependent on AMPK activation, while its ability to suppress hepatic glucose production in vitro was not. In addition, R419 treatment of mouse primary hepatocytes increased fatty acid oxidation and inhibited lipogenesis in an AMPK-dependent fashion. We have performed an extensive metabolic characterization of its effects in the db/db mouse diabetes model. In vivo metabolite profiling of R419-treated db/db mice showed a clear upregulation of fatty acid oxidation and catabolism of branched chain amino acids. Additionally, analyses performed using both (13)C-palmitate and (13)C-glucose tracers revealed that R419 induces complete oxidation of both glucose and palmitate to CO2 in skeletal muscle, liver, and adipose tissue, confirming that the compound increases mitochondrial function in vivo. Taken together, our results show that R419 is a potent inhibitor of complex I and modulates mitochondrial function in vitro and in diabetic animals in vivo. R419 may serve as a valuable molecular tool for investigating the impact of modulating mitochondrial function on nutrient metabolism in multiple tissues and on glucose and lipid homeostasis in diabetic animal models.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3855387.xml
SHA-256: 903b694e1297ce8b6b93da85a7915a929d6e669da62cba81a60ba2d55680cd91

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "AMPK activation"
    ],
    "paragraph_index": 1,
    "text": "Mitochondria are intracellular organelles devoted mainly to energy metabolism and perform a vital function in the production of ATP through oxidation of carbohydrates, fatty acids, and amino acids. Cumulative evidence has linked reduced mitochondrial function to the pathogenesis of diabetes and its complications [1,2]. However, over the past years, several studies have suggested that over activation of mitochondria is a potential risk for insulin resistance and that reduction of mitochondrial function may actually be protective under certain conditions [3-6], raising the possibility of mitochondrial modulation as a potential therapy for diabetes and its complications. Indeed, metformin, which is widely used for the treatment of type 2 diabetes, has been shown to directly inhibit complex I of the respiratory chain and reduce respiration with potencies in the high µM/low mM range [7,8]. In addition to metformin, several mitochondrial modulators have been reported to improve insulin sensitivity and metabolic complications [9,10]. Administration of such mitochondrial modulators results in activation of the 5'-AMP-activated protein kinase (AMPK), a master regulator of energy homeostasis, through increased AMP/ATP and ADP/ATP ratios. This results in initiation of both immediate and delayed responses that improve cellular capacity to restore ATP levels. Acutely, AMPK stimulates glucose transport and fatty acid oxidation in skeletal muscle [11,12]. Chronic adaptations to AMPK activation include up-regulation of proteins involved in substrate availability and oxidation capacity [13,"
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 2,
    "text": "Here, we have identified and characterized the activity of a novel small molecule inhibitor of complex I, R419, that potently activates AMPK in the low nM range. Our comprehensive analyses demonstrate that R419 treatment clearly altered mitochondrial function in vivo, resulting in increased branched chain amino acid catabolism and increased oxidation of both glucose and palmitate in three major metabolic organs, liver, skeletal muscle, and adipose tissue. These mitochondrial effects observed with R419 treatment reveal how small molecule modulation of mitochondrial function can lead to significant improvements in metabolic parameters in diabetic mouse models."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 3,
    "text": "Antibodies against phospho-acetyl-CoA-carboxylase (ACC) S79, total ACC, phospho-AMPK T172, total AMPK α1/2, phospho-UNC-51-like kinase (ULK) 1 S555, β-actin and glyceraldehyde-3-phosphate dehydrogenase (GAPDH) were from Cell Signaling Technologies. A-769662 was from Tocris Bioscience. AICAR and metformin were from Toronto Research Chemicals Inc. Rotenone, carbonylcyanide-p-trifluoromethoxyphenylhydrazone (FCCP), antimycin, and oligomycin were purchased from Seahorse Biosciences. All other reagents were purchased from Sigma-Aldrich unless indicated otherwise. NAD+/NADH was measured using a commercially available kit (Abcam Ltd.) according to manufacturer’s instructions."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 4,
    "text": "HepG2 cells (ATCC) were maintained in minimum essential Eagle medium supplemented with 10% FCS (Sigma-Aldrich). C2C12 myoblasts (ATCC) were maintained in Dulbecco’s modified Eagle medium (DMEM) supplemented with 10% FCS and differentiated by incubating confluent monolayers in DMEM containing 2% horse serum (Hyclone). XA15A1 human preadipocytes (Lonza) were maintained in complete SKGM-2 medium (Lonza) and differentiated by incubating confluent monolayers in DMEM containing PGM-2 supplements (Lonza). Primary muscle cells from wild type mice and mice lacking both AMPKα1 and AMPKα2 catalytic subunits (AMPK α1/α2 KO mice) were isolated and maintained as described previously [17]. Primary hepatocytes from both wild type mice and mice lacking both AMPKα1 and AMPKα2 catalytic subunits [18] were isolated from fed adult mice by a modified version of the collagenase method [19] and maintained as previously described [20]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 8,
    "text": "Primary myotubes from wild type and AMPK α1/α2 KO mice were serum-starved for 2 hours prior to assaying glucose uptake and were exposed to 500 nM R419 or 2 mM metformin for the times indicated in the figure. Cells were washed three times with HEPES-buffered saline (HBS: 140 mM NaCl, 20 mM HEPES, 5 mM KCl, 2.5 mM MgSO4, 1 mM CaCl2, pH 7.4). Glucose uptake was assayed by incubation of 2-deoxy-D-[3H]glucose (1 µCi/ml, 26.2 Ci/mmol) for 10 min as described previously [23,24]. Nonspecific binding was determined by quantitating cell-associated radioactivity in the presence of 10 µM cytochalasin B. Radioactive medium was aspirated prior to washing cells three times with ice-cold saline. Cells were subsequently lysed in 50 mM NaOH, and radioactivity was quantitated using a Beckman LS 6000IC scintillation counter. Protein concentration in cell lysates was determined using the Bradford method [25]. The radioactivity was normalized to protein concentration in the cell lysate and the nonspecific binding was subtracted. The data at each time point is normalized to the corresponding vehicle control."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation"
    ],
    "paragraph_index": 17,
    "text": "R419 activates AMPK in liver, muscle, and adipose cells. The compound R419 (N-(1-(4-cyanobenzyl)piperidin-4-yl)-6-(4-(4-methoxybenzoyl)piperidine-1-carbonyl)nicotinamide, molecular mass of 565.67, international application publication no. WO 2012/016217, February 2, 2012) (Figure 1A) is a representative example of a potent series of small molecules identified through structure activity relationship studies as AMPK activators using upregulation of substrate ACC S79 phosphorylation in HepG2 liver cells as a readout. Dose response curves in HepG2 cells and C2C12 myotubes yielded EC50s of 0.03±0.02 µM and 0.23±0.19 µM, respectively (Figure 1B and 1C). Further analysis of P-AMPK kinetics as well as phosphorylation of AMPK substrates (ACC and ULK1) in both cell types as well as XA15A1 adipocytes revealed an increase in substrate phosphorylation within ten minutes that plateaus between 0.5 to 2 hours (Figure 1D), demonstrating that AMPK activation by R419 is rapid and occurs in cell lines representing the three major metabolic organs."
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

### Packet heldout_rrpv1_0068

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
  "title": "Exercise effects on γ3-AMPK activity, phosphorylation of Akt2 and AS160, and insulin-stimulated glucose uptake in insulin-resistant rat skeletal muscle.",
  "pmid": "31944891",
  "pmcid": "PMC7052582",
  "doi": "10.1152/japplphysiol.00428.2019"
}
```

Abstract:
One exercise session can increase subsequent insulin-stimulated glucose uptake (ISGU) by skeletal muscle. Prior research on healthy muscle suggests that enhanced postexercise ISGU depends on elevated γ3-AMPK activity leading to greater phosphorylation of Akt substrate of 160 kDa (pAS160) on an AMPK-phosphomotif (Ser704). Phosphorylation of AS160Ser704, in turn, may favor greater insulin-stimulated pAS160 on an Akt-phosphomotif (Thr642) that regulates ISGU. Accordingly, we tested if exercise-induced increases in γ3-AMPK activity and pAS160 on key regulatory sites accompany improved ISGU at 3 h postexercise (3hPEX) in insulin-resistant muscle. Rats fed a high-fat diet (HFD; 2-wk) that induces insulin resistance either performed acute swim-exercise (2 h) or were sedentary (SED). SED rats fed a low-fat diet (LFD; 2 wk) served as healthy controls. Isolated epitrochlearis muscles from 3hPEX and SED rats were analyzed for ISGU, pAS160, pAkt2 (Akt-isoform that phosphorylates pAS160Thr642), and γ1-AMPK and γ3-AMPK activity. ISGU was lower in HFD-SED muscles versus LFD-SED, but this decrement was eliminated in the HFD-3hPEX group. γ3-AMPK activity, but not γ1-AMPK activity, was elevated in HFD-3hPEX muscles versus both SED controls. Furthermore, insulin-stimulated pAS160Thr642, pAS160Ser704, and pAkt2Ser474 in HFD-3hPEX muscles were elevated above HFD-SED and equal to values in LFD-SED muscles, but insulin-independent pAS160Ser704 was unaltered at 3hPEX. These results demonstrated, for the first time in an insulin-resistant model, that the postexercise increase in ISGU was accompanied by sustained enhancement of γ3-AMPK activation and greater pAkt2Ser474. Our working hypothesis is that these changes along with enhanced insulin-stimulated pAS160 increase ISGU of insulin-resistant muscles to values equaling insulin-sensitive sedentary controls.NEW & NOTEWORTHY Earlier research focusing on signaling events linked to increased insulin sensitivity in muscle has rarely evaluated insulin resistant muscle after exercise. We assessed insulin resistant muscle after an exercise protocol that improved insulin-stimulated glucose uptake. Prior exercise also amplified several signaling steps expected to favor enhanced insulin-stimulated glucose uptake: increased γ3-AMP-activated protein kinase activity, greater insulin-stimulated Akt2 phosphorylation on Ser474, and elevated insulin-stimulated Akt substrate of 160 kDa phosphorylation on Ser588, Thr642, and Ser704.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC7052582.xml
SHA-256: 46b33bfd04b9c07119ebd1f9156c764d2873a41e4f9e24336b9fde632aef577f

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
