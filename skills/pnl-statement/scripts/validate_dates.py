#!/usr/bin/env python3
"""
Date Validation Script

Validates date format and logical constraints before P&L generation.
This prevents errors and wasted compute time.

Usage:
    python validate_dates.py <start_date> <end_date>

Example:
    python validate_dates.py 2024-01-01 2024-01-31

Output:
    VALID - Dates are valid
    ERROR:<message> - Validation failed with reason

Exit codes:
    0 - Valid
    1 - Invalid
"""

import sys
from datetime import datetime


def validate_date_format(date_str: str, param_name: str) -> datetime:
    """Validate date is in YYYY-MM-DD format"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        print(f"ERROR:{param_name} must be in YYYY-MM-DD format, got: {date_str}")
        sys.exit(1)


def validate_dates(start_str: str, end_str: str):
    """Validate date range logic"""

    # Validate format
    start_date = validate_date_format(start_str, "start_date")
    end_date = validate_date_format(end_str, "end_date")

    # Check end date is not before start date
    if end_date < start_date:
        print(f"ERROR:End date ({end_str}) is before start date ({start_str})")
        return 1

    # Check dates are not in the future
    now = datetime.now()
    if start_date > now:
        print(f"ERROR:Start date ({start_str}) is in the future")
        return 1

    if end_date > now:
        print(f"ERROR:End date ({end_str}) is in the future")
        return 1

    # Check date range is not too large (max 1 year)
    days_diff = (end_date - start_date).days
    if days_diff > 365:
        print(f"ERROR:Date range too large ({days_diff} days). Maximum is 365 days.")
        return 1

    # All validations passed
    print("VALID")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("ERROR:Usage: python validate_dates.py <start_date> <end_date>")
        sys.exit(1)

    start_date = sys.argv[1]
    end_date = sys.argv[2]

    sys.exit(validate_dates(start_date, end_date))
