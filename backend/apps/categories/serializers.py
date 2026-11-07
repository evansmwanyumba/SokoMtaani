from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from .models import Category


class CategorySummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug", "description", "icon")


class CategorySerializer(CategorySummarySerializer):
    count = serializers.SerializerMethodField()
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "count",
            "subcategories",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_count(self, obj):
        return getattr(obj, "active_product_count", 0)

    @extend_schema_field(CategorySummarySerializer(many=True))
    def get_subcategories(self, obj):
        children = getattr(obj, "active_children", None)
        if children is None:
            children = obj.children.filter(is_active=True)
        return CategorySummarySerializer(children, many=True, context=self.context).data
