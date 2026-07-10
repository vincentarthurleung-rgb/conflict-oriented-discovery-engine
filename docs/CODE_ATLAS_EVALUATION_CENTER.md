# C.O.D.E. Atlas Evaluation Center

Metrics are computed by System B, not hand-entered. Missing Gold or missing predictions return explicit statuses such as `needs_adjudication` or `needs_annotation`; they are not shown as zero.

The first implemented metric engine covers precision, recall, F1, accuracy, specificity, macro/micro/weighted F1, and Cohen's Kappa. Formal paper metrics must read frozen production Gold only. Draft, pilot, calibration, and test annotations are isolated from production results.

The planned paper export root is:

```text
system_b_outputs/evaluation/<project_id>/
```
