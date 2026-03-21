from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from .models import Product, Category, CartItem, StoreOrder, StoreOrderItem, StoreNotification


def is_store_admin(user):
    return user.groups.filter(name="store_admin").exists() or user.is_superuser

def is_repro_admin(user):
    return user.groups.filter(name="repro_admin").exists()

def is_customer(user):
    return not (is_store_admin(user) or is_repro_admin(user))


# ── Customer Views ────────────────────────────────────────────────────────────

@login_required
def store_home(request):
    if is_repro_admin(request.user):
        return redirect("home")
    if request.user.groups.filter(name="store_admin").exists():
        return redirect("store_admin_dashboard")

    products = Product.objects.filter(is_active=True).select_related("category")

    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(name__icontains=query)

    category_id = request.GET.get("category", "")
    if category_id:
        products = products.filter(category_id=category_id)

    categories = Category.objects.all()
    cart_count = CartItem.objects.filter(user=request.user).count()

    return render(request, "store/store_home.html", {
        "products": products,
        "categories": categories,
        "query": query,
        "selected_category": category_id,
        "cart_count": cart_count,
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
            messages.warning(request, f"⚠️ Only {product.stock} unit(s) available.")
        else:
            cart_item.quantity += 1
            cart_item.save()
            messages.success(request, f"✅ Updated cart for '{product.name}'.")
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
    """Show payment confirmation screen."""
    if is_repro_admin(request.user):
        return redirect("home")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    if not cart_items.exists():
        messages.error(request, "❌ Your cart is empty.")
        return redirect("cart")

    # Validate stock
    for item in cart_items:
        if item.quantity > item.product.stock:
            messages.error(request, f"❌ Only {item.product.stock} unit(s) of '{item.product.name}' left.")
            return redirect("cart")

    total = sum(item.subtotal for item in cart_items)
    return render(request, "store/checkout.html", {"cart_items": cart_items, "total": total})


@login_required
def store_payment(request):
    """Show payment screen (GET) or process payment (POST)."""
    if is_repro_admin(request.user):
        return redirect("home")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    if not cart_items.exists():
        return redirect("cart")

    total = sum(item.subtotal for item in cart_items)

    if request.method == "GET":
        return render(request, "store/store_payment.html", {
            "cart_items": cart_items,
            "total": total,
        })

    if request.method != "POST":
        return redirect("checkout")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")
    if not cart_items.exists():
        return redirect("cart")

    action = request.POST.get("action")
    if action == "cancel":
        messages.info(request, "Payment cancelled.")
        return redirect("cart")

    cart_items = CartItem.objects.filter(user=request.user).select_related("product")

    with transaction.atomic():
        for item in cart_items:
            if item.quantity > item.product.stock:
                messages.error(request, f"❌ Stock changed for '{item.product.name}'. Please review cart.")
                return redirect("cart")

        total = sum(item.subtotal for item in cart_items)
        order = StoreOrder.objects.create(user=request.user, total_amount=total, status="paid")

        for item in cart_items:
            StoreOrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product.name,
                price=item.product.price,
                quantity=item.quantity,
            )
            item.product.stock -= item.quantity
            item.product.save(update_fields=["stock"])

            # Check low stock after deduction
            if item.product.is_low_stock:
                StoreNotification.objects.create(
                    type="low_stock",
                    message=f"⚠️ Low stock alert: '{item.product.name}' has only {item.product.stock} unit(s) left.",
                    related_product=item.product,
                )
            elif item.product.stock == 0:
                StoreNotification.objects.create(
                    type="low_stock",
                    message=f"🚨 Out of stock: '{item.product.name}' is now out of stock.",
                    related_product=item.product,
                )

        # New order notification
        StoreNotification.objects.create(
            type="new_order",
            message=f"🛒 New order {order.order_number} placed by {request.user.username} — ₹{total}",
            related_order=order,
        )

        cart_items.delete()

    messages.success(request, f"✅ Payment successful! Order ID: {order.order_number}")
    return redirect("my_store_orders")


@login_required
def my_store_orders(request):
    if is_repro_admin(request.user):
        return redirect("home")
    orders = StoreOrder.objects.filter(user=request.user).prefetch_related("items").order_by("-created_at")
    return render(request, "store/my_orders.html", {"orders": orders})


@login_required
def cancel_store_order(request, order_id):
    """Cancel order within 5 minutes and restore stock."""
    order = get_object_or_404(StoreOrder, id=order_id, user=request.user)

    if not order.can_cancel:
        messages.error(request, "❌ Cancellation window has passed (5 minutes) or order already processed.")
        return redirect("my_store_orders")

    with transaction.atomic():
        for item in order.items.all():
            if item.product:
                item.product.stock += item.quantity
                item.product.save(update_fields=["stock"])
        order.status = "cancelled"
        order.save(update_fields=["status"])

    messages.success(request, f"✅ Order {order.order_number} cancelled. Stock restored.")
    return redirect("my_store_orders")


# ── Store Admin Views ─────────────────────────────────────────────────────────

@login_required
@user_passes_test(is_store_admin, login_url="home")
def store_admin_dashboard(request):
    products = Product.objects.filter(is_active=True).select_related("category").order_by("-id")
    orders = StoreOrder.objects.all().prefetch_related("items").order_by("-created_at")
    categories = Category.objects.all()

    unread_notifications = StoreNotification.objects.filter(is_read=False).order_by("-created_at")
    all_notifications = StoreNotification.objects.all().order_by("-created_at")[:30]

    # Mark all as read when dashboard is opened
    StoreNotification.objects.filter(is_read=False).update(is_read=True)

    return render(request, "store/store_admin_dashboard.html", {
        "products": products,
        "orders": orders,
        "categories": categories,
        "total_products": products.count(),
        "out_of_stock": products.filter(stock=0).count(),
        "low_stock_count": sum(1 for p in products if p.is_low_stock),
        "total_orders": orders.count(),
        "paid_orders": orders.filter(status="paid").count(),
        "unread_count": unread_notifications.count(),
        "notifications": all_notifications,
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
        low_stock_threshold = request.POST.get("low_stock_threshold", 5)

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
            low_stock_threshold=low_stock_threshold,
        )
        messages.success(request, f"✅ '{name}' added.")
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
        product.low_stock_threshold = request.POST.get("low_stock_threshold", product.low_stock_threshold)

        new_category = request.POST.get("new_category", "").strip()
        category_id = request.POST.get("category")
        if new_category:
            cat, _ = Category.objects.get_or_create(name=new_category)
            product.category = cat
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
        product.is_active = False
        product.save()
        messages.success(request, f"✅ '{product.name}' removed from store.")
    return redirect("store_admin_dashboard")


@login_required
@user_passes_test(is_store_admin, login_url="home")
def update_stock(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == "POST":
        product.stock = int(request.POST.get("stock", product.stock))
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
        messages.success(request, f"✅ Order {order.order_number} updated.")
    return redirect("store_admin_dashboard")
