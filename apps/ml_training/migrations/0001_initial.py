# Generated manually for ML Training Platform
# Based on models in apps/ml_training/models.py

from django.conf import settings
import django.contrib.postgres.fields
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('peoples', '0001_initial'),  # Depends on People model
        ('tenants', '0001_initial'),  # Depends on Tenant model
    ]

    operations = [
        migrations.CreateModel(
            name='TrainingDataset',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('name', models.CharField(help_text='Descriptive name for the training dataset', max_length=200, verbose_name='Dataset Name')),
                ('description', models.TextField(help_text='Detailed description of dataset purpose and content', verbose_name='Description')),
                ('dataset_type', models.CharField(choices=[('OCR_METERS', 'OCR - Meter Readings'), ('OCR_LICENSE_PLATES', 'OCR - License Plates'), ('OCR_DOCUMENTS', 'OCR - Documents'), ('FACE_RECOGNITION', 'Face Recognition'), ('OBJECT_DETECTION', 'Object Detection'), ('CLASSIFICATION', 'Image Classification'), ('CUSTOM', 'Custom Domain')], db_index=True, max_length=30, verbose_name='Dataset Type')),
                ('version', models.CharField(default='1.0', help_text='Dataset version (semantic versioning recommended)', max_length=50, verbose_name='Version')),
                ('status', models.CharField(choices=[('DRAFT', 'Draft'), ('ACTIVE', 'Active'), ('TRAINING', 'In Training'), ('ARCHIVED', 'Archived'), ('DEPRECATED', 'Deprecated')], db_index=True, default='DRAFT', max_length=20, verbose_name='Status')),
                ('total_examples', models.PositiveIntegerField(default=0, help_text='Total number of training examples', verbose_name='Total Examples')),
                ('labeled_examples', models.PositiveIntegerField(default=0, help_text='Number of fully labeled examples', verbose_name='Labeled Examples')),
                ('quality_score', models.FloatField(blank=True, help_text='Overall dataset quality score (0-1)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='Quality Score')),
                ('labeling_guidelines', models.TextField(blank=True, help_text='Instructions for labelers', verbose_name='Labeling Guidelines')),
                ('metadata', models.JSONField(default=dict, help_text='Additional dataset configuration and metrics', verbose_name='Metadata')),
                ('tags', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=50), blank=True, default=list, help_text='Tags for organization and search', size=None)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_datasets', to=settings.AUTH_USER_MODEL, verbose_name='Created By')),
                ('last_modified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='modified_datasets', to=settings.AUTH_USER_MODEL, verbose_name='Last Modified By')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ml_training_trainingdataset_tenant', to='tenants.tenant')),
            ],
            options={
                'db_table': 'ml_training_dataset',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='TrainingExample',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('image_path', models.CharField(help_text='Path to the training image file', max_length=500, verbose_name='Image Path')),
                ('image_hash', models.CharField(help_text='SHA256 hash for deduplication', max_length=64, unique=True, verbose_name='Image Hash')),
                ('image_width', models.PositiveIntegerField(blank=True, null=True, verbose_name='Image Width')),
                ('image_height', models.PositiveIntegerField(blank=True, null=True, verbose_name='Image Height')),
                ('file_size', models.PositiveIntegerField(blank=True, help_text='File size in bytes', null=True, verbose_name='File Size')),
                ('ground_truth_text', models.TextField(blank=True, help_text='Correct text/label for this example', verbose_name='Ground Truth Text')),
                ('ground_truth_data', models.JSONField(default=dict, help_text='Structured ground truth (bounding boxes, classifications, etc.)', verbose_name='Ground Truth Data')),
                ('example_type', models.CharField(choices=[('PRODUCTION', 'Production Data'), ('SYNTHETIC', 'Synthetic Data'), ('AUGMENTED', 'Data Augmentation'), ('CROWDSOURCED', 'Crowdsourced'), ('EXPERT_LABELED', 'Expert Labeled')], default='PRODUCTION', max_length=20, verbose_name='Example Type')),
                ('labeling_status', models.CharField(choices=[('UNLABELED', 'Unlabeled'), ('IN_PROGRESS', 'In Progress'), ('LABELED', 'Labeled'), ('REVIEWED', 'Reviewed'), ('DISPUTED', 'Disputed'), ('REJECTED', 'Rejected')], db_index=True, default='UNLABELED', max_length=20, verbose_name='Labeling Status')),
                ('is_labeled', models.BooleanField(db_index=True, default=False, help_text='Whether this example has valid ground truth', verbose_name='Is Labeled')),
                ('quality_score', models.FloatField(blank=True, help_text='Label quality score (0-1)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='Quality Score')),
                ('difficulty_score', models.FloatField(blank=True, help_text='Example difficulty for learning (0-1)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='Difficulty Score')),
                ('uncertainty_score', models.FloatField(blank=True, help_text='Model uncertainty on this example (0-1)', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='Uncertainty Score')),
                ('source_system', models.CharField(blank=True, help_text='System that generated this example', max_length=100, verbose_name='Source System')),
                ('source_id', models.CharField(blank=True, help_text='Original record ID in source system', max_length=100, verbose_name='Source ID')),
                ('capture_metadata', models.JSONField(default=dict, help_text='Original capture conditions and metadata', verbose_name='Capture Metadata')),
                ('selected_for_labeling', models.BooleanField(db_index=True, default=False, help_text='Selected by active learning algorithm', verbose_name='Selected for Labeling')),
                ('labeling_priority', models.PositiveIntegerField(default=0, help_text='Priority for labeling (higher = more important)', verbose_name='Labeling Priority')),
                ('dataset', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='training_examples', to='ml_training.trainingdataset', verbose_name='Dataset')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ml_training_trainingexample_tenant', to='tenants.tenant')),
            ],
            options={
                'db_table': 'ml_training_example',
                'ordering': ['-labeling_priority', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='LabelingTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Updated At')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('task_type', models.CharField(choices=[('INITIAL_LABELING', 'Initial Labeling'), ('REVIEW', 'Quality Review'), ('CORRECTION', 'Correction'), ('CONSENSUS', 'Consensus Resolution'), ('VALIDATION', 'Validation')], default='INITIAL_LABELING', max_length=20, verbose_name='Task Type')),
                ('task_status', models.CharField(choices=[('ASSIGNED', 'Assigned'), ('IN_PROGRESS', 'In Progress'), ('COMPLETED', 'Completed'), ('REVIEWED', 'Reviewed'), ('REJECTED', 'Rejected')], db_index=True, default='ASSIGNED', max_length=20, verbose_name='Task Status')),
                ('priority', models.PositiveIntegerField(default=5, help_text='Task priority (1-10, higher = more urgent)', verbose_name='Priority')),
                ('assigned_at', models.DateTimeField(auto_now_add=True, verbose_name='Assigned At')),
                ('due_date', models.DateTimeField(blank=True, null=True, verbose_name='Due Date')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='Started At')),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Completed At')),
                ('examples_completed', models.PositiveIntegerField(default=0, verbose_name='Examples Completed')),
                ('total_examples', models.PositiveIntegerField(default=0, verbose_name='Total Examples')),
                ('quality_score', models.FloatField(blank=True, help_text='Task quality score from review', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)], verbose_name='Quality Score')),
                ('review_notes', models.TextField(blank=True, verbose_name='Review Notes')),
                ('instructions', models.TextField(help_text='Specific instructions for this labeling task', verbose_name='Instructions')),
                ('metadata', models.JSONField(default=dict, help_text='Task-specific configuration and tracking data', verbose_name='Metadata')),
                ('assigned_to', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assigned_labeling_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Assigned To')),
                ('dataset', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='labeling_tasks', to='ml_training.trainingdataset', verbose_name='Dataset')),
                ('examples', models.ManyToManyField(related_name='labeling_tasks', to='ml_training.trainingexample', verbose_name='Examples')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_labeling_tasks', to=settings.AUTH_USER_MODEL, verbose_name='Reviewer')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ml_training_labelingtask_tenant', to='tenants.tenant')),
            ],
            options={
                'db_table': 'ml_labeling_task',
                'ordering': ['-priority', '-assigned_at'],
            },
        ),
        # Indexes for TrainingDataset
        migrations.AddIndex(
            model_name='trainingdataset',
            index=models.Index(fields=['dataset_type', 'status'], name='ml_training_dataset_type_status_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingdataset',
            index=models.Index(fields=['created_by', 'created_at'], name='ml_training_dataset_created_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingdataset',
            index=models.Index(fields=['total_examples', 'labeled_examples'], name='ml_training_dataset_examples_idx'),
        ),
        # Indexes for TrainingExample
        migrations.AddIndex(
            model_name='trainingexample',
            index=models.Index(fields=['dataset', 'labeling_status'], name='ml_training_example_dataset_status_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingexample',
            index=models.Index(fields=['is_labeled', 'quality_score'], name='ml_training_example_labeled_quality_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingexample',
            index=models.Index(fields=['selected_for_labeling', 'labeling_priority'], name='ml_training_example_selected_priority_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingexample',
            index=models.Index(fields=['uncertainty_score', 'difficulty_score'], name='ml_training_example_uncertainty_difficulty_idx'),
        ),
        migrations.AddIndex(
            model_name='trainingexample',
            index=models.Index(fields=['source_system', 'source_id'], name='ml_training_example_source_idx'),
        ),
        # Indexes for LabelingTask
        migrations.AddIndex(
            model_name='labelingtask',
            index=models.Index(fields=['assigned_to', 'task_status'], name='ml_labeling_task_assigned_status_idx'),
        ),
        migrations.AddIndex(
            model_name='labelingtask',
            index=models.Index(fields=['dataset', 'task_type'], name='ml_labeling_task_dataset_type_idx'),
        ),
        migrations.AddIndex(
            model_name='labelingtask',
            index=models.Index(fields=['priority', 'due_date'], name='ml_labeling_task_priority_due_idx'),
        ),
        migrations.AddIndex(
            model_name='labelingtask',
            index=models.Index(fields=['completed_at', 'quality_score'], name='ml_labeling_task_completed_quality_idx'),
        ),
        # Constraints for TrainingDataset
        migrations.AddConstraint(
            model_name='trainingdataset',
            constraint=models.CheckConstraint(check=models.Q(('labeled_examples__lte', models.F('total_examples'))), name='labeled_examples_not_exceed_total'),
        ),
    ]
