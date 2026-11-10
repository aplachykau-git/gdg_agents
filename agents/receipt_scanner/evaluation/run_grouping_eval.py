"""Run deterministic receipt grouping and table-to-proof alignment evaluations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents.receipt_scanner.docx_generator import reorder_proofs_for_grouped_receipts
from agents.receipt_scanner.summary import _category, _semantic_cluster, group_and_sort_receipts


def _case_file() -> Path:
    return Path(__file__).with_name("grouping_eval_cases.json")


def load_grouping_cases() -> dict[str, Any]:
    with _case_file().open(encoding="utf-8") as file:
        return json.load(file)


def _clusters_are_contiguous(grouped_receipts: list[dict[str, Any]]) -> bool:
    """Return True if every (category, semantic_cluster) pair forms a single contiguous block."""
    seen_completed: set[tuple[str, str]] = set()
    previous_key: tuple[str, str] | None = None
    for item in grouped_receipts:
        cat = _category(item.get("category"))
        desc_raw = str(item.get("desc") or item.get("description") or item.get("merchant") or "").strip()
        merch_raw = str(item.get("merchant") or "").strip()
        cluster = _semantic_cluster(f"{desc_raw} {merch_raw}")
        key = (cat, cluster)
        if previous_key is not None and key != previous_key:
            seen_completed.add(previous_key)
            if key in seen_completed:
                return False
        previous_key = key
    return True


def evaluate_grouping_case(case: dict[str, Any]) -> dict[str, Any]:
    raw_receipts = case["receipts"]
    proof_bytes = [label.encode("utf-8") for label in case["proof_labels"]]

    grouped = group_and_sort_receipts(raw_receipts)
    actual_descriptions = [item.get("desc", "") for item in grouped]
    reordered_proofs = reorder_proofs_for_grouped_receipts(grouped, proof_bytes)
    actual_proof_labels = [
        proof.decode("utf-8") if isinstance(proof, (bytes, bytearray)) else str(proof) for proof in reordered_proofs
    ]
    contiguous = _clusters_are_contiguous(grouped)

    failures: list[str] = []
    if not contiguous:
        failures.append("cluster_contiguity")
    if actual_descriptions != case["expected_descriptions"]:
        failures.append("grouped_descriptions")
    if actual_proof_labels != case["expected_proof_labels"]:
        failures.append("proof_alignment")

    return {
        "case_id": case["case_id"],
        "passed": not failures,
        "failures": failures,
        "cluster_contiguity": contiguous,
        "expected": {
            "descriptions": case["expected_descriptions"],
            "proof_labels": case["expected_proof_labels"],
        },
        "actual": {
            "descriptions": actual_descriptions,
            "proof_labels": actual_proof_labels,
        },
    }


def run() -> int:
    dataset = load_grouping_cases()
    results = [evaluate_grouping_case(case) for case in dataset["cases"]]
    passed = sum(result["passed"] for result in results)
    artifact = {
        "dataset": dataset["dataset_id"],
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "results": results,
    }
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(run())
