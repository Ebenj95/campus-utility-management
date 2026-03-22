from django.contrib import admin
from django.http import HttpResponseRedirect
from .models import PrintOrder
from django.urls import reverse
from django.utils.html import format_html


@admin.action(description="Start printing (set status to Printing)")
def start_printing(modeladmin, request, queryset):
    queryset.update(status="printing")


@admin.register(PrintOrder)
class PrintOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "copies", "color_mode", "paper_size", "print_side", "binding", "print_btn")
    list_filter = ("status",)
    list_editable = ("status",)

    readonly_fields = (
        "document", "copies", "color_mode", "paper_size",
        "print_side", "binding", "instructions", "created_at"
    )

    actions = [start_printing]
    
    # Disable delete actions
    actions = None

    # Hide delete button on detail page
    def has_delete_permission(self, request, obj=None):
        return False
        
    def print_btn(self, obj):
        url = reverse("print_with_footer", args=[obj.pk])
        return format_html('<a class="button" href="{}">Print</a>', url)
    print_btn.short_description = "Print"