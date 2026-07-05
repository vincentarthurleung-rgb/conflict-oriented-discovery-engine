# System B Display KG v2

Display KG v2 is a bounded, UI-ready projection of the complete clean KG. It adds low-risk display-label normalization, exact generic-term downranking, high-degree unknown review, UI metadata, and separate global and per-case ranking. It does not remove records from the complete KG or change scientific classification.

Numeric parenthetical suffixes and selected Greek symbols are normalized only for `display_label`; original labels remain aliases. Meaningful parentheses are preserved. Unknown abbreviations are reviewed rather than automatically promoted to gene or protein types.

Default limits are 500 entities, 500 triples, 1,500 chains, 150 triples per case, and 300 chains per case. The CLI exposes all limits. Scores are navigation heuristics and must not be interpreted as biological confidence.
