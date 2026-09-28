# Signalpost Norwegian Company Research Agent

This repository contains the Signalpost submission and reference agent for researching Norwegian companies from official Brønnøysundregistrene (BRREG) records, registered subunits (`underenheter`), verified company-owned websites, and permitted public external signals.

The public universe contains 411,160 eligible Norwegian companies. This repository includes a completed, deterministic 1,000-company corpus (`entry-companies.jsonl`, `out/profiles.jsonl`, `out/envelopes.jsonl`) and supports both 1,000-company batch reproduction and 100-company daily evaluation runs.

## What the agent does

- **Input**: Reads a batch of 9-digit Norwegian organisation numbers from JSONL (`{"organisation_number": "..."}`), JSON, or plain text (`--organisations`).
- **Official Foundation (BRREG)**:
  - Anchors legal identity in the Brønnøysund bulk entity snapshot (`brreg-enheter.csv`) and live entity endpoint (`registry_live`).
  - Matches active registered workplaces/establishments from the official BRREG subunits snapshot (`brreg-underenheter.csv`, module `locations`).
  - Fetches official annual accounts (`Regnskapsregisteret`, module `financials`) and statutory governance roles (`Enhetsregisteret /roller`, module `roles`).
  - Deterministically propagates verified retained BRREG evidence into explicit top-level profile fields with full provenance metadata (`source_url`, `source_type`, `retrieved_at`, `content_sha256`):
    - **Financials (Phase 18)**: `financials`, `revenue`, `operating_result`, `profit_before_tax`, `annual_result`, `assets`, `equity`, `debt`, `currency`, `reporting_period_from`, `reporting_period_to` (`997 / 1,000` companies).
    - **Governance & Roles (Phase 19)**: `roles`, `board_chair`, `managing_director`, `board_members`, `deputy_board_members`, `auditors`, `authorized_accountants` (`1,000 / 1,000` companies, `4,019` role records).
    - **Addresses, Contact Channels & Core Registration Dates (Phase 21)**: `business_address` (`998`), `postal_address` (`246`), `official_email` (`242`), `official_phone` (`182`), `official_mobile` (`182`), `registration_date` (`1,000`), `foundation_date` (`991`), `articles_date` (`967`), `foretaksregisteret_date` (`974`), `foretaksregisteret_registered` (`1,000`).
    - **Share Capital & Equity Registration (Phase 22)**: `capital`, `share_capital` (`938`), `share_capital_currency` (`938`), `capital_registered_date` (`938`), `share_count` (`919`), `capital_type` (`938`), plus sparse `paid_in` (`14`), `fully_paid_in` (`13`), `bound` (`0`).
    - **Statutory Purpose, Operational Activity, MVA/VAT & Audit Metadata (Phase 23)**: `purpose_activity`, `statutory_purpose` (`963`), `operational_activity` (`997`), `vat`, `vat_registered` (`1,000`), `vat_registered_date` (`507`), `vat_enhetsregisteret_registered_date` (`507`), `vat_voluntary_descriptions` (`94`), `vat_voluntary_registered_date` (`94`), `audit`, `audit_exemption_date` (`636`), `audit_decision_date` (`436`).
  - Enforces row-level CSV quote-shift protection (`is_csv_quote_shifted` and `get_safe_bulk_field`) so bulk registry rows with unescaped quotes/commas in `vedtektsfestetFormaal`/`aktivitet` (`998600421`, `914882036`, `926768026`) never leak shifted column values (`>= 64`).
- **Website & External Footprint**:
  - Visits registry-listed and verified candidate company websites (`robots.txt`-compliant static HTTP fetch).
  - Applies strict exact-entity identity gates (`src/norway_company_agent/identity.py`) requiring Norwegian organisation-number verification or multi-signal exact-entity proof; uncertain or name-only matches are quarantined (`publishable: false`).
  - Extracts verified social handles, company-site news/activity, and official workforce snapshots under `PUBLISHABLE_ACQUISITION_MODES = {"official_api", "licensed_api", "company_authorized_export", "permitted_public_page"}` with `rights_status == "approved"`.
- **Output Contract & Refresh**:
  - Emits one complete profile per organisation in `out/profiles.jsonl` and one terminal envelope per organisation in `out/envelopes.jsonl` (`zero_silent_drops: true`).
  - Supports deterministic checkpoint/resume (`--resume`) and material-change diffing between snapshots (`scripts/run_refresh_replay.py`).

---

## Requirements & Installation

- **Python**: `>=3.12` (tested on Python 3.12 and 3.13)
- **Package Manager**: [`uv`](https://docs.astral.sh/uv/)
- **Declared Production Dependencies** (`pyproject.toml` / `uv.lock`):
  - `beautifulsoup4>=4.14,<5`
  - `extruct>=0.18,<1`
  - `lxml>=6,<7`
  - `pydantic>=2.12,<3`
  - `pypdf>=6,<7`
  - `tldextract>=5.3,<6`
  - `trafilatura>=2.0,<3`

Install the locked environment from the repository root:

```bash
uv sync
```

Verify the offline saved-snapshot smoke check (no network calls or API keys required):

```bash
uv run python first_run.py
```

---

## Production Run Commands

### 1. Portable Single-Line Command (Works in Bash, Zsh, and Windows PowerShell)

**A. Reproduce the 1,000-company submission corpus from retained evidence (offline, 0 HTTP requests, ~28s):**

```bash
uv run python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id local-001 --expected-count 1000 --resume
```

**B. Run a live 100-company daily evaluation batch (`--expected-count 100` is the default):**

```bash
uv run python scripts/run_competition_batch.py --organisations <batch-100.jsonl> --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/eval-100-profiles.jsonl --output out/eval-100-envelopes.jsonl --report out/eval-100-report.json --run-id eval-100
```

**C. Run the deterministic refresh / material-change replay:**

```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-test.json
```

### 2. Multi-Line Windows PowerShell Form

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

### 3. Downloading Fresh BRREG Bulk Snapshots (Only Required for New Live Runs)

If `brreg-enheter.csv` or `brreg-underenheter.csv` are not already present locally:

```bash
curl -L 'https://data.brreg.no/enhetsregisteret/api/enheter/lastned/csv' -o brreg-enheter.csv
curl -L 'https://data.brreg.no/enhetsregisteret/api/underenheter/lastned/csv' -o brreg-underenheter.csv
```

---

## Running Tests

Run all active phase, emission, workforce, subunits, connector-rights, website-optimization, and safety test suites:

```bash
uv run python -m unittest tests/test_purpose_vat_audit_emission.py tests/test_capital_emission.py tests/test_contact_registration_emission.py tests/test_roles_emission.py tests/test_financial_emission.py tests/test_official_workforce.py tests/test_ratings_reviews_audit.py tests/test_hiring_jobs_audit.py tests/test_freshness_and_breadth_audit.py tests/test_subunits.py tests/test_phase11_connectors.py tests/test_phase10B_safety.py tests/test_website_optimizations.py
```

---

## Resource, Provenance & Source-Rights Summary

- **Third-Party API Cost**: `\$0.00` (uses zero paid APIs or external LLMs).
- **Request & Runtime Budget**:
  - **1,000-company corpus (`out/run-report.json`)**: `6,121` total live HTTP requests (`103,662,028` bytes, `p50 = 848 ms`, `p95 = 1,379 ms`); `0` HTTP requests and `~28s` runtime when re-emitted with `--resume`.
  - **100-company daily evaluation batch**: `~387–612` outbound HTTP requests and `~1.5–3.5` minutes runtime (`\$0.00` cost), well within the daily evaluator limits (`45` minutes, `2,000` requests, `\$10.00` cost).
- **Source Rights Policy**: Only `official_api` (BRREG Enhetsregisteret / Regnskapsregisteret / Underenheter) and `permitted_public_page` (`robots.txt`-compliant company-owned websites) with `rights_status == "approved"` are published. Experimental connectors are quarantined from production runs.

---

## Key Submission Artifacts

| Path | Description |
| :--- | :--- |
| `entry-companies.jsonl` | Frozen 1,000-company input manifest (9-digit Norwegian organisation numbers) |
| `out/profiles.jsonl` | 1,000 completed company profiles with retained evidence and Phase 18–23 top-level structured fields |
| `out/envelopes.jsonl` | 1,000 validated terminal envelopes (`state: "complete"`, `zero_silent_drops: true`) |
| `out/run-report.json` | Machine-readable batch execution and validation report |
| `out/refresh-test.json` | Deterministic snapshot refresh diff report (`precision: 1.0`, `recall: 1.0`, `idempotent_rerun: true`) |
| `docs/audit/final-submission-audit.json` | Machine-readable final submission audit report |
| `docs/audit/final-submission-audit.md` | Human-readable final submission audit report |




