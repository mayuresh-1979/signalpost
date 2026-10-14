# No-paid-API external discovery pilot

Signalpost can test a limited no-paid-API approach by generating a small, deterministic set of likely domains from a registered legal name and fetching those public websites directly. This does **not** use a search engine or a search API, and it does not guarantee discovery: guessed domains may be wrong, unavailable, or unrelated.

The adapter is deliberately conservative:

- tries at most three guesses per company (`name.no`, `name-with-hyphens.no`, `name.com`);
- uses the existing public-URL/redirect protections and robots-aware website fetcher;
- applies the separate strict guessed-domain identity gate;
- keeps every candidate review-only and never changes canonical `evidence.website`;
- reports attempts and identity-gate results, not a qualification score;
- should be run on an isolated copy of profiles and outputs.

This is a coverage experiment, not a replacement for search. A failed domain guess is not proof that a company has no website. Do not increase candidate volume or relax identity thresholds merely to improve apparent coverage.

## Run an offline unit test

```bash
uv run --locked python -m unittest scripts/test_no_api_domain_discovery.py
```

## Run a small no-paid-API pilot

Use the existing generated profiles as input, and a fresh output directory. Start with 20 missing-website profiles. The script makes direct public website requests; it does not require a search-provider key, but the target websites still receive HTTP requests.

```bash
uv run --locked python scripts/run_no_api_domain_discovery.py \
  --input out/profiles.jsonl \
  --output out/no-api-domain-pilot/profiles-discovered.jsonl \
  --report out/no-api-domain-pilot/report.json \
  --limit 20
```

Review the report and every candidate before any further use. Do not pass results directly into canonical website evidence. For any accepted candidate, verify the legal entity against the official registry and inspect the fetched page and content hash. If the gate rejects a candidate, keep it rejected.

The pilot's report explicitly sets `qualification` to `not_evaluated_on_500_org_external_final_corpus`. It must not be represented as official Builderr scoring or as evidence that the production external-discovery gate has passed.
