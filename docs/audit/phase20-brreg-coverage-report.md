# Phase 20 — Remaining BRREG Evidence Coverage & Evaluator Recognition Audit

## 1. Executive Summary

Phase 20 conducted a strictly read-only, zero-network-request audit across all 22 remaining official BRREG categories retained in `out/profiles.jsonl`, `out/envelopes.jsonl`, and `out/phase17-external-combined.jsonl` across the frozen 1,000-company corpus.

### Key Findings
1. **Local Evaluator Recognition Reality (`Step 10`)**:
   - All local scoring scripts (`scripts/score_competition_v3.py`, `scripts/score_company_completeness.py`, `scripts/evaluate_research_agent.py`, `src/norway_company_agent/research.py`, `src/norway_company_agent/refresh.py`) already score **14.988 / 15.0** on `official_company_foundation` and **10.0 / 10.0** on `research_agent` by inspecting `evidence.registry_live`, `evidence.financials`, `evidence.roles`, `evidence.locations`, and `evidence.website` directly.
   - **None** of the remaining unemitted BRREG categories (purpose/activity, share capital, registration dates, MVA/VAT, audit exemption, street/postal addresses, phone/email, secondary NACE, or corporate groups) are classified as **A (Directly recognized)** by the local evaluator scripts; all unemitted fields are **C (Not recognized by local evaluator)**, while their exact weight in the hidden official 35-point Information Coverage judge is **D (Unknown)**.
2. **Over 15,000 Verified Official Facts Remain Trapped in `evidence.*`**:
   - Beyond Phase 18 financials (9,651 facts) and Phase 19 roles (4,019 records), the corpus retains **15,785+ clean, entity-anchored facts** inside `evidence.registry.value`, `evidence.registry_live.value`, `evidence.locations.value`, and `evidence.group.value` at zero network cost.
3. **Two Critical Data-Integrity Hazards Discovered Before Any Future Emission**:
   - **Hazard 1 — CSV Quote-Shift in 3 Bulk Registry Rows**: In `evidence.registry.value`, 3 companies (`998600421`, `914882036`, `926768026`) contain embedded quotes and commas inside `vedtektsfestetFormaal` (column 64) or `aktivitet` (column 65). Because `csv.Sniffer` split on those commas, all columns from index 64 onward (`vedtektsfestetFormaal`, `aktivitet`, `fravalgRevisjonDato`, `erIKonsern`, `kapital.*`) are shifted right for those 3 rows (detectable via `"null" in evidence["registry"]["value"]`). All columns prior to index 64 (0–63, including identity, NACE 1/2/3, contact info, addresses, registration/foundation/articles/MVA dates) are 100% unshifted across all 1,000 companies.
   - **Hazard 2 — Corporate Group Tree Rooted at Ultimate Parent**: In `evidence.group.value` (70 companies), BRREG's `/api/konsernstruktur/{org}` endpoint returns the **entire corporate group tree starting from the ultimate parent (`val["organisasjonsnummer"]`)**. For **50 of the 70 companies**, the profile company is a **subsidiary** inside the tree (`val["organisasjonsnummer"] != profile["organisation_number"]`), and **860 of the 902 child nodes** across the 70 trees belong to parent/sister/cousin companies rather than the profile company. Only **42 child records across 23 companies** have `parentOrganisasjonsnummer == profile["organisation_number"]`.

---

## 2. Step 1 — Current Output Contract & Field Mapping

| Retained Evidence Path | Current Emitted Top-Level Field | Terminal Envelope Representation | Local Evaluator Recognition |
|---|---|---|---|
| `evidence.registry.value.organisasjonsnummer` / `evidence.registry_live.value.organisation_number` | `profile["organisation_number"]` (1,000) | `envelope["organisation_number"]` & `envelope["profile"]["organisation_number"]` | **A (Directly recognized)**: `score_competition_v3.py` (`official_identity`), `score_company_completeness.py`, `research.py`, `refresh.py`, `validate_envelopes` |
| `evidence.registry.value.navn` / `evidence.registry_live.value.name` | `profile["name"]` (1,000) | `envelope["profile"]["name"]` | **A (Directly recognized)**: `research.py` (`Registered name`), `refresh.py` (`registry.name`), `build_prototype.py` |
| `evidence.registry.value["organisasjonsform.kode"]` / `evidence.registry_live.value.legal_form` | `profile["legal_form"]` (1,000) | `envelope["profile"]["legal_form"]` | **A (Directly recognized)**: `research.py` (`legal_form` screen & QA), `refresh.py` (`registry.legal_form`) |
| `evidence.registry.value.antallAnsatte` / `evidence.registry_live.value.employees` | `profile["employees"]` (143) + `out/phase17-external-combined.jsonl` (143 entity + 194 subunit `workforce_snapshot` obs) | `envelope["profile"]["employees"]` | **A (Directly recognized)**: `evaluate_external_footprint.py` (`workforce_jobs`), `research.py` (`employees` filter/sort/QA), `refresh.py` (`registry.employees`) |
| `evidence.registry.value.konkurs` & `underAvvikling` | `profile["bankrupt"]` (1,000) & `profile["liquidating"]` (1,000) | `envelope["profile"]["bankrupt"]` & `liquidating` | **B (Indirectly used)**: `build_prototype.py` (`adverse` flag) |
| `evidence.registry.value["forretningsadresse.kommune"]` & `kommunenummer` | `profile["municipality"]` (996) & `profile["municipality_number"]` (996) | `envelope["profile"]["municipality"]` & `municipality_number` | **A (Directly recognized)**: `research.py` (`municipality` filter & QA), `refresh.py` (`registry.municipality`) |
| `evidence.registry.value["naeringskode1.kode"]` & `beskrivelse` | `profile["industry_code"]` (1,000) & `profile["industry_label"]` (1,000) | `envelope["profile"]["industry_code"]` & `industry_label` | **A (Directly recognized)**: `research.py` (`industry` filter), `build_prototype.py` |
| `evidence.registry.value.hjemmeside` / `evidence.registry_live.value.website` | `profile["website"]` (107 non-empty) | `envelope["profile"]["website"]` & `envelope["modules"]["website"]` | **A (Directly recognized)**: `score_competition_v3.py` (`website_seed_and_terminal_state`), `research.py`, `refresh.py` (`registry.website`) |
| `evidence.registry.value.sisteInnsendteAarsregnskap` | `profile["latest_submitted_accounts"]` (1,000) | `envelope["profile"]["latest_submitted_accounts"]` | **A (Directly recognized)**: `refresh.py` (`registry.latest_submitted_accounts`), `build_prototype.py` |
| `evidence.financials.value.records` (Phase 18) | `profile["financials"]` (997) + 10 top-level scalar fields (`revenue`, `operating_result`, `profit_before_tax`, `annual_result`, `assets`, `equity`, `debt`, `currency`, `reporting_period_from`, `reporting_period_to`) | `envelope["modules"]["financials"]` & `envelope["profile"]["financials"]` + top-level scalars | **A via `evidence.financials`** (`score_competition_v3.py`, `research.py`, `refresh.py`); **C** for top-level convenience fields in local proxy |
| `evidence.roles.value.roles` (Phase 19) | `profile["roles"]` (1,000; 4,019 records) + 6 convenience fields (`board_chair`, `managing_director`, `board_members`, `deputy_board_members`, `auditors`, `authorized_accountants`) | `envelope["modules"]["roles"]` & `envelope["profile"]["roles"]` + convenience fields | **A via `evidence.roles`** (`score_competition_v3.py`, `research.py`, `refresh.py`); **C** for top-level convenience fields in local proxy |
| `evidence.locations.value.locations` | Not emitted at top level (only in `evidence.locations` and workforce observations) | `envelope["modules"]["locations"]` & `envelope["profile"]["evidence"]["locations"]` | **A via `evidence.locations`** (`score_competition_v3.py`, `research.py`, `refresh.py`) and **A via workforce observations** (`evaluate_external_footprint.py`) |

---

## 3. Step 2 — Corporate Purpose & Operational Activity Audit

| Field | Evidence Path | Raw Non-Empty | Clean (Unshifted) | Shifted / Corrupted | Missing | Currently Emitted? | Local Evaluator |
|---|---|---:|---:|---:|---:|---|---|
| **Statutory Purpose (`vedtektsfestetFormaal`)** | `evidence.registry.value.vedtektsfestetFormaal` | 966 | **963** | 3 | 34 | No | **C** (Not recognized) |
| **Operational Activity (`aktivitet`)** | `evidence.registry.value.aktivitet` | 1,000 | **997** | 3 | 0 | No | **C** (Not recognized) |

- **Terminal Envelope Representation**: Retained only inside `envelope["profile"]["evidence"]["registry"]["value"]`.
- **Score Contribution**: `0.0` in local evaluator (`research.py` only inspects `evidence.website.value.description` for descriptions and `industry_code`/`industry_label` for industry).
- **Information-Coverage Relevance**: High conceptual relevance for official company profile completeness (statutory objects and registered business activity), provided the 3 quote-shifted bulk CSV rows (`998600421`, `914882036`, `926768026`) are excluded or set to `None`.

---

## 4. Step 3 — Capital & Equity-Registration Audit

| Field | Evidence Path | Raw Non-Empty | Valid Typed Facts | Shifted / Invalid | Missing | Currently Emitted? | Local Evaluator |
|---|---|---:|---:|---:|---:|---|---|
| **Share Capital Amount (`kapital.belop`)** | `evidence.registry.value["kapital.belop"]` | 941 | **938** (valid float) | 3 (`"2012-08-08"`, `" debattledelse"`, `"2021-02-20"`) | 59 | No | **C** |
| **Share Capital Currency (`kapital.valuta`)** | `evidence.registry.value["kapital.valuta"]` | 941 | **938** (`"NOK"`) | 3 (`"100"`, `"false"`, `"Aksjekapital"`) | 59 | No | **C** |
| **Capital Registration Date (`kapital.innfortDato`)** | `evidence.registry.value["kapital.innfortDato"]` | 940 | **938** (unshifted ISO date) | 2 (`"NOK"` in `998600421`, shifted date in `914882036`) | 60 | No | **C** |
| **Total Share Count (`kapital.antallAksjer`)** | `evidence.registry.value["kapital.antallAksjer"]` | 921 | **919** (valid int) | 2 (`" investeringsvirksomhet..."`, `"false"`) | 79 | No | **C** |
| **Capital Type (`kapital.type`)** | `evidence.registry.value["kapital.type"]` | 941 | **938** (`924` Aksjekapital, `14` Grunnkapital) | 3 (`"false"`, `" samt..."`, `"32000.00"`) | 59 | No | **C** |
| **Paid-In / Bound Capital (`innbetalt`, `fulltInnbetalt`, `bundet`)** | `evidence.registry.value["kapital.*"]` | 15 / 14 / 3 | **15 / 13 / 2** | 0 / 1 / 1 | 985+ | No | **C** |

- **Total Clean Capital Facts**: **4,671** valid facts across **938** companies (5 main fields) or **4,701** including sparse paid-in fields.
- **Fact vs. Inference Discipline**: Share price (`belop / antallAksjer`) and ownership percentages are **never** calculated or inferred.

---

## 5. Step 4 — Corporate Registration Dates Audit

| Date Category | Evidence Path | Companies Covered | Valid ISO Dates (`YYYY-MM-DD`) | Missing | Tied to Reporting Period? | Currently Emitted? | Local Evaluator |
|---|---|---:|---:|---:|---|---|---|
| **Enhetsregisteret Registration Date** | `evidence.registry.value.registreringsdatoenhetsregisteret` | **1,000** | **1,000** (100.0%) | 0 | No (point-in-time statutory registration) | No | **C** |
| **Foundation / Incorporation Date** | `evidence.registry.value.stiftelsesdato` | **991** | **991** (99.1%) | 9 | No (point-in-time incorporation date) | No | **C** |
| **Articles-of-Association Date** | `evidence.registry.value.vedtektsdato` | **967** | **967** (96.7%) | 33 | No (date of current statutory articles) | No | **C** |
| **Foretaksregisteret Registration Date** | `evidence.registry.value.registreringsdatoForetaksregisteret` | **974** | **974** (97.4%) | 26 | No (point-in-time register entry; boolean `registrertIForetaksregisteret` is 1,000/1,000) | No | **C** |

- **Column Shift Immunity**: All 4 registration dates occupy CSV columns `37`, `38`, `47`, and `63`—all strictly **before** column `64` (`vedtektsfestetFormaal`). Every single non-empty value across all 1,000 profiles is a valid `YYYY-MM-DD` date (`3,932` date facts total, plus `1,000` boolean `registrertIForetaksregisteret` facts).

---

## 6. Step 5 — MVA / VAT & Audit Exemption Audit

| Category | Evidence Path | Raw Non-Empty | Clean / Valid Facts | Shifted / Invalid | Missing | Currently Emitted? | Local Evaluator |
|---|---|---:|---:|---:|---:|---|---|
| **MVA Registration Status** | `evidence.registry.value.registrertIMvaRegisteret` | 1,000 | **1,000** (`507` true, `493` false) | 0 | 0 | No | **C** |
| **MVA Registration Date** | `evidence.registry.value.registreringsdatoMerverdiavgiftsregisteret` | 507 | **507** (`YYYY-MM-DD`) | 0 | 493 | No | **C** |
| **MVA Enhetsregisteret Date** | `evidence.registry.value.registreringsdatoMerverdiavgiftsregisteretEnhetsregisteret` | 507 | **507** (`YYYY-MM-DD`) | 0 | 493 | No | **C** |
| **Voluntary MVA Registration** | `evidence.registry.value.frivilligMvaRegistrertBeskrivelser` & `...Dato` | 94 | **94** descriptions + **94** dates | 0 | 906 | No | **C** |
| **Audit Exemption Date (`fravalgRevisjonDato`)** | `evidence.registry.value.fravalgRevisjonDato` | 638 | **636** (`YYYY-MM-DD`) | 2 (`"false"`, `" herunder..."`) | 362 | No | **C** |
| **Audit Exemption Decision Date (`fravalgRevisjonBeslutningsDato`)** | `evidence.registry.value.fravalgRevisjonBeslutningsDato` | 437 | **436** (`YYYY-MM-DD`) | 1 (`""`/shifted) | 563 | No | **C** |

- **Note on MVA Fields**: All MVA fields sit at CSV columns `39–43` (before column `64`), so they have zero CSV shift corruption.
- **Note on Audit Exemption Fields**: Columns `69–70` sit after column `64`, so 2 of the 3 shifted rows put non-date strings into `fravalgRevisjonDato`. Validating `^\d{4}-\d{2}-\d{2}$` cleanly isolates the **636** valid audit exemption dates and **436** decision dates.

---

## 7. Step 6 — Addresses & Official Contact Information Audit

| Category | Evidence Path(s) | Companies Covered | Individual Facts | Currently Emitted at Top Level? | Local Evaluator | Duplication Analysis |
|---|---|---:|---:|---|---|---|
| **Registered Business Address** | `evidence.registry_live.value.business_address` (structured dict) & `evidence.registry.value["forretningsadresse.*"]` | **998** | **6,969** component facts (`991` street, `996` postal code, `998` city, `996` muni, `996` muni code, `998` country, `998` country code) | Only `municipality` (996) and `municipality_number` (996) | **A** for `municipality`; **C** for street/postal code/city | Street address (`adresse`), `postnummer`, and `poststed` are **not** at top level; only in `evidence`. |
| **Postal Address** | `evidence.registry_live.value.postal_address` (structured dict) & `evidence.registry.value["postadresse.*"]` | **246** | **1,715** component facts (`245` street/box, `242` postal code, `246` city, `242` muni, `242` muni code, `246` country, `246` country code) | No | **C** | Covers the **2** companies lacking a business address (`993803308`, `974811871`), giving **1,000 / 1,000** combined address coverage. |
| **Official Registered Email** | `evidence.registry.value.epostadresse` | **242** | **242** | No | **C** | Not emitted anywhere outside `evidence.registry.value`. |
| **Official Registered Phone (`telefon`)** | `evidence.registry.value.telefon` | **182** | **182** | No | **C** | Not emitted anywhere outside `evidence.registry.value`. |
| **Official Registered Mobile (`mobil`)** | `evidence.registry.value.mobil` | **182** | **182** | No | **C** | **315** companies have `telefon` OR `mobil` (`49` have both); **357** companies have at least one official contact channel (`email`, `telefon`, or `mobil`). |
| **Municipality & Code** | `profile["municipality"]` & `profile["municipality_number"]` | **996** | **1,992** | **Yes** (`municipality`, `municipality_number`) | **A** (`research.py`, `refresh.py`, `build_prototype.py`) | Already emitted at top level; 2 additional companies (`993803308` KONGSBERG) have municipality in `postal_address`. |

---

## 8. Step 7 — Subunits / Establishments / Workplaces Audit

- **Evidence Path**: `profile["evidence"]["locations"]["value"]["locations"]` (sourced from `brreg-underenheter.csv` via `src/norway_company_agent/subunits.py`) and `out/phase17-external-combined.jsonl` (`brreg-workforce-subunit-*`).
- **Quantitative Measurements across 1,000 Companies**:
  - Companies with `evidence.locations.status == "available"`: **1,000 / 1,000**
  - Companies with $\ge 1$ active subunit: **747** (253 companies have `0` subunits, i.e., `locations: []`)
  - Total active subunits retained: **876**
  - Subunit organisation numbers (`organisation_number`): **876** (100% of subunits)
  - Establishment names (`name`): **876** (100% of subunits)
  - Subunit addresses (`address` with street/postal/city): **876** (100% of subunits)
  - Subunit municipality & code (`kommune` & `kommunenummer`): **873** (99.7% of subunits)
  - Subunit NACE (`industry.kode` & `industry.beskrivelse`): **869** (99.2% of subunits)
  - Subunit employee counts (`employees` integer $\ge 0$): **194** subunits across **142** companies
  - Active/inactive status: Inactive/closed subunits (`nedleggelsesdato` non-empty in `brreg-underenheter.csv`) are filtered out at bulk load (`src/norway_company_agent/subunits.py:83`); all 876 retained subunits are active.
- **How Subunit Information is Counted by the Local Evaluator**:
  - Classification: **D (workforce/location evidence)** + **B (individual cited facts in research Q&A)**.
  - `scripts/score_competition_v3.py`: Checks `"locations" in row.get("evidence", {})` for `official_company_foundation.roles_and_locations` (`4.0 / 4.0` pts), and scores the 194 subunit `workforce_snapshot` observations in `external_footprint_intelligence.workforce_and_jobs` (`1.001 / 7.0` pts across 143 companies).
  - `scripts/score_company_completeness.py`: Checks `module_present(evidence, "locations")` for `5.0 / 5.0` foundation points.
  - `src/norway_company_agent/research.py`: Emits up to 12 `"Registered subunit"` facts (`name` and `address`) per company from `evidence.locations.value.locations` during single-company Q&A.
  - `src/norway_company_agent/refresh.py`: Tracks `("evidence", "locations", "value", "locations")` as `locations.locations`.
  - Subunits are **never** treated as separate top-level company entities (`C` is false).

---

## 9. Step 8 — Secondary NACE Classifications Audit

| Classification | Evidence Path | Companies | Facts (Code + Label) | Currently Emitted? | Local Evaluator |
|---|---|---:|---:|---|---|
| **Primary NACE (`naeringskode1`)** | `evidence.registry.value["naeringskode1.*"]` & `evidence.registry_live.value.industry` | **1,000** | **2,000** | **Yes** (`industry_code`, `industry_label`) | **A** (`research.py` industry screen, `build_prototype.py`) |
| **Secondary NACE 2 (`naeringskode2`)** | `evidence.registry.value["naeringskode2.kode"]` & `beskrivelse` | **16** | **32** (16 codes + 16 labels) | No | **C** (`research.py` only inspects `industry_code` and `industry_label`) |
| **Tertiary NACE 3 (`naeringskode3`)** | `evidence.registry.value["naeringskode3.kode"]` & `beskrivelse` | **2** | **4** (2 codes + 2 labels) | No | **C** |
| **Ancillary Unit Code (`hjelpeenhetskode`)** | `evidence.registry.value["hjelpeenhetskode.kode"]` & `beskrivelse` | **74** | **148** (74 codes + 74 labels) | No | **C** |

---

## 10. Step 9 — Corporate Group (`evidence.group`) Audit

- **Evidence Paths**: `profile["evidence"]["group"]["value"]` (from BRREG `/api/konsernstruktur/{org}`) and `profile["evidence"]["registry"]["value"]["erIKonsern"]`.
- **Coverage across 1,000 Companies**:
  - `evidence.group.status == "available"`: **70** companies (`930` have `status == "not_found"`).
  - `erIKonsern` in bulk CSV: `70` `"true"`, `927` `"false"`, `3` shifted rows.
- **Tree Structure & Entity-Safety Breakdown across the 70 Companies**:
  - **Profile Company is Ultimate Parent (`val["organisasjonsnummer"] == profile["organisation_number"]`)**: **20** companies.
  - **Profile Company is a Subsidiary in the Group Tree (`val["organisasjonsnummer"] != profile["organisation_number"]`)**: **50** companies (all **50** have an explicit direct parent `parentOrganisasjonsnummer` and `parentNavn`, plus ultimate parent `val["organisasjonsnummer"]` and `val["navn"]`).
  - **Profile Company Has Direct Subsidiaries (`parentOrganisasjonsnummer == profile["organisation_number"]`)**: **23** companies (20 ultimate parents + 3 intermediate holding subsidiaries) owning **42** direct subsidiary records.
  - **Direct Subsidiary Metadata Completeness**: All **42 / 42** direct subsidiary records contain `organisasjonsnummer`, `navn`, `parentOrganisasjonsnummer`, `grunnlag` (ownership percentage, e.g., `"100%"`, `"100 %"`, `"51%"`), `dato`, and `organisasjonsform`.
  - **Non-Direct Nodes in Retained Group Trees**: Out of **902** total child nodes across the 70 trees, **860** nodes belong to other parent companies in the same corporate group (sister companies, cousins, or deeper sub-subsidiaries).
- **Current Output Representation & Evaluator Recognition**:
  - Not emitted at top level (`profile["group"]` does not exist).
  - Retained in `envelope["profile"]["evidence"]["group"]` (note: `"group"` is not in `envelope["modules"]` default 7-module list).
  - Local Evaluator Recognition: **C (Not recognized)** by `score_competition_v3.py`, `score_company_completeness.py`, `research.py`, and `refresh.py`.

---

## 11. Step 10 — Local Evaluator Recognition Matrix

| Evaluator Component | Script / Module | Exact Fields Inspected | Classification of Remaining Unemitted BRREG Fields |
|---|---|---|---|
| **Official Company Foundation (15 pts)** | `scripts/score_competition_v3.py` | `evidence.registry_live.value.organisation_number == organisation_number` (4 pts), `evidence.financials.status == "available"` (4 pts), `"roles"` & `"locations"` in `evidence` (4 pts), `"website"` in `evidence` (3 pts) | **C (Not recognized)** — already at `14.988 / 15.0` ceiling (only 3 companies lack official financials in BRREG). |
| **All-Source Completeness v1 (30 foundation pts)** | `scripts/score_company_completeness.py` | Same 5 `evidence` module checks (`official_identity`, `annual_accounts`, `roles`, `locations`, `website_terminal_state`) | **C (Not recognized)** — already at `29.97 / 30.0` foundation mean. |
| **External Footprint Intelligence (55 pts)** | `scripts/evaluate_external_footprint.py` | Reads `out/phase17-external-combined.jsonl` (`platform`, `signal_type`, `effective_at`, `sentiment_label`, `rights_status`, `acquisition_mode`). Includes 143 entity + 194 subunit BRREG `workforce_snapshot` observations. | **A for BRREG workforce/subunit employee counts** (already emitted in Phase 14); **C** for all other BRREG fields. |
| **Research Agent (10 pts)** | `scripts/evaluate_research_agent.py` & `src/norway_company_agent/research.py` | Top-level `name`, `organisation_number`, `legal_form`, `municipality`, `employees`, `industry_code`, `industry_label`; plus `evidence.financials.value.records[0]`, `evidence.roles.value.roles`, `evidence.locations.value.locations`, `evidence.website.value` | **A for primary NACE, municipality, employees, roles, locations, financials**; **C** for purpose, activity, capital, dates, MVA, audit exemption, contact info, secondary NACE, and group. Already scores `10.0 / 10.0` (`12/12` raw). |
| **Daily Extensibility & Refresh (12 pts)** | `scripts/run_refresh_replay.py` & `src/norway_company_agent/refresh.py` | `TRACKED_FIELDS`: top-level `name`, `legal_form`, `employees`, `municipality`, `website`, `latest_submitted_accounts`, plus `evidence` paths for `financials.records`, `financial_history.years`, `roles.roles`, `locations.locations`, `website.*` | **C (Not recognized)** for remaining unemitted BRREG fields. |
| **Product UX Design (8 pts)** | `scripts/build_prototype.py` | Top-level identity/industry/municipality/employees/website/adverse fields + `evidence` modules | **C (Not recognized)** — already scores `8.0 / 8.0`. |
| **Official 35-Point Information Coverage Judge** | External organizer evaluation | Evaluates company coverage and fact counts across company profile categories on hidden/submission corpora | **D (Unknown exact field weights)** — Phase 18 (financials) and Phase 19 (roles) surfaced top-level facts for this judge. |

---

## 12. Step 12 — Existing-But-Not-Emitted Inventory (Avoiding Phase 18/19 Double Count)

The following retained BRREG facts are currently trapped inside `evidence.*` (excluding Phase 18 financials and Phase 19 roles):

1. `evidence.registry_live.value.business_address`: **998** companies (**6,969** address component facts; only `municipality` and `municipality_number` are at top level; street `adresse` [991], `postnummer` [996], `poststed` [998], `land` [998], `landkode` [998] are unemitted).
2. `evidence.registry_live.value.postal_address`: **246** companies (**1,715** address component facts; covers the 2 companies without `business_address` for **1,000 / 1,000** combined address coverage).
3. `evidence.registry.value.epostadresse`: **242** companies (**242** official email facts).
4. `evidence.registry.value.telefon` & `mobil`: **315** companies (**182** `telefon` + **182** `mobil` = **364** phone/mobile facts; **357** companies have email or phone/mobile).
5. `evidence.registry.value.registreringsdatoenhetsregisteret`: **1,000** companies (**1,000** valid ISO date facts).
6. `evidence.registry.value.stiftelsesdato`: **991** companies (**991** valid ISO date facts).
7. `evidence.registry.value.registreringsdatoForetaksregisteret` & `registrertIForetaksregisteret`: **974** valid ISO date facts + **1,000** boolean status facts.
8. `evidence.registry.value.vedtektsdato`: **967** companies (**967** valid ISO date facts).
9. `evidence.registry.value.aktivitet`: **997** clean unshifted companies (**997** operational activity facts; 3 shifted).
10. `evidence.registry.value.vedtektsfestetFormaal`: **963** clean unshifted companies (**963** statutory purpose facts; 3 shifted).
11. `evidence.registry.value["kapital.*"]`: **938** clean unshifted companies (**938** `belop` + **938** `valuta` + **938** `innfortDato` + **919** `antallAksjer` + **938** `type` = **4,671** core capital facts, plus **30** paid-in/bound capital facts).
12. `evidence.registry.value.registrertIMvaRegisteret` & MVA dates: **1,000** boolean status facts + **507** MVA registration dates + **507** MVA Enhetsregisteret dates + **94** voluntary MVA descriptions + **94** voluntary MVA dates (**2,202** MVA facts).
13. `evidence.registry.value.fravalgRevisjonDato` & `fravalgRevisjonBeslutningsDato`: **636** valid audit-exemption dates + **436** valid decision dates (**1,072** audit-exemption facts).
14. `evidence.registry.value["naeringskode2.*"]`, `["naeringskode3.*"]`, `["hjelpeenhetskode.*"]`: **16** NACE2 companies (**32** facts), **2** NACE3 companies (**4** facts), **74** ancillary unit companies (**148** facts).
15. `evidence.locations.value.locations`: **747** companies with $\ge 1$ active subunit (**876** subunits; **5,437** component facts: `876` org numbers, `876` names, `876` addresses, `873` municipalities, `873` municipality codes, `869` NACE codes/labels, `194` employee counts). Already recognized in `evidence.locations` and workforce observations, but not mirrored to a top-level `profile["subunits"]` / `profile["locations"]` list.
16. `evidence.group.value`: **70** companies (**20** ultimate parents, **50** subsidiaries with direct/ultimate parent links, **23** companies with **42** direct subsidiary records containing ownership `%` and registration dates).

---

## 13. Step 11 — Priority Matrix

| Category | Companies | Clean Facts | Retained | Currently Emitted at Top Level | Evaluator Recognizes? | Current Score Component | Network Needed | Cost | Compliance / Integrity Risk | Priority |
|---|---:|---:|---|---|---|---|---:|---:|---|---|
| **12–13. Business & Postal Addresses** | 1,000 | 8,684 (or 1,998 street/postal/city) | `evidence.registry_live.value` & `registry.value` | Partial (`municipality` only) | **A** (muni) / **C** (street, postal) / **D** (official) | Foundation / Research (muni) | 0 | \$0.00 | **Zero CSV-shift risk** (clean JSON in `registry_live`) | **P1 (High)** |
| **6–9. Corporate Registration Dates (4 dates)** | 1,000 | 3,932 (+1,000 Foretaksreg flag) | `evidence.registry.value` (cols 37, 38, 47, 63) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Zero CSV-shift risk** (all cols < 64; 100% ISO dates) | **P1 (High)** |
| **14–15. Official Email & Phone/Mobile** | 357 | 606 (`242` email, `182` tel, `182` mob) | `evidence.registry.value` (cols 17–19) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Zero CSV-shift risk** (cols 17–19 < 64; official BRREG contact) | **P1 (High)** |
| **3–5. Share Capital & Share Count** | 938 | 4,671 (`belop`, `valuta`, `innfortDato`, `antallAksjer`, `type`) | `evidence.registry.value` (cols 72–79) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Low if guarded**: 3 CSV-shifted rows must be excluded via type/null check | **P2 (Medium-High)** |
| **1–2. Corporate Purpose & Activity** | 997 | 1,960 (`963` purpose, `997` activity) | `evidence.registry.value` (cols 64–65) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Low if guarded**: 3 CSV-shifted rows (`"null"` key present) must be set to `None` | **P2 (Medium-High)** |
| **10–11. MVA/VAT & Audit Exemption** | 1,000 | 3,274 (`2,202` MVA + `1,072` audit exemption) | `evidence.registry.value` (cols 39–43, 69–70) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Low**: MVA cols unshifted; `fravalgRevisjon*` guarded by ISO date check | **P3 (Medium)** |
| **16–19. Top-Level Subunits Mirror** | 747 | 5,437 (across 876 active subunits) | `evidence.locations.value.locations` | No (in `evidence.locations` & workforce obs) | **A/D** via `evidence.locations` & workforce obs | `roles_and_locations` (4/4), `workforce_jobs` (1.001/7) | 0 | \$0.00 | **Zero risk**, but already surfaced in `evidence.locations` and workforce obs | **P3 (Medium)** |
| **22. Corporate Group (`evidence.group`)** | 70 | 162 (`50` parent links, `42` direct subsidiaries) | `evidence.group.value` | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Moderate**: Must filter `parentOrganisasjonsnummer == org` to avoid attributing 860 sister/cousin nodes | **P4 (Low)** |
| **21. Secondary NACE (`naeringskode2/3`)** | 16 | 36 (`32` NACE2, `4` NACE3) | `evidence.registry.value` (cols 6–9) | No | **C** (local) / **D** (official) | None locally | 0 | \$0.00 | **Zero risk**, but very low company coverage (1.6%) | **P4 (Low)** |

---

## 14. Step 13 — Top 3 Future Implementation Candidates

### Candidate 1: Structured Official Addresses, Registered Contact Channels & Core Registration Dates
- **Exact Fields to Expose**:
  - `profile["business_address"]` (from `evidence.registry_live.value.business_address`: 998 companies)
  - `profile["postal_address"]` (from `evidence.registry_live.value.postal_address`: 246 companies; combined 1,000/1,000 address coverage)
  - `profile["email"]` (`epostadresse`: 242 companies), `profile["phone"]` (`telefon`: 182 companies), `profile["mobile"]` (`mobil`: 182 companies)
  - `profile["foundation_date"]` (`stiftelsesdato`: 991 companies), `profile["registration_date"]` (`registreringsdatoenhetsregisteret`: 1,000 companies), `profile["articles_date"]` (`vedtektsdato`: 967 companies), `profile["foretaksregisteret_date"]` (`registreringsdatoForetaksregisteret`: 974 companies)
- **Companies & Facts Affected**: **1,000 companies** and **6,199+ structured facts**.
- **Evaluator Component Affected**: Does not alter the local proxy v3 score (already `14.988/15` foundation), but directly populates foundational company-profile fields (full street/postal address, official phone/email, incorporation/registration dates) commonly inspected by official 35-point Information Coverage evaluators.
- **Implementation Complexity & Risk**: **Very Low**. All fields come from either clean JSON (`registry_live.value`) or CSV columns `17–47` and `63` (strictly prior to column `64`, so **0 rows** are affected by CSV quote-shifting). Zero network requests, `\$0.00` cost, zero interference with existing fields.

### Candidate 2: Share Capital & Equity Registration Metadata (with Strict Type & Shift Guards)
- **Exact Fields to Expose**:
  - `profile["share_capital"]` (float from `kapital.belop`: 938 companies)
  - `profile["share_capital_currency"]` (`kapital.valuta`: 938 companies)
  - `profile["share_count"]` (int from `kapital.antallAksjer`: 919 companies)
  - `profile["capital_registered_date"]` (`kapital.innfortDato`: 938 companies)
  - `profile["capital_type"]` (`kapital.type`: 938 companies)
  - Structured `profile["capital"]` object containing these fields plus provenance metadata.
- **Companies & Facts Affected**: **938 companies** and **4,671 verified facts**.
- **Evaluator Component Affected**: Targets the official 35-point Information Coverage dimension (capital/equity structure).
- **Implementation Complexity & Risk**: **Low**, provided the emitter enforces a strict guard: if `"null" in evidence["registry"]["value"]` (the 3 shifted CSV rows `998600421`, `914882036`, `926768026`) or if numeric/currency/ISO-date validation fails, emit `None`. Zero network requests, `\$0.00` cost.

### Candidate 3: Statutory Purpose, Operational Activity, MVA Status & Audit Exemption (with Unshifted Guard)
- **Exact Fields to Expose**:
  - `profile["purpose"]` (`vedtektsfestetFormaal`: 963 clean companies)
  - `profile["activity"]` (`aktivitet`: 997 clean companies)
  - `profile["vat_registered"]` (bool from `registrertIMvaRegisteret`: 1,000 companies) & `profile["vat_registration_date"]` (`registreringsdatoMerverdiavgiftsregisteret`: 507 companies)
  - `profile["audit_exemption_date"]` (`fravalgRevisjonDato`: 636 valid ISO date companies) & `profile["audit_exemption_decision_date"]` (`fravalgRevisjonBeslutningsDato`: 436 valid ISO date companies)
- **Companies & Facts Affected**: **1,000 companies** and **4,103+ verified facts**.
- **Implementation Complexity & Risk**: **Low**, provided the emitter sets `purpose`, `activity`, and `audit_exemption_*` to `None` for the 3 CSV-shifted rows (`"null" in evidence["registry"]["value"]`) and validates `YYYY-MM-DD` on date fields. Zero network requests, `\$0.00` cost.

---

## 15. Compliance & Risk Analysis

1. **Zero Network / Zero Cost**: All 22 audited categories are already retained on disk in `out/profiles.jsonl`. Emitting any subset requires `0` HTTP requests and `\$0.00` third-party cost.
2. **CSV Quote-Shift Protection**: The 3 bulk CSV rows (`998600421`, `914882036`, `926768026`) where embedded quotes caused column shifting after column 64 are 100% identifiable via `"null" in profile["evidence"]["registry"]["value"]` and strict regex/type validation (`^\d{4}-\d{2}-\d{2}$` for dates, numeric float/int checks for capital).
3. **Corporate Group Entity-Anchoring Protection**: If `evidence.group` is ever emitted in the future, it must never emit `val["children"]` blindly, because 50 of the 70 companies are subsidiaries whose `evidence.group.value` root is the ultimate parent. Any future group emitter must filter `node["parentOrganisasjonsnummer"] == profile["organisation_number"]` for direct subsidiaries (42 records across 23 companies) and `node["organisasjonsnummer"] == profile["organisation_number"]` for the company's own direct parent (50 companies).
4. **Refresh & Evaluator Non-Interference**: None of `TRACKED_FIELDS` in `src/norway_company_agent/refresh.py` or the filter grammar in `src/norway_company_agent/research.py` are altered by adding new top-level profile fields, preserving 100% idempotent refresh replay and research Q&A scores.

---

## 16. Step 14 — Invariant Verification

All audit invariants were verified via read-only inspection:
- **Production source files unchanged**: `True` (`git status` / source tree untouched during Phase 20)
- **Network requests made**: `0`
- **Corpus files unchanged**: `out/profiles.jsonl` (1,000 profiles), `out/envelopes.jsonl` (1,000 envelopes), and `out/phase17-external-combined.jsonl` (396 observations) are completely unmodified.
- **Phase 18 Financials Unchanged**: `997` companies with `profile["financials"]`, `774` with `revenue`, `9,651` top-level financial facts.
- **Phase 19 Roles Unchanged**: `1,000` companies with `profile["roles"]`, `4,019` role records, `986` `board_chair`, `648` `managing_director`.
- **External Observations Unchanged**: `143` entity workforce, `194` subunit workforce, `43` social handles, `16` website activity/news observations.

---

## 17. Final Recommendation

1. **Acknowledge Local Proxy Saturation**: The local proxy evaluator (`score_competition_v3.py`) is already at its official-foundation ceiling (`14.988 / 15.0`) and does not score additional BRREG fields (`Category C` locally, `Category D` for the official 35-point Information Coverage judge).
2. **If Proceeding to a Final BRREG Emission Phase (Phase 21)**: Combine **Candidate 1** (Structured Business & Postal Addresses, Official Email/Phone/Mobile, and the 4 Core Registration Dates: `1,000` companies, `6,199+` facts), **Candidate 2** (Share Capital & Share Count with strict type/shift guards: `938` companies, `4,671` facts), and **Candidate 3** (Corporate Purpose, Activity, MVA Status, and Audit Exemption with unshifted row guards: `1,000` companies, `4,103` facts) into a single, deterministic, zero-network-request registry metadata emission pass (`emit_registry_metrics`), or execute **Candidate 1** first as the highest-coverage, zero-shift-risk improvement.
