from django.shortcuts import render, redirect
from django.contrib import messages
from .models import PrintOrder
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.db.models import Count, Sum
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
import os


# ── Role Helpers ─────────────────────────────────────────────────────────────

def is_store_admin(user):
    return user.groups.filter(name="store_admin").exists() or user.is_superuser

def is_repro_admin(user):
    return user.groups.filter(name="repro_admin").exists() or user.is_superuser

def is_customer(user):
    return not (
        user.groups.filter(name="store_admin").exists() or
        user.groups.filter(name="repro_admin").exists() or
        user.is_superuser
    )


# ── Home ─────────────────────────────────────────────────────────────────────

@login_required
def home(request):
    if request.user.groups.filter(name="repro_admin").exists():
        return redirect("repro_admin_dashboard")
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("store_admin_dashboard")
    if request.user.is_superuser:
        return redirect("super_admin_dashboard")
    return render(request, "printing/main.html")


# ── Repro (Customer) ──────────────────────────────────────────────────────────

@login_required
def repro(request):
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("home")
    if request.user.groups.filter(name="repro_admin").exists():
        return redirect("home")

    if request.method == "POST":
        # Calculate estimated price
        copies = int(request.POST.get("copies", 1))
        color_mode = request.POST.get("color_mode", "bw")
        paper_size = request.POST.get("paper_size", "A4")
        print_side = request.POST.get("print_side", "single")
        binding = request.POST.get("binding", "none")

        # Store order in session for payment screen
        request.session["pending_repro"] = {
            "copies": copies,
            "color_mode": color_mode,
            "paper_size": paper_size,
            "print_side": print_side,
            "binding": binding,
            "instructions": request.POST.get("instructions", ""),
        }

        # Save file to session via temp storage - we'll handle in payment confirm
        # Actually we need to save file now and store pk
        order = PrintOrder.objects.create(
            user=request.user,
            document=request.FILES.get("document"),
            copies=copies,
            color_mode=color_mode,
            paper_size=paper_size,
            print_side=print_side,
            binding=binding,
            instructions=request.POST.get("instructions", ""),
            status="pending_payment",
        )
        return redirect("repro_payment", pk=order.pk)

    return render(request, "printing/repro.html")


@login_required
def repro_payment(request, pk):
    """Dummy payment screen for repro order."""
    if not is_customer(request.user):
        return redirect("home")

    order = get_object_or_404(PrintOrder, pk=pk, user=request.user)

    if order.status != "pending_payment":
        return redirect("orders")

    # Calculate price
    price_per_page = 10 if order.color_mode == "color" else 2
    if order.paper_size == "A3":
        price_per_page *= 2
    binding_cost = {"spiral": 30, "thermal": 50, "hardcover": 100}.get(order.binding, 0)
    # Estimate 5 pages as default (we don't count pages here)
    estimated = (price_per_page * 5 * order.copies) + binding_cost

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "pay":
            order.status = "paid"
            order.estimated_price = estimated
            order.save()
            messages.success(request, f"✅ Payment successful! Your order ID is {order.order_number}")
            return redirect("orders")
        elif action == "cancel":
            order.delete()
            messages.info(request, "Order cancelled.")
            return redirect("repro")

    return render(request, "printing/repro_payment.html", {
        "order": order,
        "estimated": estimated,
    })


@login_required
def orders(request):
    if request.user.is_superuser:
        orders = PrintOrder.objects.exclude(status="pending_payment").order_by("-id")
    elif request.user.groups.filter(name="repro_admin").exists():
        orders = PrintOrder.objects.exclude(status="pending_payment").order_by("-id")
    elif request.user.groups.filter(name="store_admin").exists():
        return redirect("home")
    else:
        orders = PrintOrder.objects.filter(
            user=request.user
        ).exclude(status="pending_payment").order_by("-id")

    return render(request, "printing/orders.html", {"orders": orders})


# ── Repro Admin ───────────────────────────────────────────────────────────────

@login_required
def repro_admin_dashboard(request):
    if not (request.user.is_superuser or request.user.groups.filter(name="repro_admin").exists()):
        return redirect("home")

    orders = PrintOrder.objects.exclude(status="pending_payment").order_by("-id")

    # Stats
    total = orders.count()
    paid = orders.filter(status="paid").count()
    printing = orders.filter(status="printing").count()
    collected = orders.filter(status="collected").count()

    return render(request, "printing/repro_admin_dashboard.html", {
        "orders": orders,
        "total": total,
        "paid": paid,
        "printing": printing,
        "collected": collected,
    })


@login_required
def download_document(request, pk):
    if not (request.user.is_superuser or request.user.groups.filter(name="repro_admin").exists()):
        return redirect("home")

    order = get_object_or_404(PrintOrder, pk=pk)

    order.status = "printing"
    order.save(update_fields=["status"])

    reader = PdfReader(order.document.path)
    writer = PdfWriter()

    for page in reader.pages:
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A4)
        footer = f"Order: {order.order_number}  |  User: {order.user.username}  |  {timezone.now().strftime('%d %b %Y, %I:%M %p')}  |  Cut here after collection"
        can.setFont("Helvetica", 8)
        can.setDash(4, 4)
        can.line(40, 38, 555, 38)
        can.setDash()
        can.setFont("Helvetica", 9)
        can.drawCentredString(300, 22, footer)
        can.save()
        packet.seek(0)
        overlay = PdfReader(packet).pages[0]
        page.merge_page(overlay)
        writer.add_page(page)

    out = io.BytesIO()
    writer.write(out)
    out.seek(0)
    return FileResponse(out, as_attachment=True, filename=f"{order.order_number}.pdf")


@login_required
def update_status(request, pk):
    if not (request.user.is_superuser or request.user.groups.filter(name="repro_admin").exists()):
        return redirect("home")

    order = get_object_or_404(PrintOrder, pk=pk)
    if request.method == "POST":
        order.status = request.POST.get("status")
        order.save()
    return redirect("repro_admin_dashboard")


# ── Super Admin ───────────────────────────────────────────────────────────────

@login_required
def super_admin_dashboard(request):
    if not request.user.is_superuser:
        return redirect("home")

    from store.models import StoreOrder

    # User stats
    total_users = User.objects.count()
    users = User.objects.all().order_by("-id")

    # Repro stats
    repro_orders = PrintOrder.objects.exclude(status="pending_payment")
    total_print = repro_orders.count()
    pending_print = repro_orders.filter(status="paid").count()
    repro_revenue = repro_orders.exclude(status="cancelled").aggregate(
        total=Sum("estimated_price"))["total"] or 0

    # Per-day repro (last 7 days)
    today = timezone.now().date()
    repro_daily = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = repro_orders.filter(created_at__date=day).count()
        repro_daily.append({"day": day.strftime("%a"), "count": count})

    # Store stats
    store_orders = StoreOrder.objects.all()
    total_store = store_orders.count()
    pending_store = store_orders.filter(status="paid").count()
    store_revenue = store_orders.exclude(status="cancelled").aggregate(
        total=Sum("total_amount"))["total"] or 0

    store_daily = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        count = store_orders.filter(created_at__date=day).count()
        store_daily.append({"day": day.strftime("%a"), "count": count})

    return render(request, "printing/super_admin_dashboard.html", {
        "total_users": total_users,
        "users": users,
        "total_print": total_print,
        "pending_print": pending_print,
        "repro_revenue": repro_revenue,
        "repro_daily": repro_daily,
        "total_store": total_store,
        "pending_store": pending_store,
        "store_revenue": store_revenue,
        "store_daily": store_daily,
        "repro_orders": repro_orders.order_by("-id")[:20],
        "store_orders": store_orders.order_by("-id")[:20],
    })


@login_required
def update_user_role(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        new_role = request.POST.get("role")
        user.groups.clear()
        if new_role == "repro_admin":
            group, _ = Group.objects.get_or_create(name="repro_admin")
            user.groups.add(group)
            user.is_staff = True
        elif new_role == "store_admin":
            group, _ = Group.objects.get_or_create(name="store_admin")
            user.groups.add(group)
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
        email = request.POST.get("email", "").strip()
        if User.objects.filter(username=username).exists():
            messages.error(request, "❌ Username already exists!")
        else:
            User.objects.create(
                username=username,
                password=make_password(password),
                email=email,
            )
            messages.success(request, f"✅ User '{username}' created.")
    return redirect("super_admin_dashboard")


@login_required
def delete_user(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = get_object_or_404(User, id=user_id)
    if not user.is_superuser:
        user.delete()
        messages.success(request, "✅ User deleted.")
    return redirect("super_admin_dashboard")


@login_required
def reset_password(request, user_id):
    if not request.user.is_superuser:
        return redirect("home")
    user = get_object_or_404(User, id=user_id)
    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
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
        new_email = request.POST.get("email", "").strip()
        user.email = new_email
        user.save()
        messages.success(request, f"✅ Email updated for {user.username}")
    return redirect("super_admin_dashboard")


# ── Forgot Password (username-based) ─────────────────────────────────────────

def forgot_password(request):
    """
    Custom forgot-password view: user enters their username,
    we look up the associated email and send the reset link there.
    No email input is shown to the user.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.http import urlsafe_base64_encode
    from django.utils.encoding import force_bytes
    from django.core.mail import send_mail

    from django.template.loader import render_to_string

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Don't reveal whether the username exists — just redirect to done
            return redirect("forgot_password_done")

        if not user.email:
            messages.error(request, "⚠️ No email address is registered for this account. Please contact the admin.")
            return redirect("forgot_password")

        # Generate reset token
        uid   = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Build reset URL
        protocol = "https" if request.is_secure() else "http"
        domain   = request.get_host()
        reset_url = f"{protocol}://{domain}/password-reset-confirm/{uid}/{token}/"

        # Send email
        subject = "Campus Portal — Password Reset Request"
        body = (
            f"Hi {user.username},\n\n"
            f"You requested a password reset for your Campus Portal account.\n\n"
            f"Click the link below to reset your password:\n{reset_url}\n\n"
            f"⚠️  This link will expire in 5 minutes. Please use it immediately.\n\n"
            f"If you didn't request this, you can safely ignore this email.\n\n"
            f"— Campus Portal Team"
        )
        from django.conf import settings
        send_mail(subject, body, settings.campusportal26@gmail.com, [user.email])

        return redirect("forgot_password_done")

    return render(request, "forgot_password.html")


# ── Login / About ─────────────────────────────────────────────────────────────

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
    return render(request, "printing/about.html")
