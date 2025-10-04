from django.apps import AppConfig


class MqttConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.mqtt'
    verbose_name = 'MQTT Integration'

    def ready(self):
        pass