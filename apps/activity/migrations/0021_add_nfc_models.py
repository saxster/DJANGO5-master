# Generated migration for NFC models (Sprint 4.1)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0020_migrate_to_json_fields'),
        ('onboarding', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='NFCTag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('tag_uid', models.CharField(help_text='Unique identifier of the NFC tag (hexadecimal)', max_length=50, unique=True, verbose_name='Tag UID')),
                ('status', models.CharField(choices=[('ACTIVE', 'Active'), ('INACTIVE', 'Inactive'), ('DAMAGED', 'Damaged'), ('LOST', 'Lost'), ('DECOMMISSIONED', 'Decommissioned')], default='ACTIVE', max_length=20, verbose_name='Status')),
                ('last_scan', models.DateTimeField(blank=True, help_text='Timestamp of most recent scan', null=True, verbose_name='Last Scan')),
                ('scan_count', models.IntegerField(default=0, help_text='Total number of scans performed', verbose_name='Scan Count')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional tag metadata (tag type, manufacturer, etc.)', verbose_name='Metadata')),
                ('asset', models.ForeignKey(help_text='Asset this tag is bound to', on_delete=django.db.models.deletion.CASCADE, related_name='nfc_tags', to='activity.asset', verbose_name='Asset')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'NFC Tag',
                'verbose_name_plural': 'NFC Tags',
                'db_table': 'activity_nfc_tag',
            },
        ),
        migrations.CreateModel(
            name='NFCDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('device_id', models.CharField(help_text='Unique identifier for NFC reader device', max_length=100, unique=True, verbose_name='Device ID')),
                ('device_name', models.CharField(help_text='Human-readable device name', max_length=200, verbose_name='Device Name')),
                ('status', models.CharField(choices=[('ONLINE', 'Online'), ('OFFLINE', 'Offline'), ('MAINTENANCE', 'Maintenance'), ('DECOMMISSIONED', 'Decommissioned')], default='ONLINE', max_length=20, verbose_name='Status')),
                ('last_active', models.DateTimeField(auto_now=True, help_text='Timestamp of last activity', verbose_name='Last Active')),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='Network IP address of the device', null=True, verbose_name='IP Address')),
                ('firmware_version', models.CharField(blank=True, default='', help_text='Device firmware version', max_length=50, verbose_name='Firmware Version')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional device metadata (model, serial, etc.)', verbose_name='Metadata')),
                ('location', models.ForeignKey(blank=True, help_text='Physical location of the device', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='nfc_devices', to='onboarding.typeassist', verbose_name='Location')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'NFC Device',
                'verbose_name_plural': 'NFC Devices',
                'db_table': 'activity_nfc_device',
            },
        ),
        migrations.CreateModel(
            name='NFCScanLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('scan_type', models.CharField(choices=[('CHECKIN', 'Check-In'), ('CHECKOUT', 'Check-Out'), ('INSPECTION', 'Inspection'), ('INVENTORY', 'Inventory'), ('MAINTENANCE', 'Maintenance')], default='INSPECTION', max_length=20, verbose_name='Scan Type')),
                ('scan_result', models.CharField(choices=[('SUCCESS', 'Success'), ('FAILED', 'Failed'), ('INVALID_TAG', 'Invalid Tag')], default='SUCCESS', max_length=20, verbose_name='Scan Result')),
                ('response_time_ms', models.IntegerField(blank=True, help_text='Tag response time in milliseconds', null=True, verbose_name='Response Time (ms)')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional scan metadata (RSSI, read quality, etc.)', verbose_name='Metadata')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_logs', to='activity.nfcdevice', verbose_name='NFC Device')),
                ('scan_location', models.ForeignKey(blank=True, help_text='Location where scan occurred', null=True, on_delete=django.db.models.deletion.SET_NULL, to='onboarding.typeassist', verbose_name='Scan Location')),
                ('scanned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='nfc_scans', to=settings.AUTH_USER_MODEL, verbose_name='Scanned By')),
                ('tag', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scan_logs', to='activity.nfctag', verbose_name='NFC Tag')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'NFC Scan Log',
                'verbose_name_plural': 'NFC Scan Logs',
                'db_table': 'activity_nfc_scan_log',
                'ordering': ['-cdtz'],
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='nfctag',
            index=models.Index(fields=['tenant', 'tag_uid'], name='activity_nf_tenant_tag_idx'),
        ),
        migrations.AddIndex(
            model_name='nfctag',
            index=models.Index(fields=['tenant', 'asset'], name='activity_nf_tenant_ass_idx'),
        ),
        migrations.AddIndex(
            model_name='nfctag',
            index=models.Index(fields=['tenant', 'status'], name='activity_nf_tenant_sta_idx'),
        ),
        migrations.AddIndex(
            model_name='nfctag',
            index=models.Index(fields=['last_scan'], name='activity_nf_last_sc_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcdevice',
            index=models.Index(fields=['tenant', 'device_id'], name='activity_nf_tenant_dev_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcdevice',
            index=models.Index(fields=['tenant', 'status'], name='activity_nf_tenant_st2_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcdevice',
            index=models.Index(fields=['location'], name='activity_nf_locatio_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcscanlog',
            index=models.Index(fields=['tenant', 'tag', 'cdtz'], name='activity_nf_tenant_tag_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcscanlog',
            index=models.Index(fields=['tenant', 'device', 'cdtz'], name='activity_nf_tenant_dev_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcscanlog',
            index=models.Index(fields=['tenant', 'scanned_by', 'cdtz'], name='activity_nf_tenant_sca_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcscanlog',
            index=models.Index(fields=['scan_type'], name='activity_nf_scan_ty_idx'),
        ),
        migrations.AddIndex(
            model_name='nfcscanlog',
            index=models.Index(fields=['cdtz'], name='activity_nf_cdtz_idx'),
        ),
    ]
