from django.apps import AppConfig

class PrintingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'printing'

    def ready(self):
        from django.contrib.auth.models import Group # type: ignore

        Group.objects.get_or_create(name="Store Admin")
        Group.objects.get_or_create(name="Repro Admin")