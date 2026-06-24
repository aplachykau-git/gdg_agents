import os

import requests

# ---------------------------------------------------------------------------
# Tool: get_public_holidays
# ---------------------------------------------------------------------------


def get_public_holidays(year: int, country_code: str = "PL") -> dict:
    """
    Fetches the official public holidays for a given year and country from the
    completely free and open Nager.Date API.

    Args:
        year: The calendar year (e.g. 2026) to query holidays for.
        country_code: The ISO-2 country code of the community's country (e.g. 'PL', 'DE'). Default is 'PL'.

    Returns:
        dict: Success status, calendar year, country code, and list of public holidays
              including dates, local names, and English names.
    """
    country_code = country_code.upper().strip()
    api_url = f"https://date.nager.at/api/v3/PublicHolidays/{year}/{country_code}"
    try:
        print(f"[DEBUG] Fetching holidays for {year} (country: {country_code}) from Nager.Date API...")
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

        return {"success": True, "year": year, "country_code": country_code, "holidays": cleaned_holidays}

    except Exception as e:
        print(f"[WARNING] Failed to fetch holidays from Nager.Date: {e}")
        # Dynamic fallback based on country code
        if country_code == "PL":
            static_holidays = [
                {"date": f"{year}-01-01", "localName": "Nowy Rok", "name": "New Year's Day"},
                {"date": f"{year}-01-06", "localName": "Trzech Króli", "name": "Epiphany"},
                {"date": f"{year}-05-01", "localName": "Święto Państwowe", "name": "May Day"},
                {"date": f"{year}-05-03", "localName": "Święto Narodowe Trzeciego Maja", "name": "Constitution Day"},
                {
                    "date": f"{year}-08-15",
                    "localName": "Wniebowzięcie Najświętszej Maryi Panny",
                    "name": "Assumption Day",
                },
                {"date": f"{year}-11-01", "localName": "Wszystkich Świętych", "name": "All Saints' Day"},
                {"date": f"{year}-11-11", "localName": "Narodowe Święto Niepodległości", "name": "Independence Day"},
                {"date": f"{year}-12-25", "localName": "Pierwszy dzień Bożego Narodzenia", "name": "Christmas Day"},
                {
                    "date": f"{year}-12-26",
                    "localName": "Drugi dzień Bożego Narodzenia",
                    "name": "Second Day of Christmas",
                },
            ]
            note = "API query failed, used static list of fixed-date Polish holidays."
        else:
            static_holidays = [
                {"date": f"{year}-01-01", "localName": "New Year's Day", "name": "New Year's Day"},
                {"date": f"{year}-12-25", "localName": "Christmas Day", "name": "Christmas Day"},
            ]
            note = f"API query failed, used minimum generic holidays for {country_code}."

        return {
            "success": True,
            "year": year,
            "country_code": country_code,
            "holidays": static_holidays,
            "source_fallback": True,
            "note": note,
        }
