# Source quote localization whitespace V1

This Owner-scoped engineering contract permits deterministic localization only.
It grants no Quality PASS, scientific validity, V3/Core eligibility or authority.

The existing exact localizer remains unchanged. Legacy callers without an
explicit source-bound context remain exact-only. With this V1 context, the source
file must match its frozen raw-byte SHA256, and every Construction BODY paragraph
must map byte-for-byte back to its original ArticleJSON region. Matching is
restricted to explicitly authorized existing BODY anchor identities.

1. Prefer a unique exact UTF8-identical source substring in authorized BODY.
   Multiple exact authorized locations fail; never pick the first.
2. Only after no exact authorized span exists, substitute U+00A0 with U+0020
   in comparison views (one codepoint for one codepoint, in either direction).
   Source and model originals remain unchanged. Do not collapse whitespace.
3. Only trailing U+0020 SPACE in the raw model quote may be omitted for search.
   Tabs, CR, LF and other Unicode whitespace are not boundary-normalized. No
   leading or internal content is inserted/deleted. A source span is the minimal
   original substring matching the quote core; adjacent source spaces remain
   outside that span. Exact matching can naturally omit adjacent source suffixes.
4. Require exactly one permissible span wholly inside one authorized paragraph;
   zero or multiple locations fail closed. Character offsets are directly
   recoverable because the comparison substitution preserves length.

No normalization of numbers, decimal points, units, Greek letters, operators,
minus signs, dashes, entity names, words, statistical values or punctuation is
performed. No NFKC, edit distance, semantic similarity or model adjudication.

Every accepted record separates raw_model_quote/hash from original_source_text/
hash and records policy version, exact_match_boolean, permitted operations,
original source/BODY coordinates, original anchor identity and localization
status. Fallback status is PERMITTED_WHITESPACE_EQUIVALENT, never verbatim exact.

Quality rendering uses the recovered original source substring in its evidence
packet. It preserves the original model response, raw candidate payload/hash,
candidate ID, scientific fields and candidate cardinality. The rendering manifest
retains the source-bound context and full localization audit. No uncertain or
failed localization is passed downstream with null coordinates. The existing
Quality-to-claim bridge recomputes the same policy and checks the exact audit and
evidence payload before consuming any future real Quality response.

Failures include SOURCE_QUOTE_NOT_FOUND, SOURCE_QUOTE_AMBIGUOUS,
SOURCE_QUOTE_OUTSIDE_AUTHORIZED_BODY and SOURCE_ANCHOR_INTEGRITY_FAILURE.
SOURCE_QUOTE_DISALLOWED_DIFFERENCE protects any comparison invariant violation;
substantive unmatched text normally reports NOT_FOUND, without fuzzy guessing
which scientific field was changed.

This contract is separately versioned; historical prompts, source files,
responses, frozen manifests, terminal failures and provider caches are immutable.
