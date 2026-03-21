from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from printing import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("", include("printing.urls")),
    path("store/", include("store.urls")),
    path("repro/", views.repro, name="repro"),
    path("orders/", views.orders, name="orders"),
    path("my-orders/", views.my_orders_combined, name="my_orders_combined"),
    path("download/<int:pk>/", views.download_document, name="download_document"),
    path("repro-admin/", views.repro_admin_dashboard, name="repro_admin_dashboard"),
    path("update-status/<int:pk>/", views.update_status, name="update_status"),
    path("super-admin/", views.super_admin_dashboard, name="super_admin_dashboard"),
    path("update-role/<int:user_id>/", views.update_user_role, name="update_user_role"),
    path("create-user/", views.create_user, name="create_user"),
    path("delete-user/<int:user_id>/", views.delete_user, name="delete_user"),
    path("reset-password/<int:user_id>/", views.reset_password, name="reset_password"),
    path("update-email/<int:user_id>/", views.update_user_email, name="update_user_email"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="forgot_password_done.html"), name="forgot_password_done"),
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="password_reset_confirm.html"), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="password_reset_complete.html"), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
