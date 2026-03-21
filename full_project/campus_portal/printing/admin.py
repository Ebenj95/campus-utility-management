from django.contrib import admin
from .models import PrintOrder

@admin.register(PrintOrder)
class PrintOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "color_mode", "paper_size", "copies", "created_at")
    list_filter = ("status", "color_mode", "paper_size")
    search_fields = ("order_number", "user__username")
