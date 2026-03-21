from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class NotificationSeen(models.Model):
    """
    Stores the last time each user clicked the notification bell.
    The red dot only shows if new notifications arrived AFTER seen_at.
    One row per user — created on first click, updated on every subsequent click.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notif_seen")
    seen_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} seen_at {self.seen_at}"


class PrintOrder(models.Model):

    # 🔹 Unique order number (professional ID)
    order_number = models.CharField(max_length=30, unique=True, blank=True)

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
        ("pending", "Pending"),
        ("printing", "Printing"),
        ("done", "Done"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)

    # 🔹 Auto-generate order number
    def save(self, *args, **kwargs):
        if not self.order_number:
            timestamp = timezone.now().strftime("%Y%m%d%H%M%S")
            unique_part = str(uuid.uuid4())[:6].upper()
            self.order_number = f"ORD-{timestamp}-{unique_part}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.order_number}"