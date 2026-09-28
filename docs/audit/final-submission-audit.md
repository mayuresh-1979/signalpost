# Final Submission Audit

## Final status

**READY FOR SUBMISSION**

This audit describes the repository state after cleanup, Git initialization, Git LFS setup, the initial submission commit, and independent clean-clone verification on September 28, 2026.

## Repository state

- Repository: `mayuresh-1979/signalpost`
- Default/submission branch: `master`
- Source package: `src/norway_company_agent/`
- Production scripts: `scripts/`
- Tests: 14 test modules
- Documentation: `docs/`
- Canonical outputs retained in `out/`: `profiles.jsonl`, `envelopes.jsonl`, `run-report.json`, `refresh-test.json`
- Large BRREG snapshots are tracked with Git LFS.
- Python caches, virtual environments, scratch/debug files, and temporary smoke files were removed from the submission tree.

## Frozen canonical artifacts

| Artifact | Size | SHA-256 |
|---|---:|---|
| `entry-companies.jsonl` | 319,526 bytes | `1dd834b29f7d97b689fb222399ef9d713ffa9f3dc20a94a824da07012d68d408` |
| `out/profiles.jsonl` | 20,040,151 bytes | `c2e1aa0382b6a5c0f9e0f01f3b0d91f18dc06e393517645eb0acdf17227cdd0e` |
| `out/envelopes.jsonl` | 20,916,240 bytes | `894b8f4e47f91fa3098edb516e6668fb21bf5fdaa0f46500bb5b8fe058192f0c8` |
| `out/run-report.json` | 1,359 bytes | `939bdba56c408a525059010DFCA89C50C2A129ACBE5DF12D667E8E213F6198BA` |
| `out/refresh-test.json` | 2,551 bytes | `04b2adf2e813c8a46cdbbc1e8b389b1813e64fff3031ebfeec6f968bd51f77e7` |

## Reproducibility

A fresh clone of the public repository was checked out at the submission commit and verified:

- Exact commit: `c4fe38ced197134eb1bef5e2610d370e7cf48410`
- Working tree: clean
- Git LFS: both BRREG CSV snapshots restored
- `brreg-enheter.csv`: 154,701,389 bytes
- `brreg-underenheter.csv`: 61,410,497 bytes
- Python: 3.13.11
- uv: 0.12.17
- `uv sync`: PASS
- `uv run python first_run.py`: PASS
- Audited non-POC suites: **74 / 74 passed**

The historical full source audit recorded **178 / 178** tests across the 14 modules, including the POC/integration suite. The fresh-clone verification above deliberately reran the 13 non-POC suites and did not rerun the POC suite.

## Corpus integrity

- Input organisations: 1,000 unique
- Profiles: 1,000 unique
- Envelopes: 1,000 unique
- Ordered organisation-number alignment: PASS
- Silent drops: 0
- Phase 18–23 structured emission: retained and audited
- CSV quote-shift protection: active for organisation numbers `998600421`, `914882036`, and `926768026`

## Identity and source-rights safety

- Strict entity identity gates are enforced before publication.
- Uncertain/name-only website matches are quarantined.
- 441 published external observations were audited.
- Wrong-company external publications in that audited set: 0.
- Unsupported external claims in that audited set: 0.
- Production acquisition modes are limited to approved `official_api` and `permitted_public_page`.
- Experimental connectors are not invoked by the production batch.

## Refresh and determinism

The retained refresh audit reports:

- expected changes: 2
- observed changes: 2
- true positives: 2
- false positives: 0
- false negatives: 0
- precision: 1.0
- recall: 1.0
- idempotent rerun: true

The retained Phase 18–23 emission checks were deterministic across the 1,000-company corpus.

## Local diagnostic score

The repository records **56.869 / 100** from `signalpost_external_first_competition_proxy_v3`.

This is a **local optimization/diagnostic proxy only**. It is not an official Builderr score or evaluator result.

## Important distinction

The repository's frozen outputs and historical audit evidence are submission artifacts. A fresh `--resume` replay is intended to demonstrate deterministic reproduction from retained evidence; it is not a new Builderr evaluation.

## Submission metadata still supplied separately

The Builderr submission should provide:

- repository URL: `https://github.com/mayuresh-1979/signalpost`
- exact final commit SHA
- `entry-companies.jsonl`
- exact 100-company command
- expected third-party cost: $0.00
- models/paid APIs: none in the audited production configuration
- data/source-rights description
- submitter contact information
