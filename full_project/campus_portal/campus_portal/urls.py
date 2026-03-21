from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from printing import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("printing.urls")),
    path("store/", include("store.urls")),

    # Auth
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),

    # Custom Forgot Password (username-based — no email input shown to user)
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("forgot-password/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="forgot_password_done.html",
    ), name="forgot_password_done"),

    # Password Reset confirm / complete (linked from the email)
    path("password-reset-confirm/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="password_reset_confirm.html",
    ), name="password_reset_confirm"),
    path("password-reset-complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="password_reset_complete.html",
    ), name="password_reset_complete"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
