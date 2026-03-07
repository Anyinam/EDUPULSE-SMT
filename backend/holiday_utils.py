from datetime import date
from typing import Dict

import holidays


def get_national_holidays(country_code: str, year: int) -> Dict[date, str]:
    """Return national holidays for a given country and year."""
    try:
        code = (country_code or "GH").upper()
        holiday_map = holidays.country_holidays(code, years=[year])
        return {day: name for day, name in holiday_map.items()}
    except Exception:
        return {}
