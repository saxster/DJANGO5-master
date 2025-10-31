# Generated migration for Asset Audit Trail models (Sprint 4.4)

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0021_add_nfc_models'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetFieldHistory',
            fields=[
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('field_name', models.CharField(help_text='Name of the field that changed', max_length=100, verbose_name='Field Name')),
                ('old_value', models.TextField(blank=True, help_text='Previous value (JSON serialized for complex types)', verbose_name='Old Value')),
                ('new_value', models.TextField(blank=True, help_text='New value (JSON serialized for complex types)', verbose_name='New Value')),
                ('change_reason', models.TextField(blank=True, help_text='Optional reason for the change', verbose_name='Change Reason')),
                ('correlation_id', models.UUIDField(default=uuid.uuid4, help_text='Correlation ID for tracking related changes', verbose_name='Correlation ID')),
                ('change_source', models.CharField(choices=[('WEB_UI', 'Web UI'), ('MOBILE_APP', 'Mobile App'), ('API', 'REST API'), ('BULK_IMPORT', 'Bulk Import'), ('SYSTEM', 'System'), ('MIGRATION', 'Data Migration')], default='WEB_UI', help_text='Source of the change', max_length=50, verbose_name='Change Source')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional change metadata (IP address, user agent, etc.)', verbose_name='Metadata')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='field_history', to='activity.asset', verbose_name='Asset')),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asset_changes', to=settings.AUTH_USER_MODEL, verbose_name='Changed By')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Asset Field History',
                'verbose_name_plural': 'Asset Field History',
                'db_table': 'activity_asset_field_history',
                'ordering': ['-cdtz'],
            },
        ),
        migrations.CreateModel(
            name='AssetLifecycleStage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('stage', models.CharField(choices=[('ACQUISITION', 'Acquisition'), ('INSTALLATION', 'Installation'), ('OPERATION', 'Operation'), ('MAINTENANCE', 'Maintenance'), ('DECOMMISSIONING', 'Decommissioning'), ('DISPOSED', 'Disposed')], max_length=20, verbose_name='Lifecycle Stage')),
                ('stage_started', models.DateTimeField(help_text='When this lifecycle stage began', verbose_name='Stage Started')),
                ('stage_ended', models.DateTimeField(blank=True, help_text='When this lifecycle stage ended', null=True, verbose_name='Stage Ended')),
                ('is_current', models.BooleanField(default=True, help_text='Whether this is the current lifecycle stage', verbose_name='Is Current Stage')),
                ('stage_metadata', models.JSONField(blank=True, default=dict, help_text='Stage-specific metadata (installation date, disposal method, etc.)', verbose_name='Stage Metadata')),
                ('notes', models.TextField(blank=True, help_text='Notes about this lifecycle stage', verbose_name='Notes')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lifecycle_stages', to='activity.asset', verbose_name='Asset')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
                ('transitioned_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Transitioned By')),
            ],
            options={
                'verbose_name': 'Asset Lifecycle Stage',
                'verbose_name_plural': 'Asset Lifecycle Stages',
                'db_table': 'activity_asset_lifecycle_stage',
                'ordering': ['-stage_started'],
            },
        ),
        # Add indexes for AssetFieldHistory
        migrations.AddIndex(
            model_name='assetfieldhistory',
            index=models.Index(fields=['tenant', 'asset', 'cdtz'], name='activity_af_tenant_ass_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='assetfieldhistory',
            index=models.Index(fields=['tenant', 'field_name', 'cdtz'], name='activity_af_tenant_fie_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='assetfieldhistory',
            index=models.Index(fields=['tenant', 'changed_by', 'cdtz'], name='activity_af_tenant_cha_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='assetfieldhistory',
            index=models.Index(fields=['correlation_id'], name='activity_af_correla_idx'),
        ),
        migrations.AddIndex(
            model_name='assetfieldhistory',
            index=models.Index(fields=['cdtz'], name='activity_af_cdtz_idx'),
        ),
        # Add indexes for AssetLifecycleStage
        migrations.AddIndex(
            model_name='assetlifecyclestage',
            index=models.Index(fields=['tenant', 'asset', 'is_current'], name='activity_al_tenant_ass_is_idx'),
        ),
        migrations.AddIndex(
            model_name='assetlifecyclestage',
            index=models.Index(fields=['tenant', 'stage', 'cdtz'], name='activity_al_tenant_sta_cd_idx'),
        ),
        migrations.AddIndex(
            model_name='assetlifecyclestage',
            index=models.Index(fields=['stage_started'], name='activity_al_stage_s_idx'),
        ),
    ]
