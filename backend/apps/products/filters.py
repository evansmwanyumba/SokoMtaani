from decimal import Decimal, InvalidOperation

from django.db.models import Avg, Q
from rest_framework.exceptions import ValidationError
from rest_framework.filters import BaseFilterBackend

from .models import ProductCondition


class ProductFilterBackend(BaseFilterBackend):
    search_fields = ("name", "description", "category__name", "county", "town", "neighbourhood")

    def filter_queryset(self, request, queryset, view):
        params = request.query_params

        county = params.get("county")
        if county:
            queryset = queryset.filter(county__iexact=county.strip())

        town = params.get("town")
        if town:
            queryset = queryset.filter(
                Q(town__icontains=town.strip())
                | Q(neighbourhood__icontains=town.strip())
            )

        category = params.get("category")
        if category:
            queryset = queryset.filter(
                Q(category__name__iexact=category.strip())
                | Q(category__slug__iexact=category.strip())
            )
        subcategory = params.get("subcategory")
        if subcategory:
            queryset = queryset.filter(
                Q(category__name__iexact=subcategory.strip())
                | Q(category__slug__iexact=subcategory.strip())
            )

        seller = params.get("seller")
        if seller:
            queryset = queryset.filter(seller_id=seller)

        condition = params.get("condition")
        if condition:
            condition = condition.strip().casefold().replace(" ", "_")
            valid_conditions = {value for value, _ in ProductCondition.choices}
            if condition not in valid_conditions:
                # Accept the human-readable condition labels used by the frontend.
                condition = condition.replace("_", " ")
                condition = next(
                    (value for value, label in ProductCondition.choices if label.casefold() == condition),
                    None,
                )
            if condition is None:
                raise ValidationError({"condition": "Choose a valid product condition."})
            queryset = queryset.filter(condition=condition)

        minimum = self._price(params.get("min_price"), "min_price")
        maximum = self._price(params.get("max_price"), "max_price")
        if minimum is not None:
            queryset = queryset.filter(price__gte=minimum)
        if maximum is not None:
            queryset = queryset.filter(price__lte=maximum)
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValidationError({"max_price": "Maximum price must be greater than or equal to minimum price."})

        minimum_rating = params.get("rating") or params.get("min_rating")
        if minimum_rating not in (None, ""):
            try:
                minimum_rating = float(minimum_rating)
            except (TypeError, ValueError):
                raise ValidationError({"rating": "Enter a rating from 0 to 5."}) from None
            if not 0 <= minimum_rating <= 5:
                raise ValidationError({"rating": "Enter a rating from 0 to 5."})
            queryset = queryset.annotate(
                seller_rating_filter=Avg(
                    "seller__seller_reviews_received__rating",
                    filter=Q(seller__seller_reviews_received__is_visible=True),
                )
            ).filter(seller_rating_filter__gte=minimum_rating)

        keyword = params.get("search") or params.get("keyword")
        if keyword:
            query = Q()
            for field in self.search_fields:
                query |= Q(**{f"{field}__icontains": keyword.strip()})
            queryset = queryset.filter(query)

        sort = params.get("sort", "newest")
        orderings = {
            "newest": ("-published_at", "-created_at"),
            "price_asc": ("price", "id"),
            "price_desc": ("-price", "id"),
            "popular": ("-view_count", "-published_at"),
        }
        if sort not in orderings:
            raise ValidationError({"sort": "Choose newest, price_asc, price_desc, or popular."})
        return queryset.order_by(*orderings[sort])

    @staticmethod
    def _price(value, field):
        if value in (None, ""):
            return None
        try:
            price = Decimal(value)
        except (InvalidOperation, TypeError):
            raise ValidationError({field: "Enter a valid price."}) from None
        if not price.is_finite() or price < 0:
            raise ValidationError({field: "Price must be a non-negative number."})
        return price
