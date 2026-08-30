# Video Editor Evaluations

The evaluation suite is in:

```text
agents/video_editor/evaluation/
```

It covers conversational contract compliance — whether the agent calls `create_video_card` at the right points in a multi-turn conversation, using a deterministic render stub so no Veo or Omni quota is consumed.

## What is evaluated

- **Happy path (single-turn)**: Agent calls `create_video_card` when all required inputs are present in one message.
- **Happy path (multi-turn)**: Agent accumulates inputs across turns and calls the tool only when complete.
- **Draft persistence under unrelated input**: Agent ignores an unrelated message mid-conversation without clearing the draft or calling the tool.
- **Typo correction gating**: Agent proposes a correction for an obvious spelling error and does not call the tool until the user confirms.

## Metric

`video_editor_chat_contract_score` — a deterministic custom ADK metric defined in `agents/video_editor/evaluation/evaluator.py`. Scores 100 when every invocation in the eval case satisfies its tool-call contract (call expected → tool was called; no call expected → tool was not called). A release requires all cases to pass.

## Run

```bash
make video-editor-evals
```

Run unit tests and then the chat eval suite:

```bash
make video-editor-evals-all
```

The Makefile runs Python tools through `uv run --locked`. Use `make tools` to print the resolved commands.

## Render stub

The eval suite patches the render pipeline so no video is generated during evaluation. This means evals run without Vertex AI credentials and complete in seconds. The stub does not validate render output quality — only agent conversation behavior is assessed.

## Baselines

Create a baseline only after an intentional change to the agent instruction, tool schema, typo-correction flag, or output contract. Store baselines alongside the eval set. Do not create a baseline for every routine run.
