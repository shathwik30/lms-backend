import uuid

from rest_framework import serializers


class UUIDOrLegacyIntegerField(serializers.UUIDField):
    """Accept UUIDs while keeping old integer IDs on the not-found path."""

    def to_internal_value(self, data):
        if isinstance(data, int) and data >= 0:
            return self._uuid_from_int(data)
        if isinstance(data, str) and data.isdigit():
            return self._uuid_from_int(int(data))
        return super().to_internal_value(data)

    @staticmethod
    def _uuid_from_int(value: int):
        return uuid.UUID(int=value)
