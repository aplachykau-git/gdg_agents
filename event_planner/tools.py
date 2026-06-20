import requests

# ---------------------------------------------------------------------------
# Tool: get_polish_holidays
# ---------------------------------------------------------------------------


def get_polish_holidays(year: int) -> dict:
    """
    Fetches the official Polish public holidays for a given year from the
    completely free and open Nager.Date API.

    Args:
        year: The calendar year (e.g. 2026) to query holidays for.

    Returns:
        dict: Success status, calendar year, and list of public holidays
              including dates, local names, and English names.
    """
    api_url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/PL"
    try:
        print(f"[DEBUG] Fetching Polish holidays for {year} from Nager.Date API...")
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        holidays_data = resp.json()

        cleaned_holidays = []
        for h in holidays_data:
            cleaned_holidays.append(
                {
                    "date": h.get("date"),
                    "localName": h.get("localName"),
                    "name": h.get("name"),
                    "global": h.get("global", True),
                }
            )

        return {"success": True, "year": year, "holidays": cleaned_holidays}

    except Exception as e:
        print(f"[WARNING] Failed to fetch holidays from Nager.Date: {e}")
        # Robust static fallback of main Polish holidays in case API is down
        static_holidays = [
            {"date": f"{year}-01-01", "localName": "Nowy Rok", "name": "New Year's Day"},
            {"date": f"{year}-01-06", "localName": "Trzech Króli", "name": "Epiphany"},
            {"date": f"{year}-05-01", "localName": "Święto Państwowe", "name": "May Day"},
            {"date": f"{year}-05-03", "localName": "Święto Narodowe Trzeciego Maja", "name": "Constitution Day"},
            {"date": f"{year}-08-15", "localName": "Wniebowzięcie Najświętszej Maryi Panny", "name": "Assumption Day"},
            {"date": f"{year}-11-01", "localName": "Wszystkich Świętych", "name": "All Saints' Day"},
            {"date": f"{year}-11-11", "localName": "Narodowe Święto Niepodległości", "name": "Independence Day"},
            {"date": f"{year}-12-25", "localName": "Pierwszy dzień Bożego Narodzenia", "name": "Christmas Day"},
            {"date": f"{year}-12-26", "localName": "Drugi dzień Bożego Narodzenia", "name": "Second Day of Christmas"},
        ]
        return {
            "success": True,
            "year": year,
            "holidays": static_holidays,
            "source_fallback": True,
            "note": "API query failed, used static list of fixed-date Polish holidays.",
        }
