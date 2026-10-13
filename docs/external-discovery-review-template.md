# External discovery pilot review template

This is a schema/template only. It contains no observed company results and must not be treated as ground truth. Copy one row per discovered candidate and fill it after independently reviewing the fetched company page and official registry identity.

Recommended file location for a local pilot:
`out/external-discovery-pilot/development-labels.jsonl`

One JSON object per line:

```json
{
  "id": "replace-with-stable-observation-id",
  "organisation_number": "replace-with-9-digit-brreg-number",
  "candidate_url": "https://example.no/",
  "exact_entity": false,
  "metric_correct": false,
  "sentiment_correct": false,
  "site_exists_and_is_company_owned": false,
  "identity_evidence_url": "https://example.no/about",
  "official_registry_url": "https://data.brreg.no/enhetsregisteret/api/enheter/replace-with-org-number",
  "reviewer_decision": "pending",
  "reason": "Explain the evidence supporting the decision",
  "reviewed_at": "2026-10-13T00:00:00Z",
  "source_rights_checked": false,
  "source_rights_notes": "Record the applicable terms and retention decision"
}
```

## Labeling rules

- `id` must exactly match the observation ID in the frozen observations JSONL. Do not use organisation number as a substitute unless it is the observation ID.
- `exact_entity` is true only when the page proves the exact legal entity, ideally with organisation number and/or strong official cross-reference. A name match alone is insufficient.
- `metric_correct` is true only when the published field/claim is supported by the fetched page and is represented accurately.
- `sentiment_correct` applies only to a sentiment prediction actually present in the observation. Leave false until reviewed; do not infer correctness from a website match.
- `site_exists_and_is_company_owned` is a separate adjudication from whether the candidate is the right legal entity.
- `reviewer_decision` should be one of `accepted`, `rejected_wrong_entity`, `rejected_not_company_owned`, `rejected_unsupported`, `inaccessible`, or `pending`.
- Check provider terms and data-retention rights before storing any external search result or fetched content. Do not copy raw search titles/snippets into the label file.
- Preserve the original observations and the generated manifest. Never tune against the held-out validation cohort.
- Do not use this template to claim the benchmark passed; only the actual completed, labeled observations and evaluator report can support that claim.
