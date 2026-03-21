from django.apps import AppConfig

class PrintingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'printing'

    def ready(self):
        from django.db.models.signals import post_migrate
        from django.contrib.auth.models import Group

        