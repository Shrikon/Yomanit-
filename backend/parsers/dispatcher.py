# parsers/dispatcher.py
# נקודת כניסה אחידה לכל סוגי הקבצים

from typing import Dict, Any
from parsers.electricity import parse_buller, ElectricityParserError


class ParseError(Exception):
    """שגיאת פרסור כללית"""
    pass


def parse_file(file_type: str, content: bytes) -> Dict[str, Any]:
    """
    dispatcher – מנתב לפי סוג קובץ.

    file_type: 'bezeq' | 'electricity'
    content:   תוכן הקובץ כ-bytes

    מחזיר dict אחיד עם:
      rows, row_errors, total, sum_details,
      balance_ok, balance_diff, customer_name,
      period, date_from, date_to
    """
    if file_type == "electricity":
        try:
            return parse_buller(content)
        except ElectricityParserError as e:
            raise ParseError(str(e))

    if file_type == "bezeq":
        # בזק מטופל ב-upload.py הקיים
        raise ParseError("בזק מטופל דרך upload endpoint הקיים")

    raise ParseError(f"סוג קובץ לא נתמך: '{file_type}'")
