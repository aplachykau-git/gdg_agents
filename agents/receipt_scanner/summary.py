"""What the receipt scanner recognised, as a structured card plus a copy-paste text.

The model reads every receipt with its own vision and passes the extracted lines here. This module
only does deterministic work: tidy the numbers, check that the line items add up to the receipt
total, group totals by currency and category, convert to the report currency and compare with the
approved budget. Nothing is invented: missing values stay empty.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable, Iterable

CATEGORIES = ("Transport", "Hotel", "Food & drinks", "Swag", "Prizes", "Venue", "Other")
_TOLERANCE = 0.02


def _num(value: Any) -> float | None:
    """'1 234,50' / '1,234.50' / 12 / None -> float or None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d,.\-]", "", str(value))
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        # The right-most separator is the decimal one.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = f"{head.replace(',', '')}.{tail}" if len(tail) in (1, 2) else text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _money(amount: float | None, currency: str) -> str:
    if amount is None:
        return "—"
    return f"{amount:,.2f} {currency}".replace(",", " ")


def _category(raw: Any) -> str:
    text = str(raw or "").strip().lower()
    for name in CATEGORIES:
        if text == name.lower():
            return name
    aliases = {
        "food": "Food & drinks",
        "drinks": "Food & drinks",
        "catering": "Food & drinks",
        "taxi": "Transport",
        "travel": "Transport",
        "accommodation": "Hotel",
        "merch": "Swag",
        "gifts": "Prizes",
    }
    return aliases.get(text, "Other")


def parse_budget(text: str) -> tuple[float, str] | None:
    """'500 EUR' / 'EUR 500' / '1 200,50 pln' -> (amount, currency)."""
    if not text:
        return None
    currency = re.search(r"\b([A-Za-z]{3})\b", text)
    amount = _num(re.sub(r"[A-Za-z]", "", text))
    if amount is None:
        return None
    return amount, (currency.group(1).upper() if currency else "")


def _normalise_item(item: dict) -> dict:
    quantity = _num(item.get("quantity"))
    unit_price = _num(item.get("unit_price"))
    total = _num(item.get("total"))
    if total is None and unit_price is not None:
        total = round(unit_price * (quantity if quantity is not None else 1), 2)
    return {
        "name": str(item.get("name") or "").strip() or "Item",
        "quantity": quantity,
        "unit_price": unit_price,
        "total": total,
    }


def _normalise_receipt(index: int, raw: dict, default_currency: str) -> dict:
    currency = str(raw.get("currency") or default_currency or "").upper().strip()
    items = [_normalise_item(i) for i in (raw.get("items") or []) if isinstance(i, dict)]
    items_sum = round(sum(i["total"] for i in items if i["total"] is not None), 2) if items else None
    total = _num(raw.get("total"))
    if total is None:
        total = items_sum
    warnings: list[str] = []
    if items_sum is not None and total is not None and abs(items_sum - total) > _TOLERANCE:
        warnings.append(
            f"Line items add up to {_money(items_sum, currency)}, the receipt total is {_money(total, currency)}."
        )
    if total is None:
        warnings.append("Total amount is not readable.")
    if not currency:
        warnings.append("Currency is not readable.")
    for note in raw.get("notes") or []:
        if str(note).strip():
            warnings.append(str(note).strip())
    return {
        "index": index,
        "merchant": str(raw.get("merchant") or raw.get("desc") or f"Receipt {index}").strip(),
        "description": str(raw.get("desc") or "").strip(),
        "date": str(raw.get("date") or "").strip(),
        "category": _category(raw.get("category")),
        "currency": currency,
        "total": total,
        "tax": _num(raw.get("tax")),
        "payment_method": str(raw.get("payment_method") or "").strip(),
        "document_number": str(raw.get("document_number") or "").strip(),
        "items": items,
        "items_sum": items_sum,
        "warnings": warnings,
    }


def build_receipt_summary(
    receipts: Iterable[dict] | None,
    target_currency: str = "",
    approved_budget: str = "",
    rate_to_pln: Callable[[str], float] | None = None,
) -> dict:
    """Structured summary of the recognised receipts (the ``receipt_summary`` UI payload body).

    ``rate_to_pln(code)`` returns how many PLN one unit of ``code`` costs; it is only called when
    receipts are in a different currency than ``target_currency``.
    """
    rows = [_normalise_receipt(i, r, "") for i, r in enumerate(receipts or [], start=1) if isinstance(r, dict)]
    currencies = [r["currency"] for r in rows if r["currency"]]
    budget = parse_budget(approved_budget)
    target = (target_currency or (budget[1] if budget and budget[1] else "") or "").upper().strip()
    if not target:
        target = max(set(currencies), key=currencies.count) if currencies else "PLN"

    by_currency: dict[str, float] = defaultdict(float)
    for row in rows:
        if row["total"] is not None and row["currency"]:
            by_currency[row["currency"]] += row["total"]

    rates: dict[str, float] = {}
    conversion_ok = True
    needed = {c for c in by_currency if c != target}
    if budget and budget[1] and budget[1] != target:
        needed.add(budget[1])
    if needed:
        if rate_to_pln is None:
            conversion_ok = False
        else:
            try:
                target_pln = 1.0 if target == "PLN" else float(rate_to_pln(target))
                for code in sorted(needed):
                    code_pln = 1.0 if code == "PLN" else float(rate_to_pln(code))
                    rates[code] = code_pln / target_pln
            except Exception:
                conversion_ok = False
                rates = {}

    def convert(amount: float | None, code: str) -> float | None:
        if amount is None or not code:
            return None
        if code == target:
            return amount
        if conversion_ok and code in rates:
            return round(amount * rates[code], 2)
        return None

    by_category: dict[str, float] = defaultdict(float)
    for row in rows:
        row["total_target"] = convert(row["total"], row["currency"])
        if row["total_target"] is not None:
            by_category[row["category"]] += row["total_target"]

    converted = [r["total_target"] for r in rows if r["total"] is not None]
    grand_total = round(sum(converted), 2) if converted and all(v is not None for v in converted) else None

    budget_info = None
    if budget:
        budget_amount = convert(budget[0], budget[1] or target)
        if budget_amount is not None:
            remaining = None if grand_total is None else round(budget_amount - grand_total, 2)
            budget_info = {
                "amount": round(budget_amount, 2),
                "currency": target,
                "source": approved_budget.strip(),
                "remaining": remaining,
                "over_budget": remaining is not None and remaining < 0,
            }

    summary = {
        "target_currency": target,
        "receipts": rows,
        "totals_by_currency": [{"currency": c, "amount": round(a, 2)} for c, a in sorted(by_currency.items())],
        "totals_by_category": [
            {"category": c, "amount": round(a, 2)} for c, a in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        "grand_total": grand_total,
        "rates": [{"currency": c, "rate": round(r, 6), "to": target} for c, r in sorted(rates.items())],
        "conversion_note": (
            "Approximate conversion at the NBP average rate; the expense report uses the bank rate."
            if rates
            else ("Could not get exchange rates; amounts are shown in the receipt currency." if needed else "")
        ),
        "budget": budget_info,
        "warnings_count": sum(len(r["warnings"]) for r in rows),
    }
    summary["text"] = summary_text(summary)
    return summary


def summary_text(summary: dict) -> str:
    """Plain-text version of the summary for copying into a chat, an e-mail or a spreadsheet."""
    target = summary["target_currency"]
    lines: list[str] = []
    for row in summary["receipts"]:
        head = f"{row['index']}. {row['merchant']}"
        meta = " · ".join(x for x in (row["date"], row["category"]) if x)
        lines.append(f"{head} ({meta})" if meta else head)
        for item in row["items"]:
            qty = item["quantity"]
            unit = item["unit_price"]
            detail = ""
            if qty is not None and unit is not None:
                detail = f"{qty:g} × {_money(unit, row['currency'])} = "
            lines.append(f"   - {item['name']}: {detail}{_money(item['total'], row['currency'])}")
        total = f"   Total: {_money(row['total'], row['currency'])}"
        if row.get("total_target") is not None and row["currency"] != target:
            total += f" (≈ {_money(row['total_target'], target)})"
        if row["tax"] is not None:
            total += f", incl. tax {_money(row['tax'], row['currency'])}"
        lines.append(total)
        for warning in row["warnings"]:
            lines.append(f"   ! {warning}")
    lines.append("")
    if summary["totals_by_category"]:
        lines.append(
            "By category: "
            + ", ".join(f"{c['category']} {_money(c['amount'], target)}" for c in summary["totals_by_category"])
        )
    if len(summary["totals_by_currency"]) > 1 or (
        summary["totals_by_currency"] and summary["totals_by_currency"][0]["currency"] != target
    ):
        lines.append(
            "By currency: " + ", ".join(_money(c["amount"], c["currency"]) for c in summary["totals_by_currency"])
        )
    if summary["grand_total"] is not None:
        lines.append(f"Grand total: {_money(summary['grand_total'], target)}")
    budget = summary.get("budget")
    if budget and budget.get("remaining") is not None:
        state = "over budget by" if budget["over_budget"] else "left in budget"
        lines.append(f"Budget {_money(budget['amount'], target)}: {state} {_money(abs(budget['remaining']), target)}")
    if summary.get("conversion_note"):
        lines.append(summary["conversion_note"])
    return "\n".join(lines).strip()
