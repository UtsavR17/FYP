# pagination.py
# Pagination helper for list views.
#
# Note: This helper paginates a list already fetched from Supabase.
# For large datasets in future phases, consider switching to
# Supabase .range(start, end) for database-level pagination.


def paginate(items, page, per_page=10):
    """
    Paginate a list of items.

    Args:
        items: full list of records fetched from Supabase
        page: current page number (1-indexed)
        per_page: number of records per page (default 10)

    Returns:
        dict with keys:
            items       — the slice of records for the current page
            page        — current page number
            per_page    — records per page
            total       — total number of records
            total_pages — total number of pages
            has_prev    — True if a previous page exists
            has_next    — True if a next page exists
    """
    total = len(items)
    total_pages = max(1, -(-total // per_page))  # ceiling division
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page

    return {
        'records': items[start:end],
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }