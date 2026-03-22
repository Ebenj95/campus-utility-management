from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("repro/", views.repro, name="repro"),
    path("orders/", views.orders, name="order"),
    path("my-orders/", views.my_orders_combined, name="my_orders_combined"),
    path("download/<int:pk>/", views.download_document, name="download_document"),
    path("about/", views.about, name="about"),
    path("notifications/seen/", views.mark_notifications_seen, name="mark_notifications_seen"),
]
