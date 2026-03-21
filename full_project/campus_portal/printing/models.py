from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class PrintOrder(models.Model):

    order_number = models.CharField(max_length=50, unique=True, blank=True)

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    document = models.FileField(upload_to="uploads/")
    copies = models.IntegerField(default=1)

    COLOR_CHOICES = [
        ("bw", "Black & White"),
        ("color", "Color"),
    ]
    color_mode = models.CharField(max_length=10, choices=COLOR_CHOICES)

    PAPER_CHOICES = [
        ("A4", "A4"),
        ("A3", "A3"),
    ]
    paper_size = models.CharField(max_length=5, choices=PAPER_CHOICES)

    SIDE_CHOICES = [
        ("single", "Single Sided"),
        ("double", "Double Sided"),
    ]
    print_side = models.CharField(max_length=10, choices=SIDE_CHOICES)

    BINDING_CHOICES = [
        ("none", "No Binding"),
        ("spiral", "Spiral"),
        ("thermal", "Thermal"),
        ("hardcover", "Hardcover"),
    ]
    binding = models.CharField(max_length=20, choices=BINDING_CHOICES, default="none")

    instructions = models.TextField(blank=True, null=True)

    STATUS_CHOICES = [
        ("paid", "Paid"),
        ("printing", "Printing"),
        ("collected", "Collected"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="paid")

    created_at = models.DateTimeField(auto_now_add=True)

    # Estimated price stored at order time
    estimated_price = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def save(self, *args, **kwargs):
        if not self.order_number:
            count = PrintOrder.objects.filter(user=self.user).count() + 1
            username = self.user.username.upper()[:6]
            self.order_number = f"RPR-{username}-{count:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number
