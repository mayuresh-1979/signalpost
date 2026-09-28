# Final Submission Audit

## 1. Repository State

- **Repository Root**: `signalpost-starter-kit`
- **Source Package**: `src/norway_company_agent/` (`25` Python modules including `financial_emission.py`, `roles_emission.py`, `contact_registration_emission.py`, `capital_emission.py`, and `purpose_vat_audit_emission.py`)
- **CLI & Evaluation Scripts**: `scripts/` (`27` scripts, anchored by `scripts/run_competition_batch.py` and `scripts/run_refresh_replay.py`)
- **Test Suite & Fixtures**: `tests/` (`14` test modules) and `tests/fixtures/` (`13` fixture files)
- **Documentation & Metadata**: `README.md`, `OUTPUT_CONTRACT.md`, `docs/` (`6` architecture and policy documents), `data/universe-metadata.json`
- **Input Corpus & Bulk Snapshots**: `entry-companies.jsonl` (`1,000` companies), `brreg-enheter.csv`, `brreg-underenheter.csv`
- **Output Directory**: `out/` (contains canonical submission outputs `out/profiles.jsonl`, `out/envelopes.jsonl`, `out/run-report.json`, `out/refresh-test.json`, `out/phase17-external-combined.jsonl`, `out/phase17-external-report.json`, and phase audit reports)
- **Temporary Scratch Directory**: `scratch/` (`56` local analysis scripts, classified under **DO NOT SUBMIT**)

---

## 2. Installation Result

- **Environment Mechanism**: `uv sync`
- **Python Version Tested**: `Python 3.13.11` (`requires-python = ">=3.12"` in `pyproject.toml`)
- **uv Version**: `uv 0.12.17`
- **Package Resolution**: `Resolved 111 packages in 2ms; Checked 41 packages in 2ms`
- **Clean Smoke Verification (`uv run python first_run.py`)**: **PASS** (`2` true positive changes detected, `0` false positives, `0` false negatives, idempotent rerun verified)

---

## 3. Dependency Audit

- **Declared Production Dependencies (`pyproject.toml` / `uv.lock`)**:
  - `beautifulsoup4>=4.14,<5`
  - `extruct>=0.18,<1`
  - `lxml>=6,<7`
  - `pydantic>=2.12,<3`
  - `pypdf>=6,<7`
  - `tldextract>=5.3,<6`
  - `trafilatura>=2.0,<3`
- **Optional Dependency Groups**:
  - `crawler`: `scrapy>=2.13,<3`, `scrapy-playwright>=0.0.44,<1`
  - `sentiment`: `accelerate>=1.10,<2`, `torch>=2.5,<3`, `transformers>=4.51,<5`
- **Static AST Import Audit**:
  - Production modules in `src/norway_company_agent/` import only Python standard library modules plus `bs4`, `extruct`, `tldextract`, and `trafilatura` (with `lxml` as parser backend).
  - `scripts/run_competition_batch.py` and `scripts/run_refresh_replay.py` import only Python standard library modules plus `norway_company_agent`.
  - **Undeclared production imports**: **`0`**.

---

## 4. Exact Production Command

### A. Portable Single-Line Command (Bash / Zsh / PowerShell) — 1,000-Company Submission Corpus (Offline Deterministic Resume)

```bash
uv run python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id local-001 --expected-count 1000 --resume
```

### B. Portable Single-Line Command — 100-Company Daily Evaluation Batch (Live Run)

```bash
uv run python scripts/run_competition_batch.py --organisations <batch-100.jsonl> --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/eval-100-profiles.jsonl --output out/eval-100-envelopes.jsonl --report out/eval-100-report.json --run-id eval-100 --expected-count 100
```

### C. Portable Single-Line Command — Deterministic Refresh / Material-Change Replay

```bash
uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-test.json
```

### D. Windows PowerShell Multi-Line Form

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

---

## 5. 1,000-Corpus Integrity

- **Input Manifest (`entry-companies.jsonl`)**: `1,000` valid 9-digit Norwegian organisation numbers (`1,000` unique, `0` duplicates)
- **Profiles (`out/profiles.jsonl`)**: `1,000` profiles (`1,000` unique, exact order match with `entry-companies.jsonl`)
- **Envelopes (`out/envelopes.jsonl`)**: `1,000` terminal envelopes (`1,000` unique, exact order match with `entry-companies.jsonl`)
- **Silent Drops / Missing Entities**: `0`
- **Phase 18–23 Emitted Coverage Verified**:
  - **Phase 18 Financials**: `997 / 1,000` companies (`9,651` financial facts)
  - **Phase 19 Governance & Roles**: `1,000 / 1,000` companies (`4,019` role records)
  - **Phase 21 Addresses, Contact & Registration Dates**: `business_address=998` (`6,973` component facts), `postal_address=246` (`1,709` component facts), `official_email=242`, `official_phone=182`, `official_mobile=182`, `registration_date=1,000`, `foundation_date=991`, `articles_date=967`, `foretaksregisteret_date=974`, `foretaksregisteret_registered=1,000` (`14,222` total component and scalar facts)
  - **Phase 22 Share Capital**: `938 / 1,000` companies (`4,671` core facts, `4,698` total facts)
  - **Phase 23 Purpose, Activity, MVA/VAT & Audit**: `purpose_activity=997` (`statutory_purpose=963`, `operational_activity=997`, `1,960` facts), `vat=1,000` (`2,202` facts), `audit=636` (`exemption_date=636`, `decision_date=436`, `1,072` facts) (`5,234` total Phase 23 facts)
  - **CSV Quote-Shift Protection**: Active on `998600421`, `914882036`, and `926768026` (`0` shifted values emitted).

---

## 6. Artifact Hashes

| Artifact Path | Size (Bytes) | SHA-256 |
| :--- | :---: | :--- |
| `entry-companies.jsonl` | `319,526` | `1dd834b29f7d97b689fb222399ef9d713ffa9f3dc20a94a824da07012d68d408` |
| `out/profiles.jsonl` | `20,040,151` | `c2e1aa0382b6a5c0f9e0f01f3b0d91f18dc06e393517645eb0acdf17227cdd0e` |
| `out/envelopes.jsonl` | `20,916,240` | `894b8f4e47f91fa3098edb516e6668fb21bf5fdaa0f4658bb5b8fe058192f0c8` |
| `out/run-report.json` | `1,359` | `939bdba56c408a525059010dfca89c50c2a129acbe5df12d667e8e213f6198ba` |
| `out/refresh-test.json` | `2,551` | `04b2adf2e813c8a46cdbbc1e8b389b1813e64fff3031ebfeec6f968bd51f77e7` |
| `out/phase17-external-combined.jsonl` | `486,121` | `206035caba405e192cfffea44a423cd9f96a0dc5c91051259500b09f90b23a3f` |
| `out/phase17-external-report.json` | `1,092` | `ddf1085dccd93676a9f105b4a6894f701a9c70814e54b5103996b97b8e798933` |
| `out/phase23-competition-v3-score.json` | `1,825` | `7494e94eba6411c93bbcc3614b6f8b1afd8246f963b2fdfac91280d670be3af2` |
| `out/phase23-purpose-vat-audit-report.json` | `9,813` | `4125dd52b508e9dcf1e42345a5879021f16ab8a05481102386da9d54f91b827a` |

---

## 7. Determinism

- Repeated invocation of `emit_financial_metrics`, `emit_roles_metrics`, `emit_contact_registration_metrics`, `emit_capital_metrics`, and `emit_purpose_vat_audit_metrics` across all `1,000` profiles produces byte-for-byte identical profile objects (`PASS`).
- Historical source retrieval timestamps (`retrieved_at`) from retained evidence are preserved untouched; no execution-time timestamps are injected into profile evidence or emitted top-level structures (`PASS`).
- Zero random identifiers or machine-specific file paths exist in `out/profiles.jsonl` or `out/envelopes.jsonl` (`PASS`).

---

## 8. Refresh / Idempotency

- Verified via `uv run python scripts/run_refresh_replay.py --manifest tests/fixtures/refresh-snapshots.json --output out/refresh-test.json`:
  - `expected_changes`: `2`
  - `observed_changes`: `2`
  - `true_positive`: `2`, `false_positive`: `0`, `false_negative`: `0`
  - `precision`: `1.0`, `recall`: `1.0`
  - `evidence_complete`: `true`
  - `idempotent_rerun`: `true`
  - `qualification_passed`: `true` (`PASS`)

---

## 9. Terminal Validation

- Verified via `norway_company_agent.batch.validate_envelopes(envelopes, 1000)`:
  - `passed`: `true`
  - `exact_expected_count`: `true` (`1,000`)
  - `unique_organisation_numbers`: `true` (`1,000`)
  - `all_entity_states_terminal`: `true` (`1,000` `"complete"`)
  - `all_module_states_terminal`: `true` (`7,000 / 7,000` module states terminal across `registry`, `accounting_obligation`, `registry_live`, `financials`, `roles`, `locations`, `website`)
  - `zero_silent_drops`: `true`
  - `invalid_states`: `[]` (`PASS`)

---

## 10. Identity Safety

- **Production Identity Gates (`src/norway_company_agent/identity.py`)**:
  - Registry-linked websites and email-domain fallbacks must pass `apply_website_identity_gate` (`assess_website_identity`).
  - Guessed name-domain candidates must pass `assess_guessed_website_identity`.
  - Uncertain or name-only matches without exact entity anchoring are quarantined (`publishable: false`), preventing downstream social-link or site-activity extraction from crossing entity boundaries.
- **External Footprint Audit (`out/phase17-external-report.json` & `out/phase17-external-combined.jsonl`)**:
  - Total published observations: `441`
  - Wrong-company external publications: **`0`**
  - Unsupported external claims: **`0`** (`PASS`)

---

## 11. Source-Rights Audit

- All `441` published external observations in `out/phase17-external-combined.jsonl` use `acquisition_mode in {"official_api", "permitted_public_page"}` and `rights_status == "approved"`.
- Experimental / review-required scripts (`run_google_news_rss_connector.py`, `run_linkedin_guest_experiment.py`, `run_linkedin_guest_jobs_connector.py`, `run_fagfolkguiden_reviews_connector.py`, `run_youtube_search_connector.py`, `normalize_google_maps_results.py`) are strictly isolated standalone scripts; none are imported or invoked by `scripts/run_competition_batch.py`, and `0` experimental observations exist in production outputs (`PASS`).

---

## 12. Test Results

- **Total Test Modules**: `14` modules (`178` unit tests total).
- **Non-POC Active Phase, Emission, Workforce, Subunits, Connector-Rights, Website-Optimization & Safety Suites (`13` modules)**: **`74 / 74` passed** (`0` failures, `0` errors).
- **POC & Integration Suite (`tests/test_poc.py`, `1` module)**: **`104 / 104` passed** (`0` failures, `0` errors).
- **Full `unittest discover -s tests` (`14` modules, `178` tests)**: **`178 / 178` passed** (`0` failures, `0` errors).
- **Local Competition Proxy V3 / Local Diagnostic Score (`out/phase23-competition-v3-score.json`)**: **`56.869 / 100.0`** (`scorer: "signalpost_external_first_competition_proxy_v3"`, `qualification_passed: true`, all 7 qualification gates `PASS`; local optimization proxy only — no official Builderr evaluator score is claimed).

---

## 13. README / Documentation Audit

- `README.md` has been updated to accurately document:
  - Project purpose, input/output contracts, and Phase 18–23 top-level structured fields
  - Python `>=3.12` and `uv sync` installation
  - Portable single-line and PowerShell multi-line production commands for both the 1,000-company submission corpus (`--expected-count 1000 --resume`) and the 100-company daily evaluation batch (`--expected-count 100`)
  - Refresh replay command (`scripts/run_refresh_replay.py`) and test suite command
  - Measured runtime, request count, and `\$0.00` third-party API cost without exaggerated or unverifiable score claims (`PASS`).

---

## 14. Git Status & Secret Scan

- **Git Initialization State**: The workspace was extracted from the starter-kit archive and does not currently have a `.git` directory initialized (`git status` returns exit code 128 `not a git repository`). No commits or pushes have been made during this audit.
- **Secret & Credential Scan**:
  - `.env`, `.pem`, `.key` files found: **`0`**
  - API keys, bearer tokens, private keys, or cloud credentials found: **`0`**
  - Local machine paths (`C:\Users\crypt`) in `src/`, `scripts/`, `tests/`, `docs/`, or `out/`: **`0`** (only found in 2 helper scripts inside `scratch/`, which is excluded from submission).

---

## 15. Files to Submit

### MUST SUBMIT (Core Code, Lockfile, Manifest, Canonical Outputs & Tests)
- `pyproject.toml`, `uv.lock`, `README.md`, `OUTPUT_CONTRACT.md`, `first_run.py`, `select_entry_batch.py`
- `entry-companies.jsonl`
- `src/norway_company_agent/` (all `25` `.py` modules)
- `scripts/run_competition_batch.py`, `scripts/run_refresh_replay.py`, `scripts/extract_official_workforce.py`, `scripts/extract_verified_social_handles.py`, `scripts/extract_company_site_activity.py`, `scripts/extract_company_site_news.py`, `scripts/evaluate_external_footprint.py`, `scripts/evaluate_research_agent.py`, `scripts/score_competition_v3.py`, `scripts/score_company_completeness.py`, `scripts/build_prototype.py`, `scripts/ask_agent.py`
- `tests/` (all `14` test modules and `tests/fixtures/`)
- `docs/` (all `6` documentation files) and `data/universe-metadata.json`
- `out/profiles.jsonl`
- `out/envelopes.jsonl`
- `out/run-report.json`
- `out/refresh-test.json`
- `out/phase17-external-combined.jsonl`
- `out/phase17-external-report.json`

### SHOULD SUBMIT (Audit & Verification Reports)
- `out/phase18-financial-emission-report.json`, `out/phase18-financial-emission-report.md`
- `out/phase19-roles-emission-report.json`, `out/phase19-roles-emission-report.md`
- `out/phase20-brreg-coverage-audit.json`, `out/phase20-brreg-coverage-report.md`
- `out/phase21-contact-registration-report.json`, `out/phase21-contact-registration-report.md`
- `out/phase22-capital-report.json`, `out/phase22-capital-report.md`
- `out/phase23-purpose-vat-audit-report.json`, `out/phase23-purpose-vat-audit-report.md`, `out/phase23-competition-v3-score.json`
- `out/final-submission-audit.json`, `out/final-submission-audit.md`
- `out/research-report.json`, `out/ux-report.json`

---

## 16. Files Not to Submit

### DO NOT SUBMIT (Exclude via `.gitignore` before `git add`)
- `.venv/`, `__pycache__/`, `.pytest_cache/`, `*.tmp`
- `scratch/` (`56` ad-hoc local analysis scripts)
- Root-level ad-hoc debug/inspection scripts and temporary smoke files (`add_candidate_gate.py`, `diagnose_candidate_gate.py`, `inspect_*.py`, `test_*.py` in root, `smoke-*.jsonl`)
- Large external raw downloads (`brreg-enheter.csv`, `brreg-underenheter.csv`, `signalpost-universe.jsonl.gz` — downloadable via the documented `curl` commands in `README.md`)
- Intermediate experimental outputs in `out/` (`out/candidate-*`, `out/smoke-*`, `out/phase3-*` through `out/phase16-*` intermediate experiment JSONLs)

---

## 17. Submission Metadata Checklist (`submit@builderr.ai`)

- **Repository URL**: `<INSERT_GIT_REPOSITORY_URL>`
- **Final Commit Hash**: `<INSERT_FINAL_COMMIT_SHA>`
- **Organisation-Number Input File**: `entry-companies.jsonl` (`1,000` companies, SHA-256 `1dd834b29f7d97b689fb222399ef9d713ffa9f3dc20a94a824da07012d68d408`)
- **Exact Run Command (100-Company Daily Evaluation)**:
  `uv run python scripts/run_competition_batch.py --organisations <input.jsonl> --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id eval-run --expected-count 100`
- **Exact Run Command (1,000-Company Corpus Deterministic Replay)**:
  `uv run python scripts/run_competition_batch.py --organisations entry-companies.jsonl --bulk brreg-enheter.csv --subunits-bulk brreg-underenheter.csv --profiles-output out/profiles.jsonl --output out/envelopes.jsonl --report out/run-report.json --run-id local-001 --expected-count 1000 --resume`
- **Models / External Paid APIs Used**: `None` (deterministic rule-based extraction and entity verification; no paid LLM or third-party commercial APIs)
- **Data Sources & Licences**:
  - Brønnøysundregistrene (BRREG) Enhetsregisteret, Underenheter, and Regnskapsregisteret open public data (`NLOD 2.0` / Norwegian Licence for Open Government Data)
  - Public company-owned websites (`robots.txt`-compliant static HTTP fetch; `permitted_public_page`)
- **Expected Third-Party Cost per 100-Company Run**: **`\$0.00 USD`**
- **Contact Information**: `<INSERT_SUBMITTER_NAME_AND_EMAIL>`

---

## 18. Daily 100-Company Compatibility

- `scripts/run_competition_batch.py` defaults to `--expected-count 100` and accepts any 100-company JSONL/JSON/text manifest via `--organisations`.
- Measured 100-company batch performance across repository benchmarks (`out/smoke-100-report.json`, `out/phase10A-100-report.json`, `out/optimized-100-report.json`):
  - **Runtime**: `1.5 to 3.5 minutes` (Competition limit: **`<= 45 minutes`**) — **PASS**
  - **Outbound HTTP Requests**: `318 to 684 requests` (`~612` avg from the 1,000-company run) (Competition limit: **`<= 2,000 requests`**) — **PASS**
  - **Third-Party API Cost**: **`\$0.00`** (Competition limit: **`<= \$10.00`**) — **PASS**

---

## 19. PASS / FAIL / WARNING Final Gate

- [x] **installation**: **PASS** (`uv sync` + `first_run.py` verified)
- [x] **dependency declaration**: **PASS** (all production imports declared in `pyproject.toml` and locked in `uv.lock`)
- [x] **production command**: **PASS** (single-line portable and PowerShell commands verified)
- [x] **1,000 input corpus**: **PASS** (`entry-companies.jsonl`, `1,000` unique orgs)
- [x] **1,000 profiles**: **PASS** (`out/profiles.jsonl`, `1,000` unique orgs)
- [x] **1,000 envelopes**: **PASS** (`out/envelopes.jsonl`, `1,000` unique orgs)
- [x] **exact organisation-number alignment**: **PASS** (`100%` ordered match across input, profiles, and envelopes)
- [x] **terminal validation**: **PASS** (`validate_envelopes` all checks `true`, `0` silent drops)
- [x] **refresh replay**: **PASS** (`precision=1.0`, `recall=1.0`, `idempotent_rerun=true`)
- [x] **deterministic replay**: **PASS** (idempotent across all `1,000` profiles)
- [x] **identity safety**: **PASS** (strict org-number / multi-signal gates enforced)
- [x] **wrong-company = 0**: **PASS** (`0` wrong-company publications)
- [x] **unsupported claims = 0**: **PASS** (`0` unsupported claims)
- [x] **source-rights compliance**: **PASS** (`official_api` and `permitted_public_page` only)
- [x] **no production experimental connectors**: **PASS** (`0` experimental observations in production outputs)
- [x] **no secrets**: **PASS** (`0` keys, tokens, or `.env` files)
- [x] **no temporary artifacts**: **PASS** (`0` `.tmp` files in `out/`)
- [x] **README accuracy**: **PASS** (updated with verified commands and measurable facts)
- [x] **reproducibility**: **PASS** (`uv.lock` + deterministic `--resume` pipeline)
- [x] **Git cleanliness**: **PASS** (ready for `git init` + `.gitignore` + clean stage of `MUST SUBMIT` / `SHOULD SUBMIT` files)
- [x] **final submission metadata**: **PASS** (complete checklist prepared in Section 17)
- [x] **daily 100-company compatibility**: **PASS** (`~3.5 min`, `~612 requests`, `\$0.00` cost)

---

## 20. Remaining Actions Before Final Commit

1. Initialize the Git repository (`git init`) and add a `.gitignore` excluding `.venv/`, `__pycache__/`, `.pytest_cache/`, `scratch/`, root debug scripts (`inspect_*.py`, `test_*.py`, `smoke-*.jsonl`), intermediate `out/` experiment files, and raw bulk CSV downloads (`brreg-enheter.csv`, `brreg-underenheter.csv`, `signalpost-universe.jsonl.gz`).
2. Stage the **MUST SUBMIT** and **SHOULD SUBMIT** files listed in Section 15, create the final commit, push to the submission repository URL, and send the submission email to `submit@builderr.ai`.

---

# FINAL STATUS

READY_FOR_FINAL_COMMIT
