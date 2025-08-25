from django.apps import AppConfig


class PadresConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'padres'


def ready(self):
    # Importa las señales cuando la app esté lista
    import padres.signals
