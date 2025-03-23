from accounts.models import User
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.db import IntegrityError
from .models import Product, UserPreference
from .serializers import ProductSerializer, UserPreferenceSerializer
from .utils import scrape_product
import logging

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer

    def get_queryset(self):
        return Product.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        url = request.data.get("url")
        store = request.data.get("store", "daraz")

        try:
            data = scrape_product(url, store)

            if not data:
                return Response(
                    {"error": "Could not fetch product data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                product, created = Product.objects.get_or_create(
                    url=url,
                    user=request.user,
                    defaults={
                        "title": data["title"],
                        "current_price": data["price"],
                        "image_url": data.get("image_url", ""),
                        "description": data.get("description", ""),
                        "store": store,
                    },
                )
                if not created:
                    # ? if the product exists, update
                    product.current_price = data["price"]
                    if "image_url" in data:
                        product.image_url = data["image_url"]
                    if "description" in data:
                        product.description = data["description"]
                    product.save()

                # ? check if the price dropped below threshold for notification
                should_notify = False
                user_preferences = self.request.user.preferences

                if not created and data["price"] < product.lowest_price:
                    # ? price hit alltime low
                    should_notify = True
                elif (
                    product.alert_threshold and data["price"] <= product.alert_threshold
                ):
                    # ? price hit users target
                    should_notify = True

                # ?send notification if needed and user prefers instant notifications
                if (
                    should_notify
                    and user_preferences.email_notifications
                    and user_preferences.notification_frequency == "instant"
                ):
                    try:
                        send_mail(
                            "🔥 Price Drop Alert!",
                            f"The price of {product.title} has dropped to Rs. {data['price']}!",
                            "aviralale@gmail.com",
                            [request.user.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send email: {str(e)}")

                return Response(
                    ProductSerializer(product).data,
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
                )

            except IntegrityError:
                return Response(
                    {"error": "YOu're already tracking this product"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except Exception as e:
            logger.error(f"Error creating product: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"])
    def set_alert(self, request, pk=None):
        product = self.get_object()
        threshold = request.data.get("threshold")

        if threshold is None:
            return Response(
                {"error": "Threshold is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            threshold = int(threshold)
            product.alert_threshold = threshold
            product.save(update_fields=["alert_threshold"])
            return Response(
                {"success": True, "message": f"Alert set at Rs. {threshold}"}
            )
        except ValueError:
            return Response(
                {"error": "Invalid threshold value"}, status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        product = self.get_object()

        try:
            data = scrape_product(product.url, product.store)

            if not data:
                return Response(
                    {"error": "Could not fetch product data"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            old_price = product.current_price
            product.current_price = data["price"]

            if "image_url" in data:
                product.image_url = data["image_url"]
            if "description" in data:
                product.description = data["description"]

            product.save()

            # ? check for price drop notification

            if data["price"] < old_price:
                user_preferences = request.user.preferences
                if (
                    user_preferences.email_notifications
                    and user_preferences.notification_frequency == "instant"
                ):
                    try:
                        send_mail(
                            "🔥 Price Drop Alert!",
                            f"The price of {product.title} has dropped from Rs. {old_price} to Rs. {data['price']}!",
                            "your-email@example.com",
                            [request.user.email],
                            fail_silently=False,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send email: {str(e)}")

            return Response(ProductSerializer(product).data)

        except Exception as e:
            logger.error(f"Error refreshing product: {str(e)}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserPreferenceView(APIView):
    def get(self, request):
        preference, created = UserPreference.objects.get_or_create(user=request.user)
        return Response(UserPreferenceSerializer(preference).data)

    def put(self, request):
        preference, created = UserPreference.objects.get_or_create(user=request.user)
        serializer = UserPreferenceSerializer(
            preference, data=request.data, partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
