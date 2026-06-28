# Pharmacological Polarity Schema

Simple positive/negative signs are insufficient for biomedical claims. The
progressive L1 path records three independent fields:

- `relation_family`: drug target, gene expression, pathway activity, protein
  interaction, phenotype, clinical outcome, adverse event, or association.
- `polarity_type`: mechanistic, expression, pathway, phenotypic, clinical,
  safety, association, or unknown.
- `direction`: activate, inhibit, increase, decrease, bind, improve, worsen,
  no effect, mixed, associated, or unknown.

English and Chinese directional terms are normalized deterministically. An
unrecognized direction remains `unknown` and is excluded from primary entropy.
Mechanistic inhibition describes target/pathway direction and does not imply
therapeutic harm. For example, target inhibition and improvement of a phenotype
belong to different polarity groups and are never combined into one entropy
distribution.

The historical `relation_sign` remains only as a compatibility projection for
legacy L1.5/L2 consumers; new screening and confirmation use the structured
polarity fields.
