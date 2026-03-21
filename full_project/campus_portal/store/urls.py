from django.urls import path
from . import views

urlpatterns = [
    path("", views.store_home, name="store_home"),
    path("cart/", views.cart, name="cart"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/<int:item_id>/", views.update_cart, name="update_cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("payment/", views.store_payment, name="store_payment"),
    path("my-orders/", views.my_store_orders, name="my_store_orders"),
    path("cancel-order/<int:order_id>/", views.cancel_store_order, name="cancel_store_order"),

    # Store Admin
    path("admin/", views.store_admin_dashboard, name="store_admin_dashboard"),
    path("admin/add-product/", views.add_product, name="add_product"),
    path("admin/edit-product/<int:product_id>/", views.edit_product, name="edit_product"),
    path("admin/delete-product/<int:product_id>/", views.delete_product, name="delete_product"),
    path("admin/update-stock/<int:product_id>/", views.update_stock, name="update_stock"),
    path("admin/update-order-status/<int:order_id>/", views.update_order_status, name="update_order_status"),
]
