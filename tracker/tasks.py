from celery import shared_task
from django.core.mail import send_mail
from django.db.models import F
from django.utils import timezone
from django.template.loader import render_to_string
from datetime import timedelta
import logging

from .models import Product, User, UserPreference
from .utils import scrape_product

logger = logging.getLogger(__name__)


@shared_task
def update_all_products():
    """Update all products in the database"""
    products = Product.objects.all()
    logger.info(f"Starting update of {products.count()} products")

    products_updated = 0
    price_drops = 0

    for product in products:
        try:
            data = scrape_product(product.url, product.store)

            if data and "price" in data:
                old_price = product.current_price

                # Update product
                product.current_price = data["price"]
                if "image_url" in data and data["image_url"]:
                    product.image_url = data["image_url"]
                if "description" in data and data["description"]:
                    product.description = data["description"]

                product.is_in_stock = True
                product.save()

                products_updated += 1

                # Check for price drop
                if data["price"] < old_price:
                    price_drops += 1

                    # Store price drop info for notifications
                    # (will be used by daily/weekly notification tasks)
                    if not hasattr(product.user, "_price_drops"):
                        product.user._price_drops = []

                    product.user._price_drops.append(
                        {
                            "product": product,
                            "old_price": old_price,
                            "new_price": data["price"],
                            "drop_percentage": round(
                                ((old_price - data["price"]) / old_price) * 100, 2
                            ),
                        }
                    )
            else:
                # Product might be out of stock or page changed
                product.is_in_stock = False
                product.save()

        except Exception as e:
            logger.error(f"Error updating product {product.id}: {str(e)}")

    logger.info(f"Updated {products_updated} products, found {price_drops} price drops")
    return f"Updated {products_updated} products, found {price_drops} price drops"


@shared_task
def check_daily_price_drops():
    """Send daily price drop notifications to users who prefer daily updates"""
    users = UserPreference.objects.filter(
        email_notifications=True, notification_frequency="daily"
    ).select_related("user")

    for preference in users:
        user = preference.user

        # Get user's products with price drops in the last 24 hours
        yesterday = timezone.now() - timedelta(days=1)
        products = Product.objects.filter(
            user=user, last_checked__gte=yesterday, current_price__lt=F("highest_price")
        ).order_by("-highest_price")

        if products.exists():
            try:
                # Prepare email content
                context = {
                    "user": user,
                    "products": products,
                    "base_url": "http://yourdomain.com",  # Replace with your frontend URL
                }

                html_message = render_to_string(
                    "emails/price_drops_daily.html", context
                )
                plain_message = f"Daily Price Drops Update for {user.username}. Check your tracked products."

                # Send email
                send_mail(
                    subject="🔥 Your Daily Price Drops Update",
                    message=plain_message,
                    from_email="pricetrackerapp@example.com",
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                logger.info(f"Sent daily price drop email to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send daily email to {user.email}: {str(e)}")


@shared_task
def check_weekly_price_drops():
    """Send weekly price drop notifications to users who prefer weekly updates"""
    users = UserPreference.objects.filter(
        email_notifications=True, notification_frequency="weekly"
    ).select_related("user")

    for preference in users:
        user = preference.user

        # Get user's products with price drops in the last 7 days
        last_week = timezone.now() - timedelta(days=7)
        products = Product.objects.filter(
            user=user, last_checked__gte=last_week, current_price__lt=F("highest_price")
        ).order_by("-highest_price")

        if products.exists():
            try:
                # Prepare email content
                context = {
                    "user": user,
                    "products": products,
                    "base_url": "http://yourdomain.com",  # Replace with your frontend URL
                }

                html_message = render_to_string(
                    "emails/price_drops_weekly.html", context
                )
                plain_message = f"Weekly Price Drops Update for {user.username}. Check your tracked products."

                # Send email
                send_mail(
                    subject="🔥 Your Weekly Price Drops Update",
                    message=plain_message,
                    from_email="pricetrackerapp@example.com",
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )

                logger.info(f"Sent weekly price drop email to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send weekly email to {user.email}: {str(e)}")


@shared_task
def delete_old_products():
    """Remove products that haven't been updated in over 30 days"""
    cutoff_date = timezone.now() - timedelta(days=30)
    old_products = Product.objects.filter(last_checked__lt=cutoff_date)

    count = old_products.count()
    old_products.delete()

    logger.info(f"Deleted {count} old products")
    return f"Deleted {count} old products"
