from django.urls import path
from . import views
from django.shortcuts import render

urlpatterns = [
    path("", views.home, name="home"),
    path("repro/", views.repro, name="repro"),
    path("repro/payment/<int:pk>/", views.repro_payment, name="repro_payment"),
    path("orders/", views.orders, name="orders"),
    path("download/<int:pk>/", views.download_document, name="download_document"),
    path("repro-admin/", views.repro_admin_dashboard, name="repro_admin_dashboard"),
    path("update-status/<int:pk>/", views.update_status, name="update_status"),
    path("super-admin/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("update-role/<int:user_id>/", views.update_user_role, name="update_user_role"),
    path("create-user/", views.create_user, name="create_user"),
    path("delete-user/<int:user_id>/", views.delete_user, name="delete_user"),
    path("reset-password/<int:user_id>/", views.reset_password, name="reset_password"),
    path("update-email/<int:user_id>/", views.update_user_email, name="update_user_email"),
    path("about/", views.about, name="about"),

    # Custom Forgot Password (username-based, no email input)
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/done/", lambda req: render(req, "forgot_password_done.html"), name="forgot_password_done"),
]
