# Signalpost Norwegian Company Research Agent

This repository contains the Signalpost submission and reference agent for researching Norwegian companies from official Brønnøysundregistrene (BRREG) records, registered subunits (`underenheter`), verified company-owned websites, and permitted public external signals.

The public universe contains 411,160 eligible Norwegian companies. This repository includes a completed, deterministic 1,000-company corpus (`entry-companies.jsonl`, `out/profiles.jsonl`, `out/envelopes.jsonl`) and supports both 1,000-company batch reproduction and 100-company daily evaluation runs.

## Verification Status

- **Repository:** `mayuresh-1979/signalpost`
- **Latest completed code-test run:** [Run #16 — live smoke test + independent clean-clone reproducibility](https://github.com/mayuresh-1979/signalpost/actions/runs/38404792692) — **PASS** on code commit `96c25ba703b061f20d9b733e467a3c21ce7d876f`.
- **Checks added in that run:** external-footprint freshness evaluator regression tests and deterministic external-discovery benchmark split tests both passed; both live 100-company smoke test and clean-clone reproducibility jobs passed.
- **Live 100-company baseline (previous fully inspected run):** 100/100 inputs produced 100 profiles and 100 terminal envelopes; all IDs were unique and aligned; zero silent drops. Runtime was approximately 95 seconds, with 387 HTTP requests and about 7.57 MB transferred.
- **Evidence audit baseline:** 621/621 available evidence records had valid URL, retrieval timestamp, and SHA-256. Of 21 website candidates, 8 passed the strict publication identity gate and 13 were quarantined.
- **Builderr contract baseline:** 100 output rows validated; 4,334 claims and 621 evidence records; zero contract validation errors. These counts describe the earlier inspected run, not newly asserted artifact contents for Run #16.
- **Artifact scope:** CI establishes the checks actually run, structural correctness and reproducibility; it is **not** an official Builderr score or human factual-accuracy certification.
- **Local score diagnostic:** `signalpost_external_first_competition_proxy_v3` records **56.869 / 100**. It is a local proxy, not an official evaluator result. The largest remaining weakness is external-footprint intelligence (multi-source breadth, ratings/reviews, buzz, qualified sentiment, and freshness).
- **External discovery:** deterministic benchmark cohorts and the manual review queue are implemented and tested. A bounded no-paid-API guessed-domain pilot is now implemented; it is review-only and does not auto-promote guessed websites. No live no-paid-API pilot result or external-discovery qualification is claimed yet. Follow [the no-paid-API pilot guide](docs/no-paid-api-discovery.md), preserve canonical outputs, and inspect every candidate.
- **Canonical outputs:** frozen submission artifacts under `out/` must not be overwritten during experiments. Use a fresh clone or isolated output directory for every benchmark.
- **Large BRREG snapshots:** stored with Git LFS.

**Submission caveat:** the last completed code-test run passed on `96c25ba...`. Documentation commits made after that run are not themselves covered by Run #16; the final submission commit must have a fresh successful workflow run. Official evaluation and qualification remain unconfirmed. Do not describe the local proxy or smoke-test PASS as Builderr qualification.

**Submission checklist:** see [`docs/submission-checklist.md`](docs/submission-checklist.md) for required materials, final gates, and the external-discovery pilot procedure.

## What the agent does

- **Input**: Reads a batch of 9-digit Norwegian organisation numbers from JSONL (`{"organisation_number": "..." }`), JSON, or plain text (`--organisations`).
- **Official Foundation (BRREG)**:
  - Anchors legal identity in the Brønnøysund bulk entity snapshot (`brreg-enheter.csv`) and live entity endpoint (`registry_live`).
  - Matches active registered workplaces/establishments from the official BRREG subunits snapshot (`brreg-underenheter.csv`, module `locations`).
  - Fetches official annual accounts (`Regnskapsregisteret`, module `financials`) and statutory governance roles (`Enhetsregisteret /roller`, module `roles`).
  - Deterministically propagates verified retained BRREG evidence into explicit top-level profile fields with provenance metadata (`source_url`, `source_type`, `retrieved_at`, `content_sha256`).
  - Emits the audited Phase 18–23 financial, governance, contact/registration, capital, purpose/activity, VAT, and audit fields described in the repository audit.
  - Enforces row-level CSV quote-shift protection so malformed BRREG rows cannot leak shifted column values.
- **Website & External Footprint**:
  - Visits registry-listed and verified candidate company websites with robots-aware static HTTP fetching.
  - Applies strict exact-entity identity gates; uncertain or name-only matches are quarantined (`publishable: false`).
  - Publishes only observations acquired through approved production acquisition modes.
- **Output Contract & Refresh**:
  - Emits one profile per organisation in `out/profiles.jsonl` and one terminal envelope per organisation in `out/envelopes.jsonl`.
  - Supports deterministic checkpoint/resume (`--resume`) and material-change diffing through `scripts/run_refresh_replay.py`.

---

## Requirements & Installation

- **Python**: `>=3.12`
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/)
- **Declared production dependencies** are pinned by the version ranges in `pyproject.toml` and resolved in `uv.lock`.

Install the locked environment:

```bash
uv sync
```

Verify the offline saved-snapshot smoke check:

```bash
uv run python first_run.py
```

---

## Production Run Commands

### 1. Reproduce the 1,000-company submission corpus

The canonical retained-evidence replay is deterministic and uses `--resume`:

```bash
uv run python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id local-001 --expected-count 1000 --resume
```

**Important:** running this command in the submission checkout writes to the canonical `out/` paths. For a clean reproducibility test, use a fresh clone or alternate output paths so the frozen submission artifacts remain untouched.

### 2. Run a live 100-company daily evaluation batch

```bash
uv run python scripts/run_competition_batch.py --organisations <batch-100.jsonl> --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/eval-100-profiles.jsonl --output out/eval-100-envelopes.jsonl --report out/eval-100-report.json --run-id eval-100 --expected-count 100
```

### 3. One-command Builderr submission run

Use the evaluator-supplied input file and its exact row count. This command runs the agent, audits evidence provenance, exports the Builderr contract, and validates the output. It does not use precomputed profiles as evaluation answers.

```bash
uv run --locked python scripts/run_builderr_submission.py --organisations <evaluator-batch.jsonl> --expected-count <N> --run-id builderr-official-001 --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --output-dir out/builderr-run --workers 8
```

The final machine-readable contract is written to `out/builderr-run/builderr-output.jsonl`. A local PASS is not an official Builderr score.

### 4. Deterministic refresh / material-change replay

```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-test.json
```

### Windows PowerShell

```powershell
uv run python scripts/run_competition_batch.py `
  --organisations entry-companies.jsonl `
  --bulk brreg-enheter.csv `
  --subunits-bulk brreg-underenheter.csv `
  --profiles-output out/profiles.jsonl `
  --output out/envelopes.jsonl `
  --report out/run-report.json `
  --run-id local-001 `
  --expected-count 1000 `
  --resume
```

### Fresh BRREG snapshots

If the LFS snapshots are not available locally for a new environment:

```bash
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv' -o brreg-underenheter.csv
```

---

## Running Tests

Run the 13 non-POC audited suites:

```bash
uv run python -m unittest tests/test_purpose_vat_audit_emission.py tests/test_capital_emission.py tests/test_contact_registration_emission.py tests/test_roles_emission.py tests/test_financial_emission.py tests/test_official_workforce.py tests/test_ratings_reviews_audit.py tests/test_hiring_jobs_audit.py tests/test_freshness_and_breadth_audit.py tests/test_subunits.py tests/test_phase11_connectors.py tests/test_phase10B_safety.py tests/test_website_optimizations.py
```

The independently reproduced clean-clone run on September 28, 2026 completed with **74 / 74 tests passing**.

---

## Resource, Provenance & Source-Rights Summary

- **Third-party API cost:** $0.00 in the audited production configuration.
- **1,000-company historical live run:** 6,121 HTTP requests; retained-evidence resume replay is offline.
- **100-company historical benchmark range:** approximately 318–684 outbound HTTP requests and 1.5–3.5 minutes runtime.
- **Production acquisition modes:** `official_api` and `permitted_public_page`, with approved rights status.
- Experimental connectors are quarantined from the production batch.

---

## Key Submission Artifacts

| Path | Description |
| :--- | :--- |
| `entry-companies.jsonl` | Frozen 1,000-company input manifest |
| `out/profiles.jsonl` | 1,000 completed company profiles |
| `out/envelopes.jsonl` | 1,000 validated terminal envelopes |
| `out/run-report.json` | Machine-readable batch execution and validation report |
| `out/refresh-test.json` | Deterministic snapshot refresh diff report |
| `docs/audit/final-submission-audit.json` | Machine-readable final submission audit |
| `docs/audit/final-submission-audit.md` | Human-readable final submission audit |

## Frozen Artifact Hashes

- `entry-companies.jsonl`: `1dd834b29f7d97b689fb222399ef9d713ffa9f3dc20a94a824da07012d68d408`
- `out/profiles.jsonl`: `c2e1aa0382b6a5c0f9e0f01f3b0d91f18dc06e393517645eb0acdf17227cdd0e`
- `out/envelopes.jsonl`: `894b8f4e47f91fa3098edb516e6668fb21bf5fdaa0f46500bb5b8fe058192f0c8`
- `out/run-report.json`: `939bdba56c408a525059010dfca89c50c2a129acbe5df12d667e8e213f6198ba`
- `out/refresh-test.json`: `04b2adf2e813c8a46cdbbc1e8b389b1813e64fff3031ebfeec6f968bd51f77e7`

## Local Diagnostic, Not Official Score

The repository contains a local competition optimization proxy of **56.869 / 100**, recorded as `signalpost_external_first_competition_proxy_v3`. This is a local diagnostic only and is **not** an official Builderr evaluator score.

