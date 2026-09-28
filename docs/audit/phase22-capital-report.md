# Phase 22 — Emit Share Capital & Equity Registration Metadata

## 1. Executive Summary

Phase 22 deterministically propagates clean, retained official Brønnøysundregistrene (BRREG) share-capital and equity-registration metadata from `profile["evidence"]["registry"]["value"]` into explicit structured and top-level convenience fields across the frozen 1,000-company corpus (`out/profiles.jsonl` and `out/envelopes.jsonl`):

- **Canonical structured object**: `profile["capital"]` (`938 / 1,000` companies; `None` on the `59` companies without capital evidence and the `3` companies excluded by the CSV quote-shift safety guard)
- **Top-level convenience fields**:
  - `profile["share_capital"]` (`938 / 1,000` companies)
  - `profile["share_capital_currency"]` (`938 / 1,000` companies)
  - `profile["capital_registered_date"]` (`938 / 1,000` companies)
  - `profile["share_count"]` (`919 / 1,000` companies)
  - `profile["capital_type"]` (`938 / 1,000` companies: `924` `Aksjekapital`, `14` `Grunnkapital`)
- **Total verified capital facts emitted**: **`4,671` core facts + `27` sparse metadata facts = `4,698` total capital facts** across `938` companies.
- **Operations & Cost**: **0 network requests**, **0 outbound bytes**, **\$0.00 external API cost**, **28.35s** deterministic `--resume` rebuild.

---

## 2. Exact Capital Coverage (Before vs. After Phase 22)

| Capital Field | Structured Path | Top-Level Convenience Field | Source Evidence Key (`evidence.registry.value`) | Before | After | Coverage % | Missing / Excluded | Emitted Facts |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| Share capital amount | `capital.amount` | `share_capital` | `kapital.belop` | 0 | **938** | 93.8% | 62 | **938** |
| Share capital currency | `capital.currency` | `share_capital_currency` | `kapital.valuta` | 0 | **938** | 93.8% | 62 | **938** (`NOK`: 938) |
| Capital registered date | `capital.registered_date` | `capital_registered_date` | `kapital.innfortDato` | 0 | **938** | 93.8% | 62 | **938** |
| Total share count | `capital.share_count` | `share_count` | `kapital.antallAksjer` | 0 | **919** | 91.9% | 81 | **919** |
| Capital type | `capital.type` | `capital_type` | `kapital.type` | 0 | **938** | 93.8% | 62 | **938** (`Aksjekapital`: 924, `Grunnkapital`: 14) |
| Paid-in capital (sparse) | `capital.paid_in` | — | `kapital.innbetalt` | 0 | **14** | 1.4% | 986 | **14** |
| Fully paid-in flag (sparse) | `capital.fully_paid_in` | — | `kapital.fulltInnbetalt` | 0 | **13** | 1.3% | 987 | **13** (`True`: 13, `False`: 0) |
| Bound / restricted capital (sparse) | `capital.bound` | — | `kapital.bundet` | 0 | **0** | 0.0% | 1,000 | **0** |
| **Total Structured Capital** | `profile.capital` | 5 convenience fields | `evidence.registry.value` | **0** | **938 companies** | **93.8%** | **62** (`59` absent + `3` CSV-shifted) | **4,671 core / 4,698 total facts** |

---

## 3. CSV-Shift Safety Exclusions

Three bulk registry rows exhibit the Phase 20 CSV quote-shift corruption signature (unescaped quotes and commas in `vedtektsfestetFormaal` / `aktivitet` shifting columns $\ge 64$ rightward) and were **explicitly excluded** by `is_csv_quote_shifted`:

1. **`998600421` (`PRISMA CONSULT AS`)**: Excluded (`profile["capital"] = None`). In the raw bulk row, `kapital.belop` held `'2012-08-08'`, `kapital.valuta` held `'100'`, `kapital.innfortDato` held `'NOK'`, and `kapital.bundet` held `'30000.00'` (shifted from `kapital.belop`).
2. **`914882036` (`KULTURLANDRO AS`)**: Excluded (`profile["capital"] = None`). In the raw bulk row, `kapital.belop` held `' debattledelse'` and `kapital.innfortDato` held `'2015-01-29'` (shifted from an earlier date column).
3. **`926768026` (`THREE SOULS AS`)**: Excluded (`profile["capital"] = None`). In the raw bulk row, `kapital.belop` held `'2021-02-20'`, `kapital.valuta` held `'Aksjekapital'`, `kapital.type` held `'32000.00'`, and `kapital.bundet` held `'320'`.

**Corrupted or shifted capital values emitted**: **`0`**.

---

## 4. Data-Quality Findings

1. **Row-level CSV-shift guard is essential beyond field-level type validation**: On `914882036`, `kapital.innfortDato` contained `'2015-01-29'` (a syntactically valid ISO date shifted from an earlier column), and on `998600421` and `926768026`, `kapital.bundet` contained `'30000.00'` and `'320'` (valid numbers shifted from `kapital.belop` / `kapital.antallAksjer`). Field-level type validation alone would have emitted false facts for those companies; the row-level `is_csv_quote_shifted` check prevented all 3 false emissions.
2. **Non-integer cent precision in `kapital.belop` and `kapital.innbetalt`**: `15` of the `938` clean companies have non-`.00` decimal share-capital amounts (e.g., `122569.75`, `27864258.96`, `775057.05` NOK). Preserving `amount` and `paid_in` as `float` (while enforcing strict `int` on `share_count`) retains exact øre precision.
3. **Foundation (`STI`) with `paid_in == amount` but blank `fulltInnbetalt`**: All `14` companies with `kapital.innbetalt` are foundations (`STI`, `Grunnkapital`). On `977539366` (`SELVAAGS FOND TIL ALMENNYTTIGE FORMÅL STI`), both `kapital.belop` and `kapital.innbetalt` equal `800000.00`, but `kapital.fulltInnbetalt` is blank (`""`) in BRREG. In accordance with strict non-inference rules, `paid_in` is emitted as `800000.0` and `fully_paid_in` remains `None` (neither `True` nor `False`).
4. **Five older `AS` companies lack `kapital.antallAksjer` in BRREG**: Of the `19` capital-bearing companies without `share_count` (`938 - 919 = 19`), `14` are `Grunnkapital` foundations (`STI`) where shares do not exist, and `5` are older `AS` companies (`979346050`, `937418906`, `861401812`, `916070276`, `810059672`) where BRREG records `Aksjekapital` without `antallAksjer`. All `19` are emitted with `share_count = None`.

---

## 5. Competition Diagnostic & Regression Invariants

- **Local Competition Proxy v3 Score (`out/phase22-competition-v3-score.json`)**:
  - Phase 21 score: **`56.869 / 100.0`**
  - Phase 22 score: **`56.869 / 100.0`**
  - Difference: **`0.0` (`local score unchanged`)** — the local proxy v3 evaluator does not inspect `profile["capital"]` or the top-level share-capital convenience fields.
- **Regression Invariants**:
  - Phase 18 financials unchanged: `997 / 1,000` companies (`9,651` facts)
  - Phase 19 roles unchanged: `1,000 / 1,000` companies (`4,019` role records)
  - Phase 21 addresses/contact/dates unchanged: `business_address=998`, `postal_address=246`, `official_email=242`, `official_phone=182`, `official_mobile=182`, `registration_date=1000`, `foundation_date=991`, `articles_date=967`, `foretaksregisteret_date=974`, `foretaksregisteret_registered=1000`
  - Workforce, website, and external footprint observations unchanged
  - Wrong-company publications: `0`
  - Unsupported claims: `0`
  - Terminal validation: `PASS` (`1,000` profiles, `1,000` envelopes, `0` silent drops)
  - Refresh replay (`out/refresh-test.json`): `PASS` (`precision=1.0`, `recall=1.0`, `idempotent_rerun=true`)
  - Deterministic idempotent replay: `PASS`
- **Recommendation**: **ACCEPT Phase 22**.
