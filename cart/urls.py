from django.urls import path
from .views import cart_page, add_to_cart, remove_from_cart

urlpatterns = [
    path("", cart_page, name="cart-page"),
    path("add/", add_to_cart, name="cart-add"),
    path("remove/", remove_from_cart, name="cart-remove"),
]