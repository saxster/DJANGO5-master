# Generated manually for AI Testing Platform Phase 3

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('issue_tracker', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AdaptiveThreshold',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('metric_name', models.CharField(choices=[('latency_p95', 'P95 Latency (ms)'), ('latency_p99', 'P99 Latency (ms)'), ('error_rate', 'Error Rate (%)'), ('jank_score', 'UI Jank Score'), ('composition_time', 'Compose Composition Time (ms)'), ('memory_usage', 'Memory Usage (MB)'), ('battery_drain', 'Battery Drain Rate'), ('frame_drop_rate', 'Frame Drop Rate (%)'), ('network_failure_rate', 'Network Failure Rate (%)'), ('startup_time', 'App Startup Time (ms)')], max_length=50)),
                ('user_segment', models.CharField(choices=[('power_user', 'Power User'), ('casual_user', 'Casual User'), ('enterprise_user', 'Enterprise User'), ('developer', 'Developer/Tester'), ('all_users', 'All Users')], default='all_users', max_length=20)),
                ('app_version', models.CharField(blank=True, help_text='Optional: version-specific threshold', max_length=50)),
                ('platform', models.CharField(default='all', help_text='android, ios, or all', max_length=20)),
                ('static_baseline', models.FloatField(help_text='Original static threshold value')),
                ('adaptive_value', models.FloatField(help_text='Current AI-adapted threshold value')),
                ('confidence_lower', models.FloatField(help_text='Lower bound of confidence interval')),
                ('confidence_upper', models.FloatField(help_text='Upper bound of confidence interval')),
                ('confidence_level', models.FloatField(default=0.95, help_text='Confidence level for threshold estimation (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('adaptation_method', models.CharField(choices=[('time_series', 'Time Series Analysis'), ('percentile_based', 'Percentile-Based Adaptive'), ('ml_regression', 'ML Regression Model'), ('seasonal_aware', 'Seasonal Pattern Aware'), ('user_behavior', 'User Behavior Pattern')], max_length=20)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('update_frequency_hours', models.IntegerField(default=24, help_text='How often to recalculate threshold in hours', validators=[django.core.validators.MinValueValidator(1)])),
                ('sample_size', models.IntegerField(default=0, help_text='Number of data points used for current threshold')),
                ('historical_values', models.JSONField(default=list, help_text='Recent threshold values for trend analysis')),
                ('improvement_score', models.FloatField(blank=True, help_text='Score indicating threshold effectiveness (higher = better)', null=True, validators=[django.core.validators.MinValueValidator(0.0)])),
                ('false_positive_rate', models.FloatField(blank=True, help_text='Rate of false positives with current threshold', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('seasonal_patterns', models.JSONField(default=dict, help_text='Detected seasonal patterns (hourly, daily, weekly)')),
                ('is_seasonal_aware', models.BooleanField(default=False, help_text='Whether threshold adapts to seasonal patterns')),
                ('is_active', models.BooleanField(default=True)),
                ('is_validated', models.BooleanField(default=False, help_text='Whether threshold has been validated with production data')),
                ('validation_notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['metric_name', 'user_segment', 'platform'],
            },
        ),
        migrations.CreateModel(
            name='MLBaseline',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('baseline_type', models.CharField(choices=[('visual', 'Visual/UI Baseline'), ('performance', 'Performance Baseline'), ('functional', 'Functional Baseline'), ('api', 'API Response Baseline'), ('accessibility', 'Accessibility Baseline')], max_length=20)),
                ('component_name', models.CharField(help_text='UI component or API endpoint name', max_length=200)),
                ('test_scenario', models.CharField(help_text='Test scenario description', max_length=200)),
                ('platform', models.CharField(default='all', help_text='android, ios, web, or all', max_length=20)),
                ('app_version', models.CharField(max_length=50)),
                ('device_class', models.CharField(blank=True, help_text='Device class: phone, tablet, desktop, etc.', max_length=50)),
                ('visual_hash', models.CharField(blank=True, help_text='Hash of visual baseline image', max_length=64)),
                ('visual_metadata', models.JSONField(blank=True, help_text='Visual analysis metadata (layout, colors, text, etc.)', null=True)),
                ('semantic_elements', models.JSONField(default=dict, help_text='ML-identified semantic elements (buttons, text, images, etc.)')),
                ('element_hierarchy', models.JSONField(default=dict, help_text='UI element hierarchy and relationships')),
                ('interaction_regions', models.JSONField(default=list, help_text='Identified clickable/interactive regions')),
                ('performance_metrics', models.JSONField(blank=True, help_text='Performance baseline metrics', null=True)),
                ('approval_status', models.CharField(choices=[('auto_approved', 'Auto-Approved'), ('pending_review', 'Pending Review'), ('community_approved', 'Community Approved'), ('rejected', 'Rejected'), ('deprecated', 'Deprecated')], default='pending_review', max_length=20)),
                ('semantic_confidence', models.CharField(choices=[('low', 'Low (0-40%)'), ('medium', 'Medium (40-70%)'), ('high', 'High (70-90%)'), ('very_high', 'Very High (90%+)')], default='medium', max_length=20)),
                ('validation_score', models.FloatField(default=0.5, help_text='ML validation score for baseline quality', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('approval_votes', models.IntegerField(default=0)),
                ('rejection_votes', models.IntegerField(default=0)),
                ('total_validations', models.IntegerField(default=0)),
                ('tolerance_threshold', models.FloatField(default=0.05, help_text='Threshold for detecting meaningful changes (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('ignore_cosmetic_changes', models.BooleanField(default=True, help_text='Whether to ignore purely cosmetic changes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('last_validated', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('superseded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='superseded_baselines', to='ai_testing.mlbaseline')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ModelPerformanceMetrics',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('model_name', models.CharField(choices=[('gradient_boosting', 'Gradient Boosting'), ('random_forest', 'Random Forest'), ('neural_network', 'Neural Network'), ('time_series', 'Time Series Analysis'), ('ensemble', 'Ensemble Model')], max_length=50)),
                ('model_version', models.CharField(max_length=20)),
                ('prediction_type', models.CharField(choices=[('performance', 'Performance Regression'), ('visual', 'Visual Regression'), ('functional', 'Functional Regression'), ('crash', 'Crash/Stability'), ('memory', 'Memory Leak'), ('network', 'Network Issues'), ('battery', 'Battery Drain'), ('security', 'Security Vulnerability')], max_length=20)),
                ('accuracy_score', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('precision_score', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('recall_score', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('f1_score', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('auc_score', models.FloatField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('training_samples', models.IntegerField()),
                ('validation_samples', models.IntegerField()),
                ('feature_count', models.IntegerField()),
                ('false_positive_rate', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('false_negative_rate', models.FloatField(validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('measured_at', models.DateTimeField(auto_now_add=True)),
                ('measurement_period_days', models.IntegerField(default=30)),
                ('hyperparameters', models.JSONField(default=dict)),
                ('feature_importance_top10', models.JSONField(default=list)),
            ],
            options={
                'ordering': ['-measured_at'],
            },
        ),
        migrations.CreateModel(
            name='TestCoverageGap',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('coverage_type', models.CharField(choices=[('visual', 'Visual Regression'), ('performance', 'Performance'), ('functional', 'Functional'), ('integration', 'Integration'), ('edge_case', 'Edge Case'), ('error_handling', 'Error Handling'), ('user_flow', 'User Flow'), ('api_contract', 'API Contract'), ('device_specific', 'Device-Specific'), ('network_condition', 'Network Condition')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('affected_endpoints', models.JSONField(default=list, help_text='List of affected API endpoints or UI components')),
                ('affected_platforms', models.JSONField(default=list, help_text='Platforms affected: android, ios, web')),
                ('priority', models.CharField(choices=[('critical', 'Critical'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low')], max_length=20)),
                ('confidence_score', models.FloatField(help_text='ML confidence in gap identification (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('impact_score', models.FloatField(help_text='Estimated impact of filling this gap (0.0-10.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(10.0)])),
                ('recommended_framework', models.CharField(blank=True, choices=[('paparazzi', 'Paparazzi (Visual)'), ('macrobenchmark', 'Macrobenchmark (Performance)'), ('espresso', 'Espresso (UI)'), ('junit', 'JUnit (Unit)'), ('robolectric', 'Robolectric (Unit/Integration)'), ('ui_testing', 'SwiftUI Testing (iOS)'), ('xctest', 'XCTest (iOS)'), ('custom', 'Custom Framework')], help_text='Recommended test framework for this gap', max_length=20)),
                ('auto_generated_test_code', models.TextField(blank=True, help_text='AI-generated test code ready for implementation')),
                ('test_file_path', models.CharField(blank=True, help_text='Suggested file path for the test', max_length=500)),
                ('status', models.CharField(choices=[('identified', 'Identified'), ('test_generated', 'Test Generated'), ('test_implemented', 'Test Implemented'), ('test_verified', 'Test Verified'), ('dismissed', 'Dismissed')], default='identified', max_length=20)),
                ('implemented_test_file', models.CharField(blank=True, help_text='Actual path of implemented test file', max_length=500)),
                ('implementation_commit', models.CharField(blank=True, help_text='Git commit SHA of test implementation', max_length=40)),
                ('verification_notes', models.TextField(blank=True)),
                ('similar_gaps_count', models.IntegerField(default=0, help_text='Number of similar gaps found in codebase')),
                ('pattern_metadata', models.JSONField(default=dict, help_text='Metadata about detected patterns and similarities')),
                ('identified_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('implemented_at', models.DateTimeField(blank=True, null=True)),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('anomaly_signature', models.ForeignKey(help_text='Anomaly that revealed this coverage gap', on_delete=django.db.models.deletion.CASCADE, related_name='coverage_gaps', to='issue_tracker.anomalysignature')),
                ('assigned_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_coverage_gaps', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-priority', '-confidence_score', '-impact_score', '-identified_at'],
            },
        ),
        migrations.CreateModel(
            name='TestCoveragePattern',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('pattern_type', models.CharField(choices=[('recurring_endpoint', 'Recurring Endpoint Issues'), ('platform_specific', 'Platform-Specific Gaps'), ('framework_weakness', 'Framework Coverage Weakness'), ('user_flow_gap', 'User Flow Coverage Gap'), ('error_scenario', 'Error Scenario Pattern'), ('performance_blind_spot', 'Performance Blind Spot')], max_length=30)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('pattern_signature', models.CharField(help_text='Hash signature of the pattern for deduplication', max_length=64)),
                ('pattern_criteria', models.JSONField(help_text='JSON criteria that define this pattern')),
                ('occurrence_count', models.IntegerField(default=1)),
                ('confidence_score', models.FloatField(help_text='Confidence in pattern validity', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('recommended_actions', models.JSONField(default=list, help_text='List of recommended actions to address this pattern')),
                ('template_test_code', models.TextField(blank=True, help_text='Template test code for gaps matching this pattern')),
                ('first_detected', models.DateTimeField(auto_now_add=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('is_active', models.BooleanField(default=True)),
                ('coverage_gaps', models.ManyToManyField(help_text='Coverage gaps that match this pattern', related_name='patterns', to='ai_testing.testcoveragegap')),
            ],
            options={
                'ordering': ['-occurrence_count', '-confidence_score'],
            },
        ),
        migrations.CreateModel(
            name='SemanticElement',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('element_type', models.CharField(choices=[('button', 'Button'), ('text_field', 'Text Field'), ('label', 'Text Label'), ('image', 'Image'), ('icon', 'Icon'), ('container', 'Container/Layout'), ('navigation', 'Navigation Element'), ('form', 'Form Element'), ('list_item', 'List Item'), ('modal', 'Modal/Dialog')], max_length=20)),
                ('element_id', models.CharField(blank=True, help_text='UI element ID if available', max_length=200)),
                ('element_text', models.TextField(blank=True, help_text='Visible text content')),
                ('element_description', models.TextField(blank=True, help_text='AI-generated description')),
                ('bounding_box', models.JSONField(help_text='Element bounding box: {x, y, width, height}')),
                ('z_index', models.IntegerField(default=0, help_text='Layer/depth information')),
                ('interaction_type', models.CharField(choices=[('clickable', 'Clickable'), ('scrollable', 'Scrollable'), ('input', 'Input Field'), ('display_only', 'Display Only'), ('navigation', 'Navigation')], default='display_only', max_length=20)),
                ('is_critical', models.BooleanField(default=False, help_text='Whether this element is critical for user flow')),
                ('visual_properties', models.JSONField(default=dict, help_text='Visual properties: colors, fonts, styles, etc.')),
                ('detection_confidence', models.FloatField(help_text='ML confidence in element detection and classification', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('baseline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='elements', to='ai_testing.mlbaseline')),
            ],
            options={
                'ordering': ['baseline', 'element_type', 'z_index'],
            },
        ),
        migrations.CreateModel(
            name='RegressionPrediction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('prediction_type', models.CharField(choices=[('performance', 'Performance Regression'), ('visual', 'Visual Regression'), ('functional', 'Functional Regression'), ('crash', 'Crash/Stability'), ('memory', 'Memory Leak'), ('network', 'Network Issues'), ('battery', 'Battery Drain'), ('security', 'Security Vulnerability')], max_length=20)),
                ('app_version', models.CharField(help_text='Target app version', max_length=50)),
                ('build_number', models.CharField(blank=True, max_length=50)),
                ('platform', models.CharField(default='all', help_text='android, ios, or all', max_length=20)),
                ('risk_level', models.CharField(choices=[('low', 'Low Risk (0-30%)'), ('medium', 'Medium Risk (30-70%)'), ('high', 'High Risk (70-90%)'), ('critical', 'Critical Risk (90%+)')], max_length=20)),
                ('predicted_risk_score', models.FloatField(help_text='ML predicted risk score (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('confidence_level', models.FloatField(help_text='Model confidence in prediction (0.0-1.0)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField()),
                ('affected_components', models.JSONField(default=list, help_text='List of components/features likely to be affected')),
                ('contributing_factors', models.JSONField(help_text='Factors contributing to the prediction')),
                ('model_used', models.CharField(choices=[('gradient_boosting', 'Gradient Boosting'), ('random_forest', 'Random Forest'), ('neural_network', 'Neural Network'), ('time_series', 'Time Series Analysis'), ('ensemble', 'Ensemble Model')], max_length=30)),
                ('model_version', models.CharField(default='1.0', max_length=20)),
                ('feature_importance', models.JSONField(help_text='Feature importance scores from the ML model')),
                ('training_data_timeframe', models.CharField(help_text='Timeframe of training data (e.g., \'90 days\', \'6 months\')', max_length=50)),
                ('similar_past_regressions', models.JSONField(default=list, help_text='References to similar past regressions')),
                ('status', models.CharField(choices=[('pending', 'Pending Validation'), ('validated', 'Validated'), ('false_positive', 'False Positive'), ('confirmed', 'Confirmed in Production'), ('mitigated', 'Mitigated')], default='pending', max_length=20)),
                ('actual_outcome', models.TextField(blank=True)),
                ('validation_notes', models.TextField(blank=True)),
                ('recommended_actions', models.JSONField(default=list, help_text='Recommended mitigation actions')),
                ('suggested_tests', models.JSONField(default=list, help_text='Suggested additional tests to run')),
                ('predicted_at', models.DateTimeField(auto_now_add=True)),
                ('target_release_date', models.DateTimeField(blank=True, help_text='Expected release date for the version', null=True)),
                ('validated_at', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('based_on_anomalies', models.ManyToManyField(blank=True, help_text='Historical anomalies used for prediction', related_name='regression_predictions', to='issue_tracker.anomalysignature')),
            ],
            options={
                'ordering': ['-predicted_risk_score', '-confidence_level', '-predicted_at'],
            },
        ),
        migrations.CreateModel(
            name='BaselineComparison',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('comparison_type', models.CharField(choices=[('visual_diff', 'Visual Difference'), ('functional_diff', 'Functional Difference'), ('performance_diff', 'Performance Difference')], max_length=20)),
                ('test_run_id', models.UUIDField(help_text='Reference to test run from streamlab')),
                ('comparison_result', models.CharField(choices=[('identical', 'Identical'), ('acceptable_diff', 'Acceptable Difference'), ('significant_diff', 'Significant Difference'), ('regression', 'Regression Detected')], max_length=20)),
                ('difference_score', models.FloatField(help_text='Quantified difference score (0.0 = identical, 1.0 = completely different)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('significant_changes', models.JSONField(default=list, help_text='List of significant changes detected')),
                ('cosmetic_changes', models.JSONField(default=list, help_text='List of cosmetic/insignificant changes')),
                ('ml_confidence', models.FloatField(help_text='ML confidence in comparison analysis', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('false_positive_likelihood', models.FloatField(blank=True, help_text='Likelihood this is a false positive', null=True, validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(1.0)])),
                ('human_validated', models.BooleanField(default=False)),
                ('human_agreement', models.BooleanField(blank=True, help_text='Whether human reviewer agreed with ML analysis', null=True)),
                ('validation_notes', models.TextField(blank=True)),
                ('compared_at', models.DateTimeField(auto_now_add=True)),
                ('validated_at', models.DateTimeField(blank=True, null=True)),
                ('baseline', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comparisons', to='ai_testing.mlbaseline')),
            ],
            options={
                'ordering': ['-compared_at'],
            },
        ),
        # Add indexes
        migrations.AddIndex(
            model_name='adaptivethreshold',
            index=models.Index(fields=['metric_name', 'platform'], name='ai_testing_a_metric__3fb94b_idx'),
        ),
        migrations.AddIndex(
            model_name='adaptivethreshold',
            index=models.Index(fields=['last_updated', 'update_frequency_hours'], name='ai_testing_a_last_up_8e7f5c_idx'),
        ),
        migrations.AddIndex(
            model_name='adaptivethreshold',
            index=models.Index(fields=['is_active', 'is_validated'], name='ai_testing_a_is_acti_4b5e2d_idx'),
        ),
        migrations.AddIndex(
            model_name='adaptivethreshold',
            index=models.Index(fields=['user_segment', 'metric_name'], name='ai_testing_a_user_se_f8d6c1_idx'),
        ),
        migrations.AddIndex(
            model_name='adaptivethreshold',
            index=models.Index(fields=['app_version', 'platform', 'metric_name'], name='ai_testing_a_app_ver_9a2b4c_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbaseline',
            index=models.Index(fields=['baseline_type', 'platform'], name='ai_testing_m_baselin_5c8d7e_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbaseline',
            index=models.Index(fields=['component_name', 'app_version'], name='ai_testing_m_compone_1f9a3b_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbaseline',
            index=models.Index(fields=['approval_status', 'is_active'], name='ai_testing_m_approva_7e4f2c_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbaseline',
            index=models.Index(fields=['visual_hash'], name='ai_testing_m_visual__6d5a8b_idx'),
        ),
        migrations.AddIndex(
            model_name='mlbaseline',
            index=models.Index(fields=['validation_score', 'semantic_confidence'], name='ai_testing_m_validat_2b9c4d_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['coverage_type', 'priority'], name='ai_testing_t_coverag_8a3e5f_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['status', 'identified_at'], name='ai_testing_t_status_1b7c9d_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['confidence_score', 'impact_score'], name='ai_testing_t_confide_4f2a6e_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['anomaly_signature', 'status'], name='ai_testing_t_anomaly_7d8c1b_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['assigned_to', 'status'], name='ai_testing_t_assigne_9e5f3a_idx'),
        ),
        migrations.AddIndex(
            model_name='testcoveragegap',
            index=models.Index(fields=['recommended_framework'], name='ai_testing_t_recomme_2c6d8f_idx'),
        ),
        migrations.AddIndex(
            model_name='regressionprediction',
            index=models.Index(fields=['app_version', 'platform'], name='ai_testing_r_app_ver_3b7e9f_idx'),
        ),
        migrations.AddIndex(
            model_name='regressionprediction',
            index=models.Index(fields=['prediction_type', 'risk_level'], name='ai_testing_r_predict_5a8c2d_idx'),
        ),
        migrations.AddIndex(
            model_name='regressionprediction',
            index=models.Index(fields=['status', 'predicted_at'], name='ai_testing_r_status_4e1b6f_idx'),
        ),
        migrations.AddIndex(
            model_name='regressionprediction',
            index=models.Index(fields=['predicted_risk_score', 'confidence_level'], name='ai_testing_r_predict_7c9a4b_idx'),
        ),
        migrations.AddIndex(
            model_name='regressionprediction',
            index=models.Index(fields=['target_release_date'], name='ai_testing_r_target__8f3d2e_idx'),
        ),
        # Add unique constraints
        migrations.AlterUniqueTogether(
            name='adaptivethreshold',
            unique_together={('metric_name', 'user_segment', 'app_version', 'platform')},
        ),
        migrations.AlterUniqueTogether(
            name='mlbaseline',
            unique_together={('baseline_type', 'component_name', 'test_scenario', 'platform', 'app_version')},
        ),
        migrations.AlterUniqueTogether(
            name='testcoveragepattern',
            unique_together={('pattern_type', 'pattern_signature')},
        ),
    ]