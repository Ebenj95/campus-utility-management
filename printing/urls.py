from django.urls import path
from . import views

urlpatterns = [
    # Customer
    path("", views.home, name="home"),
    path("repro/", views.repro, name="repro"),
    path("repro/payment/<int:pk>/", views.repro_payment, name="repro_payment"),
    path("orders/", views.orders, name="orders"),
    path("my-orders/", views.my_orders_combined, name="my_orders_combined"),
    path("download/<int:pk>/", views.download_document, name="download_document"),
    path("about/", views.about, name="about"),
    path("notifications/seen/", views.mark_notifications_seen, name="mark_notifications_seen"),

    # Repro admin
    path("repro-admin/", views.repro_admin_dashboard, name="repro_admin_dashboard"),
    path("repro-admin/update-status/<int:pk>/", views.update_status, name="update_status"),

    # Super admin
    path("super-admin/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("super-admin/create-user/", views.create_user, name="create_user"),
    path("super-admin/delete-user/<int:user_id>/", views.delete_user, name="delete_user"),
    path("super-admin/update-role/<int:user_id>/", views.update_user_role, name="update_user_role"),
    path("super-admin/reset-password/<int:user_id>/", views.reset_password, name="reset_password"),
    path("super-admin/update-email/<int:user_id>/", views.update_user_email, name="update_user_email"),
]