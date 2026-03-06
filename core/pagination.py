from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SmallPagination(PageNumberPagination):
    """For student-facing lists with moderate data (notifications, bookmarks, doubts)."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class LargePagination(PageNumberPagination):
    """For admin tables with many records (questions, attempts, students)."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
