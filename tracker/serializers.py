from .models import Product, UserPreference
from accounts.serializers import UserCreateSerializer, UserSerializer
from rest_framework import serializers


class UserPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreference
        fields = ["email_notifications", "notification_frequency", "target_price_drop"]


class ProductSerializer(serializers.ModelSerializer):
    price_drop_percentage = serializers.SerializerMethodField()
    price_history = serializers.JSONField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "url",
            "title",
            "current_price",
            "lowest_price",
            "highest_price",
            "last_checked",
            "image_url",
            "description",
            "price_history",
            "alert_threshold",
            "is_in_stock",
            "store",
            "price_drop_percentage",
            "created_at",
        ]
        read_only_fields = [
            "title",
            "current_price",
            "lowest_price",
            "highest_price",
            "last_checked",
            "image_url",
            "description",
            "price_history",
        ]

    def get_price_drop_percentage(self, obj):
        if obj.highest_price > 0:
            drop = obj.highest_price - obj.current_price
            percentage = drop / obj.highest_price
            return round(percentage, 2)
        return 0
