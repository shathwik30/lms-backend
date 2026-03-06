from rest_framework import serializers

from .models import Banner


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "image_url",
            "link_type",
            "link_id",
            "link_url",
            "order",
            "is_active",
        ]


class BannerReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = [
            "id",
            "title",
            "subtitle",
            "image_url",
            "link_type",
            "link_id",
            "link_url",
        ]
        read_only_fields = fields
