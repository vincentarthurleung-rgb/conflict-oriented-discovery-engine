# AI-first scientific review: offline workflow

The owner authorizes development AI review without human signatures. Formal
independent review remains a separate future decision. Existing production
scientific authorization, canonical identity and Strict Core gates still apply.

1. Pin an authentic evidence packet, original local article, exact evidence spans,
   prompt version/bytes and existing V3/Core record where available.
2. An AI assistant explicitly assesses all nine fields and source-bound candidate
   facets. Preserve partial support, uncertainty and unsupported statements. An
   interactive review sharing extraction context is never independent; record the
   exposed model identity accurately and leave an unavailable exact ID null.
3. Save the review as `AIReview` JSON. There is no global PASS, network inference
   or automatic annotation of a fresh input. A missing review stops ingestion.
4. Run `tools/run_ai_scientific_review_shadow.py --packet LEFT RIGHT --review
   LEFT_REVIEW RIGHT_REVIEW --core LEFT_CORE RIGHT_CORE --prompt PROMPT
   --output-root NEW_DEVELOPMENT_RUN`. Omit `--core` only for evidence packets
   without V3/Core reconstructions; that absence stays explicit.
5. Inspect append-only `shadow/<content-hash>.json` artifacts and returned
   receipts. The existing weak comparison is a diagnostic, not production
   Candidate Qualification. Context differences are candidate modifiers, not
   established explanations. Non-increase and non-significance are not negative
   directions. Hypotheses require adequately supported provisional opposition;
   concordant and insufficiently comparable inputs legitimately yield zero.

All scientific outputs use namespace `seen_development_shadow`, label
`AI_PROVISIONAL_NOT_INDEPENDENTLY_VALIDATED`, and four false formal authority
flags. No Atlas account, assignment, annotation or Gold record is created. Atlas
canonical serialization conventions are reused for provenance hashes. Formal
handoff/import and the direct core gate reject explicit shadow provenance,
including wrapped artifacts. There is no shadow-to-formal promotion command.

For an independent model diagnostic, prepare two isolated source-review requests
with the same pinned prompt/schema and source inputs. Use `plan_model_reviews`
to report token estimates, completion caps and both-price cost estimates. Obtain
a separately approved model/rate/execution budget before any external call. The
workflow itself contains no API client. Human expert review may be introduced
later under the retained independent-review integration decision.
