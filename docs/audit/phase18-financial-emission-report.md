# Phase 18 — Emit Detailed Financial Metrics from Retained Evidence Report

## Executive Summary

Phase 18 successfully implemented the safe, zero-network-request propagation of already-retained official annual accounts evidence into the competition profile and terminal envelope structures across the frozen 1,000-company corpus.

### Key Achievements
- **Zero Network Requests**: 0 HTTP requests emitted during emission; $0.00 third-party API cost.
- **9,651 New Verified Financial Facts Emitted**: Surfaced 10 distinct financial statement metrics directly to top-level profile fields and structured `financials` objects.
- **100% Entity Anchoring**: Strict validation that every emitted financial record matches the profile's exact organisation number.
- **Evidence Integrity Preserved**: Original evidence blobs, source URLs, content hashes, and retrieval timestamps remain completely untouched.
- **Zero Fabrication / Inference**: Missing values strictly remain `None`. Debt is never inferred from assets/equity; revenue/operating profit are never estimated.
- **All 7 Hard Qualification Gates Passed**: 1,000/1,000 valid terminal envelopes, 100% exact identity, 100% idempotent refresh replay, 0 wrong companies, 0 unsupported claims.

---

## 1. Schema Inspection & Design Decision

### Audit of Retained Financial Structure
As established in Phase 17C, `profile["evidence"]["financials"]["value"]["records"]` already retained structured annual accounts from the official Regnskapsregisteret API for 997 companies. Prior to Phase 18, however, the top-level `profile` only emitted a single scalar string: `"latest_submitted_accounts": "2025"`.

### Safest Existing Location
To ensure maximum compatibility with automated evaluators, research queries, and schema validators:
1. **Dedicated Structured Object (`profile["financials"]`)**: Emits the complete, entity-anchored financial record including accounting period, currency, statement metrics, source metadata (`source_url`, `retrieved_at`, `content_sha256`), and the full `records` list (preserving multiple records if present).
2. **Top-Level Convenience Fields**: Exposes the primary financial fields directly on `profile` (`revenue`, `operating_result`, `profit_before_tax`, `annual_result`, `assets`, `equity`, `debt`, `currency`, `reporting_period_from`, `reporting_period_to`).
3. **Missing Value Handling**: When financial evidence is absent or non-available (`not_found`, `source_error`), all financial fields are set to `None`, perfectly preserving missing data without converting to zero.

---

## 2. Implementation Details

A dedicated module was introduced at `src/norway_company_agent/financial_emission.py` with two core functions:
- `extract_financial_record(...)`: Transforms a single retained financial record into an entity-anchored dictionary.
- `emit_financial_metrics(profile)`: Safely extracts and attaches financial fields to the profile after validating entity identity and source integrity.

### Integration Points
- `src/norway_company_agent/__init__.py`: Exports `emit_financial_metrics` and `extract_financial_record`.
- `scripts/run_competition_batch.py`:
  - Called inside `enrich(profile)` after official modules are fetched.
  - Applied to `ordered_profiles` before envelope packaging and serialization.
  - Merges prior operations metrics during `--resume` runs to preserve exact `p50_ms` and `p95_ms` latency metrics.

---

## 3. Entity Safety & Integrity Guarantees

Every emitted financial record is strictly guarded by deterministic safety checks:
1. **Organisation Number Matching**: If `source_row_key` is present on the financial evidence, it must exactly equal `profile["organisation_number"]`.
2. **Source URL Verification**: If `source_url` contains a `/regnskap/{org}` path, the extracted organisation number must match the profile organisation number.
3. **No Cross-Entity Leakage**: Any mismatch immediately raises a `ValueError`, halting emission.
4. **No Overwrites**: The original `evidence["financials"]` dictionary is preserved verbatim.

---

## 4. Focused Test Suite (`tests/test_financial_emission.py`)

A new, comprehensive unit test suite was added in `tests/test_financial_emission.py` covering all required scenarios:
1. `test_complete_financial_record`: Validates extraction of complete balance sheet and income statement metrics.
2. `test_partial_financial_record_preserves_none_and_never_calculates`: Verifies that missing metrics (e.g., None revenue or None debt) remain None and are never inferred or calculated.
3. `test_missing_financial_evidence_leaves_fields_none`: Verifies `status == 'not_found'` or `'source_error'` results in `None` for all fields.
4. `test_multiple_financial_records_preserved`: Verifies that historical records are preserved in `records` and latest record populates top-level fields.
5. `test_entity_number_mismatch_rejection`: Confirms mismatch between URL/row_key and profile org raises `ValueError`.
6. `test_preservation_of_source_metadata`: Validates retention of `source_url`, `source_type`, `retrieved_at`, and `content_sha256`.
7. `test_deterministic_output_and_idempotence`: Confirms repeated executions yield identical, idempotent output.
8. `test_no_network_requests_during_emission`: Mocks sockets to prove zero network activity during execution.
9. `test_original_evidence_unmodified`: Confirms original evidence dictionaries remain unmutated.

**Test Result**: 9/9 tests passed in 0.001s.

---

## 5. 1,000-Company Corpus Rebuild & Validation

The full 1,000-company corpus was rebuilt using the official batch command:
```bash
uv run python scripts/run_competition_batch.py \
  --organisations entry-companies.jsonl \
  --bulk brreg-enheter.csv \
  --subunits-bulk brreg-underenheter.csv \
  --profiles-output out/profiles.jsonl \
  --output out/envelopes.jsonl \
  --report out/run-report.json \
  --run-id local-001 \
  --expected-count 1000 \
  --resume
```

### Validation Audit Results
- **Profiles Emitted**: Exactly 1,000
- **Envelopes Emitted**: Exactly 1,000
- **Unique Organisation Numbers**: Exactly 1,000 / 1,000
- **Silent Drops**: 0
- **Terminal Envelope Validation**: **PASSED** (`validation.passed == True`, 0 invalid states)
- **Refresh Replay Validation**: **PASSED** (precision: 1.0, recall: 1.0, idempotent: True)
- **Official Identity Completeness**: **PASSED** (1,000 / 1,000 exact matches)
- **Wrong-Company Publications**: 0
- **Unsupported Claims**: 0

---

## 6. Measured Improvement & Coverage Comparison

| Metric / Dimension | Before Phase 18 | After Phase 18 | Change |
|---|---|---|---|
| **Companies with Financial Evidence** | 997 | 997 | 0 (No new fetching) |
| **Companies with Missing Financials** | 3 (2 source_error, 1 not_found) | 3 | 0 (Accurate missingness) |
| **Financial Records Emitted** | 0 | 997 | **+997 records** |
| **Top-Level Financial Facts Emitted** | 0 | 9,651 | **+9,651 facts** |
| **- Turnover / Revenue (`revenue`)** | 0 | 774 (77.4%) | **+774 facts** |
| **- Operating Result (`operating_result`)** | 0 | 982 (98.2%) | **+982 facts** |
| **- Profit Before Tax (`profit_before_tax`)**| 0 | 962 (96.2%) | **+962 facts** |
| **- Net Profit (`annual_result`)** | 0 | 997 (99.7%) | **+997 facts** |
| **- Total Assets (`assets`)** | 0 | 997 (99.7%) | **+997 facts** |
| **- Total Equity (`equity`)** | 0 | 992 (99.2%) | **+992 facts** |
| **- Total Debt (`debt`)** | 0 | 956 (95.6%) | **+956 facts** |
| **- Currency (`currency`)** | 0 | 997 (99.7%) | **+997 facts** |
| **- Period From (`reporting_period_from`)** | 0 | 997 (99.7%) | **+997 facts** |
| **- Period To (`reporting_period_to`)** | 0 | 997 (99.7%) | **+997 facts** |
| **Network Requests Emitted** | 0 | 0 | **0** |
| **Outbound Bandwidth** | 0 bytes | 0 bytes | **0 bytes** |
| **Third-Party API Cost** | $0.00 | $0.00 | **$0.00** |
| **Batch Runtime** | - | 23.6s | Pure in-memory transformation |
| **Local Proxy v3 Score** | 54.869 | 54.869 | Unchanged (proxy checks evidence status only) |
| **Official 35-Pt Coverage Benefit** | Unsurfaced evidence | 9,651 verified facts | **Substantial official gain** (unverified by local proxy) |

---

## 7. Regression Checks

A full regression run across all existing test suites confirmed:
- `tests/test_financial_emission.py`: 9/9 passed
- `tests/test_official_workforce.py`: 5/5 passed
- `tests/test_ratings_reviews_audit.py`: 5/5 passed
- `tests/test_hiring_jobs_audit.py`: 6/6 passed
- `tests/test_freshness_and_breadth_audit.py`: 5/5 passed
- `tests/test_subunits.py`: 6/6 passed
- `tests/test_phase11_connectors.py`: 2/2 passed
- **Total Tests Passed**: 36 / 36 tests passed in 0.008s

### Invariants Preserved
- Website request count: unchanged
- External connector behavior: unchanged
- Workforce observations (337 BRREG observations): unchanged
- Social observations (43 verified handles): unchanged
- News observations (16 website posts): unchanged
- Exact identity gates: unchanged
- Terminal envelope schema: 100% compliant

---

## 8. Artifacts Created
- Module: `src/norway_company_agent/financial_emission.py`
- Test Suite: `tests/test_financial_emission.py`
- Audit JSON: `out/phase18-financial-emission-report.json`
- Full Report: `out/phase18-financial-emission-report.md`
- Updated Profiles: `out/profiles.jsonl`
- Updated Envelopes: `out/envelopes.jsonl`
- Updated Run Report: `out/run-report.json`
- Competition v3 Score: `out/phase18-competition-v3-score.json`
