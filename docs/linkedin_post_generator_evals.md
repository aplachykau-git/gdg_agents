# LinkedIn Post Generator Evaluations and Baselines

The source of truth for the LinkedIn post-generator evaluation suite is:

```text
agents/linkedin_post_generator/evaluation/
```

It combines deterministic contract checks with a few-shot semantic judge:

- `judge_train.json` contains human-labeled examples sent to the judge as
  in-context examples.
- `judge_eval.json` contains held-out human-labeled examples. They are never
  placed in the judge prompt and measure judge agreement.
- `post_generator_eval_set.json` contains ADK end-to-end generator cases.
- `post_generator_eval_config.json` configures the custom ADK metric.
- `manifest.json` records the suite version, models, temperatures, and required
  pass rates.
- `baselines/` stores approved, human-readable snapshots of evaluation results.

The deterministic suite requires headers in the exact form
`### Variant N: Variant name`; parentheses around the variant name are not
accepted. It ignores hashtag-only and link-only footer blocks when deciding
whether the final prose paragraph has a CTA.

## Judge labels

Each semantic label uses:

- `pass`: the source supports the post;
- `fail`: the post changes the topic or invents unsupported session content;
- `unknown`: title/description lack enough detail to decide.

`pass` and `fail` include an integer `score` from 0 to 100. `unknown` must
use `score: null`.

## Baselines

A baseline is an approved comparison point, not a raw execution log. The
initial baseline is:

```text
agents/linkedin_post_generator/evaluation/baselines/2026-08-21_v1.0.0.md
```

Create a new baseline when an intentional change affects the prompt, evaluator,
rubric, fixture/gold label, model, temperature, threshold, or output contract.
Each baseline must include the manifest version, Git commit, exact models, and
the full judge and generator results.

Do not create a baseline for every routine run. Keep routine raw output in CI
artifacts or local ADK history. Never move a held-out judge example into the
few-shot train set without adding a new human-labeled held-out replacement.

## Run

Set the normal Gemini backend environment variables, then run the held-out
judge suite first:

```bash
make linkedin-judge-evals
```

Run the deterministic ADK generator suite:

```bash
make linkedin-evals
```

Run both in order:

```bash
make linkedin-evals-all
```

The Makefile runs Python tools through `uv run --locked`. Use `make tools` to
print the resolved commands.

The judge command prints a compact JSON artifact with verdict agreement and
scores. The ADK suite prints the contract metric per case. A release requires
the held-out judge suite and every deterministic generator case to pass.

The judge defaults to `gemini-3.7-flash`; override it with
`LINKEDIN_JUDGE_MODEL` when needed.
