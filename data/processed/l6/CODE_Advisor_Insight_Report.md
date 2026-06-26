# C.O.D.E. Layer 8: Ranked Candidate Intervention Report
**Pipeline Base Version**: v4.0-alpha | **Report Export**: deterministic markdown renderer

> Validation statuses reflect validator coverage. Curated omics support is not full LINCS validation.

---

### Rank 1: H_Track_Full_001
* **Core causal seed pair**: `KETAMINE -> ANTIDEPRESSANT RESPONSE`
* **Anchor gene**: **GRIA1** (`omics_anchor_gene`)
* **Ranking score**: `1.5354`
* **Validation status**: `Sign_Consistent_Under_Curated_Index`
* **Validation score**: `0.75`

#### Separating Contexts
* `treatment_duration`: ['ACUTE_PHASE'] (unresolved)
* `oxygen_condition`: ['NORMOXIA', 'HYPOXIA'] (unresolved)

#### Legacy Context Compatibility
> ` CHRONIC_PHASE, NORMOXIA, HYPOXIA `

#### Evidence Traceability
| Evidence ID | Source / DOI | Polarity | Evidence Sentence |
| :--- | :--- | :--- | :--- |
| `a9a9886ef027` | *PMC3572668* (10.3109/03009734.2012.724118) | Positive (+1) | "However, a large number of studies have shown that a single acute administration of a sub-anesthetic dose of ketamine, an ionotropic glutamatergic N-methyl-D-aspartate receptor (NMDAR) antagonist, produces a fast-acting and robust antidepressant effect both in patients suffering major depressive disorders (MDD) and in animal models of depression (1,2)." |
| `a8a1538a96db` | *PMC3747027* (10.2147/NDT.S36689) | Positive (+1) | "These findings were also extended to BPD; ketamine added to a mood stabilizer exerted a rapid antidepressant effect in BPD patients who were in a refractory depressive episode at the time of randomization." |
| `1895ea74ca56` | *PMC3894182* (10.1371/journal.pone.0083879) | Negative (-1) | "the direct infusion of ketamine into the mPFC is not sufficient to produce anti-depressant response in rats" |
| `ed3b58e8e9d7` | *PMC3905222* (10.1038/tp.2013.112) | Positive (+1) | "Ketamine has also been reported to induce an antidepressant response in rodents: a decrease in immobility time during the forced swim test." |
| `491406a9a635` | *PMC4153858* (10.9758/cpn.2014.12.2.124) | Positive (+1) | "In this study, we found that neonatal DEX exposure (days 1-3) caused depression-like behavior (i.e., decreased preference for consumption of 1% sucrose and increased immobility times in the TST and FST) in juvenile mice and that a single dose of ketamine produced a long-lasting antidepressant effect in these affected animals." |
| `39a6210c6c01` | *PMC4153858* (10.9758/cpn.2014.12.2.124) | Positive (+1) | "we found that a single dose of ketamine produced a long-lasting antidepressant effect in these affected animals." |
| `ba6ffb1105ed` | *PMC4243034* (10.2174/1570159X12666140619204251) | Positive (+1) | "Based on most of the included studies, ketamine was found to exert a rapid and sustained antidepressant effect on samples of TRD patients." |
| `62aab95bdccc` | *PMC4249453* (10.3389/fnmol.2014.00094) | Positive (+1) | "The juvenile mice were treated with 3.0 mg/kg ketamine (i.p.), a dose that triggers a rapid antidepressant response in young adult (6–8 week old) mice (Autry et al., 2011; Nosyreva et al., 2013) and examined 30 min later in the NSF test." |
| `c05cacd08839` | *PMC4249453* (10.3389/fnmol.2014.00094) | Negative (-1) | "We found no difference between the ketamine and vehicle treated mice in the latency to consume the food pellet in the juvenile mice suggesting that ketamine did not trigger an antidepressant response (Figure 1A)." |
| `97e971c41ad6` | *PMC4368871* (10.1093/ijnp/pyu033) | Positive (+1) | "Recent clinical studies demonstrate that a single, low dose of ketamine, an N-methyl-D-asparate (NMDA) receptor antagonist, produces a rapid and long-lasting antidepressant response in treatment-resistant patients (Berman et al., 2000; Zarate et al., 2006; Price et al., 2009)." |
| `35fbef98b435` | *PMC4445748* (10.1038/tp.2015.10) | Positive (+1) | "Ketamine results in an antidepressant response within one day of a single intravenous infusion,4, 5, 6, 8, 9 but few studies to date have investigated changes in neurocircuitry following ketamine administration in patients with depression." |
| `58e19d4785aa` | *PMC4758914* (10.1038/mp.2015.83) | Positive (+1) | "A single subanesthetic dose of ketamine, a glutamate N-methyl-D-aspartate (NMDA) receptor antagonist, based on two meta-analyses3, 4 of ketamine’s antidepressant effect in randomized placebo-controlled trials (10 trials and 246 patients total; 6 trials and 163 patients overlapped; 34 patients had bipolar disorder), produces an antidepressant effect in hours to days with standardized mean differences of −0.91 and 0.9." |

#### Ranking Components
* Complexity: `1.0`
* Consistency: `0.8567`
* Identifiability: `1.0`

#### Suggested Experiment Blueprint
* **Paradigm**: `Gain-of-function / positive perturbation assay`
* **Design**: Overexpression or positive perturbation design targeting GRIA1.
* **Guideline**: Measure downstream synaptic or transcriptional response with matched controls.

#### Validation Limitations
* Curated/demo omics index; not full LINCS validation.

#### Confidence Interval
* Objective loss interval: `[-0.3305 , -0.3266]`

---

