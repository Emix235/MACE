from django.apps import AppConfig


class EstudiantesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'estudiantes'

    def ready(self):
        # Importa signals aquí si los necesitas
        pass