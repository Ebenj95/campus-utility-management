from django.contrib import admin
from .models import Product, Category, CartItem, StoreOrder, StoreOrderItem, StoreNotification

class StoreOrderItemInline(admin.TabularInline):
    model = StoreOrderItem
    extra = 0
    readonly_fields = ("product_name", "price", "quantity")

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_active", "added_by")
    list_filter = ("category", "is_active")
    search_fields = ("name",)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)

@admin.register(StoreOrder)
class StoreOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "total_amount", "status", "created_at")
    list_filter = ("status",)
    inlines = [StoreOrderItemInline]

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "quantity")

@admin.register(StoreNotification)
class StoreNotificationAdmin(admin.ModelAdmin):
    list_display = ("type", "message", "is_read", "created_at")
    list_filter = ("type", "is_read")
