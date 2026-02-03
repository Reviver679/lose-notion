# Date Utilities for Task Bot
# Handles date parsing and formatting

import frappe
from frappe.utils import getdate, today, add_days

# Try to import dateparser, fallback to basic parsing if not available
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False


def parse_date(date_str):
    """Parse natural language date string to Python date
    
    Handles:
    - "today", "tomorrow", "yesterday"
    - Natural language like "next friday", "in 3 days"
    - Date formats like "Feb 10", "2024-02-10"
    
    Returns today's date if parsing fails.
    """
    if not date_str:
        return getdate(today())
    
    date_str = date_str.strip().lower()
    
    # Handle common keywords
    if date_str == 'today':
        return getdate(today())
    elif date_str == 'tomorrow':
        return add_days(getdate(today()), 1)
    elif date_str == 'yesterday':
        return add_days(getdate(today()), -1)
    
    # Try dateparser if available
    if HAS_DATEPARSER:
        try:
            parsed = dateparser.parse(date_str, settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': frappe.utils.now_datetime()
            })
            if parsed:
                return getdate(parsed)
        except Exception:
            pass
    
    # Fallback to dateutil
    try:
        from dateutil import parser as date_parser
        parsed = date_parser.parse(date_str, fuzzy=True)
        return getdate(parsed)
    except Exception:
        pass
    
    # Default to today
    return getdate(today())


def format_date_display(date_obj):
    """Format date for user-friendly display
    
    Returns:
    - "Today" for today's date
    - "Tomorrow" for tomorrow
    - "Feb 10" format for other dates
    """
    if not date_obj:
        return "Today"
    
    today_date = getdate(today())
    if date_obj == today_date:
        return "Today"
    elif date_obj == add_days(today_date, 1):
        return "Tomorrow"
    else:
        return date_obj.strftime("%b %d")


def get_days_text(deadline, today_date=None):
    """Get human-readable text for deadline relative to today
    
    Returns text like:
    - "2 days overdue"
    - "Due today"
    - "Due tomorrow"
    - "Due in 5 days"
    - "No deadline"
    """
    if not deadline:
        return "No deadline"
    
    if today_date is None:
        today_date = getdate(today())
    
    from frappe.utils import date_diff
    deadline = getdate(deadline)
    days_diff = date_diff(deadline, today_date)
    
    if days_diff < 0:
        return f"{abs(days_diff)} day{'s' if abs(days_diff) > 1 else ''} overdue"
    elif days_diff == 0:
        return "Due today"
    elif days_diff == 1:
        return "Due tomorrow"
    else:
        return f"Due in {days_diff} days"
