"""Discover, download, and verify receipt evaluation fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import requests
from PIL import Image

DATASET_ROWS_URL = "https://datasets-server.huggingface.co/rows"
FIXTURE_MANIFEST = Path(__file__).with_name("receipt_fixtures.json")
DOWNLOAD_DIRECTORY = Path(__file__).with_name("fixtures") / "downloaded"
REQUEST_TIMEOUT_SECONDS = 30
DISCOVERY_PAGE_SIZE = 100
RECEIPT_LABEL = 3
MAX_TYPICAL_TOTAL = 200
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_HOSTS = {
    "datasets-server.huggingface.co",
    "huggingface.co",
    "cdn-lfs.hf.co",
    "us.aws.cdn.hf.co",
}
ALLOWED_IMAGE_CONTENT_TYPES = {
    "application/octet-stream",
    "binary/octet-stream",
    "image/jpeg",
    "image/png",
    "image/webp",
}

AMOUNT_PATTERN = re.compile(r"(?<!\d)(?:0|[1-9]\d?|1\d\d)[,.]\d{2}(?!\d)")
POLISH_MARKERS = (
    " pln",
    "zł",
    "paragon fiskalny",
    "gotówka",
    "do zapłaty",
    "warszawa",
    "kraków",
    "wrocław",
    "poznań",
    "gdańsk",
    "łódź",
)
EUROPEAN_MARKERS = (
    " eur",
    "€",
    " chf",
    " sek",
    " byn",
    "summe",
    "totalt",
    "totaal",
    "totale",
    "mwst",
    "moms",
)
NON_EUROPEAN_MARKERS = (
    " idr",
    " rp.",
    " myr",
    " sgd",
    " hkd",
    " cny",
    " rmb",
    "kembali",
    "tunai",
    "pajak",
)


def _load_manifest() -> dict[str, Any]:
    with FIXTURE_MANIFEST.open(encoding="utf-8") as file:
        return json.load(file)


def _request_rows(dataset: str, split: str, offset: int, length: int) -> dict[str, Any]:
    response = requests.get(
        DATASET_ROWS_URL,
        params={
            "dataset": dataset,
            "config": "default",
            "split": split,
            "offset": offset,
            "length": length,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()


def _get_row(fixture: dict[str, Any]) -> dict[str, Any]:
    payload = _request_rows(
        fixture["dataset"],
        fixture["split"],
        fixture["row_id"],
        1,
    )
    rows = payload.get("rows") or []
    if len(rows) != 1 or rows[0].get("row_idx") != fixture["row_id"]:
        raise ValueError(f"Dataset row {fixture['row_id']} was not returned.")
    return rows[0]["row"]


def _validate_asset_url(url: str) -> None:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_IMAGE_HOSTS:
        raise ValueError(f"Unexpected fixture asset URL: {url}")


def _download_image(url: str, target: Path) -> None:
    _validate_asset_url(url)
    size = 0
    with requests.get(
        url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        stream=True,
    ) as response:
        response.raise_for_status()
        _validate_asset_url(response.url)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise ValueError(f"Unexpected fixture content type: {content_type or '<missing>'}.")
        content_length = int(response.headers.get("content-length", "0"))
        if content_length > MAX_IMAGE_BYTES:
            raise ValueError(f"Fixture image exceeds {MAX_IMAGE_BYTES} bytes.")
        with target.open("wb") as file:
            for chunk in response.iter_content(1024 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise ValueError(f"Fixture image exceeds {MAX_IMAGE_BYTES} bytes.")
                file.write(chunk)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_image(path: Path, expected_sha256: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Fixture is missing: {path}")
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise ValueError(f"Checksum mismatch for {path.name}: expected {expected_sha256}, got {actual_sha256}.")
    with Image.open(path) as image:
        image.verify()


def download() -> int:
    DOWNLOAD_DIRECTORY.mkdir(parents=True, exist_ok=True)
    for fixture in _load_manifest()["fixtures"]:
        row = _get_row(fixture)
        expected_label = fixture.get("receipt_label")
        if expected_label is not None and row.get("label") != expected_label:
            raise ValueError(f"{fixture['fixture_id']} has label {row.get('label')}, expected {expected_label}.")

        image = row.get(fixture["image_column"]) or {}
        row_image_url = image.get("src")
        if not row_image_url:
            raise ValueError(f"{fixture['fixture_id']} has no image URL.")
        if fixture["revision"] not in row_image_url:
            raise ValueError(f"{fixture['fixture_id']} is no longer served from revision {fixture['revision']}.")

        target = DOWNLOAD_DIRECTORY / fixture["file_name"]
        temporary = target.with_suffix(f"{target.suffix}.tmp")
        try:
            _download_image(row_image_url, temporary)
            _verify_image(temporary, fixture["sha256"])
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(f"verified {fixture['fixture_id']}: {target}")
    return 0


def verify() -> int:
    for fixture in _load_manifest()["fixtures"]:
        target = DOWNLOAD_DIRECTORY / fixture["file_name"]
        _verify_image(target, fixture["sha256"])
        print(f"verified {fixture['fixture_id']}: {target}")
    return 0


def _full_ocr_text(row: dict[str, Any]) -> str:
    ocr = row.get("ocr") or []
    if ocr:
        return str(ocr[0].get("text", ""))

    ground_truth = row.get("ground_truth")
    if not ground_truth:
        return ""
    try:
        parsed = json.loads(ground_truth)
    except (TypeError, json.JSONDecodeError):
        return ""
    lines = parsed.get("valid_line") or []
    return " ".join(str(word.get("text", "")) for line in lines for word in line.get("words", []))


def _cord_total(row: dict[str, Any]) -> str | None:
    ground_truth = row.get("ground_truth")
    if not ground_truth:
        return None
    try:
        parsed = json.loads(ground_truth)
    except (TypeError, json.JSONDecodeError):
        return None
    total = parsed.get("gt_parse", {}).get("total", {}).get("total_price")
    return str(total).strip() if total is not None else None


def _cord_total_is_polish_scale(row: dict[str, Any]) -> bool:
    total = _cord_total(row)
    if total is None:
        return False
    if re.fullmatch(r"\d{1,3}[,.]\d{3}", total):
        return False
    try:
        return float(total.replace(",", ".")) < MAX_TYPICAL_TOTAL
    except ValueError:
        return False


def _amounts_below_limit(text: str) -> list[str]:
    amounts = []
    for amount in AMOUNT_PATTERN.findall(text):
        if float(amount.replace(",", ".")) < MAX_TYPICAL_TOTAL:
            amounts.append(amount)
    return amounts


def _candidate_score(text: str, amounts: list[str]) -> int:
    normalised = text.casefold()
    if any(marker in normalised for marker in POLISH_MARKERS):
        score = 100
    elif any(marker in normalised for marker in EUROPEAN_MARKERS):
        score = 20
    else:
        return 0
    if amounts:
        score += 5
    if any(marker in normalised for marker in NON_EUROPEAN_MARKERS):
        score -= 100
    return score


def discover(dataset: str, split: str, limit: int) -> int:
    first_page = _request_rows(dataset, split, 0, DISCOVERY_PAGE_SIZE)
    total_rows = int(first_page.get("num_rows_total", 0))
    rows = list(first_page.get("rows") or [])
    for offset in range(DISCOVERY_PAGE_SIZE, total_rows, DISCOVERY_PAGE_SIZE):
        rows.extend(_request_rows(dataset, split, offset, DISCOVERY_PAGE_SIZE).get("rows") or [])

    candidates = []
    for item in rows:
        row = item.get("row") or {}
        if "label" in row and row.get("label") != RECEIPT_LABEL:
            continue
        if "ground_truth" in row and not _cord_total_is_polish_scale(row):
            continue
        text = _full_ocr_text(row)
        amounts = _amounts_below_limit(text)
        score = _candidate_score(text, amounts)
        if score <= 0:
            continue
        candidates.append(
            {
                "row_id": item.get("row_idx"),
                "score": score,
                "amounts_below_200": amounts[:10],
                "ocr_preview": re.sub(r"\s+", " ", text)[:300],
            }
        )

    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["row_id"]))
    print(json.dumps(candidates[:limit], ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("download")
    subparsers.add_parser("verify")
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("--dataset", default="amaye15/receipts-google-ocr")
    discover_parser.add_argument("--split", default="test")
    discover_parser.add_argument("--limit", type=int, default=50)
    arguments = parser.parse_args()

    if arguments.command == "download":
        return download()
    if arguments.command == "verify":
        return verify()
    return discover(arguments.dataset, arguments.split, arguments.limit)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, requests.RequestException, ValueError) as error:
        print(f"Fixture preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
