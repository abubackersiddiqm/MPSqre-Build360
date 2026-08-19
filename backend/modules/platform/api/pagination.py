from rest_framework.pagination import CursorPagination as DRFCursorPagination


class CursorPagination(DRFCursorPagination):
    page_size = 50
    max_page_size = 100
    ordering = ("-created_at", "-public_id")

