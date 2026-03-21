from django.shortcuts import render, redirect
from django.contrib import messages
from .models import PrintOrder, NotificationSeen
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io, os
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.contrib.auth.hashers import make_password
from store.models import StoreOrder, CartItem


# ── Role helpers ───────────────────────────────────────────────────────────────
def is_store_admin(user):
    return user.groups.filter(name="store_admin").exists() or user.is_superuser

def is_repro_admin(user):
    return user.groups.filter(name="repro_admin").exists() or user.is_superuser

def is_customer(user):
    return not (is_store_admin(user) or is_repro_admin(user))

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".txt", ".odt", ".ods", ".odp",
    ".rtf", ".csv", ".png", ".jpg", ".jpeg",
}


# ── Notification helpers ───────────────────────────────────────────────────────

def _get_seen_at(user):
    """Return the datetime the user last clicked the bell, or None."""
    try:
        return user.notif_seen.seen_at
    except NotificationSeen.DoesNotExist:
        return None


def get_user_notifications(user):
    """
    For regular users: their last 10 repro+store orders as status notifications.
    Each note includes is_new=True if created after the user last saw the bell.
    """
    seen_at = _get_seen_at(user)
    notes = []
    for o in PrintOrder.objects.filter(user=user).order_by("-id")[:10]:
        label = {"pending": "⏳ Pending", "printing": "🖨️ Printing", "done": "✅ Done"}.get(o.status, o.status)
        is_new = seen_at is None or o.created_at > seen_at
        notes.append({
            "id": f"repro-{o.id}",
            "icon": "🖨️",
            "order_number": o.order_number,
            "message": f"Repro order {o.order_number} — {label}",
            "status": o.status,
            "url": reverse("my_orders_combined") + "#repro",
            "is_new": is_new,
        })
    for o in StoreOrder.objects.filter(user=user).order_by("-created_at")[:10]:
        label = {"pending": "⏳ Pending", "ready": "📦 Ready for Pickup",
                 "completed": "✅ Completed", "cancelled": "❌ Cancelled"}.get(o.status, o.status)
        is_new = seen_at is None or o.created_at > seen_at
        notes.append({
            "id": f"store-{o.id}",
            "icon": "🛒",
            "order_number": o.order_number,
            "message": f"Store order {o.order_number} — {label}",
            "status": o.status,
            "url": reverse("my_orders_combined") + "#store",
            "is_new": is_new,
        })
    return notes


def get_repro_admin_notifications(limit=20):
    """Pending + printing repro orders for repro admin bell."""
    notes = []
    for o in PrintOrder.objects.filter(status__in=["pending", "printing"]).order_by("-id")[:limit]:
        label = {"pending": "⏳ Pending", "printing": "🖨️ Printing"}.get(o.status)
        notes.append({
            "id": f"repro-{o.id}",
            "icon": "🖨️",
            "order_number": o.order_number,
            "message": f"{o.user.username} — {o.order_number} [{label}]",
            "status": o.status,
            "url": reverse("repro_admin_dashboard") + f"#order-{o.id}",
            "is_new": False,
        })
    return notes


def get_store_admin_notifications(limit=20):
    """Pending store orders for store admin bell."""
    notes = []
    for o in StoreOrder.objects.filter(status="pending").order_by("-created_at")[:limit]:
        notes.append({
            "id": f"store-{o.id}",
            "icon": "🛒",
            "order_number": o.order_number,
            "message": f"{o.user.username} — {o.order_number} [⏳ Pending]",
            "status": "pending",
            "url": reverse("store_admin_dashboard") + f"#order-{o.id}",
            "is_new": False,
        })
    return notes


def _notif_count(user, notifications):
    """
    For ALL users: only notifications newer than seen_at count toward the red dot.
    - Regular users: orders created after seen_at
    - Admins: pending orders created after seen_at (so clicking the bell clears the dot
      permanently until a genuinely new order comes in)
    """
    seen_at = _get_seen_at(user)
    if seen_at is None:
        return len(notifications)
    if is_customer(user):
        return sum(1 for n in notifications if n.get("is_new"))
    # For admins: count pending orders created after they last viewed the bell
    from store.models import StoreOrder
    new_store = StoreOrder.objects.filter(status="pending", created_at__gt=seen_at).count()
    new_repro  = PrintOrder.objects.filter(status__in=["pending", "printing"], created_at__gt=seen_at).count()
    if user.groups.filter(name="store_admin").exists() or user.is_superuser:
        return new_store
    if user.groups.filter(name="repro_admin").exists():
        return new_repro
    return 0


@login_required
def mark_notifications_seen(request):
    """
    POST endpoint called silently when the user opens the bell.
    Saves timezone.now() as seen_at so the dot disappears permanently
    until a genuinely new notification arrives.
    """
    if request.method == "POST":
        NotificationSeen.objects.update_or_create(
            user=request.user,
            defaults={"seen_at": timezone.now()},
        )
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False}, status=405)


# ── PDF footer stamping ────────────────────────────────────────────────────────
def _stamp_footer_on_pdf(pdf_bytes, order_number, username, timestamp_str):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    footer_text = f"Order: {order_number}  |  User: {username}  |  {timestamp_str}"
    for page in reader.pages:
        packet = io.BytesIO()
        c = canvas.Canvas(packet, pagesize=A4)
        c.setFont("Helvetica", 8)
        c.setDash(4, 3)
        c.line(40, 38, 555, 38)
        c.setDash()
        c.drawString(20, 28, "✂")
        c.setFont("Helvetica", 9)
        c.drawCentredString(300, 18, footer_text)
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)
        writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return out


@login_required
@user_passes_test(is_repro_admin)
def download_document(request, pk):
    order = get_object_or_404(PrintOrder, pk=pk)
    order.status = "printing"
    order.save(update_fields=["status"])
    file_path = order.document.path
    ext = os.path.splitext(file_path)[1].lower()
    timestamp_str = timezone.now().strftime("%d %b %Y, %I:%M %p")
    safe_name = f"print_{order.order_number}{ext}"
    if ext == ".pdf":
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()
        out = _stamp_footer_on_pdf(pdf_bytes, order.order_number, order.user.username, timestamp_str)
        return FileResponse(out, as_attachment=True, filename=f"print_{order.order_number}.pdf")
    else:
        return FileResponse(open(file_path, "rb"), as_attachment=True, filename=safe_name)


# ── Customer views ─────────────────────────────────────────────────────────────
@login_required
def home(request):
    if request.user.groups.filter(name="repro_admin").exists():
        return redirect("repro_admin_dashboard")
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("store_admin_dashboard")
    if request.user.is_superuser:
        return redirect("super_admin_dashboard")

    repro_orders = PrintOrder.objects.filter(user=request.user).order_by("-id")[:5]
    store_orders = StoreOrder.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")[:5]
    notifications = get_user_notifications(request.user)

    return render(request, "printing/main.html", {
        "repro_orders": repro_orders,
        "store_orders": store_orders,
        "notifications": notifications,
        "notif_count": _notif_count(request.user, notifications),
    })


@login_required
def repro(request):
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("home")
    if request.user.groups.filter(name="repro_admin").exists():
        return redirect("home")

    if request.method == "POST":
        uploaded = request.FILES.get("document")
        if uploaded:
            ext = os.path.splitext(uploaded.name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                messages.error(request,
                    f"❌ File type '{ext}' is not allowed. "
                    "Please upload PDF, Word, Excel, PowerPoint, image, or text files.")
                return redirect("repro")
        PrintOrder.objects.create(
            user=request.user, document=uploaded,
            copies=request.POST.get("copies"),
            color_mode=request.POST.get("color_mode"),
            paper_size=request.POST.get("paper_size"),
            print_side=request.POST.get("print_side"),
            binding=request.POST.get("binding"),
            instructions=request.POST.get("instructions"),
        )
        messages.success(request, "✅ Your print order has been submitted!")
        return redirect("repro")

    notifications = get_user_notifications(request.user)
    return render(request, "printing/repro.html", {
        "notifications": notifications,
        "notif_count": _notif_count(request.user, notifications),
    })


@login_required
def orders(request):
    # Only repro orders here — used by "Order History" link from repro page
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("home")
    if request.user.is_superuser or request.user.groups.filter(name="repro_admin").exists():
        qs = PrintOrder.objects.all().order_by("-id")
    else:
        qs = PrintOrder.objects.filter(user=request.user).order_by("-id")

    notifications = get_user_notifications(request.user) if is_customer(request.user) else []
    return render(request, "printing/orders.html", {
        "orders": qs,
        "notifications": notifications,
        "notif_count": _notif_count(request.user, notifications),
    })


@login_required
def my_orders_combined(request):
    if request.user.groups.filter(name="repro_admin").exists() or \
       request.user.groups.filter(name="store_admin").exists() or \
       request.user.is_superuser:
        return redirect("home")
    repro_orders = PrintOrder.objects.filter(user=request.user).order_by("-id")
    store_orders = StoreOrder.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")
    notifications = get_user_notifications(request.user)
    return render(request, "printing/my_orders.html", {
        "repro_orders": repro_orders,
        "store_orders": store_orders,
        "notifications": notifications,
        "notif_count": _notif_count(request.user, notifications),
    })


@login_required
def store(request):
    if is_repro_admin(request.user):
        return redirect("home")
    return render(request, "printing/store.html")


# ── Repro admin ────────────────────────────────────────────────────────────────
@login_required
def repro_admin_dashboard(request):
    if not (request.user.is_superuser or
            request.user.groups.filter(name="repro_admin").exists()):
        return redirect("home")
    all_orders     = PrintOrder.objects.all().order_by("-id")
    print_orders   = all_orders.filter(binding="none")
    binding_orders = all_orders.exclude(binding="none")
    pending_orders = all_orders.filter(status="pending")
    notifications  = get_repro_admin_notifications()
    return render(request, "printing/repro_admin_dashboard.html", {
        "print_orders": print_orders,
        "binding_orders": binding_orders,
        "pending_orders": pending_orders,
        "notifications": notifications,
        "notif_count": _notif_count(request.user, notifications),
    })


@login_required
def update_status(request, pk):
    if not (request.user.is_superuser or
            request.user.groups.filter(name="repro_admin").exists()):
        return redirect("home")
    order = PrintOrder.objects.get(pk=pk)
    if request.method == "POST":
        order.status = request.POST.get("status")
        order.save()
    return redirect("repro_admin_dashboard")


# ── Super admin ────────────────────────────────────────────────────────────────
@login_required
def super_admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect("home")
    total_users          = User.objects.count()
    total_print_orders   = PrintOrder.objects.count()
    pending_print_orders = PrintOrder.objects.filter(status="pending").count()
    total_store_orders   = StoreOrder.objects.count()
    pending_store_orders = StoreOrder.objects.filter(status="pending").count()
    users = User.objects.all().order_by("-id")
    return render(request, "printing/super_admin_dashboard.html", {
        "total_users": total_users,
        "total_print_orders": total_print_orders,
        "pending_print_orders": pending_print_orders,
        "total_store_orders": total_store_orders,
        "pending_store_orders": pending_store_orders,
        "users": users,
    })


@login_required
def update_user_role(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = User.objects.get(id=user_id)
    if request.method == "POST":
        new_role = request.POST.get("role")
        user.groups.clear()
        if new_role == "repro_admin":
            user.groups.add(Group.objects.get(name="repro_admin"))
            user.is_staff = True
        elif new_role == "store_admin":
            user.groups.add(Group.objects.get(name="store_admin"))
            user.is_staff = True
        else:
            user.is_staff = False
        user.save()
    return redirect("super_admin_dashboard")


@login_required
def create_user(request):
    if not request.user.is_superuser:
        return redirect("home")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        email    = request.POST.get("email", "").strip()
        if User.objects.filter(username=username).exists():
            messages.error(request, "❌ Username already exists!")
        else:
            User.objects.create(username=username, password=make_password(password), email=email)
            messages.success(request, "✅ User created successfully!")
    return redirect("super_admin_dashboard")


@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = User.objects.get(id=user_id)
    if not user.is_superuser:
        user.delete()
    return redirect("super_admin_dashboard")


@login_required
def reset_password(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = User.objects.get(id=user_id)
    if request.method == "POST":
        new_password = request.POST.get("new_password")
        if new_password:
            user.password = make_password(new_password)
            user.save()
            messages.success(request, f"✅ Password reset for {user.username}")
    return redirect("super_admin_dashboard")


@login_required
def update_user_email(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        user.email = request.POST.get("email", "").strip()
        user.save()
        messages.success(request, f"✅ Email updated for {user.username}")
    return redirect("super_admin_dashboard")


def forgot_password(request):
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return redirect("forgot_password_done")
        user.refresh_from_db()
        if not user.email or user.email.strip() == "":
            messages.error(request, f"⚠️ No email for '{username}'. Ask admin to add it.")
            return render(request, "forgot_password.html")
        uid   = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        protocol = "https" if request.is_secure() else "http"
        domain   = request.get_host()
        reset_url = f"{protocol}://{domain}/password-reset-confirm/{uid}/{token}/"
        subject = "Campus Portal — Password Reset Request"
        body = (f"Hi {user.username},\n\nReset link:\n{reset_url}\n\n"
                f"⚠️ Expires in 5 minutes.\n\n— Campus Portal Team")
        try:
            send_mail(subject, body, django_settings.DEFAULT_FROM_EMAIL, [user.email])
        except Exception as e:
            messages.error(request, f"⚠️ Failed to send email: {str(e)}")
            return render(request, "forgot_password.html")
        return redirect("forgot_password_done")
    return render(request, "forgot_password.html")


class CustomLoginView(LoginView):
    template_name = "login.html"
    def get_success_url(self):
        user = self.request.user
        if user.groups.filter(name="repro_admin").exists():
            return reverse("repro_admin_dashboard")
        if user.groups.filter(name="store_admin").exists():
            return reverse("store_admin_dashboard")
        if user.is_superuser:
            return reverse("super_admin_dashboard")
        return reverse("home")


def about(request):
    notifications = []
    notif_count = 0
    if request.user.is_authenticated and is_customer(request.user):
        notifications = get_user_notifications(request.user)
        notif_count   = _notif_count(request.user, notifications)
    return render(request, "printing/about.html", {
        "notifications": notifications,
        "notif_count": notif_count,
    })
