"""Shared pagination helpers for list APIs.

Nurse FE clients historically expect bare arrays for vitals/notes/medication
history and wrap them client-side. Keep returning arrays in the body, and expose
accurate totals via response headers so pagination stays correct without a
frontend contract break.
"""

from __future__ import annotations

from typing import Sequence, TypeVar

from fastapi import Response

T = TypeVar("T")

TOTAL_COUNT_HEADER = "X-Total-Count"
PAGE_HEADER = "X-Page"
PAGE_SIZE_HEADER = "X-Page-Size"


def clamp_page(page: int | None, default: int = 1) -> int:
    return max(int(page or default), 1)


def clamp_page_size(
    page_size: int | None,
    *,
    default: int = 20,
    maximum: int = 100,
) -> int:
    size = int(page_size or default)
    return min(max(size, 1), maximum)


def paginate_sequence(
    rows: Sequence[T],
    *,
    page: int | None = None,
    page_size: int | None = None,
    default_page_size: int = 20,
    maximum: int = 100,
) -> tuple[list[T], int, int, int]:
    """Slice an in-memory list. When page is None, return all rows (legacy)."""
    total = len(rows)
    if page is None:
        return list(rows), total, 1, total or default_page_size

    page_n = clamp_page(page)
    size = clamp_page_size(
        page_size, default=default_page_size, maximum=maximum
    )
    start = (page_n - 1) * size
    return list(rows[start : start + size]), total, page_n, size


def set_pagination_headers(
    response: Response,
    *,
    total: int,
    page: int,
    page_size: int,
) -> None:
    response.headers[TOTAL_COUNT_HEADER] = str(int(total))
    response.headers[PAGE_HEADER] = str(int(page))
    response.headers[PAGE_SIZE_HEADER] = str(int(page_size))


def paged_payload(
    items: Sequence[T],
    *,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    return {
        "success": True,
        "total": int(total),
        "page": int(page),
        "page_size": int(page_size),
        "items": list(items),
    }
