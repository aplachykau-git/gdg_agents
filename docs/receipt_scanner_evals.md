# Receipt Scanner Evaluations

The evaluation suite is in:

```text
agents/receipt_scanner/evaluation/
```

It covers:

- critical extraction of total, currency and date from five receipt images;
- deterministic currency conversion and displayed totals (`run_conversion_eval.py`);
- semantic batch grouping, contiguous ordering and synced 2-per-row proof alignment (`grouping_eval_cases.json` / `run_grouping_eval.py` and `evaluate_batch_workflow_contract`).

Google Docs API integration, CER and line-item semantic judging are not evaluated live in this suite.

## Fixtures

Images are downloaded to the ignored `fixtures/downloaded/` directory. The fixture manifest pins dataset revision, split, row, checksum and manually reviewed gold fields.

PLN receipts are preferred during candidate discovery. The current public datasets did not provide enough confirmed PLN samples, so the locked set uses explicit EUR and CHF receipts that visually resemble Polish thermal receipts and have totals below 200.

The `receipts-google-ocr` dataset card declares no explicit licence or provenance. The project uses the publicly accessible rows selected in `fixtures/ATTRIBUTION.md`.

Discover candidates:

```bash
make receipt-eval-discover
```

Download and verify locked images:

```bash
make receipt-eval-fixtures
```

## Run

Run deterministic conversion evaluations:

```bash
make receipt-conversion-evals
```

Run deterministic grouping and proof-alignment evaluations:

```bash
make receipt-grouping-evals
```

Run live Gemini extraction evaluations:

```bash
make receipt-extraction-evals
```

Prepare fixtures and run conversion, grouping and extraction evaluations together:

```bash
make receipt-evals-all
```

The extraction command requires the normal Gemini or Vertex credentials and incurs model/network usage. It defaults both the agent and OCR tool to the production `gemini-3.8-flash` model; override them with `RECEIPT_EVAL_MODEL` only for an intentional model comparison. Live FX lookups in production require NBP, Pekao, Frankfurter or Open ER to succeed or prompt for an explicit manual rate (no silent hardcoded fallback); deterministic evals use fixed rates and do not contact Pekao, NBP, Frankfurter, Open ER, Google Docs or Drive. These targets are manual and are not part of CI.

## Success and baselines

Every case must pass. Extraction validates the arguments supplied to the export tool (`evaluate_export_arguments` and `evaluate_batch_workflow_contract`) rather than the conversational response. Conversion and grouping evals run offline without network or LLM calls.

Create a reviewed baseline only after a human confirms every image and gold label and the complete suite passes. Prompt, model, fixture, gold-label, conversion-rule or threshold changes require evaluation against the approved baseline.
