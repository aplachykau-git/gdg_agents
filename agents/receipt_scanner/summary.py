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

_CURRENCY_ALIASES: dict[str, str] = {
    "£": "GBP",
    "UKP": "GBP",
    "STG": "GBP",
    "POUND": "GBP",
    "POUNDS": "GBP",
    "GBP": "GBP",
    "€": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "EUR": "EUR",
    "$": "USD",
    "US$": "USD",
    "DOLLAR": "USD",
    "DOLLARS": "USD",
    "USD": "USD",
    "ZŁ": "PLN",
    "ZL": "PLN",
    "ZLOTY": "PLN",
    "ZŁOTY": "PLN",
    "PLN": "PLN",
    "KČ": "CZK",
    "KC": "CZK",
    "CZK": "CZK",
    "FR": "CHF",
    "FR.": "CHF",
    "SFR": "CHF",
    "CHF": "CHF",
    "₴": "UAH",
    "UAH": "UAH",
    "¥": "JPY",
    "YEN": "JPY",
    "JPY": "JPY",
    "CN¥": "CNY",
    "RMB": "CNY",
    "YUAN": "CNY",
    "CNY": "CNY",
    "C$": "CAD",
    "CA$": "CAD",
    "CAD": "CAD",
    "A$": "AUD",
    "AU$": "AUD",
    "AUD": "AUD",
    "KR": "SEK",
    "SEK": "SEK",
    "NOK": "NOK",
    "DKK": "DKK",
    "FT": "HUF",
    "HUF": "HUF",
    "LEI": "RON",
    "RON": "RON",
    "BGN": "BGN",
    "₺": "TRY",
    "TL": "TRY",
    "TRY": "TRY",
    "₪": "ILS",
    "ILS": "ILS",
    "₹": "INR",
    "INR": "INR",
    "R$": "BRL",
    "BRL": "BRL",
    "₩": "KRW",
    "KRW": "KRW",
    "S$": "SGD",
    "SGD": "SGD",
    "HK$": "HKD",
    "HKD": "HKD",
    "NZ$": "NZD",
    "NZD": "NZD",
    "MXN": "MXN",
    "ZAR": "ZAR",
    "₾": "GEL",
    "GEL": "GEL",
    "₸": "KZT",
    "KZT": "KZT",
}


def normalize_currency_code(raw: Any, default: str = "") -> str:
    """Normalize currency symbols, names, or ISO codes into a 3-letter uppercase ISO-4217 code."""
    text = str(raw or "").strip().upper()
    if not text:
        return default.upper().strip()
    if text in _CURRENCY_ALIASES:
        return _CURRENCY_ALIASES[text]
    for symbol, iso in _CURRENCY_ALIASES.items():
        if symbol in text and not symbol.isalpha():
            return iso
    match = re.search(r"\b([A-Z]{3})\b", text)
    if match:
        token = match.group(1)
        return _CURRENCY_ALIASES.get(token, token)
    for word, iso in _CURRENCY_ALIASES.items():
        if word in text:
            return iso
    return text if len(text) == 3 and text.isalpha() else default.upper().strip()


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


_CATEGORY_SORT_ORDER: dict[str, int] = {
    "Food & drinks": 1,
    "Transport": 2,
    "Hotel": 3,
    "Swag": 4,
    "Prizes": 5,
    "Venue": 6,
    "Other": 7,
}

_CLUSTER_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("01_printing", ("print", "druk", "banner", "poster", "flyer", "adwall", "cardboard", "cut", "sticker")),
    (
        "02_catering_food",
        ("catering", "restaurant", "dinner", "lunch", "pizza", "water", "cisowianka", "snack", "coffee", "grocery"),
    ),
    ("03_trains_transit", ("train", "pkp", "intercity", "uber", "bolt", "taxi", "flight", "bus", "parking")),
    ("04_courier_delivery", ("courier", "delivery", "shipping", "post", "inpost", "dpd", "dhl")),
    ("05_hotel_lodging", ("hotel", "hostel", "airbnb", "accommodation", "lodging")),
    (
        "06_swag_gifts",
        ("lanyard", "gift", "jam", "tea", "shirt", "hoodie", "swag", "merch", "allegro", "prize", "award"),
    ),
    ("07_subscriptions_cloud_domain", ("subscription", "ai video", "ai voice", "cloud", "hosting", "domain", "saas")),
    ("08_cables_connectors", ("cable", "hdmi", "usb", "adapter", "switch", "cord")),
    ("09_storage_memory", ("microsd", "memory card", "sd card", "ssd", "samsung", "flash drive")),
    ("10_lighting_stands", ("light", "led", "rgb", "tube", "tripod", "stand", "easel")),
    (
        "11_audio_video_gear",
        ("video mixer", "atem", "recorder", "zoom", "speaker", "marshall", "microphone", "antenna", "sdr", "camera"),
    ),
    ("12_venue_supplies_services", ("contractor", "shelving", "frame", "putty", "patafix", "box", "stationery")),
)


def _semantic_cluster(text: str) -> str:
    low = (text or "").lower()
    for cluster_name, keywords in _CLUSTER_RULES:
        if any(kw in low for kw in keywords):
            return cluster_name
    return "99_other"


def group_and_sort_receipts(receipts: Iterable[dict] | None) -> list[dict]:
    """
    Group receipts deterministically by (Category, Semantic Cluster, Description, Date)
    while recording each item's original 0-based attachment index in '_orig_idx' so proof
    images can be ordered in the exact same sequence as the table rows.
    """
    tagged: list[tuple[int, dict]] = []
    for idx, raw in enumerate(receipts or []):
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if "_orig_idx" not in item:
            att_idx = item.get("attachment_index")
            orig_idx = idx
            if att_idx is not None:
                try:
                    parsed = int(att_idx)
                    if parsed >= 1:
                        orig_idx = parsed - 1
                except (TypeError, ValueError):
                    pass
            item["_orig_idx"] = orig_idx
        tagged.append((idx, item))

    def _sort_key(pair: tuple[int, dict]) -> tuple[int, str, str, str, int]:
        pos, r = pair
        cat = _category(r.get("category"))
        cat_rank = _CATEGORY_SORT_ORDER.get(cat, 99)
        desc_raw = str(r.get("desc") or r.get("description") or r.get("merchant") or "").strip()
        merch_raw = str(r.get("merchant") or "").strip()
        cluster = _semantic_cluster(f"{desc_raw} {merch_raw}")
        norm_desc = re.sub(r"\s+", " ", desc_raw.lower())
        date_str = str(r.get("date") or "9999-99-99").strip()
        return (cat_rank, cluster, norm_desc, date_str, pos)

    tagged.sort(key=_sort_key)
    return [item for _, item in tagged]


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
    currency = normalize_currency_code(raw.get("currency") or default_currency or "")
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
    community_currency: str = "",
) -> dict:
    """Structured summary of the recognised receipts (the ``receipt_summary`` UI payload body).

    ``rate_to_pln(code)`` returns how many PLN one unit of ``code`` costs; it is only called when
    receipts are in a different currency than ``target_currency`` or ``community_currency``.
    """
    rows = [_normalise_receipt(i, r, "") for i, r in enumerate(receipts or [], start=1) if isinstance(r, dict)]
    currencies = [r["currency"] for r in rows if r["currency"]]
    budget = parse_budget(approved_budget)
    comm_curr = normalize_currency_code(community_currency)
    target = normalize_currency_code(target_currency or (budget[1] if budget and budget[1] else "") or comm_curr)
    if not target:
        target = max(set(currencies), key=currencies.count) if currencies else "PLN"

    by_currency: dict[str, float] = defaultdict(float)
    for row in rows:
        if row["total"] is not None and row["currency"]:
            by_currency[row["currency"]] += row["total"]

    rates: dict[str, float] = {}
    rates_to_comm: dict[str, float] = {}
    conversion_ok = True
    comm_conversion_ok = True
    needed = {c for c in by_currency if c != target}
    if budget and budget[1] and budget[1] != target:
        needed.add(budget[1])
    needed_comm = {c for c in by_currency if comm_curr and c != comm_curr}

    if needed or needed_comm:
        if rate_to_pln is None:
            if needed:
                conversion_ok = False
            if needed_comm:
                comm_conversion_ok = False
        else:
            pln_cache: dict[str, float] = {"PLN": 1.0}

            def _get_pln(code: str) -> float:
                if code not in pln_cache:
                    pln_cache[code] = float(rate_to_pln(code))
                return pln_cache[code]

            if needed:
                try:
                    target_pln = _get_pln(target)
                    for code in sorted(needed):
                        rates[code] = _get_pln(code) / target_pln
                except Exception:
                    conversion_ok = False
                    rates = {}

            if needed_comm and comm_curr:
                try:
                    comm_pln = _get_pln(comm_curr)
                    for code in sorted(needed_comm):
                        rates_to_comm[code] = _get_pln(code) / comm_pln
                except Exception:
                    comm_conversion_ok = False
                    rates_to_comm = {}

    def convert(amount: float | None, code: str) -> float | None:
        if amount is None or not code:
            return None
        if code == target:
            return amount
        if conversion_ok and code in rates:
            return round(amount * rates[code], 2)
        return None

    def convert_to_comm(amount: float | None, code: str) -> float | None:
        if not comm_curr or amount is None or not code:
            return None
        if code == comm_curr:
            return amount
        if comm_conversion_ok and code in rates_to_comm:
            return round(amount * rates_to_comm[code], 2)
        return None

    by_category: dict[str, float] = defaultdict(float)
    for row in rows:
        row["total_target"] = convert(row["total"], row["currency"])
        if comm_curr:
            row["total_community"] = convert_to_comm(row["total"], row["currency"])
        if row["total_target"] is not None:
            by_category[row["category"]] += row["total_target"]

    converted = [r["total_target"] for r in rows if r["total"] is not None]
    grand_total = round(sum(converted), 2) if converted and all(v is not None for v in converted) else None

    community_total = None
    if comm_curr:
        converted_comm = [r.get("total_community") for r in rows if r["total"] is not None]
        community_total = (
            round(sum(converted_comm), 2) if converted_comm and all(v is not None for v in converted_comm) else None
        )

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

    rates_list = [{"currency": c, "rate": round(r, 6), "to": target} for c, r in sorted(rates.items())]
    if comm_curr and comm_curr != target:
        for c, r in sorted(rates_to_comm.items()):
            if not any(entry["currency"] == c and entry["to"] == comm_curr for entry in rates_list):
                rates_list.append({"currency": c, "rate": round(r, 6), "to": comm_curr})

    summary = {
        "target_currency": target,
        "community_currency": comm_curr or target,
        "community_total": community_total if comm_curr else grand_total,
        "receipts": rows,
        "totals_by_currency": [{"currency": c, "amount": round(a, 2)} for c, a in sorted(by_currency.items())],
        "totals_by_category": [
            {"category": c, "amount": round(a, 2)} for c, a in sorted(by_category.items(), key=lambda kv: -kv[1])
        ],
        "grand_total": grand_total,
        "rates": rates_list,
        "conversion_note": (
            "Approximate conversion at the public exchange rate; the expense report uses the bank rate."
            if rates_list
            else (
                "Could not get exchange rates; amounts are shown in the receipt currency."
                if (needed or needed_comm)
                else ""
            )
        ),
        "budget": budget_info,
        "warnings_count": sum(len(r["warnings"]) for r in rows),
    }
    summary["text"] = summary_text(summary)
    return summary


def summary_text(summary: dict) -> str:
    """Plain-text version of the summary for copying into a chat, an e-mail or a spreadsheet."""
    target = summary["target_currency"]
    comm_curr = summary.get("community_currency") or target
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
        conversions: list[str] = []
        if row.get("total_target") is not None and row["currency"] != target:
            conversions.append(f"≈ {_money(row['total_target'], target)}")
        if comm_curr != target and row.get("total_community") is not None and row["currency"] != comm_curr:
            conversions.append(f"≈ {_money(row['total_community'], comm_curr)}")
        if conversions:
            total += f" ({', '.join(conversions)})"
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
    if comm_curr != target and summary.get("community_total") is not None:
        lines.append(f"Community total ({comm_curr}): {_money(summary['community_total'], comm_curr)}")
    budget = summary.get("budget")
    if budget and budget.get("remaining") is not None:
        state = "over budget by" if budget["over_budget"] else "left in budget"
        lines.append(f"Budget {_money(budget['amount'], target)}: {state} {_money(abs(budget['remaining']), target)}")
    if summary.get("conversion_note"):
        lines.append(summary["conversion_note"])
    return "\n".join(lines).strip()
