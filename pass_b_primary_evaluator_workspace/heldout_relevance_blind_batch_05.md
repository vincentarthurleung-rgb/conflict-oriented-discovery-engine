# Held-out PASS B — relevance review

Use a fresh evaluator session for this phase. Expected reviewer type: model_retrieval_adjudicator.
All adjudication fields are blank. Complete all 70 judgments in this phase before freezing its corpus.
Do not calculate partial or running metrics.

Allowed relevance_state: DIRECTLY_RELEVANT, PLAUSIBLY_RELEVANT_FULLTEXT_REQUIRED, RELATED_BUT_WRONG_PROPOSITION, WRONG_ENDPOINT, WRONG_ENTITY, WRONG_EVIDENCE_MODE, WRONG_THERAPY, TOPIC_ONLY, INSUFFICIENT_SOURCE_EVIDENCE

### Packet heldout_rrpv1_0009

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
  "title": "IL-6-Dependent STAT3 Activation and Induction of Proinflammatory Cytokines in Primary Sclerosing Cholangitis.",
  "pmid": "37256725",
  "pmcid": "PMC10461951",
  "doi": "10.14309/ctg.0000000000000603"
}
```

Abstract:
Primary sclerosing cholangitis (PSC) is a rare cholestatic liver disease with periductal inflammation and fibrosis. Genetic studies suggest inflammatory cytokines and IL-6-dependent activation of transcription factor STAT3 as pivotal steps in PSC pathogenesis. However, details of inflammatory regulation remain unclear.
We recruited 50 patients with PSC (36 with inflammatory bowel disease, 14 without inflammatory bowel disease), 12 patients with autoimmune hepatitis, and 36 healthy controls to measure cytokines in the serum, bile, and immune cell supernatant using bead-based immunoassays and flow cytometry and immunohistochemistry to analyze phosphorylation of STATs in immune cells. Finally, we analyzed cytokines and STAT3 phosphorylation of T cells in the presence of JAK1/2 inhibitors.
In PSC, IL-6 specifically triggered phosphorylation of STAT3 in CD4 + T cells and lead to enhanced production of interferon (IFN) gamma and interleukin (IL)-17A. Phospho-STAT3-positive CD4 + T cells correlated with systemic inflammation (C-reactive protein serum levels). Combination of immunohistology and flow cytometry indicated that phospho-STAT3-positive cells were enriched in the peribiliary liver stroma and represented CD4 + T cells with prominent production of IFN gamma and IL-17A. JAK1/2 inhibitors blocked STAT3 phosphorylation and production of IFN gamma and IL-6, whereas IL-17A was apparently resistant to this inhibition.
Our results demonstrate systemic and local activation of the IL-6/STAT3 pathway in PSC. Resistance of IL-17A to STAT3-targeted inhibition points to a more complex immune dysregulation beyond STAT3 activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10461951.xml
SHA-256: d38761cfb77820a677002079c0b879aa2b2f8bcb8c47c520986c646243c34823

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 2,
    "text": "Although the exact pathogenesis remains unclear, proinflammatory T helper cells type 1 (TH1) (6,7) and type 17 (TH17) seem to play an essential role in PSC (8,9). Thus, the production of proinflammatory cytokines is considered to be pivotal for hepatic inflammation in PSC (10,11). Moreover, a recent gene-disease association study identified several genes comprising STAT3 (Signal Transducers and Activators of Transcription 3) and IL-6 as putative inflammatory hallmarks in human cholangiopathies (12). The idea of janus kinase (JAK)–STAT pathway activation in PSC is further supported by recent functional studies suggesting IL-6–dependent activation of STAT3 and subsequent release of inflammatory cytokines such as interferon (IFN) gamma and interleukin (IL)-17A as part of the pathogenesis (13,14)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 3,
    "text": "The JAK-STAT pathway regulates cellular responses to cytokines, IFNs, and growth factors (15,16). It involves 4 janus kinases, JAK1-3 and TYK2, which phosphorylate STAT1-6 proteins. On phosphorylation, STAT proteins form homodimers and heterodimers and translocate to the nucleus, where they activate genes harboring their consensus sequence. STAT1 activates IFN gamma–producing TH1 cells (17,18), whereas IL-6 promotes TH17 differentiation through STAT3 activation in naïve CD4+ T cells (19). Both IL-6 and STAT3 enhance the expression and/or activation of IL-6, IL-17, and STAT3 through a positive feedback loop (20,21). Dysregulated IL-6-signaling contributes to the onset and persistence of several autoimmune diseases including IBD (22,23) and promotes the development of various cancer types, e.g., CCA (24). IL-6 also activates STAT1 and leads to the formation of STAT1/STAT3 heterodimers (15). Such mutual interactions act as IL-6 amplifier and again involve JAK-STAT pathways (25). However, details concerning the activation of JAK-STAT pathways in PSC must still be clarified."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 4,
    "text": "In this study, we analyzed cytokines in the serum, bile, and immune cell supernatants from patients with PSC and compared the results with the STAT1/STAT3 activation state of immune cells in the blood and liver tissue. Of importance, we also performed in vitro blocking experiments of cytokines and STAT phosphorylation using broadly active JAK1/2 inhibitors."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 11,
    "text": "Recombinant human IL-6 and IFN gamma (both carrier-free, Biolegend, London) and anti-CD3 and anti-CD28 (both Thermo Fisher Scientific, Germany) were used for in vitro stimulation. JAK inhibitors baricitinib, upadacitinib, and fedratinib were purchased from MedChemExpress (NJ)."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3",
      "phospho-STAT3"
    ],
    "paragraph_index": 15,
    "text": "STAT activation was analyzed using commercially available PE-labeled antibodies against phospho-STAT1 (clone A17016B.Rec) and phospho-STAT3 (clone 13A3-1; both Biolegend) according to established protocols (https://www.biolegend.com/en-us/bio-bits/phospho-staining-and-intracellular-flow-cytometry). In addition to analysis of the whole blood allowing detection of phosphorylation from in vivo signaling, phospho-STATs were studied in PBMCs without prior stimulation and after in vitro stimulation (15 minutes at 37°C, 5% CO2) with recombinant cytokines (50 ng/mL of IL-6 for phospho-STAT3, 50 ng/mL each of IFN gamma plus IL-6 each for phospho-STAT1)."
  },
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 16,
    "text": "In brief, cells were washed with Cell Staining Buffer, and dead/viable cells were discriminated by Zombie Aqua™ staining (BioLegend). After 10 minutes, cells were stained with anti-CD3 (PE-Cy7–labeled), anti-CD4 (allophycocyanin-Cy7-labeled), and anti-CD8 (fluorescein-5-isothiocyanate-labeled) (all BioLegend). After washing with Permeabilization Wash Buffer (1X), cells were resuspended in True Phos Perm Buffer (both Biolegend) and incubated overnight at −20°C in the freezer. This protocol enabled to also measure cytokines without the need to add Golgi transport inhibitors (see Supplementary Figure 1, Supplementary Digital Content, http://links.lww.com/CTG/A950). Next day, cells were thawed, washed, and stained with anti–phospho-STAT1 and anti-STAT3 in Cell Staining Buffer, respectively. In detailed experiments, cells were further costained intracellularly with allophycocyanin-labeled anti–IFN gamma and BV-421–labelled anti–IL-17A (all Biolegend). After 30 minutes of incubation in the dark, cells were washed, resuspended in Cell staining buffer, and measured on the FACSCanto II (BD Biosciences). Using the FlowJo V10 software (TreeStar Inc), we determined frequencies of IFN gamma–producing and IL-17A–producing T-cell subsets, expression of phospho-STATs in total CD4+ and CD8+ T cells from the whole blood, and the expression in the IFN gamma–positive and IL-17A–positive T-cell subsets. Our gating strategy is illustrated in Supplementary Figure 2 (see Supplementary Digital Content, http://links.lww.com/CTG/A950). All antibodies were titrated in preceding experiments. Fluorescen"
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

### Packet heldout_rrpv1_0010

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
  "title": "Kaempferia parviflora Extract Inhibits STAT3 Activation and Interleukin-6 Production in HeLa Cervical Cancer Cells.",
  "pmid": "31470515",
  "pmcid": "PMC6747281",
  "doi": "10.3390/ijms20174226"
}
```

Abstract:
Kaempferia parviflora (KP) has been reported to have anti-cancer activities. We previously reported its effects against cervical cancer cells and continued to elucidate the effects of KP on inhibiting the production and secretion of interleukin (IL)-6, as well as its relevant signaling pathways involved in cervical tumorigenesis. We discovered that KP suppressed epidermal growth factor (EGF)-induced IL-6 secretion in HeLa cells, and it was associated with a reduced level of Glycoprotein 130 (GP130), phosphorylated signal transducers and activators of transcription 3 (STAT3), and Mcl-1. Our data clearly showed that KP has no effect on nuclear factor kappa B (NF-κB) localization status. However, we found that KP inhibited EGF-stimulated phosphorylation of tyrosine 1045 and tyrosine 1068 of EGF receptor (EGFR) without affecting its expression level. The inhibition of EGFR activation was verified by the observation that KP significantly suppressed a major downstream MAP kinase, ERK1/2. Consistently, KP reduced the expression of Ki-67 protein, which is a cellular marker for proliferation. Moreover, KP potently inhibited phosphorylation of STAT3, Akt, and the expression of Mcl-1 in response to exogenous IL-6 stimulation. These data suggest that KP suppresses EGF-induced production of IL-6 and inhibits its autocrine IL-6/STAT3 signaling critical for maintaining cancer cell progression. We believe that KP may be a potential alternative anti-cancer agent for suppressing cervical tumorigenesis.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6747281.xml
SHA-256: a2d3561698b308ae9a401ff836dfaeb1590c6f648a5e459249a91a8395f5c8b5

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "STAT3"
    ],
    "paragraph_index": 1,
    "text": "Although there is accumulating information on the biology of cervical cancer leading to advances in anti-cancer drug development, human cervical cancer is still one of the leading causes of death in women worldwide [1]. Interestingly, previous studies have revealed a strong link between cervical cancer and inflammatory cytokine signaling [2]. It has been reported that the high-risk human papilloma virus (HPV) 16 infection induces constitutive activation of signal transducers and activators of transcription 3 (STAT3) signaling [3]. HPV positive cancer cell lines such as HeLa (HPV18 positive) retained markedly higher levels of STAT3 phosphorylation at both Y705 and S727 residues compared with the HPV negative cell lines (C33A, DoTc2) [4]."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 2,
    "text": "Human IL-6 activates tyrosine kinase activity [5] and then triggers signaling cascades through the Janus family kinases (JAK)/STAT, Ras/MAPK, and PI3K/Akt pathways [6]. Specifically, upon interleukin (IL)-6 receptor activation, STAT3 is phosphorylated [7] and enhances cancer cell growth, survival, and immune evasion [3,8]. IL-6 has been proven to induce epithelial–mesenchymal transition in human cervical carcinoma cells via STAT3 activation [9]. Interestingly, IL-6 also enhances cervical cancer cell survival by upregulating the anti-apoptotic protein Mcl-1, which is mediated through the activation of the PI3K/Akt pathway [10]. Recently, it has been clearly demonstrated that the autocrine and paracrine actions of IL-6 are essential for STAT3 activation in HPV18-positive cervical cancer cell lines (SW756 and HeLa) [4]. In particular, this study revealed that activation of an IL-6 signaling axis drives the autocrine and paracrine phosphorylation of STAT3 within HPV-positive cervical cancers cells, and that activation of this pathway is essential for cervical cancer cell proliferation and survival."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "STAT3"
    ],
    "paragraph_index": 3,
    "text": "Besides cytokines, binding of growth factors to their specific receptors can lead to the activation of STAT3, which typically involves phosphorylation of the tyrosine (Y) 705 of STAT3 [11]. STAT3 phosphorylation is primarily mediated by receptor-associated kinases such as Janus family kinases (JAK) and receptor tyrosine kinases including the epidermal growth factor receptor (EGFR) [12,13]. Phosphorylated STAT3 stimulates cell proliferation, apoptosis, immune regulation, and differentiation [14]. Furthermore, the expression of EGFR is associated with HPV infection [15]. Clinically, it has been shown that levels of EGFR and human papilloma virus (HPV)-E6 and E7 proteins are increased in the cervical epithelial cells of HPV-positive women with cervical cancer [16]. It indicates that HPV-positive cancer cells are sensitive to extracellular stimulation by EGF. This statement is supported by the study in CaSki and HeLa cells, showing that exogenous EGF stimulation enhances cell proliferation by activating EGFR and cyclin D1, which is independent of COX-2 levels, suggesting that the inhibitors of EGFR and cyclin D1 may be effective against cervical cancer cell proliferation. Specifically, the E5 protein of HPV type 16 binds to a subunit of the protein pump ATPase, which consequently leads to reduced degradation of EGFR, an increase in EGFR recycling, and overexpression of EGFR [17,18,19]. Moreover, expression of high-risk HPV E6 is associated with the increased level of EGFR [20]. Additionally, a high level of expression of EGFR was found to be correlated with a high density of Ki"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6",
      "interleukin-6",
      "STAT3"
    ],
    "paragraph_index": 4,
    "text": "Kaempferia parviflora (KP) has been used as a folk remedy to treat various diseases including cancer. We previously demonstrated that the ethanolic extract of KP, with methoxyflavones as major constituents, exhibited strong anti-cancer activities against HeLa cervical cancer cells by suppressing the MAPK and PI3K/Akt signaling pathways stimulated with EGF [29]. Our previous study screened for the effects of KP at both toxic and non-toxic concentration ranges, and we successfully defined that KP at toxic concentrations induces HeLa cell death via intrinsic apoptotic pathway, and KP at non-toxic concentrations still possesses anti-cancer activities in which the extract does not directly induce cell death, but is able to suppress crucial molecular signaling in HeLa cervical cancer cells. One of our interesting findings was that KP at non-toxic concentrations interferes with EGF-stimulated growth and survival signal transduction pathways and inhibits cancer cell migration and invasion. However, the effects of KP at non-cytotoxic concentration on other important signaling pathways stimulated with EGF remain largely unexplored. In the current study, we continued our investigations to understand more about the anti-cancer activities of KP at various non-toxic concentrations by investigating the effects of KP on EGF-induced IL-6 production, and its relevant signaling pathways in an HPV18-positive cervical cancer cell line, HeLa. Because the extract at toxic concentrations can kill a majority of cells, and this eventually affects the level of intracellular proteins and the phosphory"
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 5,
    "text": "As KP exhibits the ability to impede the tumorigenic influence of EGFR and IL-6 signaling in HeLa cells, we believe that KP could be a good candidate to be developed as an agent for treating HPV18-positive cervical cancer."
  },
  {
    "matched_frozen_surfaces": [
      "IL-6"
    ],
    "paragraph_index": 8,
    "text": "IL-6 has been reported to be highly expressed in invasive cervical carcinoma and is associated with the pathogenesis of HPV-related cervical carcinoma [2,30,31]. To determine whether KP can suppress the secretion of IL-6 by HPV18-positive HeLa cells in response to EGF stimulation, we performed enzyme-linked immunosorbent assay (ELISA) to measure the level of IL-6 in the culture supernatants of HeLa cells either untreated, treated with EGF, or treated with EGF and KP at different nontoxic concentrations for 24 h. The results showed that the basal level of IL-6 in the culture supernatant of the untreated cells was 356.2 ± 19.97 pg/mL (Figure 1D). The addition of EGF to HeLa cells for 24 h resulted in a significant increase in IL-6 secretion in the supernatant to 426.8 ± 12.40 pg/mL (p = 0.0011), meaning that EGF-induced production of IL-6 was increased around 20%, as compared with that of the untreated cells. Interestingly, KP extract showed an inhibitory effect on IL-6 production in response to the influence of EGF, and the reduction of the cytokine was observed to be in a concentration-dependent manner. Specifically, KP extract at 7.5 and 15 µg/mL could significantly reduce IL-6 secretion to 326.8 ± 18.19 and 242.6 ± 13.85 pg/mL, respectively (p < 0.0001), which were both less than the basal level of IL-6 from untreated cells. The dimethyl sulfoxide (DMSO) vehicle control (0.02%) showed no inhibitory effect on IL-6 secretion (Figure 1D). These results suggest that KP, containing methoxyflavones, could be able to suppress the production and secretion of IL-6 from HeLa cervic"
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

### Packet heldout_rrpv1_0019

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
  "title": "NEK7 is an essential mediator of NLRP3 activation downstream of potassium efflux.",
  "pmid": "26814970",
  "pmcid": "PMC4810788",
  "doi": "10.1038/nature16959"
}
```

Abstract:
Inflammasomes are intracellular protein complexes that drive the activation of inflammatory caspases. So far, four inflammasomes involving NLRP1, NLRP3, NLRC4 and AIM2 have been described that recruit the common adaptor protein ASC to activate caspase-1, leading to the secretion of mature IL-1β and IL-18 proteins. The NLRP3 inflammasome has been implicated in the pathogenesis of several acquired inflammatory diseases as well as cryopyrin-associated periodic fever syndromes (CAPS) caused by inherited NLRP3 mutations. Potassium efflux is a common step that is essential for NLRP3 inflammasome activation induced by many stimuli. Despite extensive investigation, the molecular mechanism leading to NLRP3 activation in response to potassium efflux remains unknown. Here we report the identification of NEK7, a member of the family of mammalian NIMA-related kinases (NEK proteins), as an NLRP3-binding protein that acts downstream of potassium efflux to regulate NLRP3 oligomerization and activation. In the absence of NEK7, caspase-1 activation and IL-1β release were abrogated in response to signals that activate NLRP3, but not NLRC4 or AIM2 inflammasomes. NLRP3-activating stimuli promoted the NLRP3-NEK7 interaction in a process that was dependent on potassium efflux. NLRP3 associated with the catalytic domain of NEK7, but the catalytic activity of NEK7 was shown to be dispensable for activation of the NLRP3 inflammasome. Activated macrophages formed a high-molecular-mass NLRP3-NEK7 complex, which, along with ASC oligomerization and ASC speck formation, was abrogated in the absence of NEK7. NEK7 was required for macrophages containing the CAPS-associated NLRP3(R258W) activating mutation to activate caspase-1. Mouse chimaeras reconstituted with wild-type, Nek7(-/-) or Nlrp3(-/-) haematopoietic cells showed that NEK7 was required for NLRP3 inflammasome activation in vivo. These studies demonstrate that NEK7 is an essential protein that acts downstream of potassium efflux to mediate NLRP3 inflammasome assembly and activation.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4810788.xml
SHA-256: 8a4b2c22fae01d193c6f5a38488599eff85bb74f669cf4e4ec98937d47f0b364

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
    "text": "To understand the signaling mechanism of NLRP3 inflammasome activation, we sought to identify proteins that interact with NLRP3 upon inflammasome activation. To purify NLRP3 protein complexes, we generated a triple-tagged NLRP3 (NLRP3-SFP) fused with three tags in the carboxyl terminus: S-tag, FLAG (for detection), and a streptavidin-binding tag. Reconstitution of Nlrp3−/− immortalized bone-marrow-derived macrophages (iBMDMs) with NLRP3-SFP restored ATP-induced caspase-1 activation and IL-1β release (Extended Data Fig. 1a). We treated LPS-primed reconstituted iBMDMs with ATP to induce NLRP3 activation and searched for interacting partners of NLRP3 using liquid chromatography-mass spectrometry. The analysis revealed Nek7 as a major interacting partner of NLRP3 (Fig. 1a). NLRP3 did not associate with Nek6, a Nek7-related paralogue, or Nek9, another member of the Nek family10 (Extended Data Fig. 1b). The NLRP3-Nek7 interaction was confirmed by pull-down assays using streptavidin beads or immunoprecipitation (Fig. 1b, c and Extended Data Fig. 1b–d). Notably, the NLRP3-Nek7 interaction was slightly increased by LPS priming, but was clearly enhanced after ATP stimulation (Fig. 1a–c and Extended Data Fig. 1b–d). The interaction of NLRP3 with Nek7 was independent of ASC, caspase-1 or caspase-11 (Extended Data Fig. 1d). To determine the regions within NLRP3 that associate with Nek7, we expressed FLAG-tagged wild-type (WT) or mutant NLRP3 in HEK293T cells. Nek7 interacted with WT or mutant NLRP3 lacking the N-terminal Pyrin domain, but not NLRP3 with deletion of the C-terminal leucin"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 2,
    "text": "We next evaluated the requirement for Nek7 in NLRP3 inflammasome activation. Because Nek7 deficiency leads to either embryonic lethality or death of pups soon after birth14, we generated mouse chimeras after transplanting fetal liver cells from Nek7+/+ or Nek7−/− embryos into lethally-irradiated recipient mice. BMDMs from mice reconstituted with Nek7−/− cells lacked detectable expression of Nek7, but expressed normal amounts of NLRP3, caspase-1, and ASC (Fig. 2a). Importantly, activation of caspase-1 and IL-1β release induced by ATP, nigericin and toxin gramicidin, three stimuli that activate NLRP3, were abolished in Nek7−/− BMDMs (Fig. 2b, c). In contrast, activation of caspase-1 and IL-1β release in response to poly(dA:dT) that activates the AIM2 inflammasome, or Salmonella enterica serovar Typhimurium (Salmonella) that activates the NLRC4 inflammasome, were not affected in Nek7−/− BMDMs (Fig. 2b, c). Likewise, caspase-1 activation and IL-1β release induced by particulate matter and the lysosome membrane damaging agent Leu-Leu-OMe (LLOMe), were impaired in Nek7−/− BMDMs (Fig. 2d, e). In contrast, TNF-α release induced by all tested stimuli was unaffected in Nek7−/− BMDMs (Extended Data Fig. 2a, b). In addition, NLRP3-dependent caspase-1 activation and IL-1β release induced by cytosolic LPS stimulation that activates the non-canonical inflammasome via caspase-11 also required Nek7 (Extended Data Fig. 2c, d). Consistent with previous studies15–17, cytotoxicity induced by cytosolic LPS required caspase 11, but not NLRP3 or Nek7 (Extended Data Fig. 2e). To ensure that impaire"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 3,
    "text": "Stimulation of Nek7+/+ BMDMs with the NLRP3 activators ATP and nigericin, as well as poly(dA:dT) or Salmonella, induced rapid formation of large intracellular ASC aggregates called ASC specks in the cytosol (Fig. 3a, b). The formation of ASC specks induced by ATP or nigericin was abrogated, but unperturbed when induced by poly(dA:dT) or Salmonella, in Nek7−/− BMDMs (Fig. 3a, b). Consistently, ASC oligomerization triggered by stimulation with multiple NLRP3 activators, but not poly (dA:dT) or Salmonella infection, was abolished in Nek7−/− BMDMs or greatly reduced in BMDMs with knockdown of Nek7 (Fig. 3c and Extended Data Fig. 5a–c). Activated inflammasomes assemble into high-molecular-mass multiprotein complexes1,20. To assess NLRP3 inflammasome assembly, WT and Nek7−/− BMDMs were stimulated with nigericin or ATP, and digitonin-solubilized cell lysates were resolved by blue native polyacrylamide gel electrophoresis (PAGE) and then the blots were immunoblotted with anti-NLRP3 and anti-Nek7 antibodies. A large oligomeric complex (> 1,000_kDa) containing NLRP3 and Nek7 was induced in WT BMDMs after stimulation with ATP or nigericin which was greatly reduced or absent in stimulated Nek7−/− and Nlrp3−/− cells (Fig. 3d ). To better resolve the formation of NLRP3 oligomers, we separated the samples in the first dimension by blue native PAGE and then in a second dimension by SDS–PAGE. Immunoblotting revealed that Nek7 was indeed present in a high-molecular-mass NLRP3 complex induced by ATP or nigericin in primary WT BMDMs, which was absent in unstimulated WT cells and stimulated Nek"
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome",
      "IL-1β"
    ],
    "paragraph_index": 4,
    "text": "We assessed the role of Nek7 in the regulation of the inflammasome in vivo. We generated mouse chimeras after transplanting fetal liver cells from WT, Nek7−/− or Nlrp3−/− embryos into lethally-irradiated recipient mice, and IL-1β production induced by LPS challenge was assessed in the serum25,26. Administration of LPS to chimeric mice reconstituted with WT fetal liver cells induced IL-1β production, which was diminished similarly in chimeric mice reconstituted with Nek7−/− or Nlrp3−/− hematopoietic cells (Fig. 4a). Consistent with additional NLRP3 function in radio-resistant recipient cells27, chimeric Nlrp3−/− recipients transplanted with Nek−/− or Nlrp3−/− fetal liver cells showed further reduction in IL-1β production (Fig. 4a). Importantly, production of IL-6 and TNF-α in the sera of all chimeric mice was comparable (Fig. 4b, c). Likewise, production of IL-1β induced by intraperitoneal administration of MSU crystals that is also largely mediated by the NLRP3 inflammasome28, was reduced at comparable levels in chimeric mice reconstituted with Nek7−/− or Nlrp3−/− fetal liver cells (Fig. 4d). These studies indicate that Nek7 is required for activation of the NLRP3 inflammasome in vivo."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3",
      "NLRP3 inflammasome"
    ],
    "paragraph_index": 5,
    "text": "We have shown that Nek7 is an essential factor that specifically and non-redundantly functions downstream of potassium efflux to regulate the activation of the NLRP3 inflammasome. Our results are in agreement with recent studies that identified Nek7 as a critical regulator of the NLRP3 inflammasome29,30. Our studies suggest a model in which potassium efflux induced by NLRP3-activating stimuli triggers the association of NLRP3 with Nek7, leading to the assembly and activation of the NLRP3 inflammasome (Fig. 3h). Macrophages harboring the CAPS-associated Nlrp3R258W activating mutation that does not require potassium efflux for inflammasome activation19 also required Nek7 for caspase-1 activation, suggesting that this mutant NLRP3 may be competent for Nek7 association in the absence of potassium efflux. Nek7 regulates microtubule dynamic instability and spindle assembly which required the catalytic activity of Nek712,13,22,23. In contrast, the catalytic activity of Nek7 is not required for NLRP3 activation. Further work is needed to understand the dual functions of Nek7. Taken together, our studies suggest that Nek7 could be a potential target of therapeutics to treat inflammatory diseases linked to NLRP3 inflammasome activation."
  },
  {
    "matched_frozen_surfaces": [
      "NLRP3"
    ],
    "paragraph_index": 6,
    "text": "Nek7+/−, Nlrp3−/−, Asc−/−, Casp1−/−Casp11−/−, Casp11−/− mice on C57BL/6 background have been reported14,31–33. Nlrp3R258W mice were originally provided by Warren Strober (NIH). C57BL/6 mice were originally purchased from Jackson Laboratories (Bar Harbor, ME, USA) and maintained in our facility. All animal studies were approved by the University of Michigan Committee on Use and Care of Animals."
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

### Packet heldout_rrpv1_0020

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
  "title": "Britannin as a novel NLRP3 inhibitor, suppresses inflammasome activation in macrophages and alleviates NLRP3-related diseases in mice.",
  "pmid": "38172305",
  "pmcid": "PMC10943196",
  "doi": "10.1038/s41401-023-01212-5"
}
```

Abstract:
Overactivation of the NLRP3 inflammasomes induces production of pro-inflammatory cytokines and drives pathological processes. Pharmacological inhibition of NLRP3 is an explicit strategy for the treatment of inflammatory diseases. Thus far no drug specifically targeting NLRP3 has been approved by the FDA for clinical use. This study was aimed to discover novel NLRP3 inhibitors that could suppress NLRP3-mediated pyroptosis. We screened 95 natural products from our in-house library for their inhibitory activity on IL-1β secretion in LPS + ATP-challenged BMDMs, found that Britannin exerted the most potent inhibitory effect with an IC50 value of 3.630 µM. We showed that Britannin (1, 5, 10 µM) dose-dependently inhibited secretion of the cleaved Caspase-1 (p20) and the mature IL-1β, and suppressed NLRP3-mediated pyroptosis in both murine and human macrophages. We demonstrated that Britannin specifically inhibited the activation step of NLRP3 inflammasome in BMDMs via interrupting the assembly step, especially the interaction between NLRP3 and NEK7. We revealed that Britannin directly bound to NLRP3 NACHT domain at Arg335 and Gly271. Moreover, Britannin suppressed NLRP3 activation in an ATPase-independent way, suggesting it as a lead compound for design and development of novel NLRP3 inhibitors. In mouse models of MSU-induced gouty arthritis and LPS-induced acute lung injury (ALI), administration of Britannin (20 mg/kg, i.p.) significantly alleviated NLRP3-mediated inflammation; the therapeutic effects of Britannin were dismissed by NLRP3 knockout. In conclusion, Britannin is an effective natural NLRP3 inhibitor and a potential lead compound for the development of drugs targeting NLRP3.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10943196.xml
SHA-256: 16e485d7d6378e0ba68d591e8ca3736401e4b9a96d65796afb9d7614b7be9e8b

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

### Packet heldout_rrpv1_0029

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
  "title": "Interleukin-6 (IL-6) trans signaling drives a STAT3-dependent pathway that leads to hyperactive transforming growth factor-β (TGF-β) signaling promoting SMAD3 activation and fibrosis via Gremlin protein.",
  "pmid": "24550394",
  "pmcid": "PMC3975039",
  "doi": "10.1074/jbc.M113.545822"
}
```

Abstract:
Fibrosis is a common and intractable condition associated with various pathologies. It is characterized by accumulation of an excessive amount of extracellular matrix molecules that primarily include collagen type I. IL-6 is a profibrotic cytokine that is elevated in the prototypic fibrotic autoimmune condition systemic sclerosis and is known to induce collagen I expression, but the mechanism(s) behind this induction are currently unknown. Using healthy dermal fibroblasts in vitro, we analyzed the signaling pathways that underscore the IL-6-mediated induction of collagen. We show that IL-6 trans signaling is important and that the effect is dependent on STAT3; however, the effect is indirect and mediated through enhanced TGF-β signaling and the classic downstream cellular mediator Smad3. This is due to induction of the bone morphogenetic protein (BMP) antagonist Gremlin-1, and we show that Gremlin-1 is profibrotic and is mediated through canonical TGF-β signaling.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3975039.xml
SHA-256: d0e1c75c273a9e1af6a043c5392a356466003f4eabcfbf1fd728ca47a5fa4952

Frozen fulltext excerpts:
```json
[]
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

### Packet heldout_rrpv1_0030

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
  "title": "Role of integrin β1 and tenascin C mediate TGF-SMAD2/3 signaling in chondrogenic differentiation of BMSCs induced by type I collagen hydrogel.",
  "pmid": "38525326",
  "pmcid": "PMC10960929",
  "doi": "10.1093/rb/rbae017"
}
```

Abstract:
Cartilage defects may lead to severe degenerative joint diseases. Tissue engineering based on type I collagen hydrogel that has chondrogenic potential is ideal for cartilage repair. However, the underlying mechanisms of chondrogenic differentiation driven by type I collagen hydrogel have not been fully clarified. Herein, we explored potential collagen receptors and chondrogenic signaling pathways through bioinformatical analysis to investigate the mechanism of collagen-induced chondrogenesis. Results showed that the super enhancer-related genes induced by collagen hydrogel were significantly enriched in the TGF-β signaling pathway, and integrin-β1 (ITGB1), a receptor of collagen, was highly expressed in bone marrow mesenchymal stem cells (BMSCs). Further analysis showed genes such as COL2A1 and Tenascin C (TNC) that interacted with ITGB1 were significantly enriched in extracellular matrix (ECM) structural constituents in the chondrogenic induction group. Knockdown of ITGB1 led to the downregulation of cartilage-specific genes (SOX9, ACAN, COL2A1), SMAD2 and TNC, as well as the downregulation of phosphorylation of SMAD2/3. Knockdown of TNC also resulted in the decrease of cartilage markers, ITGB1 and the SMAD2/3 phosphorylation but overexpression of TNC showed the opposite trend. Finally, in vitro and in vivo experiments confirmed the involvement of ITGB1 and TNC in collagen-mediated chondrogenic differentiation and cartilage regeneration. In summary, we demonstrated that ITGB1 was a crucial receptor for chondrogenic differentiation of BMSCs induced by collagen hydrogel. It can activate TGF-SMAD2/3 signaling, followed by impacting TNC expression, which in turn promotes the interaction of ITGB1 and TGF-SMAD2/3 signaling to enhance chondrogenesis. These may provide concernful support for cartilage tissue engineering and biomaterials development.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC10960929.xml
SHA-256: 660765add725f5df96f1150d7052146e81e25172d88185b0217e51267944328e

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "type I collagen"
    ],
    "paragraph_index": 2,
    "text": "Characterized by good biocompatibility, degradability, low immunogenicity and cartilage-mimicking properties, collagen type I has been widely used in cartilage repair. It has been reported that collagen hydrogel has inherent inductivity and may provide a suitable environment and aggregate the signal molecule for the chondrogenic differentiation of BMSCs without exogenous growth factors both in vitro and in vivo [7, 8]. From the perspective of material properties, the chondrogenic potential of type I collagen hydrogel depends on multiple properties, like viscoelasticity, which plays an important regulatory factor of cell-matrix interactions [9], mechanical strength, which can affect the proliferation space of cells [10], the fiber structure, which influences chondrogenic differentiation by regulating factors such as mass transfer, protein adsorption, degradability and contraction [11, 12], the surface charge of hydrogels, which affects their hydrophilicity, protein diffusion and binding, which consequently impacts the adhesion and spreading of BMSCs on their surface [13] and there are reported that type I collagen hydrogels can support the microenvironment with cell–ECM interaction and migration space mediated by N-cadherin, beneficial for chondrogenesis [14–16]. Xiao et al. reported that type I collagen hydrogel with faster-relaxing viscoelasticity promoted cell–matrix interactions and eventually facilitated long-term chondrogenesis, similar to ROCK inhibitors, which can mitigate myosin hyperactivation and cell apoptosis [9]. However, the underlying mechanism of chondrogeni"
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β",
      "collagen I",
      "type I collagen"
    ],
    "paragraph_index": 3,
    "text": "Cells can recognize and adhere to immobilized ECM components by specific receptor–ligand types of interaction to influence subsequent cellular behavior, such as cell survival and differentiation [17, 18]. The best-known receptor of collagen is integrin, which plays a major role in mediating interactions between cells and the ECM [19]. There are at least 18 α subunits and 8 β subunits in humans, which together generate 24 integrin proteins. Among them, integrin β1 (ITGB1) is the hub subunit, which can combine with other 12 α subunits like α2β1 and α11β1 integrin [20], and it belongs to the integrin family mainly associated with chondrogenesis [21, 22]. The integrin β binds to the domain of TGF-β precursor to activate TGF-β precursor to eventually release the mature TGF-β growth factor that contributes to chondrogenesis [23, 24]. Loss of ITGB1 abolishes the ability of cells to mitigate myosin activation and would lead to failure of chondrogenic differentiation [9, 25]. Silencing of ITGB1 in MSCs abolished both osteoblastic and chondrogenic differentiation in response to substrate stiffness [26]. As the downstream of integrin β [27], TGF-β/SMAD signaling is crucial for chondrogenesis [28] and maintenance of the cartilage matrix [29]. The phosphorylation of SMAD2/3 is an important event for activating the TGF-β/SMAD signaling and its nuclear localization to initiate the chondrocyte-related gene expression [30, 31]. SMAD2/3 can upregulate the protein level of SOX9, and form transcriptional complexes with SOX9 [32, 33]. SOX9 is an important transcription factor that binds to the "
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 4,
    "text": "This study focused on the underlying mechanism of chondrogenesis triggered by collagen hydrogel by predicting collagen receptor pathways based on bioinformatical methods. We hypothesized that collagen hydrogel may regulate the TGF-β/SMAD signaling and TNC expression through activating ITGB1 as the collagen receptor, ultimately initiating chondrogenic differentiation. This study may establish the relationship between bioactive materials and molecular mechanisms for materials-optimized design guiding in cartilage tissue engineering."
  },
  {
    "matched_frozen_surfaces": [
      "TGF-β"
    ],
    "paragraph_index": 5,
    "text": "The gene expression profile (GSE40175) of chondrogenic inducement of bone marrow mesenchymal stem cells (BMSCs) was downloaded from the GEO database (https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE40175) [43]. This dataset included both the BMSCs group and the chondrocyte-induction group. Membrane-related proteins (species: Homo sapiens) were downloaded from the Membranome database (https://membranome.org/proteins, 2021 version). Expression levels of membrane proteins were analyzed in GSE40175 to obtain the top 10 membrane proteins with the highest expression levels in BMSCs by sorting from highest to lowest. Genes related to the TGF-β signaling pathway were obtained by inputting ‘TGF-β signaling pathway’ into GeneCards (https://www.genecards.org/), and non-Protein Coding genes were excluded. These genes were then subjected to protein–protein interaction analysis using the CytoscapeAPP."
  },
  {
    "matched_frozen_surfaces": [
      "collagen I"
    ],
    "paragraph_index": 12,
    "text": "Forty male SD rats (6–8 weeks old) were used. After general anesthesia, the joint of the SD rat was exposed layer by layer, and a cartilage defect (2 mm in diameter, 1.5 mm in depth) was created to establish the cartilage defect model. Rats were randomly divided into four groups: (i) COL (BMSCs + collagen); (ii) ITGB1-KD + COL (ITGB1 knockdown-BMSCs + collagen); (iii) TNC-KD + COL (TNC knockdown-BMSCs + collagen); (iv) TNC-OE + COL (TNC overexpression-BMSCs + collagen). Cells encapsulated in the collagen hydrogel were injected into the defect site and jellified. Then the wound was sutured, and 20 000 U/100 g penicillin sodium (HEBEI YUANZHENG PHARMACEUTICAL, Shijiazhuang, China) was intramuscularly injected every day for 3 days."
  },
  {
    "matched_frozen_surfaces": [
      "COL1A1"
    ],
    "paragraph_index": 15,
    "text": "Samples were incubated with 3% H2O2 for 10 min at 25°C to block endogenous peroxidase activity. After blocking with normal goat serum, primary antibodies against TNC (1:100; Proteintech, Wuhan, China), ITGB1 (1:100; Proteintech, Wuhan, China), COL2A1 (1:100; Proteintech, Wuhan, China), COL1A1 (1:100; Proteintech, Wuhan, China), p-SMAD2/3 (1:100; Cell Signaling, USA) and SMAD2/3 (1:100; Cell Signaling, USA) were added and incubated overnight at 4°C. For the immunohistochemical staining, a secondary antibody was incubated for 1 h, and then used DAB kit (ZSGB-BIO, Beijing, China) for development. After being stained with hematoxylin, the sections were sealed and photographed by a microscope. For the immunofluorescence staining, fluorescent dye-conjugated secondary antibodies FITC and CY3 (1:100; Bioss, Beijing, China) and 4′, 6-diamidino-2-phenylindole (DAPI; Beyotime Biotechnology, Shanghai, China) were used for binding and nuclear staining. Images were collected with a fluorescence microscope (ECHO, USA) and fluorescence intensity was semi-quantitatively analyzed by Image J."
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

### Packet heldout_rrpv1_0039

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
  "title": "V1bR enhances glucose-stimulated insulin secretion by paracrine production of glucagon which activates GLP-1 receptor.",
  "pmid": "39217353",
  "pmcid": "PMC11365140",
  "doi": "10.1186/s13578-024-01288-4"
}
```

Abstract:
Arginine vasopressin (AVP) has been reported to regulate insulin secretion and glucose homeostasis in the body. Previous study has shown that AVP and its receptor V1bR modulate insulin secretion via the hypothalamic-pituitary-adrenal axis. AVP has also been shown to enhance insulin secretion in islets, but the exact mechanism remains unclear.
In our study, we unexpectedly discovered that AVP could only stimulates insulin secretion from islets, but not β cells, and AVP-induced insulin secretion could be blocked by V1bR selective antagonist. Single-cell transcriptome analysis identified that V1bR is only expressed by the α cells. Further studies indicated that activation of the V1bR stimulates the α cells to secrete glucagon, which then promotes glucose-dependent insulin secretion from β cells in a paracrine way by activating GLP-1R but not GCGR on these cells.
Our study revealed a crosstalk between α and β cells initiated by AVP/V1bR and mediated by glucagon/GLP-1R, providing a mechanism to develop new glucose-controlling therapies targeting V1bR.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11365140.xml
SHA-256: d7640798f70e809f9d3d2b44c3cd28821b3eeaac57c42b276e1c510546983bec

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "insulin secretion"
    ],
    "paragraph_index": 2,
    "text": "Several studies have demonstrated the involvement of AVP and V1bR in facilitating insulin secretion and maintaining blood glucose homeostasis. AVP regulates the hypothalamic-pituitary-adrenal (HPA) axis, stimulating the release of corticotropin-releasing hormone (CRH) through V1bR activation, thereby promoting CRH-induced insulin secretion [8]. AVP has been shown to enhance insulin secretion in mouse and rat pancreas, and isolated mouse islets [7, 9, 10]. SSR149415, a selective V1b receptor antagonist, significantly attenuated AVP-stimulated insulin secretion from isolated mouse islets, while the antagonists targeting V1a receptor exert minimal influence [7]. AVP has also been reported to confer protection on islet β cells against cytokine-induced apoptosis [10, 11]."
  },
  {
    "matched_frozen_surfaces": [
      "insulin secretion"
    ],
    "paragraph_index": 3,
    "text": "AVP has also been reported to stimulate glucagon secretion from the pancreas of mouse and rat, and the α cell line InR1G9 [2, 12, 13]. Studies on AVP-related neurons have demonstrated that AVP acts as a systemic regulator of glucagon secretion under physiological conditions [14, 15]. The brain perceives glucose concentration to induce AVP secretion, which subsequently influences the pancreas to promote glucagon release and elevate blood glucose levels. However, this regulatory mechanism is impaired in individuals with type 1 diabetes [14]. Compared to wild-type mice, V1b receptor knockout mice have reduced insulin and glucagon levels in the plasma [16]. These findings highlight the crucial roles of AVP and its receptor V1bR in regulating blood glucose homeostasis, and reflect the complex and dual functions of AVP in regulating both glucagon and insulin secretion in animals."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1 receptor",
      "insulin secretion"
    ],
    "paragraph_index": 4,
    "text": "In evaluating AVP-mediated insulin secretion, we unexpectedly discovered that AVP could stimulate insulin release from isolated mouse islets, but not β cells. Single cell analysis of the islets revealed that V1bR is expressed in the α cells but not β cells. Further studies suggested that activation of V1bRs in the α cells promotes the release of glucagon, which then induces insulin secretion from β cells by activating GLP-1 receptor."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 9,
    "text": "The cAMP assay was performed with GCGR/HEK293 or GLP-1R/HEK293 cell lines. Briefly, cells were harvested and resuspended in DMEM containing 500 μM IBMX at a density of 2 × 105 cells/mL. Cells were then plated onto 384-well assay plates at 1000 cells/5 μL/well. DMEM (5 μL) containing different concentrations of antagonists were added to the cells and the incubation lasted for 15 min at 37 °C (this step was omitted in the agonist detection), then another 5 μL DMEM containing different concentrations of agonists were added to the cells and the incubation lasted for 30 min at 37 °C. Intracellular cAMP levels were detected with a LANCE Ultra cAMP kit (PerkinElmer, #TRF0264) and an Envision Plate Reader (PerkinElmer) according to the manufacturer’s instructions."
  },
  {
    "matched_frozen_surfaces": [
      "GLP1R"
    ],
    "paragraph_index": 12,
    "text": "Table 1Summary of primer and shRNA sequencesNameNucleotide sequenceqPCR-mouse GapdhF: AGGTCGGTGTGAACGGATTTGR: TGTAGACCATGTAGTTGAGGTCAqPCR-mouse Avpr1bF: GAGCCTTCTTGGACTGCTACCR: TACAGCCAGGTTGCCTCCTqPCR-mouse Ins2F: GCTTCTTCTACACACCCATGTCR: AGCACTGATCTACAATGCCACqPCR-mouse GcgF: TTACTTTGTGGCTGGATTGCTTR: AGTGGCGTTTGTCTTCATTCAqPCR-mouse Glp1rF: ACGGTGTCCCTCTCAGAGACR: ATCAAAGGTCCGGTTGCAGAAqPCR-mouse GcgrF: TGCACTGCACCCGAAACTACR: CATCGCCAATCTTCTGGCTGTqPCR-rat GapdhF: ACAGCAACAGGGTGGTGGACR: TTTGAGGGTGCAGCGAACTTqPCR-rat Avpr1bF: TCTCCGACTCAGCCTTAACCTCAGR: CCGTCCACCTGCTCTAAATCCTTCqPCR-rat Glp1rF: TCCTTCATCCTCCGAGCACTGTCR: GCCCAGAGAGTCCTGATACGAGAGqPCR-rat GcgrF: CCCAATGTCAGATGGATGATR: TAGCGTGTCTTGAGCAGCCAATCshRNA- Glp1rF: GCAGAAATGGAGAGAGTATCGshRNA-GcgrR: GCAACAGAACTTTCGACAAGT"
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 14,
    "text": "Specific sequences of shRNAs (Table 1) targeting GCGR or GLP-1R mRNA were constructed into pLKO.1 puro lentiviral vector (Addgene, #8453). Lentiviral vectors and packaging vectors were transfected into HEK293T cells by FuGENE HD Transfection Reagent (Promega, #E2312) to produce virus particles. INS-1E cells were seeded onto 6-well plates at a density of 5 × 105 cells per well and incubated with viruses and 5 μg/mL polybrene for 48 h. Transfected INS-1E cells were collected for real-time qPCR and co-culture experiments."
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

### Packet heldout_rrpv1_0040

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
  "title": "Receptor activity-modifying protein 3 enhances GLP-1-mediated insulin secretion.",
  "pmid": "40835007",
  "pmcid": "PMC12624773",
  "doi": "10.1016/j.jbc.2025.110604"
}
```

Abstract:
The targeting of the glucagon-like peptide-1 (GLP-1) receptor for diabetes and obesity is not a novel strategy, with recent therapeutics showing efficacy in weight loss and glycemic control. However, they are also associated with side effects, including gastrointestinal disruptions and pancreatitis. Developing agonists with different signaling profiles or that exert some tissue selectivity can circumvent these on-target, unwanted effects. Receptor activity-modifying proteins (RAMPs) offer the potential to do both, through modulation of agonist binding and signaling, as well as surface expression. The GLP-1 receptor was found to interact with RAMP3, with the heterodimer able to bind agonists at the cell surface. RAMP3 expression biased the receptor toward Ca2+ mobilization, away from the canonical cAMP-driven signaling. When examining G protein coupling, the interaction with RAMP3 reduced activation of the cognate Gαs but increased secondary couplings to Gαq and Gαi. These increased couplings led to an elevation in glucose-stimulated insulin secretion when cells overexpressing RAMP3 were stimulated with GLP-1. A reciprocal effect was observed when looking at reduced expression of endogenous RAMP3, with a loss of sensitivity to GLP-1 in both glucose and insulin tolerance tests in a Ramp3 KO mouse model. The effects of this interaction can then inform the selection of models and peptide design when targeting this receptor for therapeutic intervention.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12624773.xml
SHA-256: 25576c11d327ebeeb12a7cb2bbb802d524f050af22a12542ed4631a044fed7dd

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "GLP-1 receptor",
      "GLP-1R"
    ],
    "paragraph_index": 2,
    "text": "A recent therapeutic advance has been the approval of peptides targeting the glucagon-like peptide-1 (GLP-1) receptor (GLP-1R) for obesity and weight loss. The incretin effect, whereby oral glucose elevates plasma insulin levels to a greater degree than intravenous administration, was first observed in 1964 (1). This is mediated by incretin hormones, the best known of which are GLP-1 and the glucose-dependent insulinotropic polypeptide (GIP). As such, mimetics of the endogenous GLP-1 hormone, the first of which was exenatide (exendin-4), were approved for T2DM in 2005 (2). However, newer mimetics semaglutide (trade names of Ozempic and Wegovy) or tirzepatide (sold under Mounjaro or Zepbound), the latter of which targets both the GLP-1R and the GIP receptor (GIPR), have garnered much attention through their dual effects on lowering plasma glucose and aiding weight loss. Semaglutide has since been reported to protect against neurodegeneration and neuroinflammation (3) as well as cardiovascular disease (4). This culminated in semaglutide being labeled as the 2023 breakthrough of the year (5). However, with their increased use, attention is being drawn to the unwanted side effects of GLP-1 mimetics. Common side effects are nausea and vomiting as well as other gastrointestinal discomforts. However, more serious side effects are also known, such as pancreatitis, kidney failure, and gallbladder problems (6). There is therefore the unmet need to develop mimetics with improved therapeutic potential that exhibit fewer side effects."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 3,
    "text": "One method of reducing on-target unwanted effects is to selectively activate signaling pathways associated with the positive outcome, relying on the concept of signaling bias. The GLP-1R is a class B1 G protein–coupled receptor (GPCR), which predominantly couples to Gαs, leading to an increase in cAMP production. However, like other members of class B1, the GLP-1R exhibits pleiotropy, coupling to other Gα families and recruiting β-arrestins (7, 8), leading to a multifaceted signaling output. For other pleiotropic GPCRs, the activation of these different pathways can be influenced by the agonist, giving rise to signaling bias. This has been studied most heavily for the μ-opioid receptor, where it is thought that agonist tolerance is mediated by β-arrestins, leading G protein–biased agonists to be preferred (9)."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R"
    ],
    "paragraph_index": 4,
    "text": "Signaling bias can also be influenced by the tissue because of differential expression of signaling proteins as well as allosteric modulators. A common protein allosteric modulator of class B1 GPCRs is the receptor activity–modifying proteins (RAMPs). First discovered for the calcitonin-like receptor (CLR), with which they form obligate heterodimers, RAMPs influence the expression, affinity, and signaling bias of the receptor. For the calcitonin family, this leads to receptors considered functionally distinct (10, 11), although smaller effects are observed on other receptors, for example, the vasoactive intestinal peptide receptor 1 or glucagon receptor (GCGR) when coexpressed with RAMP2 (12). Importantly, the effects of RAMPs are agonist and pathway dependent, with RAMP2 increasing Gαs coupling at GCGR in response to glucagon and oxyntomodulin (an endogenous dual agonist of both GCGR and GLP-1R) but decreasing the response to GLP-1 and liraglutide (a synthetic, lipidated GLP-1 mimetic, approved in the treatment of T2DM) (13)."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "glucose-stimulated insulin secretion",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 5,
    "text": "RAMPs have been implicated in diabetes and obesity, although their role appears multifaceted. Of the GPCRs that interact with RAMPs, many are involved in the regulation of glucose levels and body weight. The pancreatic hormone amylin binds a class B1 GPCR, with the three amylin receptor heterodimers between the calcitonin receptor and RAMP1–3. RAMPs are expressed in many of the tissues of the endocrine system, such as the thyroid and hypothalamus, and global RAMP KO in rodents causes dysregulation of body weight and glycemic control (14, 15). (The role of RAMPs in diabetes and obesity is further reviewed in the study by Malcharek et al. (16)). Importantly, RAMPs are coexpressed with the incretin hormone receptors across regions of the brain and the pancreas (Human Protein Atlas as of January 2025). The interaction between GIPR and RAMPs and the consequences for glucose tolerance have been studied previously (17), but the involvement of GLP-1R is less known. GLP-1R has been previously shown to interact with all three RAMPs (18, 19), with depressive effects on cAMP accumulation observed. However, specific interactions at the plasma membrane have neither been studied nor have any effects of RAMP expression on physiological roles of the receptor, such as glucose-stimulated insulin secretion (GSIS)."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1R",
      "GSIS",
      "insulin secretion"
    ],
    "paragraph_index": 6,
    "text": "Herein, we measured a specific membrane interaction between GLP-1R and RAMP3 but not RAMP1 or 2. The two proteins were observed to form a complex able to bind agonists, but no effect was observed on the affinity of the receptor. RAMP3 expression decreased cAMP accumulation and increased mobilization of Ca2+ from intracellular stores (Ca2+)i. This was determined to be primarily because of an increase in Gαi/o coupling. In contrast, no effect was observed on internalization, with only a decrease in maximal β-arrestin recruitment. This elevation in (Ca2+)i was shown to lead to enhanced GSIS. The reciprocal effect was observed in murine cell and animal models, where a knockdown or a KO of Ramp3 decreased insulin secretion in response to GLP-1. There is therefore the potential for improved GLP-1 mimetics, which show bias toward the GLP-1R–RAMP3 complex, with subsequent effects on tissue selectivity and therapeutic profile."
  },
  {
    "matched_frozen_surfaces": [
      "GLP-1 receptor",
      "GLP-1R"
    ],
    "paragraph_index": 7,
    "text": "Although GLP-1R expression has been unable to promote RAMP membrane trafficking, interactions have been observed at the molecular level, for example, using bioluminescence resonance energy transfer (BRET) (19). Therefore, to determine if these observed interactions are present at the plasma membrane, a cell surface BRET interaction assay was used as previously described (17). Nluc-GPCR and SNAP-RAMP were transiently transfected into Cos7 cells, which do not endogenously express RAMPs, calcitonin receptor, or CLR (20), to reduce any interference from unlabeled proteins. SNAP-RAMPs were irreversibly conjugated to SNAP-Surface Alexa Fluor 488 to specifically measure cell surface interactions; the conjugate was cell impermeable, so only labeled SNAP-RAMPs were expressed at the cell surface. All three RAMPs displayed an interaction with CLR, as observed by the saturating increase in BRET ratio. GLP-1R only displayed a saturating increase in BRET with SNAP-RAMP3 (Fig. 1A). Overexpression of HA-CLR was not shown to promote an interaction between Nluc–GLP-1R and SNAP-RAMP1 or 2, indicating that the expression of RAMP at the membrane is not sufficient to induce an interaction, even when increasing the amount of SNAP-RAMP 10-fold over Nluc–GLP-1R.Figure 1GLP-1R and RAMP3 interact and can bind agonists as a complex.A, cell-surface NanoBRET assay measuring interactions between Nluc–CLR (left) and Nluc–GLP-1R (right) with SNAP-RAMPs labeled with SNAP-Surface Alexa Fluor 488 in Cos7 cells, n = 4. B, Nluc–GLP-1R interaction with labeled SNAP-RAMPs, in the presence of a fixed concentration"
  }
]
```

Fields fulltext was expected to resolve:
["evidence_mode", "context", "relation"]

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

### Packet heldout_rrpv1_0046

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
  "title": "A Multikinase Inhibitor AX-0085 Blocks FGFR1 Activation to Overcomes Osimertinib Resistance in Non-Small Cell Lung Cancer.",
  "pmid": "41595602",
  "pmcid": "PMC12838157",
  "doi": "10.3390/biomedicines14010066"
}
```

Abstract:
Background: Osimertinib is a third-generation epidermal growth factor receptor (EGFR) tyrosine kinase inhibitor (TKI) with high efficacy in treating patients with advanced non-small cell lung cancer (NSCLC) harboring EGFR-activating mutations. Although osimertinib is a frontline anticancer agent for NSCLC, several patients inevitably develop tumor recurrence caused by osimertinib resistance. The activation of anexelekto (AXL) or fibroblast growth factor receptor 1 (FGFR1) is reported as a major factor driving osimertinib resistance in NSCLC. Thus, targeting AXL and FGFR1 offers the potential to overcome osimertinib resistance. Methods: In this study, we generated osimertinib-resistant cell lines from EGFR-mutant NSCLC cell lines in vitro and investigated the biological significance of AX-0085 on these cell lines by conducting transcriptomic analyses. Results: The expression of several genes associated with MAPK, ERK, and FGF receptor signaling pathways, including AXL, was altered upon AX-0085 treatment of osimertinib-resistant cells. Furthermore, AX-0085 treatment effectively blocked AXL and FGFR1 activation and sensitized osimertinib-resistant cells. Additionally, AX-0085 inhibited AXL and FGFR1-dependent oncogenic events, including cell proliferation, clonogenicity, and migration. Conclusions: The dual inhibition of AXL and FGFR1 by AX-0085 can overcome acquired osimertinib resistance, supporting its potential as a therapeutic strategy for treating patients with osimertinib-resistant tumors.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC12838157.xml
SHA-256: 23d374e773b9c2728652615dda4e399a3d0dd79942749e1b7e35cda8924e2202

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib",
      "AZD9291"
    ],
    "paragraph_index": 1,
    "text": "Lung cancer is one of the most common causes of cancer-related mortality worldwide [1]. Particularly, non-small cell lung cancer (NSCLC) accounts for 85%, with adenocarcinomas comprising around 50% of NSCLC cases [1]. Extensive research on lung cancers, especially lung adenocarcinomas, showed several mutations in proto-oncogenes. Mutations in epidermal growth factor receptor (EGFR) account for nearly 50% of lung cancers in East Asians and ~15% in Caucasians [2]. Generally, EGFR tyrosine kinase inhibitors (TKIs) such as osimertinib (AZD9291), gefitinib, erlotinib, and afatinib are recommended as standard treatment for lung cancers with EGFR mutations [3]."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 2,
    "text": "Combinatorial targeted therapies have emerged as one of the most significant cancer treatment regimens. Osimertinib, a third-generation EGFR-TKI specifically designed to inhibit EGFR-activation mutations, has replaced first-generation EGFR-TKIs, such as gefitinib and erlotinib, as a first-line treatment for patients with metastatic EGFR mutations [4,5]. Osimertinib exhibits high anticancer activity against EGFR mutations, while only mild anticancer activity against wild type EGFR [6]. Despite the strong anticancer effects of osimertinib on lung cancers having mutations in EGFR gene contributed for acquired drug resistance [7]. Several genetic alterations are the main driving factor for acquired drug resistance to osimertinib [8,9]. In addition to genetic variations, several EGFR-dependent and EGFR-independent pathways, including EGFR C797S and T790M mutations, HER2 mutations, c-MET amplification, and epithelial-to-mesenchymal transition, facilitates to the development of acquired resistance in NSCLCs [10,11]. Hence, the discovery of therapeutic agents that reverse acquired EGFR-TKI resistance is critical for developing effective treatment strategies."
  },
  {
    "matched_frozen_surfaces": [
      "AXL"
    ],
    "paragraph_index": 3,
    "text": "The receptor tyrosine kinase (RTK) AXL was first identified in patients with chronic myeloid leukemia [12]. The upregulation of AXL is observed in several cancers such as breast, lung, and renal cell cancer, and is linked to tumor progression with poor prognosis [13,14,15]. AXL plays a critical role in tumor growth, angiogenesis, and metastasis, including the development of resistance to anti-EGFR agents [16,17]. Overexpression of AXL has been observed in lung adenocarcinomas harboring EGFR-activating mutations, compared to those with wild-type EGFR [18]. Moreover, several studies have demonstrated that overexpression and activation of AXL signaling are associated with acquired resistance to EGFR-TKI therapies [10,17,19]. Furthermore, inhibition of AXL improves the efficacy of standard EGFR-TKI-based chemotherapy regimens [10,20]."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "Recently, fibroblast growth factor receptor 1 (FGFR1), another RTK, has been implicated as a mechanism of resistance to EGFR-TKIs [21]. Elevated FGFR1 expression has been linked with reduced progression-free survival in patients undergoing EGFR-TKI therapy, highlighting its potential role in diminishing treatment efficacy [22]. Upregulation of FGFR1 expression has been linked to the induction of EMT in tumor cells [23]. On activation, FGFR1 helps in recruiting fibroblast growth factor receptor substrate 2 (FRS2) adaptor protein to its juxtamembrane region. The FGFR1–FRS2 complex functions as a central hub for downstream signaling pathways critical for cell survival, including the phosphoinositide 3-kinase (PI3K)-AKT and mitogen-activated protein kinase (MAPK) pathways [24,25]. Additionally, the FGF2-FGFR1 axis, which triggers downstream PI3K/AKT and MAPK signaling, may offer an EGFR-independent survival pathway, resulting in resistance to osimertinib [26]. Given that AXL and FGFR1 share common downstream signaling molecules, it is plausible that crosstalk occurs between these two pathways, contributing to resistance mechanisms in cancer therapy. Thus, targeting both AXL and FGFR1 represents a promising strategy for overcoming resistance to osimertinib."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "AXL activation"
    ],
    "paragraph_index": 5,
    "text": "We have synthesized a small-molecule multikinase inhibitor, AX-0085, for inhibiting AXL activation [15]. The inhibitory efficiency of AX-0085 was significant and effectively blocked the activation of AXL in triple-negative breast cancer (TNBC). Furthermore, AX-0085 inhibited several AXL-dependent events such as cell proliferation, migration, invasion, and EMT in TNBC. AX-0085 also promoted apoptosis and cell cycle arrest by suppressing CDK2 and Cyclin E expression in TNBC. Finally, AX-0085-treated tumors displayed reduced volume in a mouse xenograft model, suggesting its potential as a therapeutic inhibitor for AXL activation in TNBC."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 6,
    "text": "In this study, we aimed to further elucidate the anticancer effects of AX-0085 by examining its inhibitory efficacy on AXL and FGFR1 activation in osimertinib-resistant lung cancer cells. Transcriptome analysis revealed that AX-0085 downregulated critical genes such as FGFR1 and AXL, which were found to be elevated in osimertinib-resistant cells. Furthermore, we demonstrated that AX-0085 effectively inhibited AXL and FGFR1 activation, thereby sensitizing osimertinib-resistant HCC827 cells. Treatment with AX-0085 significantly suppressed key oncogenic processes, including proliferative capacity, clonogenic growth, and migratory activity in osimertinib-resistant cells under in vitro conditions. These findings support the potential of AX-0085 as a promising therapeutic strategy to overcome osimertinib resistance in NSCLC."
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

### Packet heldout_rrpv1_0047

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
  "title": "A novel mesenchymal epithelial transition (MET) inhibitor, CB538, relieves acquired resistance in EGFR-mutated MET-amplified non-small cell lung cancer.",
  "pmid": "40224983",
  "pmcid": "PMC11985202",
  "doi": "10.21037/tcr-24-1614"
}
```

Abstract:
Osimertinib, a third-generation epidermal growth factor receptor (EGFR) tyrosine kinase inhibitor (TKI), is the first-line standard therapy for metastatic EGFR-mutated non-small cell lung cancer (NSCLC). Although osimertinib is effective, it's durable response is invariably limited by the emergence of acquired resistance. Mesenchymal epithelial transition (MET) amplification is a frequent mechanism in patients with EGFR-mutated NSCLC who are resistant to EGFR-TKIs. Consequently, combined treatment with EGFR-TKIs and MET-TKIs has been explored as a strategy for overcoming this resistance. The current study aimed to explore the single and combination inhibition effect of CB538, a novel MET inhibitor in MET-activated, EGFR-mutant NSCLC cells.
The cellular inhibitory effects of single and co-treatment of CB538 with EGFR-TKIs were evaluated in the established EGFR-TKI-resistant cells [PC9/ER (erlotinib resistance), HCC827/OR (osimertinib resistance)]. The preclinical activities of CB538 were investigated by evaluating in vitro kinase activity, cell growth, and Western blotting of phosphorylated MET and downstream signaling molecules in MET-activated, EGFR-TKI-resistant cells. Cell viability was examined by MTT and colony formation. The inhibition of migration was determined by wound-healing assay. A xenograft tumor model was employed to investigate in vivo HCC827/OR cell growth in BALB/c nude mice.
We confirmed that activated MET/Axl signaling pathways and EMT-related proteins were inhibited by CB538 in established EGFR-TKI-resistant NSCLC cells. CB538, a novel c-MET inhibitor, decreased the growth, migration, and invasive properties of these EGFR-TKI-resistant NSCLC cells. CB538 also inhibited tumor growth and expression of activated proteins (MET and Axl) in in vivo HCC827/OR xenograft model.
Additional treatment with CB538 enhanced sensitivity to EGFR-TKIs in two EGFR-TKI-resistant NSCLC cells by inhibiting EGFR/MET/Axl pathway axis. Overall, the treatment effects of CB538 were confirmed to relieve EGFR-TKI-driven resistance in EGFR-mutant NSCLC cells.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC11985202.xml
SHA-256: 5bf2291fa2d988b242d7eb6627bf1f1cd2ae274db97ae2a72a45940f439295d2

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 3,
    "text": "• Concomitant treatment of MET inhibitor with osimertinib is known to have potential to overcome drug resistance in EGFR-TKI-resistant NSCLC cells with EGFR mutation and MET gene amplification. However, single treatment of MET inhibitor, CB538, was as effective as a combination treatment in MET-activated, EGFR-TKI-resistant NSCLCs in this study."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "osimertinib"
    ],
    "paragraph_index": 4,
    "text": "• Crosstalk between MET and Axl has been reported in several cancer cells. New findings confirmed that MET knockdown inhibited the expression of Axl as well as MET in EGFR mutant NSCLC cells (erlotinib-resistant PC9, osimertinib-resistant HCC827 cells)."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 6,
    "text": "Non-small cell lung cancer (NSCLC) is the poor prognosis tumor, accounting for approximately 80–90% of lung cancers. Furthermore, adenocarcinoma is the most frequent histological subtype of NSCLC. Epidermal growth factor receptor (EGFR) is one of the most common driver genes of NSCLC. EGFR mutations display a heterogeneous representation depending on ethnicity and region (1). Treatment of patients with NSCLC harboring EGFR tyrosine kinase inhibitor (TKI)-sensitizing mutations using EGFR-TKIs, such as erlotinib or afatinib, as an initial therapy has been shown to extend progression-free survival (PFS) (2,3). However, 50% or more of these patients exhibited disease progression. Recently, third-generation EGFR-TKIs (e.g., osimertinib) have started to represent promising therapeutic options for patients with NSCLC who have become resistant to first- or second-generation EGFR-TKIs because of the emergence of the EGFR T790M mutation (4-6) which is a potent and irreversible EGFR-TKI that targets EGFR mutations without affecting wild-type EGFR. With its remarkable efficacy and affordable safety, osimertinib is recommended as the standard first-line treatment for patients with advanced or metastatic NSCLC harboring EGFR mutations. However, resistance to the third-generation EGFR-TKIs has been described previously. Osimertinib-treated patients as first-line treatment tend to develop resistance after 18.9 months of treatment (1,3,6)."
  },
  {
    "matched_frozen_surfaces": [
      "AXL",
      "AXL activation",
      "osimertinib"
    ],
    "paragraph_index": 7,
    "text": "Several mechanisms have been related to acquired resistance to EGFR-TKIs (7,8). For osimertinib, these include the development of secondary EGFR mutations and activation of bypass signaling pathways. Additionally, mesenchymal epithelial transition (MET) amplification, Axl activation, and epithelial-to-mesenchymal transition (EMT) are crucial mechanisms responsible for acquired resistance to EGFR-TKIs. The resistance to TKIs can be involved by the EMT-status and Axl expression. EMT and Axl are associated with reduced sensitivity to many chemotherapeutic and anticancer drugs (9-13). MET amplification is a cause of the most common EGFR-independent mechanism of osimertinib resistance, accounting for 5–24% (6,14,15). Activation of the hepatocyte growth factor (HGF)/c-Met pathway provides a powerful signal for cell proliferation, survival, migration, invasion, and angiogenesis (16-18). A clinical trial on osimertinib combined with crizotinib, initially developed as a MET inhibitor, was also studied in a retrospective analysis, which showed that the overall response rate (ORR) was 100% and the median PFS was 6.2 months in patients with lung adenocarcinoma with MET amplification (17,19). Approved MET inhibitor, Tepotinib (Tepmetko®) and EGFR-TKI, osimertinib (Tagrisso®) are promising combinations for patients with osimertinib-pretreated, EGFR-mutated, MET-amplified NSCLC. Tepotinib plus osimertinib revealed an ORR of 45.8% [95% confidence interval (CI), 31.4–60.8%] in patients with MET amplificated NSCLC from phase 2 INSIGHT 2 trial (NCT03940703) (20)."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 8,
    "text": "Thus, simultaneous inhibition of both EGFR and MET is required to overcome resistance to EGFR inhibitors following MET amplification (19-22). We evaluated CB538 as a type II MET-TKI in MET-activated, EGFR-TKI-resistant NSCLCs because of its potent inhibitory efficacy against c-Met-activated cancer cells and MET mutant kinases. In this study, we determined that MET activation is a key mechanism in acquired resistance to the first- and third-generation EGFR-TKIs, erlotinib, and osimertinib. We further demonstrated that additional treatment of the CB538 MET TKI to EGFR-TKIs could be the option for overcoming the resistance exhibited by EGFR-TKIs-resistant NSCLC cells. We present this article in accordance with the MDAR and ARRIVE reporting checklists (available at https://tcr.amegroups.com/article/view/10.21037/tcr-24-1614/rc)."
  },
  {
    "matched_frozen_surfaces": [
      "osimertinib"
    ],
    "paragraph_index": 9,
    "text": "Erlotinib was obtained from Selleckchem (Houston, TX, USA), and osimertinib and capmatinib were purchased from Combi-Blocks, Inc. (San Diego, CA, USA) and MedChemExpress (Monmouth, NJ, USA), respectively. CB538 (MW. 687.7) was provided by CMG Pharmaceutical, Co., Ltd. (Seongnam City, Korea). Other chemicals were used from Sigma-Aldrich (St. Louis, MO, USA). Dimethyl sulfoxide (DMSO) was used as a vehicle solvent for in vitro experiments and stored at −20 ℃."
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

### Packet heldout_rrpv1_0059

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
  "title": "BDNF over-expression increases olfactory bulb granule cell dendritic spine density in vivo.",
  "pmid": "26211445",
  "pmcid": "PMC4547863",
  "doi": "10.1016/j.neuroscience.2015.07.056"
}
```

Abstract:
Olfactory bulb granule cells (GCs) are axon-less, inhibitory interneurons that regulate the activity of the excitatory output neurons, the mitral and tufted cells, through reciprocal dendrodendritic synapses located on GC spines. These contacts are established in the distal apical dendritic compartment, while GC basal dendrites and more proximal apical segments bear spines that receive glutamatergic inputs from the olfactory cortices. This synaptic connectivity is vital to olfactory circuit function and is remodeled during development, and in response to changes in sensory activity and lifelong GC neurogenesis. Manipulations that alter levels of the neurotrophin brain-derived neurotrophic factor (BDNF) in vivo have significant effects on dendritic spine morphology, maintenance and activity-dependent plasticity for a variety of CNS neurons, yet little is known regarding BDNF effects on bulb GC spine maturation or maintenance. Here we show that, in vivo, sustained bulbar over-expression of BDNF in transgenic mice produces a marked increase in GC spine density that includes an increase in mature spines on their apical dendrites. Morphometric analysis demonstrated that changes in spine density were most notable in the distal and proximal apical domains, indicating that multiple excitatory inputs are potentially modified by BDNF. Our results indicate that increased levels of endogenous BDNF can promote the maturation and/or maintenance of dendritic spines on GCs, suggesting a role for this factor in modulating GC functional connectivity within adult olfactory circuitry.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC4547863.xml
SHA-256: f94c41843257eec8876d12ba1cdf700c0a9daeeb526982002e484cbbc177e03b

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor",
      "dendritic spine"
    ],
    "paragraph_index": 2,
    "text": "Dendritic spines are highly plastic structures, capable of undergoing adaptive morphological and physiological changes, both during development and in adulthood, in response to a wide range of stimuli, such as hormones, growth factors, and in particular, neuronal activity (Calabrese, 2006; Knott and Holtmaat, 2008; Yoshihara et al., 2009; Bosch and Hayashi, 2012; Wyatt et al., 2012). For most CNS neurons, spines contain the postsynaptic elements of excitatory synapses, and changes in spine morphology correlate with their maturation, and with alterations in synaptic efficacy (Matsuzaki et al., 2004; Tada and Sheng, 2006; Yoshihara et al., 2009; Bosch and Hayashi, 2012). Such changes modify and refine synaptic connectivity, and a variety of identified molecular signals have been shown to control these processes. Extensive evidence has demonstrated that brain-derived neurotrophic factor (BDNF) signaling, through its receptor TrkB, regulates spine formation, maturation, pruning, maintenance, and activity-dependent structural and functional plasticity (Luikart and Parada, 2006; Tanaka et al., 2008; Rauskolb et al., 2010; Kaneko et al., 2012; Vigers et al., 2012; Yoshii, 2014). The activity-dependent nature of BDNF expression and secretion makes it ideally suited to meditate the trophic effects of activity on neuronal morphology and plasticity (Gall, 1992; Shieh and Ghosh, 1999; Lessmann and Brigadski, 2009; Kuczewski et al., 2010). Much of what is known about BDNF modulation of dendritic development, spine dynamics, and synapse maturation has emerged from studies of glutamatergi"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "dendritic spine",
      "spine density",
      "spine number"
    ],
    "paragraph_index": 3,
    "text": "BDNF is normally expressed at low levels in the rodent olfactory bulb, localizing to subpopulations of neurons in the glomerular layer and outer EPL, and to scattered cells located within and near the mitral cell layer (MCL)/superficial granule cell layer (GCL), with very low expression throughout the remaining granule cell layer (Hofer et al., 1990; Guthrie and Gall, 1991; Nef et al., 2001; Conner et al., 1997; Clevenger et al., 2008). Higher olfactory regions, including some areas that provide centrifugal afferents to the bulb such as the anterior olfactory nucleus (AON) and piriform cortex, exhibit much higher levels of expression, potentially providing an anterograde source of BDNF for bulb neurons (Guthrie and Gall, 1991). TrkB is expressed by all neuronal populations in the adult olfactory bulb, whereas cellular expression of the low affinity neurotrophin receptor, p75, is limited to ensheathing glia in the olfactory nerve layer (Deckner et al., 1993; Gong et al., 1994). As with other forebrain regions, BDNF expression in the bulb is activity-responsive, with seizure activity upregulating BDNF levels and sensory deprivation reducing them (Katoh-Semba et al., 1999; McLean et al., 2001). BDNF is not required for embryonic bulb development as knockout mice show normal bulb anatomical organization during early neonatal life (Nef et al., 2001). However in those knockout mice that survive out to ~4 weeks, the olfactory bulbs are smaller and parvalbumin (PV)-expressing GABAergic neurons show impaired dendritic development and reductions in PV expression, deficits that can be"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 4,
    "text": "All animal procedures were carried out according to protocols approved by the Florida Atlantic University Institutional Animal Care and Use Committee, in accordance with National Institutes of Health guidelines. TgBDNF mice, maintained on a C57Bl6/J background, were obtained from Jackson Laboratories (strain #006579; Bar Harbor, ME). This strain carries a transgene encoding rat BDNF under control of 8.5 kb of the α-calcium/calmodulin-dependent protein kinase II (CAMKIIα) promoter, in addition to the endogenous BDNF gene (Huang et al., 1999). Postnatal expression of the BDNF transgene follows the developmental pattern of forebrain CAMKIIα expression, beginning near the end of first postnatal week and reaching adult levels by ~1 month of age (Neve and Bear, 1989; Zou et al., 2002). TgBDNF males were mated with WT females to obtain litters composed of transgenic and WT offspring. Genotyping was carried out by PCR amplification of genomic DNA isolated from tail samples using the following the primers for detection of the transgene: 5′-CAAATGTTGCTTGTCTGGTG-3′ and 5′-GTCAGTCGAGTGCACAGTTT-3′. Cycling parameters were as follows: 94°C-30 sec, 55°C-30 sec, 72°C-45 sec (30 cycles). To test for possible progressive effects of cell exposure to increased BDNF over time, brains were collected from young adult mice at 2–3 months of age, and from older mice aged 6–7.5 months."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 5,
    "text": "Young adult males of both genotypes (n=4 each) were euthanized with sodium pentobarbital (150 mg/kg; i.p.) at 2–3 months of age. Following decapitation, brains were rapidly dissected, snap frozen in chilled isopentane (−50°C), and stored at −80°C prior to cryosectioning. Serial sections through the bulbs and forebrain (25μm; 1 in 4) were collected on charged glass slides and were hybridized with 35S-labeled BDNF cRNA as described (Guthrie and Gall, 2003). Alternate sections were stained with neutral red. The 540-base BDNF cRNA contains 384 bases complementary to the coding region of mature BDNF (GenBank sequence NM_012513). Non-specific labeling was assessed using sense RNA generated from the same template. Hybridization was conducted overnight at 65°C with the cRNA at a final concentration of 1 × 107 cpm/ml. Washing was followed by RNase A treatment to remove unbound cRNA. Sections were slide mounted and exposed to Kodak Biomax MR film (3–4 days), with tissue from paired WT and TgBDNF mice exposed on the same sheets. Densitometry was performed with NIH Image 6.2 analysis software (Wayne Rasband, NIH), with slide-mounted radiolabeled autoradiography standards used to calibrate film density (American Radiolabeled Corp., St. Louis, MO). Multiple measures were collected by overlay of adjacent sample boxes positioned around the full circumference of the granule cell layer (GCL) from a minimum of 8 sections per animal (both bulbs), with background density measured in the olfactory nerve layer subtracted from these measures for each section. Section means were used to calculate m"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 6,
    "text": "Mice at 2–3 months of age (4 per genotype; 2 male, 2 female) were euthanized as above, decapitated, and the olfactory bulbs rapidly dissected. Tissue was frozen on dry ice and stored at −80°C. Both olfactory bulbs were homogenized together on ice in Cell Lysis buffer (#9803, Cell Signaling Technology, Danvers, MA) to which 1mg/ml complete protease inhibitors and 1 mg/ml complete phosphatase inhibitors (Roche Applied Biosystems) were added. Lysates were centrifuged at 14,000 rpm for 20 min at 4°C and supernatants were collected and assayed for protein content by Qubit assay (Invitrogen, Carlsbad, CA). Aliquots were stored at −80°C, prior to performing ELISA assays or Western blotting. ELISA plates were treated overnight with monoclonal antibody to BDNF, according to the manufacturer’s instructions for the BDNF Emax immunoassay system (Promega, Madison, WI, USA). Supernatants were thawed and diluted 1:3 in Dulbecco’s phosphate-buffered saline. Samples were acidified by adding 2 μl of 1N HCl per 100μl solution, and were incubated for 20 min at room temperature (RT). The pH was normalized by then adding 2μl of 1N NaOH per 100μl of sample. Duplicate samples (150 μg protein/well) incubated overnight at 4°C, and were assayed for total BDNF protein content (pro- and mature BDNF), according to the Emax kit instructions. A standard curve was generated for each assay using serial dilutions of recombinant BDNF peptide provided in the kit. Following color development, absorbance was measured at 450nm using a SpectraMax M5 plate reader (Molecular Devices, Sunnyvale, CA), and BDNF concent"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF"
    ],
    "paragraph_index": 7,
    "text": "Olfactory bulb lysates prepared from tissue samples (as above) were thawed, diluted in Laemmli buffer and denatured at 95°C for 5 min. Protein was separated by 12% SDS-PAGE (BioRad TGX gels). Control lanes for BDNF blots included 5 ng of human recombinant mature BDNF peptide (PeproTech, Rocky Hill, NJ). Proteins were transferred to PVDF membranes (0.45μm) and blocked Odyssey blocking buffer (Li-Cor Biosciences, Lincoln, NE) for 1 hr at RT. Purified polyclonal rabbit IgG antibody to BDNF was from Santa Cruz Biotech (Santa Cruz, CA; Cat# sc-546.) It was generated using mature, human BDNF as antigen (amino acid residues 128-147: RHSDPARRGELSVCDSISEW; manufacturer’s data), and does not cross-react with other members of the neurotrophin family. It detects mature BDNF at ~14 kDa on immunoblots of hippocampal lysates from normal mice, while this band is absent on blots of hippocampal lysates prepared from BDNF knockout mice (Matsumoto et al., 2008). Mouse monoclonal anti-actin antibody was obtained from Cell Signaling Technologies (Danvers, MA, #3700). It was generated against a synthetic peptide corresponding to amino-terminal residues of human β-actin, and detects a single band of ~42–43 kDa molecular mass in immunoblots of COS and HeLa cells (manufacturer’s data). BDNF antibody (1:200) and actin antibody (1:1000) were diluted together in Odyssey blocker, with 0.2% Tween 20 added. Membrane incubation was carried out at 4°C for 2 nights. After rinsing in Tris-buffered saline (TBS; 50 mM Tris-HCl, 150 mM NaCl, pH 8.2), containing 0.1% Tween-20 (TBST), membranes incubated in a cock"
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

### Packet heldout_rrpv1_0060

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
  "title": "Electroconvulsive seizures influence dendritic spine morphology and BDNF expression in a neuroendocrine model of depression.",
  "pmid": "29674117",
  "pmcid": "PMC6245665",
  "doi": "10.1016/j.brs.2018.04.003"
}
```

Abstract:
Electroconvulsive therapy (ECT) is a rapid and effective treatment for major depressive disorder. Chronic stress-induced depression causes dendrite atrophy and deficiencies in brain-derived neurotrophic factor (BDNF), which are reversed by anti-depressant drugs. Electroconvulsive seizures (ECS), an animal model of ECT, robustly increase BDNF expression and stimulate dendritic outgrowth.
The present study aims to understand cellular and molecular plasticity mechanisms contributing to the efficacy of ECS following chronic stress-induced depression.
We quantify Bdnf transcript levels and dendritic spine density and morphology on cortical pyramidal neurons in mice exposed to vehicle or corticosterone and receiving either Sham or ECS treatment.
ECS rescues corticosterone-induced defects in spine morphology and elevates Bdnf exon 1 and exon 4-containing transcripts in cortex.
Dendritic spine remodeling and induction of activity-induced BDNF in the cortex represent important cellular and molecular plasticity mechanisms underlying the efficacy of ECS for treatment of chronic stress-induced depression.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC6245665.xml
SHA-256: dd6ac0fef8582abb3c8c45e26bf5d5bcd3cb19df5e24164680b7136d76b0112c

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "spine density"
    ],
    "paragraph_index": 1,
    "text": "Electroconvulsive therapy (ECT) is one of the most rapid and effective treatments for major depressive disorder (1, 2) and is associated with normalization of hypothalamic-pituitary-adrenal (HPA) axis abnormalities (3, 4). In rodent models, elevated glucocorticoids resulting from HPA axis dysregulation during stress cause dendritic atrophy and decreased spine density in the hippocampus and cortex (5–10), which can be reversed with anti-depressant drugs (11–13). This reorganization of morphology is associated with improved behavioral outcomes (14). While ECS can also prevent stress-induced dendrite retraction in the hippocampus (15, 16), its effects on cortical neurons, which are key players in mediating the antidepressant response (17), has not yet been determined."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "brain-derived neurotrophic factor",
      "dendritic spine",
      "spine density"
    ],
    "paragraph_index": 2,
    "text": "Successful ECT treatment is linked to increases in the activity-dependent neurotrophin, brain-derived neurotrophic factor (BDNF) (18–21), which is a robust modulator of neuronal morphology, especially dendritic spine density and structure (22–24). Indeed, a large body of literature suggests that BDNF and glucocorticoid activities are calibrated such that BDNF levels influence susceptibility and recovery from chronic stress-induced depression (25, 26). Furthermore, a genetic variation G196A (Val66Met polymorphism) that alters levels of activity-dependent BDNF (27) may influence responsiveness to ECT and cognitive outcome (28), further suggesting that BDNF may be a potential biomarker for ECT efficacy. Importantly, Bdnf has a unique genomic structure with nine promoters that drive expression of multiple transcripts encoding an identical protein (29, 30). Methylation studies suggest that patients remitting under ECT have lower methylation at specific Bdnf promoters (31)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "dendritic spine"
    ],
    "paragraph_index": 3,
    "text": "Here we investigate the ability of ECS to remodel cortical dendritic spines and induce activity-dependent BDNF from specific promoters in a neuroendocrine model of depression. This model employs chronic administration of corticosterone (Cort) in the drinking water, which recapitulates the HPA axis dysfunction and dendritic atrophy observed in chronic stress-induced depression (14, 32–34)."
  },
  {
    "matched_frozen_surfaces": [
      "dendritic spine",
      "spine number"
    ],
    "paragraph_index": 5,
    "text": "Animals were anesthetized with isoflurane and perfused transcardially with 4% paraformaldehyde (PFA) in phosphate-buffered saline. Brains were extracted, post-fixed in 4% PFA, cryoprotected in 30% sucrose, cut coronally at 50μm on a microtome, and stained in 0.05% Sudan Black (Sigma) to decrease autofluorescence. Isolated oblique apical dendrites (between 100 and 400um from the cell body) on layer 5 cortical neurons in somatosensory cortex were imaged on a Zeiss LSM 510 confocal microscope according to previously described criteria with experimenter blinded to genotype (23). Dendritic spine structure was reconstructed using Neurolucida (MicroBrightField Biosciences). Spine number, width, and height were quantified and statistically analyzed in GraphPad Prism using one- or two-way ANOVA and Bonferroni post hoc tests where appropriate (*p<0.05, **p<0.01, ***p<0.001, #p<0.0001)."
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "spine density"
    ],
    "paragraph_index": 7,
    "text": "To investigate cellular plasticity associated with the anti-depressant response mediated by ECS, we quantified spine density and morphology on cortical pyramidal neurons of mice treated with vehicle or Cort and receiving either Sham or ECS treatment (Fig. 1A). Cort significantly reduced spine density, which was not effectively rescued by ECS (one-way ANOVA, F2, 189 = 6.829, p=0.0014, Fig. 1B and 1C). We next measured both the height and width of spine heads on cortical oblique apical dendritic branches, and spines were classified by size and binned to generate frequency histograms depicting the percentage of differently sized spine populations along a defined branch (37). Cort-Sham branches showed a significant increase in the percentage of shorter spines (<0.5μm) compared to Veh-Sham branches, which was reversed following ECS (two-way ANOVA, treatment x bin interaction, F8, 945 = 8.302, p<0.0001, Fig. 1D). Similarly, Cort-Sham branches showed a significant increase in the percentage of smaller spine heads (0.4 – 0.6μm in diameter) compared to Veh-Sham branches, which was rescued following ECS (two-way ANOVA, treatment x bin interaction, F8, 945 = 3.277, p=0.0011, Fig. 1E). To investigate molecular pathways potentially contributing to this plasticity, we examined expression of Bdnf transcripts derived from promoters I, II, IV and VI (Bdnf exon 1, 2, 4, and 6-containing transcripts, respectively; Fig. 1F) using qPCR. While Cort exposure did not alter expression of distinct Bdnf transcripts, ECS treatment significantly elevated Bdnf exon 1 and 4-containing transcripts in cing"
  },
  {
    "matched_frozen_surfaces": [
      "BDNF",
      "dendritic spine",
      "spine density"
    ],
    "paragraph_index": 8,
    "text": "In the present study, we demonstrate that ECS reverses glucocorticoid-induced defects in spine morphology on cortical pyramidal neurons and augments BDNF expression. Extensive work has linked spine size and shape to synapse stability and function where larger spine heads represent more mature spines likely to contain postsynaptic densities and glutamate receptors (38, 39). Chronic stress and glucocorticoid administration has been shown to impair spine density and morphology with detectable effects after 10 to 21 days (40, 41). Previous studies show that ECS is able to prevent dendritic atrophy in the hippocampus following chronic stress (15, 16); however, these studies did not explore other brain regions associated with the anti-depressant response, including the cerebral cortex (17). Furthermore, the impact of ECS on dendritic spine morphology and BDNF levels was not investigated. Here we provide evidence that remodeling of cortical dendritic spines and induction of Bdnf from promoters I and IV, which are highly regulated by neural activity (29), may represent critical plasticity mechanisms underlying the anti-depressant efficacy of ECS."
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

### Packet heldout_rrpv1_0069

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
  "title": "Oxidative eustress is associated with AMPK and AKT activation, GLUT4 translocation and glucose uptake in skeletal muscle cells and fibres.",
  "pmid": "42693074",
  "pmcid": "PMC13543825",
  "doi": "10.1080/13510002.2026.2721882"
}
```

Abstract:
Objectives: Reactive oxygen and nitrogen species (RONS) act as signalling molecules under physiological conditions; however, how oxidative eustress regulates glucose uptake in skeletal muscle remains poorly defined. We investigated the role of moderate oxidation in skeletal muscle glucose uptake, focusing on AKT/AMPK phosphorylation, GLUT4 translocation and functional glucose uptake. Methods: AKT and AMPK phosphorylation were analysed in C2C12 myoblasts/myotubes exposed to insulin and redox-modulating stimuli associated with oxidative eustress, including hydrogen peroxide, nitric oxide donors and angiotensin II. GLUT4 translocation was assessed by quantitative immunocytochemistry and confocal fluorescence microscopy in cells expressing a GLUT4 reporter. Glucose uptake was evaluated in isolated skeletal muscle fibres using 6-NBDG. Results: Oxidative eustress was associated with increased AKT and AMPK phosphorylation and enhanced GLUT4 translocation to the plasma membrane. Hydrogen peroxide, nitric oxide donors and angiotensin II increased GLUT4 presence at the plasma membrane and enhanced glucose uptake, with hydrogen peroxide showing a dose-dependent effect. Increased glucose uptake was consistent with GLUT4 translocation. Discussion: These findings support oxidative eustress as a physiological redox mechanism linking AKT/AMPK activation, GLUT4 translocation and glucose uptake in skeletal muscle. Redox signalling may therefore contribute to skeletal muscle glucose metabolism.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC13543825.xml
SHA-256: 700b5679988e45645e595b2c45fb372e3860385b1551cf0b8d85ad522e64e125

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 4,
    "text": "Redox signalling has been increasingly recognised as a crucial regulator of cellular metabolism, including glucose handling and energy homoeostasis. Accumulating evidence indicates that RONS participate in the regulation of glucose uptake and insulin signalling, acting either as facilitators of physiological responses or as contributors to metabolic dysfunction when present at excessive levels [12–14]. In this context, oxidative eustress has been proposed as a mechanism by which moderate RONS levels enhance metabolic flexibility and adaptive responses, whereas redox imbalance and oxidative distress are associated with insulin resistance, ageing and metabolic disease [15]. However, how defined redox signals regulate GLUT4 translocation and functional glucose uptake in skeletal muscle remains incompletely understood."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "Glucose is a fundamental substrate for cellular metabolism, and skeletal muscle plays a central role in whole-body glucose disposal and glycaemic control. As glucose cannot freely diffuse across the plasma membrane, its uptake requires glucose transporters (GLUTs), with GLUT4 being the predominant isoform expressed in skeletal muscle [16]. The translocation of GLUT4 from intracellular compartments to the plasma membrane is therefore essential for the maintenance of glucose homoeostasis. Both insulin and contractile activity stimulate glucose uptake by promoting GLUT4 translocation; however, the signalling mechanisms governing this process remain incompletely defined [15,17,18]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "glucose uptake"
    ],
    "paragraph_index": 6,
    "text": "During dynamic exercise, glucose uptake by skeletal muscle can increase up to fifty-fold relative to basal levels. This response depends on glucose availability, membrane transport and intracellular metabolism, and is regulated by local factors such as reactive oxygen and nitrogen species, nitric oxide, calcium (Ca2+), calmodulin-dependent kinases (CaMK) and AMP-activated protein kinase (AMPK) [19–22]. Insulin similarly promotes GLUT4 translocation, and accumulating evidence indicates that signalling pathways regulated by RONS also participate in this process. However, the specific contribution of oxidative eustress to GLUT4 translocation and functional glucose uptake in skeletal muscle remains to be fully elucidated."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 7,
    "text": "In this context, hydrogen peroxide generation in skeletal muscle has been directly associated with increased glucose uptake in isolated preparations, and H₂O₂ appears to stimulate glucose transport through mechanisms that only partially overlap with canonical insulin signalling pathways [4,21,23]. Thus, ROS, particularly H₂O₂, together with RNS such as NO, emerge as important regulators of glucose transport during exercise and contractile activity. Our recent work and that of others support the concept that moderate levels of RONS, defined as oxidative eustress, may activate key signalling pathways such as AKT and AMPK, thereby promoting GLUT4 translocation and facilitating glucose uptake [15,21,22,24]."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 9,
    "text": "Despite the increasing recognition of reactive oxygen and nitrogen species as key modulators of cellular signalling, important gaps remain in our understanding of how redox signalling regulates glucose uptake in skeletal muscle under physiological conditions. Although hydrogen peroxide and nitric oxide have been implicated in the control of glucose transport, the specific signalling pathways involved, the degree of oxidation required to elicit a physiological response, and the relationship between redox signalling, GLUT4 translocation and functional glucose uptake remain incompletely defined [16]."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "glucose uptake"
    ],
    "paragraph_index": 10,
    "text": "Based on current evidence and our previous findings, we hypothesised that moderate levels of reactive oxygen and nitrogen species, specifically hydrogen peroxide and nitric oxide, acting within an oxidative eustress range, facilitate glucose uptake in skeletal muscle. We further proposed that this effect is associated with the activation of redox-sensitive signalling pathways, including AKT and AMPK, and with increased translocation of GLUT4 to the plasma membrane."
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

### Packet heldout_rrpv1_0070

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
  "title": "Defining the contribution of AMP-activated protein kinase (AMPK) and protein kinase C (PKC) in regulation of glucose uptake by metformin in skeletal muscle cells.",
  "pmid": "22511782",
  "pmcid": "PMC3370192",
  "doi": "10.1074/jbc.M111.330746"
}
```

Abstract:
The importance of AMP-activated protein kinase (AMPK) and protein kinase C (PKC) as effectors of metformin (Met) action on glucose uptake (GU) in skeletal muscle cells was investigated. GU in L6 myotubes was stimulated 2-fold following 16 h of Met treatment and acutely enhanced by insulin in an additive fashion. Insulin-stimulated GU was sensitive to PI3K inhibition, whereas that induced by Met was not. Met and its related biguanide, phenformin, stimulated AMPK activation/phosphorylation to a level comparable with that induced by the AMPK activator, 5-amino-1-β-d-ribofuranosyl-imidazole-4-carboxamide (AICAR). However, the increase in GU elicited by AICAR was significantly lower than that induced by either biguanide. Expression of a constitutively active AMPK mimicked the effects of AICAR on GU, whereas a dominant interfering AMPK or shRNA silencing of AMPK prevented AICAR-stimulated GU and Met-induced AMPK signaling but only repressed biguanide-stimulated GU by ∼20%. Consistent with this, analysis of GU in muscle cells from α1(-/-)/α2(-/-) AMPK-deficient mice revealed a significant retention of Met-stimulated GU, being reduced by ∼35% compared with that of wild type cells. Atypical PKCs (aPKCs) have been implicated in Met-stimulated GU, and in line with this, Met and phenformin induced activation/phosphorylation of aPKC in L6 myotubes. However, although cellular depletion of aPKC (>90%) led to loss in biguanide-induced aPKC phosphorylation, it had no effect on Met-stimulated GU, whereas inhibitors targeting novel/conventional PKCs caused a significant reduction in biguanide-induced GU. Our findings indicate that although Met activates AMPK, a significant component of Met-stimulated GU in muscle cells is mediated via an AMPK-independent mechanism that involves novel/conventional PKCs.

Frozen fulltext provenance:
runs/20260909_search_plan_v22_heldout_v1_network_retrieval/retrieval_assets/fulltext/PMC3370192.xml
SHA-256: efed8ffef11c82500168e9670d90b88938d6c85f617239922132224bc582b327

Frozen fulltext excerpts:
```json
[
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMP-activated protein kinase",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 1,
    "text": "Metformin and phenformin are biguanides that exhibit potent antihyperglycemic and insulin-sensitizing properties. Their ability to regulate blood glucose has largely been attributed to a suppression of hepatic gluconeogenesis and increased glucose uptake in peripheral tissues such as skeletal muscle (1–3). The mechanism underpinning their action in skeletal muscle still remains unclear, although a number of studies have suggested they may act to stimulate glucose uptake independently of insulin (4, 5) or may potentiate insulin-stimulated glucose uptake (6), possibly via effects on insulin binding or proximal components of the insulin signaling cascade (7–9). However, the ability of metformin to enhance insulin binding may be secondary to the effects that the drug has on glucose metabolism, which precede changes in insulin binding by ∼18 h (10). One potential candidate that may mediate the effects of biguanides on glucose utilization in muscle cells is the AMP-activated protein kinase (AMPK),4 widely regarded as a cellular “energy sensor” (11). Work by Halestrap and co-workers and Leverve and co-workers (12, 13) revealed that metformin and phenformin are both capable of inhibiting Complex I of the mitochondrial respiratory chain, which would be expected to reduce the cellular energy status and thereby promote AMPK activation. Inhibition of Complex I may also help explain the propensity of these drugs to promote lactic acidosis, an adverse complication that was particularly associated with phenformin therapy that led to its clinical withdrawal in the 1970s. However, although "
  },
  {
    "matched_frozen_surfaces": [
      "AMPK",
      "AMPK activation",
      "glucose uptake"
    ],
    "paragraph_index": 2,
    "text": "AMPK activation in skeletal muscle has been shown to promote an increase in glucose uptake via enhanced expression and translocation of GLUT4 (14–16), whereas in other cell types AMPK activation has been linked to a suppression in gluconeogenic gene expression (17) and hepatic glucose production (18), although this view has recently been challenged (19). The proposition that AMPK may function as a metformin effector is supported by work showing that AMPK phosphorylation (activation) is enhanced in skeletal muscle of type 2 diabetics following a sustained (10 weeks) period of metformin therapy and that this is associated with a reduction in intramuscular ATP (20). The observed loss in muscle ATP is most likely a consequence of the effect that the biguanide has upon mitochondrial oxidation given that recent in vitro work has demonstrated that metformin induces a substantial reduction in cellular oxygen utilization (21), consistent with the inhibitory effect the drug has on Complex I. In addition to a reduction in ATP production, reduced cellular respiration has also been proposed to trigger an increase in mitochondrial reactive nitrogen species that may subsequently promote AMPK activation via a Src/PI3K-dependent mechanism (22). If so, activation of PI3K may promote increased signaling by molecules such as protein kinase B (PKB), which lie downstream of PI3K and have been implicated strongly in the regulation of glucose transport and metabolism (23, 24). Indeed, the finding that metformin induces PKB/Akt phosphorylation in rat cardiomyocytes supports such a possibility (25)."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 3,
    "text": "α-Minimal essential medium, fetal bovine serum (FBS), and antibiotic/antimycotic solution were from Invitrogen. All other reagent-grade chemicals, insulin, phenformin hydrochloride, 1,1-dimethylbiguanide hydrochloride (metformin), AICAR, d-sorbitol, and 2,4-dinitrophenol were obtained from Sigma. Ro 31.8220, Gö6983, and Gö6976 were from Calbiochem. Wortmannin and LY294002 were obtained from Tocris (Bristol, UK). Antibody against the p85 subunit of PI3K and IRS-1 was purchased from Upstate Biotechnology. Antibodies against PKBα, phospho-PKB Ser473, phospho-GSK3α/βSer-9/21, GSK3, atypical phospho-PKCλζThr-410, AMPKα (recognizing the N-terminal domain of both α1 and α2), phospho-AMPK Thr172, phosphotyrosine, horseradish peroxidase-conjugated anti-rabbit IgG, and anti-mouse IgG were from New England Biolabs (Herts, UK). Horseradish peroxidase-conjugated anti-sheep/goat IgG was obtained from Pierce. Antibodies against PKCλ/ζ were from Santa Cruz Biotechnology (Wiltshire, UK). Antibody against phospho-acetyl-CoA carboxylase Ser79/221 was produced by the Division of Signal Transduction and Therapy (University of Dundee, Scotland, UK). Antibodies targeted against the C-terminal epitope of AMPKα1 and -α2 were a gift from Professor Grahame Hardie (University of Dundee). Protein A-Sepharose beads were purchased from Amersham Biosciences. Complete protein phosphatase inhibitor tablets were purchased from Roche Diagnostics."
  },
  {
    "matched_frozen_surfaces": [
      "glucose uptake"
    ],
    "paragraph_index": 5,
    "text": "L6 myotubes were exposed to metformin, phenformin, insulin, and AICAR for times and at concentrations indicated in the figure legends and were serum-starved 2 h prior to assaying glucose uptake. Cells were washed three times with HBS (140 mm NaCl, 20 mm HEPES, 5 mm KCl, 2.5 mm MgSO4, 1 mm CaCl2, pH 7.4). Glucose uptake was assayed by incubation of 2-deoxy-d-[3H]glucose (1 μCi/ml, 26.2 Ci/mmol) for 10 min as described previously (28, 30). Nonspecific binding was determined by quantitating cell-associated radioactivity in the presence of 10 μm cytochalasin B. Radioactive medium was aspirated prior to washing adherent cells three times with 0.9% ice-cold saline. Cells were subsequently lysed in 50 mm NaOH, and radioactivity was quantitated using a Beckman LS 6000IC scintillation counter. Protein concentration in cell lysates was determined using the Bradford method (31)."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 6,
    "text": "Following treatment with insulin or biguanides, L6 myotubes were lysed as described above. IRS-1 was immunoprecipitated using an antibody against the C-terminal domain of IRS-1. Immunocomplexes were captured by incubation with protein-A-Sepharose beads and solubilized in Laemmli sample buffer prior to immunoblotting. For analysis of AMPK activity, protein G-Sepharose beads were washed three times in PBS and incubated with anti-AMPKα1/α2 for 1 h at 4 °C on an orbital platform shaker. Bead/antibody mixture was then incubated with 500 μg of L6 cell lysate protein for 2 h at 4 °C before washing. The immunoprecipitates were washed twice with 1 ml of lysis buffer containing 0.5 m NaCl and twice with HEPES assay buffer (50 mm Na-HEPES, pH 7.0, 1 mm DTT, 0.02% Brij-35). AMPK activity toward SAMS peptide (HMRSAMSGLHVKRR) was measured as described previously (32)."
  },
  {
    "matched_frozen_surfaces": [
      "AMPK"
    ],
    "paragraph_index": 7,
    "text": "50 μg of cell lysate protein was subjected to SDS-PAGE on a 10% resolving gel as described previously (28). Separated proteins were transferred onto polyvinylidene fluoride (PVDF) membranes, which were subsequently blocked using Tris-buffered saline (TBS) containing 0.1% (v/v) Tween 20 and 5% (w/v) milk. Membranes were probed with antibodies against PKB, phospho-PKB Ser473, phospho-GSK-3α/β, IRS-1, p85-PI3K, phosphotyrosine, PKCλ/ζ, PKCλ/ζ Thr410, N-terminal AMPKα, phospho-AMPK Thr172, phospho-acetyl-CoA carboxylase Ser79/221, and a composite mixture of antibodies against the C-terminal domains of AMPKα1 and AMPKα2. The membranes were washed three times in TBS, 0.1% (v/v) Tween 20 for 15 min prior to incubation with horseradish peroxidase (HRP), anti-rabbit IgG, HRP anti-mouse IgG, or HRP anti-sheep/goat IgG as deemed appropriate. Protein bands on PVDF were visualized using enhanced chemiluminescence (Pierce) by exposure to Konica Medical Film (Konica Corp., Hohenbrunn, Germany)."
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
