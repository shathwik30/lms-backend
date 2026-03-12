def swagger_safe(model_class):
    """Wraps get_queryset to return an empty queryset when generating the OpenAPI schema."""

    def decorator(get_queryset_method):
        def wrapper(self):
            if getattr(self, "swagger_fake_view", False):
                return model_class.objects.none()
            return get_queryset_method(self)

        return wrapper

    return decorator
