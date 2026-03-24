class TrailingSlashMiddleware:
    """Internally append a trailing slash so the API accepts both
    ``/auth/register`` and ``/auth/register/`` without issuing a 301 redirect
    (which breaks POST/PUT/PATCH/DELETE in most HTTP clients)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path_info.endswith("/"):
            request.path_info += "/"
        return self.get_response(request)
