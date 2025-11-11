# Generated manually for NOC app (Ultrathink remediation - WebSocket connection tracking)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('noc', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WebSocketConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, help_text='Timestamp when record was created')),
                ('updated_at', models.DateTimeField(auto_now=True, help_text='Timestamp when record was last updated')),
                ('channel_name', models.CharField(db_index=True, help_text="Unique channel name from Django Channels (e.g., 'specific.ABC123')", max_length=255, unique=True)),
                ('group_name', models.CharField(db_index=True, help_text="Group name the connection is subscribed to (e.g., 'noc_tenant_5', 'noc_client_123')", max_length=255)),
                ('consumer_type', models.CharField(choices=[('noc_dashboard', 'NOC Dashboard'), ('threat_alerts', 'Threat Alerts'), ('streaming_anomaly', 'Streaming Anomaly'), ('presence_monitor', 'Presence Monitor')], db_index=True, help_text='Type of WebSocket consumer (for filtering/analytics)', max_length=50)),
                ('connected_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Timestamp when connection was established')),
                ('last_activity', models.DateTimeField(auto_now=True, help_text='Timestamp of last activity (updated on heartbeat/message)')),
                ('tenant', models.ForeignKey(help_text='Tenant that owns this record', on_delete=django.db.models.deletion.CASCADE, related_name='%(class)s_records', to='tenants.tenant')),
                ('user', models.ForeignKey(help_text='User who owns this WebSocket connection', on_delete=django.db.models.deletion.CASCADE, related_name='websocket_connections', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'WebSocket Connection',
                'verbose_name_plural': 'WebSocket Connections',
                'ordering': ['-connected_at'],
            },
        ),
        migrations.AddIndex(
            model_name='websocketconnection',
            index=models.Index(fields=['group_name', 'tenant'], name='noc_websock_group_n_idx'),
        ),
        migrations.AddIndex(
            model_name='websocketconnection',
            index=models.Index(fields=['tenant', '-connected_at'], name='noc_websock_tenant_idx'),
        ),
        migrations.AddIndex(
            model_name='websocketconnection',
            index=models.Index(fields=['consumer_type', 'tenant'], name='noc_websock_consume_idx'),
        ),
        migrations.AddConstraint(
            model_name='websocketconnection',
            constraint=models.UniqueConstraint(fields=('channel_name',), name='unique_channel_name'),
        ),
    ]
