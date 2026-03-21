from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from .models import Product, Category, CartItem, StoreOrder, StoreOrderItem
from printing.views import get_store_admin_notifications


# ─── Role Checks ──────────────────────────────────────────────────────────────

def is_store_admin(user):
    return user.groups.filter(name="store_admin").exists() or user.is_superuser

def is_repro_admin(user):
    return user.groups.filter(name="repro_admin").exists()

def is_customer(user):
    return not (is_store_admin(user) or is_repro_admin(user))


# ─── Customer Views ───────────────────────────────────────────────────────────

@login_required
def store_home(request):
    if is_repro_admin(request.user):
        return redirect("home")
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("store_admin_dashboard")

    products = Product.objects.filter(is_active=True, is_visible=True).select_related("category")

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(name__icontains=query)

    category_id = request.GET.get("category", "")
    if category_id:
        products = products.filter(category_id=category_id)

    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()

    notifications = _user_notifs(request.user)
    return render(request, "store/store_home.html", {
        "products": products,
        "categories": categories,
        "query": query,
        "selected_category": category_id,
        "cart_count": cart_count,
        "notifications": notifications,
        "notif_count": _user_notif_count(request.user, notifications),
    })


@login_required
def add_to_cart(request, product_id):
    if is_repro_admin(request.user):
        return redirect("home")

    product = get_object_or_404(Product, id=product_id, is_active=True)

    if not product.in_stock:
        messages.error(request, f"❌ '{product.name}' is out of stock.")
        return redirect("store_home")

    cart_item, created = CartItem.objects.get_or_create(
        user=request.user, product=product, defaults={"quantity": 1}
    )

    if not created:
        if cart_item.quantity >= product.stock:
            messages.warning(request, f"⚠️ Only {product.stock} unit(s) of '{product.name}' available.")
        else:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"✅ '{product.name}' quantity updated in cart.")
    else:
        messages.success(request, f"✅ '{product.name}' added to cart.")

    return redirect("store_home")


@login_required
def cart(request):
    if is_repro_admin(request.user):
        return redirect("home")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    total = sum(item.subtotal for item in cart_items)
    return render(request, "store/cart.html", {"cart_items": cart_items, "total": total})


@login_required
def update_cart(request, item_id):
    if request.method == "POST":
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
        action = request.POST.get("action")
        if action == "increase":
            if cart_item.quantity < cart_item.product.stock:
                cart_item.quantity += 1
                cart_item.save()
            else:
                messages.warning(request, f"⚠️ Max stock reached for '{cart_item.product.name}'.")
        elif action == "decrease":
            if cart_item.quantity > 1:
                cart_item.quantity -= 1
                cart_item.save()
            else:
                cart_item.delete()
        elif action == "remove":
            cart_item.delete()
    return redirect("cart")


@login_required
def checkout(request):
    if is_repro_admin(request.user):
        return redirect("home")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    if not cart_items.exists():
        messages.error(request, "❌ Your cart is empty.")
        return redirect("cart")

    if request.method == "POST":
        with transaction.atomic():
            cart_items = CartItem.objects.filter(user=request.user).select_related("product")
            for item in cart_items:
                if item.quantity > item.product.stock:
                    messages.error(request, f"❌ Only {item.product.stock} unit(s) of '{item.product.name}' left.")
                    return redirect("cart")

            payment_method = request.POST.get("payment_method", "Card")
            total = sum(item.subtotal for item in cart_items)
            order = StoreOrder.objects.create(
                user=request.user,
                total_amount=total,
                payment_status="paid",
                payment_method=payment_method,
            )

            for item in cart_items:
                StoreOrderItem.objects.create(
                    order=order, product=item.product,
                    product_name=item.product.name,
                    price=item.product.price, quantity=item.quantity,
                )
                item.product.stock -= item.quantity
                item.product.save(update_fields=["stock"])

            cart_items.delete()

        messages.success(request, f"✅ Payment successful! Your order ID is {order.order_number}.")
        return redirect("my_store_orders")

    total = sum(item.subtotal for item in cart_items)
    return render(request, "store/checkout.html", {"cart_items": cart_items, "total": total})


@login_required
def cancel_order(request, order_id):
    """Cancel a store order within 3 minutes. Restores stock."""
    if is_repro_admin(request.user):
        return redirect("home")

    order = get_object_or_404(StoreOrder, id=order_id, user=request.user)

    if not order.can_cancel:
        messages.error(request, "❌ This order can no longer be cancelled (3-minute window has passed or order is already processed).")
        return redirect("my_store_orders")

    with transaction.atomic():
        for item in order.items.select_related("product").all():
            if item.product:
                item.product.stock += item.quantity
                item.product.save(update_fields=["stock"])
        order.status = "cancelled"
        order.payment_status = "refunded"
        order.save(update_fields=["status", "payment_status"])

    messages.success(request, f"✅ Order {order.order_number} cancelled. Stock has been restored.")
    return redirect("my_store_orders")


@login_required
def my_store_orders(request):
    if is_repro_admin(request.user):
        return redirect("home")
    orders = StoreOrder.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")
    return render(request, "store/my_orders.html", {"orders": orders})


# ─── Store Admin Views ────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_store_admin, login_url="home")
def store_admin_dashboard(request):
    products = Product.objects.all().select_related("category").order_by("-id")
    orders = StoreOrder.objects.all().prefetch_related("items__product").order_by("-created_at")
    categories = Category.objects.all()

    pending_orders  = StoreOrder.objects.filter(status="pending").prefetch_related("items__product").order_by("-created_at")
    notifications   = get_store_admin_notifications()
    return render(request, "store/store_admin_dashboard.html", {
        "products": products,
        "orders": orders,
        "categories": categories,
        "pending_store_orders": pending_orders,
        "total_products": products.count(),
        "out_of_stock": products.filter(stock=0).count(),
        "total_orders": orders.count(),
        "pending_orders_count": orders.filter(status="pending").count(),
        "notifications": notifications,
        "notif_count": _user_notif_count(request.user, notifications),
    })


@login_required
@user_passes_test(is_store_admin, login_url="home")
def add_product(request):
    categories = Category.objects.all()

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        description = request.POST.get("description", "")
        image_url = request.POST.get("image_url", "")
        category_id = request.POST.get("category")
        new_category = request.POST.get("new_category", "").strip()

        if not name or not price or not stock:
            messages.error(request, "❌ Name, price, and stock are required.")
            return render(request, "store/add_product.html", {"categories": categories})

        if new_category:
            category, _ = Category.objects.get_or_create(name=new_category)
        elif category_id:
            category = get_object_or_404(Category, id=category_id)
        else:
            category = None

        Product.objects.create(
            name=name, price=price, stock=stock, description=description,
            image_url=image_url, category=category, added_by=request.user,
        )
        messages.success(request, f"✅ '{name}' added successfully.")
        return redirect("store_admin_dashboard")

    return render(request, "store/add_product.html", {"categories": categories})


@login_required
@user_passes_test(is_store_admin, login_url="home")
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    categories = Category.objects.all()

    if request.method == "POST":
        product.name = request.POST.get("name", product.name).strip()
        product.price = request.POST.get("price", product.price)
        product.stock = request.POST.get("stock", product.stock)
        product.description = request.POST.get("description", product.description)
        product.image_url = request.POST.get("image_url", product.image_url)

        category_id = request.POST.get("category")
        new_category = request.POST.get("new_category", "").strip()

        if new_category:
            category, _ = Category.objects.get_or_create(name=new_category)
            product.category = category
        elif category_id:
            product.category = get_object_or_404(Category, id=category_id)

        product.save()
        messages.success(request, f"✅ '{product.name}' updated.")
        return redirect("store_admin_dashboard")

    return render(request, "store/edit_product.html", {"product": product, "categories": categories})


@login_required
@user_passes_test(is_store_admin, login_url="home")
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        name = product.name
        product.delete()
        messages.success(request, f"✅ '{name}' permanently removed from store.")
    return redirect("store_admin_dashboard")


@login_required
@user_passes_test(is_store_admin, login_url="home")
def toggle_product_visibility(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        product.is_visible = not product.is_visible
        product.save(update_fields=["is_visible"])
        state = "visible" if product.is_visible else "hidden"
        messages.success(request, f"✅ '{product.name}' is now {state} on the store.")
    return redirect("store_admin_dashboard")


@login_required
@user_passes_test(is_store_admin, login_url="home")
def update_stock(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        new_stock = request.POST.get("stock")
        if new_stock is not None:
            product.stock = int(new_stock)
            product.save(update_fields=["stock"])
            messages.success(request, f"✅ Stock updated for '{product.name}'.")
    return redirect("store_admin_dashboard")


@login_required
@user_passes_test(is_store_admin, login_url="home")
def update_order_status(request, order_id):
    order = get_object_or_404(StoreOrder, id=order_id)
    if request.method == "POST":
        order.status = request.POST.get("status", order.status)
        order.save(update_fields=["status"])
        messages.success(request, f"✅ Order {order.order_number} status updated.")
    return redirect("store_admin_dashboard")


# ─── Delete Category (NEW) ────────────────────────────────────────────────────

@login_required
@user_passes_test(is_store_admin, login_url="home")
def delete_category(request, category_id):
    """
    Delete a category. Products assigned to it will have category set to NULL
    (on_delete=SET_NULL), so no products are deleted.
    """
    category = get_object_or_404(Category, id=category_id)
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f"✅ Category '{name}' deleted.")
    return redirect("store_admin_dashboard")


# ── Notification context helper for store pages ────────────────────────────────
def _user_notifs(user):
    from printing.views import get_user_notifications
    return get_user_notifications(user)

def _user_notif_count(user, notifications):
    from printing.views import _notif_count
    return _notif_count(user, notifications)


# ── Live-refresh state API ─────────────────────────────────────────────────────
import json, hashlib
from django.http import JsonResponse

def store_state_api(request):
    """
    Returns a lightweight JSON snapshot of current store state.
    Clients poll this every few seconds; if the hash changes they refresh the UI.
    No auth required — only public stock/status data is exposed.
    """
    # Products: id, name, stock, price, is_active
    # Products visible to customers
    products = list(
        Product.objects.filter(is_active=True, is_visible=True)
        .values("id", "name", "stock", "price")
        .order_by("id")
    )
    # Products that are active but hidden (so frontend can hide their cards)
    hidden_ids = list(
        Product.objects.filter(is_active=True, is_visible=False)
        .values_list("id", flat=True)
    )
    # Convert Decimal to str for JSON serialisation
    for p in products:
        p["price"] = str(p["price"])

    # Order statuses for the requesting user (if logged in)
    order_statuses = []
    if request.user.is_authenticated and not (
        request.user.is_superuser or
        request.user.groups.filter(name__in=["store_admin", "repro_admin"]).exists()
    ):
        order_statuses = list(
            StoreOrder.objects.filter(user=request.user)
            .values("id", "order_number", "status")
            .order_by("-id")[:20]
        )

    payload = {"products": products, "hidden_ids": hidden_ids, "order_statuses": order_statuses}
    raw = json.dumps(payload, sort_keys=True)
    state_hash = hashlib.md5(raw.encode()).hexdigest()

    return JsonResponse({"hash": state_hash, "data": payload})
