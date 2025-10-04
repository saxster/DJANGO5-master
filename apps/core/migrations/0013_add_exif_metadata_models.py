# Generated migration for EXIF metadata models

from django.db import migrations, models
import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.jsonb
import django.core.validators
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('peoples', '0001_initial'),
        ('core', '0012_add_query_execution_plans'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImageMetadata',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('correlation_id', models.CharField(db_index=True, help_text='Unique correlation ID for tracking and debugging', max_length=36, unique=True)),
                ('image_path', models.CharField(db_index=True, help_text='Original file path of the analyzed image', max_length=500)),
                ('file_hash', models.CharField(db_index=True, help_text='SHA256 hash for file integrity verification', max_length=32)),
                ('file_size', models.PositiveIntegerField(help_text='File size in bytes')),
                ('file_extension', models.CharField(help_text='File extension (e.g., .jpg, .png)', max_length=10)),
                ('activity_record_id', models.PositiveIntegerField(blank=True, db_index=True, help_text='Associated activity/attendance record ID', null=True)),
                ('upload_context', models.CharField(blank=True, db_index=True, help_text='Context of image upload (attendance, facility_audit, etc.)', max_length=50, null=True)),
                ('gps_coordinates', django.contrib.gis.db.models.fields.PointField(blank=True, help_text='GPS coordinates from EXIF data', null=True, srid=4326)),
                ('gps_altitude', models.FloatField(blank=True, help_text='GPS altitude in meters', null=True)),
                ('gps_accuracy', models.FloatField(blank=True, help_text='GPS accuracy in meters', null=True)),
                ('gps_timestamp', models.DateTimeField(blank=True, help_text='GPS timestamp from EXIF data', null=True)),
                ('camera_make', models.CharField(blank=True, db_index=True, help_text='Camera manufacturer', max_length=100, null=True)),
                ('camera_model', models.CharField(blank=True, db_index=True, help_text='Camera model', max_length=100, null=True)),
                ('camera_serial', models.CharField(blank=True, help_text='Camera serial number (hashed for privacy)', max_length=100, null=True)),
                ('software_signature', models.CharField(blank=True, db_index=True, help_text='Software used to process the image', max_length=200, null=True)),
                ('photo_timestamp', models.DateTimeField(blank=True, db_index=True, help_text='Original photo timestamp from EXIF', null=True)),
                ('timestamp_consistency', models.BooleanField(default=True, help_text='Whether EXIF timestamps are consistent')),
                ('server_upload_time', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Server timestamp when metadata was processed')),
                ('authenticity_score', models.FloatField(db_index=True, default=0.5, help_text='Photo authenticity score (0.0 = fake, 1.0 = authentic)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('manipulation_risk', models.CharField(choices=[('low', 'Low Risk'), ('medium', 'Medium Risk'), ('high', 'High Risk'), ('critical', 'Critical Risk')], db_index=True, default='low', help_text='Risk level for photo manipulation', max_length=20)),
                ('validation_status', models.CharField(choices=[('pending', 'Pending Analysis'), ('valid', 'Valid Metadata'), ('invalid', 'Invalid Metadata'), ('suspicious', 'Suspicious Content'), ('error', 'Analysis Error')], db_index=True, default='pending', help_text='Overall validation status of the photo', max_length=20)),
                ('raw_exif_data', django.contrib.postgres.fields.jsonb.JSONField(default=dict, help_text='Complete raw EXIF data extracted from image')),
                ('security_analysis', django.contrib.postgres.fields.jsonb.JSONField(default=dict, help_text='Security analysis results and fraud indicators')),
                ('quality_metrics', django.contrib.postgres.fields.jsonb.JSONField(default=dict, help_text='Image quality assessment and metadata completeness')),
                ('analysis_timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now, help_text='When the EXIF analysis was performed')),
                ('analysis_version', models.CharField(default='1.0', help_text='Version of analysis algorithm used', max_length=20)),
                ('people', models.ForeignKey(blank=True, help_text='User who uploaded the image', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='image_metadata', to='peoples.people')),
            ],
            options={
                'verbose_name': 'Image Metadata',
                'verbose_name_plural': 'Image Metadata Records',
                'db_table': 'core_image_metadata',
                'ordering': ['-analysis_timestamp'],
            },
        ),
        migrations.CreateModel(
            name='CameraFingerprint',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('fingerprint_hash', models.CharField(db_index=True, help_text='Unique hash identifying the camera device', max_length=32, unique=True)),
                ('camera_make', models.CharField(db_index=True, max_length=100)),
                ('camera_model', models.CharField(db_index=True, max_length=100)),
                ('first_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('last_seen', models.DateTimeField(auto_now=True, db_index=True)),
                ('usage_count', models.PositiveIntegerField(default=1)),
                ('trust_level', models.CharField(choices=[('trusted', 'Trusted Device'), ('neutral', 'Neutral Device'), ('suspicious', 'Suspicious Device'), ('blocked', 'Blocked Device')], db_index=True, default='neutral', max_length=20)),
                ('fraud_incidents', models.PositiveIntegerField(default=0, help_text='Number of fraud incidents associated with this device')),
                ('device_characteristics', django.contrib.postgres.fields.jsonb.JSONField(default=dict, help_text='Technical characteristics and patterns')),
                ('security_notes', models.TextField(blank=True, help_text='Security notes and incident history')),
                ('associated_users', models.ManyToManyField(help_text='Users who have used this camera', related_name='camera_devices', to='peoples.people')),
            ],
            options={
                'verbose_name': 'Camera Fingerprint',
                'verbose_name_plural': 'Camera Fingerprints',
                'db_table': 'core_camera_fingerprint',
                'ordering': ['-last_seen'],
            },
        ),
        migrations.CreateModel(
            name='PhotoAuthenticityLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('validation_action', models.CharField(choices=[('automatic', 'Automatic Validation'), ('manual_review', 'Manual Review'), ('location_check', 'Location Verification'), ('device_check', 'Device Fingerprint Check'), ('historical', 'Historical Pattern Analysis')], db_index=True, max_length=30)),
                ('validation_result', models.CharField(choices=[('passed', 'Validation Passed'), ('failed', 'Validation Failed'), ('flagged', 'Flagged for Review'), ('pending', 'Pending Review')], db_index=True, max_length=20)),
                ('review_timestamp', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('validation_details', django.contrib.postgres.fields.jsonb.JSONField(default=dict, help_text='Detailed validation results and analysis')),
                ('confidence_score', models.FloatField(default=0.5, help_text='Confidence in validation result', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('validation_notes', models.TextField(blank=True, help_text='Manual review notes or system comments')),
                ('follow_up_required', models.BooleanField(db_index=True, default=False, help_text='Whether this validation requires follow-up action')),
                ('image_metadata', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='authenticity_logs', to='core.imagemetadata')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='photo_reviews', to='peoples.people')),
            ],
            options={
                'verbose_name': 'Photo Authenticity Log',
                'verbose_name_plural': 'Photo Authenticity Logs',
                'db_table': 'core_photo_authenticity_log',
                'ordering': ['-review_timestamp'],
            },
        ),
        migrations.CreateModel(
            name='ImageQualityAssessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('overall_quality_score', models.FloatField(help_text='Overall quality score (0.0 - 1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('quality_level', models.CharField(choices=[('excellent', 'Excellent Quality'), ('good', 'Good Quality'), ('fair', 'Fair Quality'), ('poor', 'Poor Quality'), ('unacceptable', 'Unacceptable Quality')], db_index=True, max_length=20)),
                ('metadata_completeness', models.FloatField(help_text='EXIF metadata completeness score', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('gps_data_quality', models.FloatField(help_text='GPS data quality and precision score', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('timestamp_reliability', models.FloatField(help_text='Timestamp consistency and reliability score', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('quality_issues', django.contrib.postgres.fields.jsonb.JSONField(default=list, help_text='List of identified quality issues')),
                ('recommendations', django.contrib.postgres.fields.jsonb.JSONField(default=list, help_text='Actionable recommendations for improvement')),
                ('assessment_timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('assessment_algorithm', models.CharField(default='exif_v1.0', help_text='Algorithm version used for assessment', max_length=50)),
                ('image_metadata', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quality_assessment', to='core.imagemetadata')),
            ],
            options={
                'verbose_name': 'Image Quality Assessment',
                'verbose_name_plural': 'Image Quality Assessments',
                'db_table': 'core_image_quality_assessment',
            },
        ),
        # Add performance indexes
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_people_context ON core_image_metadata(people_id, upload_context);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_people_context;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_security ON core_image_metadata(validation_status, manipulation_risk);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_security;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_timestamp ON core_image_metadata(analysis_timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_timestamp;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_authenticity ON core_image_metadata(authenticity_score);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_authenticity;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_camera ON core_image_metadata(camera_make, camera_model);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_camera;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_fraud_analysis ON core_image_metadata(people_id, authenticity_score, analysis_timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_fraud_analysis;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_metadata_context_security ON core_image_metadata(upload_context, validation_status, manipulation_risk);",
            reverse_sql="DROP INDEX IF EXISTS idx_metadata_context_security;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_auth_result_time ON core_photo_authenticity_log(validation_result, review_timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_auth_result_time;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_auth_reviewer_action ON core_photo_authenticity_log(reviewed_by_id, validation_action);",
            reverse_sql="DROP INDEX IF EXISTS idx_auth_reviewer_action;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_auth_followup ON core_photo_authenticity_log(follow_up_required);",
            reverse_sql="DROP INDEX IF EXISTS idx_auth_followup;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_camera_trust_activity ON core_camera_fingerprint(trust_level, last_seen);",
            reverse_sql="DROP INDEX IF EXISTS idx_camera_trust_activity;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_camera_fraud_count ON core_camera_fingerprint(fraud_incidents);",
            reverse_sql="DROP INDEX IF EXISTS idx_camera_fraud_count;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_quality_level ON core_image_quality_assessment(quality_level);",
            reverse_sql="DROP INDEX IF EXISTS idx_quality_level;"
        ),
        migrations.RunSQL(
            "CREATE INDEX idx_quality_score ON core_image_quality_assessment(overall_quality_score);",
            reverse_sql="DROP INDEX IF EXISTS idx_quality_score;"
        ),
    ]