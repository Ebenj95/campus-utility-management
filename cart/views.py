from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect

def cart_page(request):
    cart = request.session.get("cart", {})
    items = []
    total_price = 0

    for product_id, item in cart.items():
        subtotal = item["price"] * item["quantity"]

        items.append({
            "id": product_id,   # ✅ ADD THIS
            "name": item["name"],
            "price": item["price"],
            "quantity": item["quantity"],
            "subtotal": subtotal
        })

        total_price += subtotal

    return render(request, "store/cart.html", {
        "cart_items": items,
        "total_price": total_price
    })


def add_to_cart(request):
    import json

    data = json.loads(request.body)
    product_id = str(data.get("product_id"))
    quantity = int(data.get("quantity", 1))  # 👈 important

    products = {
        "1": {"name": "Engineering Mathematics", "price": 450},
        "2": {"name": "Scientific Calculator", "price": 850},
        "3": {"name": "College Hoodie", "price": 799},
        "4": {"name": "Notebook Set", "price": 250},
        "5": {"name": "USB Drive", "price": 399},
        "6": {"name": "Geometry Box", "price": 180},
    }

    if product_id not in products:
        return redirect("cart-page")

    cart = request.session.get("cart", {})

    if product_id in cart:
        cart[product_id]["quantity"] += quantity

        # ❌ remove if quantity <= 0
        if cart[product_id]["quantity"] <= 0:
            del cart[product_id]
    else:
        if quantity > 0:
            cart[product_id] = {
                "name": products[product_id]["name"],
                "price": products[product_id]["price"],
                "quantity": quantity
            }

    request.session["cart"] = cart
    request.session.modified = True

    return redirect("cart-page")

def remove_from_cart(request):
    import json

    data = json.loads(request.body)
    product_id = str(data.get("product_id"))

    cart = request.session.get("cart", {})

    if product_id in cart:
        del cart[product_id]

    request.session["cart"] = cart
    request.session.modified = True

    return redirect("cart-page")

def clear_cart(request):
    request.session["cart"] = {}
    request.session.modified = True
    return redirect("cart-page")