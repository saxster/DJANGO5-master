# Generated migration for Asset Analytics models (Sprint 4.5)

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('activity', '0022_add_asset_audit_trail'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetUtilizationMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('date', models.DateField(help_text='Date of measurement', verbose_name='Date')),
                ('utilization_percentage', models.DecimalField(decimal_places=2, help_text='Percentage of time asset was in use (0-100%)', max_digits=5, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Utilization %')),
                ('uptime_hours', models.DecimalField(decimal_places=2, default=0.0, help_text='Total operational hours', max_digits=6, verbose_name='Uptime Hours')),
                ('downtime_hours', models.DecimalField(decimal_places=2, default=0.0, help_text='Total downtime hours (maintenance, repairs, etc.)', max_digits=6, verbose_name='Downtime Hours')),
                ('idle_hours', models.DecimalField(decimal_places=2, default=0.0, help_text='Hours asset was available but not in use', max_digits=6, verbose_name='Idle Hours')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional utilization metadata', verbose_name='Metadata')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='utilization_metrics', to='activity.asset', verbose_name='Asset')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Asset Utilization Metric',
                'verbose_name_plural': 'Asset Utilization Metrics',
                'db_table': 'activity_asset_utilization',
                'ordering': ['-date'],
            },
        ),
        migrations.CreateModel(
            name='MaintenanceCostTracking',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('maintenance_date', models.DateField(help_text='Date maintenance was performed', verbose_name='Maintenance Date')),
                ('cost', models.DecimalField(decimal_places=2, help_text='Maintenance cost in local currency', max_digits=10, validators=[MinValueValidator(0)], verbose_name='Cost')),
                ('cost_type', models.CharField(choices=[('REPAIR', 'Repair'), ('INSPECTION', 'Inspection'), ('REPLACEMENT', 'Replacement'), ('PREVENTIVE', 'Preventive Maintenance'), ('EMERGENCY', 'Emergency Repair')], max_length=20, verbose_name='Cost Type')),
                ('description', models.TextField(help_text='Description of maintenance work performed', verbose_name='Description')),
                ('vendor_name', models.CharField(blank=True, help_text='External vendor if applicable', max_length=200, verbose_name='Vendor Name')),
                ('invoice_number', models.CharField(blank=True, max_length=100, verbose_name='Invoice Number')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional cost metadata (parts used, labor hours, etc.)', verbose_name='Metadata')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='maintenance_costs', to='activity.asset', verbose_name='Asset')),
                ('performed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='maintenance_work', to=settings.AUTH_USER_MODEL, verbose_name='Performed By')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Maintenance Cost',
                'verbose_name_plural': 'Maintenance Costs',
                'db_table': 'activity_maintenance_cost',
                'ordering': ['-maintenance_date'],
            },
        ),
        migrations.CreateModel(
            name='AssetHealthScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cdtz', models.DateTimeField(auto_now_add=True, verbose_name='Created')),
                ('mdtz', models.DateTimeField(auto_now=True, verbose_name='Modified')),
                ('ctzoffset', models.IntegerField(blank=True, default=0, verbose_name='TZ Offset')),
                ('enable', models.BooleanField(default=True, verbose_name='Enable')),
                ('calculated_date', models.DateField(help_text='Date score was calculated', verbose_name='Calculated Date')),
                ('health_score', models.DecimalField(decimal_places=2, help_text='Overall health score (0-100, higher is better)', max_digits=5, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name='Health Score')),
                ('risk_level', models.CharField(choices=[('LOW', 'Low Risk'), ('MEDIUM', 'Medium Risk'), ('HIGH', 'High Risk'), ('CRITICAL', 'Critical Risk')], help_text='Risk level based on health score', max_length=20, verbose_name='Risk Level')),
                ('predicted_failure_date', models.DateField(blank=True, help_text='ML-predicted next failure date', null=True, verbose_name='Predicted Failure Date')),
                ('recommended_maintenance_date', models.DateField(blank=True, help_text='Recommended next maintenance date', null=True, verbose_name='Recommended Maintenance Date')),
                ('factors', models.JSONField(default=dict, help_text='Contributing factors to health score', verbose_name='Health Factors')),
                ('asset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='health_scores', to='activity.asset', verbose_name='Asset')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='tenants.tenant')),
            ],
            options={
                'verbose_name': 'Asset Health Score',
                'verbose_name_plural': 'Asset Health Scores',
                'db_table': 'activity_asset_health_score',
                'ordering': ['-calculated_date'],
            },
        ),
        # Add unique constraints
        migrations.AlterUniqueTogether(
            name='assetutilizationmetric',
            unique_together={('tenant', 'asset', 'date')},
        ),
        migrations.AlterUniqueTogether(
            name='assethealthscore',
            unique_together={('tenant', 'asset', 'calculated_date')},
        ),
        # Add indexes for AssetUtilizationMetric
        migrations.AddIndex(
            model_name='assetutilizationmetric',
            index=models.Index(fields=['tenant', 'asset', 'date'], name='activity_au_tenant_ass_da_idx'),
        ),
        migrations.AddIndex(
            model_name='assetutilizationmetric',
            index=models.Index(fields=['tenant', 'date'], name='activity_au_tenant_dat_idx'),
        ),
        migrations.AddIndex(
            model_name='assetutilizationmetric',
            index=models.Index(fields=['utilization_percentage'], name='activity_au_utiliza_idx'),
        ),
        # Add indexes for MaintenanceCostTracking
        migrations.AddIndex(
            model_name='maintenancecosttracking',
            index=models.Index(fields=['tenant', 'asset', 'maintenance_date'], name='activity_mc_tenant_ass_ma_idx'),
        ),
        migrations.AddIndex(
            model_name='maintenancecosttracking',
            index=models.Index(fields=['tenant', 'cost_type', 'maintenance_date'], name='activity_mc_tenant_cos_ma_idx'),
        ),
        migrations.AddIndex(
            model_name='maintenancecosttracking',
            index=models.Index(fields=['maintenance_date'], name='activity_mc_mainten_idx'),
        ),
        # Add indexes for AssetHealthScore
        migrations.AddIndex(
            model_name='assethealthscore',
            index=models.Index(fields=['tenant', 'asset', 'calculated_date'], name='activity_ah_tenant_ass_ca_idx'),
        ),
        migrations.AddIndex(
            model_name='assethealthscore',
            index=models.Index(fields=['tenant', 'risk_level'], name='activity_ah_tenant_ris_idx'),
        ),
        migrations.AddIndex(
            model_name='assethealthscore',
            index=models.Index(fields=['health_score'], name='activity_ah_health__idx'),
        ),
    ]
