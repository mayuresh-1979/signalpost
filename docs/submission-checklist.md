# Signalpost final submission checklist

Use this checklist against the exact commit submitted to Builderr. The official challenge page is authoritative: https://builderr.ai/challenges/signalpost

## Required submission items

- [ ] 100-company smoke-test result or report showing one complete terminal result per input.
- [ ] Public repository URL and exact commit SHA.
- [ ] One copy-paste command that runs the agent on the evaluator-provided batch.
- [ ] Models, external APIs, relevant licences and source-use/retention constraints disclosed.
- [ ] Expected third-party cost per official run declared with assumptions.
- [ ] Contact details included.
- [ ] Email the submission to submit@builderr.ai.
- [ ] Confirm the current revision cutoff on the official challenge page.

Builderr supplies the company batch for official evaluation. The 1,000-company corpus is useful for development, but precomputed profiles do not replace the smoke-test report or the live agent. A local proxy score is not an official score.

## Final technical gates

- [ ] Final commit has successful smoke-test and clean-clone reproducibility CI.
- [ ] Clean clone installs using the declared, locked dependency setup.
- [ ] Runner reads the supplied batch and returns exactly one terminal envelope per input, with unique, aligned IDs.
- [ ] Missing information is represented with explicit terminal states; no silent drops.
- [ ] Claims retain source URL, retrieval date, relevant reporting period and content hash where applicable.
- [ ] No fabricated claims, unsupported financial values or material wrong-company publications.
- [ ] Refresh is idempotent and preserves earlier evidence without duplicate records or false changes.
- [ ] Genuine 100-company report and supporting envelopes/audit outputs are downloadable.
- [ ] Frozen canonical outputs and hashes remain unchanged during experiments.
- [ ] API/source rights, retention, secrets and costs are documented.
- [ ] No official score or qualification claim is made without an official result.

## External discovery pilot — never promote automatically

- [ ] Check the current Brave Search API plan and terms for this use and evidence handling.
- [ ] Set BRAVE_SEARCH_API_KEY locally; never commit it or print it in logs.
- [ ] Prepare deterministic 20-company development and validation cohorts in a new output directory.
- [ ] Run the development pilot with promotion disabled.
- [ ] Manually adjudicate exact legal-entity identity and record rights, coverage, precision, cost and latency.
- [ ] Run the untouched validation cohort only if the development gate passes.
- [ ] Promote only if documented precision and source-rights gates pass; otherwise keep the connector experimental.

## Final submission record

Fill in only after verification:

- Repository: https://github.com/mayuresh-1979/signalpost
- Final commit SHA: `<fill after final CI run>`
- Successful workflow run for that SHA: `<link>`
- Smoke-test report/artifact: `<link>`
- Runner command: README.md, “One-command Builderr submission run”
- Models/APIs/licences/source rights: `<link to disclosure>`
- Expected third-party cost per official run: `<measured/declared amount and assumptions>`
- Contact email: `<confirm before sending>`

## Submission email contents

Include the repository URL, exact final SHA, one-command runner instruction, smoke-test report/artifact link, model/API/licence and source-rights disclosures, expected cost per official run, and contact details. CI PASS establishes the checks performed; it does not establish an official competition score or qualification.
