"""Helpers for admin-owned shift start/end times stored as SQL TIME."""
from datetime import time
from typing import Optional, Union

ShiftTimeInput = Union[str, time, None]


def format_shift_time(value: Optional[time]) -> Optional[str]:
    if value is None:
        return None
    return value.strftime("%H:%M")


def parse_shift_time(value: ShiftTimeInput) -> Optional[time]:
    if value is None:
        return None
    if isinstance(value, time):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            from datetime import datetime

            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise ValueError(f"Invalid shift time {value!r}; expected HH:MM or HH:MM:SS")
