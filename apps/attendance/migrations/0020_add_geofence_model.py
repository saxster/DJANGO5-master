"""
Add Geofence model for geographic boundary validation.

Migration for REST API geofencing feature.
"""

from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0010_add_performance_indexes'),
        ('onboarding', '0001_initial'),
        ('tenants', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Geofence',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tenant', models.CharField(default='default', max_length=100)),
                ('cdtz', models.DateTimeField(auto_now_add=True)),
                ('mdtz', models.DateTimeField(auto_now=True)),
                ('ctzoffset', models.IntegerField(default=0)),
                ('mtzoffset', models.IntegerField(default=0)),
                ('name', models.CharField(help_text='Geofence name (e.g., "Office Campus", "Site A")', max_length=255)),
                ('geofence_type', models.CharField(
                    choices=[('polygon', 'Polygon'), ('circle', 'Circle')],
                    default='polygon',
                    help_text='Type of geofence (polygon or circle)',
                    max_length=20
                )),
                ('boundary', django.contrib.gis.db.models.fields.PolygonField(
                    blank=True,
                    help_text='Geographic boundary (GeoJSON polygon)',
                    null=True,
                    srid=4326
                )),
                ('center_point', django.contrib.gis.db.models.fields.PointField(
                    blank=True,
                    help_text='Center point for circle geofences',
                    null=True,
                    srid=4326
                )),
                ('radius', models.FloatField(
                    blank=True,
                    help_text='Radius in meters (for circle geofences)',
                    null=True
                )),
                ('is_active', models.BooleanField(default=True, help_text='Whether this geofence is active')),
                ('description', models.TextField(blank=True, help_text='Additional notes about this geofence')),
                ('bu', models.ForeignKey(
                    blank=True,
                    help_text='Business unit this geofence belongs to',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    to='onboarding.bt'
                )),
                ('client', models.ForeignKey(
                    blank=True,
                    help_text='Client this geofence belongs to',
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='geofence_clients',
                    to='onboarding.bt'
                )),
            ],
            options={
                'db_table': 'geofence',
            },
        ),
        migrations.AddIndex(
            model_name='geofence',
            index=models.Index(fields=['tenant', 'is_active'], name='geofence_tenant_active_idx'),
        ),
        migrations.AddIndex(
            model_name='geofence',
            index=models.Index(fields=['tenant', 'bu'], name='geofence_tenant_bu_idx'),
        ),
        migrations.AddConstraint(
            model_name='geofence',
            constraint=models.CheckConstraint(
                check=models.Q(('radius__gte', 0), ('radius__isnull', True), _connector='OR'),
                name='radius_non_negative'
            ),
        ),
    ]
