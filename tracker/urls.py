from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, UserPreferenceView

router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")

urlpatterns = [
    path("", include(router.urls)),
    path("preferences/", UserPreferenceView.as_view(), name="user-preferences"),
]
