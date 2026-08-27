# Receipt Scanner Evaluations

The evaluation suite is in:

```text
agents/receipt_scanner/evaluation/
```

It covers:

- critical extraction of total, currency and date from five receipt images;
- deterministic currency conversion and displayed totals.

Template population, Google Docs integration, CER, line-item accuracy and semantic judging are not evaluated.

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

Run live Gemini extraction evaluations:

```bash
make receipt-extraction-evals
```

Run both:

```bash
make receipt-evals-all
```

The extraction command requires the normal Gemini or Vertex credentials and incurs model/network usage. It defaults both the agent and OCR tool to the production `gemini-3.7-flash` model; override them with `RECEIPT_EVAL_MODEL` only for an intentional model comparison. These targets are manual and are not part of CI.

## Success and baselines

Every case must pass. Extraction validates the arguments supplied to the export tool rather than the conversational response. Conversion uses fixed rates and does not contact Pekao, NBP, Google Docs or Drive.

Create a reviewed baseline only after a human confirms every image and gold label and the complete suite passes. Prompt, model, fixture, gold-label, conversion-rule or threshold changes require evaluation against the approved baseline.
