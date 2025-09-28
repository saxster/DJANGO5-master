"""
Regression Predictor Service
ML-powered prediction of performance regressions and quality issues before release
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from apps.issue_tracker.models import AnomalySignature, AnomalyOccurrence
from apps.ai_testing.models import RegressionPrediction, ModelPerformanceMetrics

logger = logging.getLogger(__name__)


@dataclass
class PredictionFeatures:
    """Feature set for regression prediction"""
    # Historical anomaly features
    anomaly_count_7d: float
    anomaly_count_30d: float
    anomaly_severity_avg: float
    anomaly_types_diversity: float

    # Performance trend features
    latency_p95_trend: float
    error_rate_trend: float
    jank_score_trend: float
    composition_time_trend: float

    # Version and deployment features
    days_since_last_release: float
    code_changes_count: float
    new_features_count: float
    bug_fixes_count: float

    # Platform-specific features
    android_specific_issues: float
    ios_specific_issues: float
    cross_platform_issues: float

    # Test coverage features
    test_coverage_percentage: float
    visual_test_count: float
    performance_test_count: float

    # User behavior features
    user_sessions_change: float
    crash_free_rate: float
    user_retention_change: float


class RegressionPredictor:
    """
    Predicts potential regressions using ML models trained on historical data
    """

    def __init__(self):
        self.models = {
            'gradient_boosting': GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                random_state=42
            ),
            'random_forest': RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                random_state=42
            ),
            'neural_network': MLPClassifier(
                hidden_layer_sizes=(100, 50),
                max_iter=1000,
                random_state=42
            )
        }
        self.scaler = StandardScaler()
        self.trained_models = {}
        self.feature_importance = {}

    def predict_regressions(self, app_version: str, build_number: str = None,
                          platform: str = 'all') -> List[Dict[str, Any]]:
        """
        Predict potential regressions for an upcoming release

        Args:
            app_version: Target app version
            build_number: Optional build number
            platform: Target platform (android, ios, all)

        Returns:
            List of regression predictions
        """
        logger.info(f"Predicting regressions for {app_version} ({platform})")

        try:
            # Extract features for prediction
            features = self._extract_prediction_features(app_version, platform)

            if not features:
                logger.warning("Insufficient data for regression prediction")
                return []

            # Load or train models
            self._ensure_models_trained()

            # Make predictions with each model
            predictions = []

            for prediction_type in ['performance', 'visual', 'functional', 'crash']:
                prediction = self._predict_regression_type(
                    features, prediction_type, app_version, platform
                )
                if prediction:
                    predictions.append(prediction)

            # Sort by risk score
            predictions.sort(key=lambda x: x['predicted_risk_score'], reverse=True)

            # Store predictions in database
            self._store_predictions(predictions, app_version, build_number, platform)

            logger.info(f"Generated {len(predictions)} regression predictions")
            return predictions

        except (AttributeError, TypeError, ValueError) as e:
            logger.error(f"Error predicting regressions: {str(e)}")
            return []

    def _extract_prediction_features(self, app_version: str, platform: str) -> Optional[PredictionFeatures]:
        """Extract features for regression prediction"""
        try:
            now = timezone.now()
            week_ago = now - timedelta(days=7)
            month_ago = now - timedelta(days=30)

            # Historical anomaly features
            recent_anomalies_7d = AnomalyOccurrence.objects.filter(
                created_at__gte=week_ago
            )
            recent_anomalies_30d = AnomalyOccurrence.objects.filter(
                created_at__gte=month_ago
            )

            anomaly_count_7d = recent_anomalies_7d.count()
            anomaly_count_30d = recent_anomalies_30d.count()

            # Anomaly severity average
            severity_scores = {
                'info': 1, 'warning': 2, 'error': 3, 'critical': 4
            }

            severity_avg = 0
            if recent_anomalies_30d.exists():
                severities = recent_anomalies_30d.values_list('signature__severity', flat=True)
                severity_avg = np.mean([severity_scores.get(s, 1) for s in severities])

            # Anomaly type diversity
            anomaly_types = set(recent_anomalies_30d.values_list('signature__anomaly_type', flat=True))
            anomaly_types_diversity = len(anomaly_types)

            # Performance trend features
            performance_trends = self._calculate_performance_trends(month_ago, platform)

            # Version features
            version_features = self._extract_version_features(app_version)

            # Platform-specific features
            platform_features = self._extract_platform_features(month_ago, platform)

            # Test coverage features
            coverage_features = self._extract_coverage_features()

            # User behavior features
            user_features = self._extract_user_behavior_features(month_ago)

            return PredictionFeatures(
                # Historical anomaly features
                anomaly_count_7d=float(anomaly_count_7d),
                anomaly_count_30d=float(anomaly_count_30d),
                anomaly_severity_avg=severity_avg,
                anomaly_types_diversity=float(anomaly_types_diversity),

                # Performance trends
                **performance_trends,

                # Version features
                **version_features,

                # Platform features
                **platform_features,

                # Coverage features
                **coverage_features,

                # User features
                **user_features
            )

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error extracting prediction features: {str(e)}")
            return None

    def _calculate_performance_trends(self, since_date: datetime, platform: str) -> Dict[str, float]:
        """Calculate performance trend features"""
        # Get recent performance data from stream events
        stream_events = StreamEvent.objects.filter(
            timestamp__gte=since_date,
            outcome='success'
        )

        if platform != 'all':
            # Filter by platform if specified (would need platform field in StreamEvent)
            pass

        if not stream_events.exists():
            return {
                'latency_p95_trend': 0.0,
                'error_rate_trend': 0.0,
                'jank_score_trend': 0.0,
                'composition_time_trend': 0.0
            }

        # Calculate trends over time
        recent_half = stream_events.filter(timestamp__gte=since_date + timedelta(days=15))
        older_half = stream_events.filter(timestamp__lt=since_date + timedelta(days=15))

        def calculate_trend(recent_queryset, older_queryset, field):
            recent_avg = recent_queryset.aggregate(avg=Avg(field))['avg'] or 0
            older_avg = older_queryset.aggregate(avg=Avg(field))['avg'] or 0

            if older_avg == 0:
                return 0.0

            return (recent_avg - older_avg) / older_avg

        return {
            'latency_p95_trend': calculate_trend(recent_half, older_half, 'latency_ms'),
            'error_rate_trend': self._calculate_error_rate_trend(recent_half, older_half),
            'jank_score_trend': calculate_trend(recent_half, older_half, 'jank_score'),
            'composition_time_trend': calculate_trend(recent_half, older_half, 'composition_time_ms')
        }

    def _calculate_error_rate_trend(self, recent_events, older_events):
        """Calculate error rate trend"""
        recent_total = recent_events.count()
        recent_errors = recent_events.filter(outcome='error').count()

        older_total = older_events.count()
        older_errors = older_events.filter(outcome='error').count()

        if recent_total == 0 or older_total == 0:
            return 0.0

        recent_rate = recent_errors / recent_total
        older_rate = older_errors / older_total

        if older_rate == 0:
            return 1.0 if recent_rate > 0 else 0.0

        return (recent_rate - older_rate) / older_rate

    def _extract_version_features(self, app_version: str) -> Dict[str, float]:
        """Extract version-related features"""
        # This would integrate with version control or release management
        # For now, return placeholder values
        return {
            'days_since_last_release': 14.0,  # Placeholder
            'code_changes_count': 150.0,  # Placeholder
            'new_features_count': 5.0,  # Placeholder
            'bug_fixes_count': 12.0  # Placeholder
        }

    def _extract_platform_features(self, since_date: datetime, platform: str) -> Dict[str, float]:
        """Extract platform-specific features"""
        anomalies = AnomalyOccurrence.objects.filter(created_at__gte=since_date)

        # Count platform-specific anomalies based on client OS
        android_issues = anomalies.filter(
            client_os_version__icontains='Android'
        ).count()

        ios_issues = anomalies.filter(
            client_os_version__icontains='iOS'
        ).count()

        total_issues = anomalies.count()
        cross_platform_issues = total_issues - android_issues - ios_issues

        return {
            'android_specific_issues': float(android_issues),
            'ios_specific_issues': float(ios_issues),
            'cross_platform_issues': float(cross_platform_issues)
        }

    def _extract_coverage_features(self) -> Dict[str, float]:
        """Extract test coverage features"""
        # This would integrate with test coverage reports
        # For now, return placeholder values based on existing test data
        from apps.ai_testing.models import TestCoverageGap

        total_gaps = TestCoverageGap.objects.count()
        resolved_gaps = TestCoverageGap.objects.filter(
            status='test_verified'
        ).count()

        coverage_percentage = (resolved_gaps / max(total_gaps, 1)) * 100

        return {
            'test_coverage_percentage': coverage_percentage,
            'visual_test_count': float(TestCoverageGap.objects.filter(
                coverage_type='visual', status='test_verified'
            ).count()),
            'performance_test_count': float(TestCoverageGap.objects.filter(
                coverage_type='performance', status='test_verified'
            ).count())
        }

    def _extract_user_behavior_features(self, since_date: datetime) -> Dict[str, float]:
        """Extract user behavior features"""
        # This would integrate with analytics/telemetry data
        # For now, return placeholder values
        return {
            'user_sessions_change': 0.05,  # 5% increase
            'crash_free_rate': 0.995,  # 99.5%
            'user_retention_change': 0.02  # 2% change
        }

    def _predict_regression_type(self, features: PredictionFeatures, prediction_type: str,
                               app_version: str, platform: str) -> Optional[Dict[str, Any]]:
        """Predict specific regression type"""
        try:
            # Convert features to numpy array
            feature_vector = self._features_to_vector(features)

            # Get the best model for this prediction type
            model_name = self._get_best_model(prediction_type)
            model = self.trained_models.get(model_name)

            if not model:
                logger.warning(f"No trained model available for {prediction_type}")
                return None

            # Make prediction
            risk_proba = model.predict_proba([feature_vector])[0]
            risk_score = risk_proba[1] if len(risk_proba) > 1 else risk_proba[0]
            confidence = max(risk_proba)

            # Determine risk level
            risk_level = self._score_to_risk_level(risk_score)

            # Generate contributing factors
            contributing_factors = self._identify_contributing_factors(
                features, prediction_type, feature_vector
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                prediction_type, risk_score, contributing_factors
            )

            return {
                'prediction_type': prediction_type,
                'app_version': app_version,
                'platform': platform,
                'risk_level': risk_level,
                'predicted_risk_score': float(risk_score),
                'confidence_level': float(confidence),
                'title': f"{prediction_type.title()} Regression Risk",
                'description': self._generate_prediction_description(
                    prediction_type, risk_score, contributing_factors
                ),
                'contributing_factors': contributing_factors,
                'model_used': model_name,
                'recommended_actions': recommendations,
                'target_release_date': None  # Would be set based on release schedule
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error predicting {prediction_type} regression: {str(e)}")
            return None

    def _features_to_vector(self, features: PredictionFeatures) -> np.ndarray:
        """Convert feature dataclass to numpy vector"""
        return np.array([
            features.anomaly_count_7d,
            features.anomaly_count_30d,
            features.anomaly_severity_avg,
            features.anomaly_types_diversity,
            features.latency_p95_trend,
            features.error_rate_trend,
            features.jank_score_trend,
            features.composition_time_trend,
            features.days_since_last_release,
            features.code_changes_count,
            features.new_features_count,
            features.bug_fixes_count,
            features.android_specific_issues,
            features.ios_specific_issues,
            features.cross_platform_issues,
            features.test_coverage_percentage,
            features.visual_test_count,
            features.performance_test_count,
            features.user_sessions_change,
            features.crash_free_rate,
            features.user_retention_change
        ])

    def _ensure_models_trained(self):
        """Ensure ML models are trained and ready"""
        if not self.trained_models:
            logger.info("Training regression prediction models...")
            self._train_models()

    def _train_models(self):
        """Train ML models using historical data"""
        try:
            # Get training data
            X, y, prediction_types = self._prepare_training_data()

            if len(X) < 10:
                logger.warning("Insufficient training data for ML models")
                return

            # Train models for each prediction type
            for pred_type in prediction_types:
                logger.info(f"Training models for {pred_type} prediction")

                # Filter data for this prediction type
                type_mask = np.array([pt == pred_type for pt in prediction_types])
                X_type = X[type_mask]
                y_type = y[type_mask]

                if len(X_type) < 5:
                    continue

                # Split data
                X_train, X_test, y_train, y_test = train_test_split(
                    X_type, y_type, test_size=0.2, random_state=42
                )

                # Scale features
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)

                # Train each model type
                best_model = None
                best_score = 0

                for model_name, model in self.models.items():
                    try:
                        model.fit(X_train_scaled, y_train)
                        y_pred = model.predict(X_test_scaled)
                        score = accuracy_score(y_test, y_pred)

                        if score > best_score:
                            best_score = score
                            best_model = model_name

                        # Store feature importance if available
                        if hasattr(model, 'feature_importances_'):
                            self.feature_importance[f"{model_name}_{pred_type}"] = model.feature_importances_

                        # Log model performance
                        self._log_model_performance(
                            model_name, pred_type, X_test_scaled, y_test, y_pred
                        )

                    except (AttributeError, TypeError, ValueError) as e:
                        logger.error(f"Error training {model_name} for {pred_type}: {str(e)}")

                # Store best model
                if best_model:
                    self.trained_models[f"{best_model}_{pred_type}"] = self.models[best_model]
                    logger.info(f"Best model for {pred_type}: {best_model} (score: {best_score:.3f})")

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error training models: {str(e)}")

    def _prepare_training_data(self) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """Prepare training data from historical anomalies and performance"""
        # This would collect historical regression data
        # For now, create synthetic training data based on patterns

        X = []  # Features
        y = []  # Labels (0 = no regression, 1 = regression)
        prediction_types = []

        # Get historical anomaly patterns
        recent_signatures = AnomalySignature.objects.filter(
            last_seen__gte=timezone.now() - timedelta(days=90)
        )

        for signature in recent_signatures:
            # Create feature vector based on signature
            features = self._create_synthetic_features(signature)

            # Label based on whether signature had high impact
            label = 1 if signature.occurrence_count > 10 and signature.severity in ['error', 'critical'] else 0

            X.append(features)
            y.append(label)
            prediction_types.append(self._map_anomaly_to_prediction_type(signature.anomaly_type))

        return np.array(X), np.array(y), prediction_types

    def _create_synthetic_features(self, signature: AnomalySignature) -> List[float]:
        """Create synthetic feature vector from anomaly signature"""
        # Create realistic feature values based on signature characteristics
        return [
            float(signature.occurrence_count / 10),  # anomaly_count_7d
            float(signature.occurrence_count),       # anomaly_count_30d
            float(signature.severity_score),         # anomaly_severity_avg
            1.0,                                    # anomaly_types_diversity
            0.1 if signature.anomaly_type == 'latency' else 0.0,  # latency_p95_trend
            0.1 if signature.anomaly_type == 'error' else 0.0,    # error_rate_trend
            0.1 if 'jank' in signature.anomaly_type else 0.0,     # jank_score_trend
            0.1 if 'composition' in signature.anomaly_type else 0.0,  # composition_time_trend
            14.0,   # days_since_last_release
            100.0,  # code_changes_count
            3.0,    # new_features_count
            8.0,    # bug_fixes_count
            5.0,    # android_specific_issues
            3.0,    # ios_specific_issues
            2.0,    # cross_platform_issues
            75.0,   # test_coverage_percentage
            10.0,   # visual_test_count
            8.0,    # performance_test_count
            0.05,   # user_sessions_change
            0.99,   # crash_free_rate
            0.02    # user_retention_change
        ]

    def _map_anomaly_to_prediction_type(self, anomaly_type: str) -> str:
        """Map anomaly type to prediction type"""
        mapping = {
            'latency': 'performance',
            'memory': 'performance',
            'jank': 'performance',
            'composition': 'performance',
            'error': 'functional',
            'crash': 'crash',
            'schema': 'functional',
            'visual': 'visual',
            'ui': 'visual'
        }
        return mapping.get(anomaly_type, 'functional')

    def _get_best_model(self, prediction_type: str) -> str:
        """Get best performing model for prediction type"""
        # Check model performance metrics
        best_model = ModelPerformanceMetrics.get_best_model(prediction_type)
        if best_model:
            return best_model.model_name

        # Default to gradient boosting
        return 'gradient_boosting'

    def _score_to_risk_level(self, risk_score: float) -> str:
        """Convert risk score to risk level"""
        if risk_score >= 0.9:
            return 'critical'
        elif risk_score >= 0.7:
            return 'high'
        elif risk_score >= 0.3:
            return 'medium'
        else:
            return 'low'

    def _identify_contributing_factors(self, features: PredictionFeatures,
                                     prediction_type: str, feature_vector: np.ndarray) -> Dict[str, Any]:
        """Identify factors contributing to prediction"""
        factors = {}

        # High anomaly count
        if features.anomaly_count_30d > 20:
            factors['high_anomaly_count'] = {
                'description': f"{features.anomaly_count_30d:.0f} anomalies in last 30 days",
                'impact': 'high'
            }

        # Performance degradation
        if features.latency_p95_trend > 0.2:
            factors['latency_degradation'] = {
                'description': f"{features.latency_p95_trend:.1%} increase in P95 latency",
                'impact': 'high'
            }

        # Low test coverage
        if features.test_coverage_percentage < 70:
            factors['low_test_coverage'] = {
                'description': f"Test coverage at {features.test_coverage_percentage:.1f}%",
                'impact': 'medium'
            }

        # Platform-specific issues
        if features.android_specific_issues > features.ios_specific_issues * 2:
            factors['android_instability'] = {
                'description': "High Android-specific issue rate",
                'impact': 'medium'
            }

        return factors

    def _generate_recommendations(self, prediction_type: str, risk_score: float,
                                contributing_factors: Dict) -> List[str]:
        """Generate recommendations based on prediction"""
        recommendations = []

        if risk_score > 0.7:
            recommendations.append("Consider delaying release for additional testing")

        if 'high_anomaly_count' in contributing_factors:
            recommendations.append("Investigate and resolve recurring anomalies before release")

        if 'latency_degradation' in contributing_factors:
            recommendations.append("Run additional performance tests and benchmarks")

        if 'low_test_coverage' in contributing_factors:
            recommendations.append("Increase test coverage, especially for changed components")

        if prediction_type == 'visual':
            recommendations.append("Run comprehensive visual regression tests")

        if prediction_type == 'performance':
            recommendations.append("Execute performance benchmark suite")

        return recommendations

    def _generate_prediction_description(self, prediction_type: str, risk_score: float,
                                       contributing_factors: Dict) -> str:
        """Generate human-readable prediction description"""
        risk_level = self._score_to_risk_level(risk_score)

        base_description = f"ML analysis indicates {risk_level} risk of {prediction_type} regression based on historical patterns."

        if contributing_factors:
            factor_descriptions = [factor['description'] for factor in contributing_factors.values()]
            base_description += f" Key factors: {', '.join(factor_descriptions[:3])}."

        return base_description

    def _store_predictions(self, predictions: List[Dict], app_version: str,
                          build_number: Optional[str], platform: str):
        """Store predictions in database"""
        try:
            for pred_data in predictions:
                # Check if prediction already exists
                existing = RegressionPrediction.objects.filter(
                    app_version=app_version,
                    prediction_type=pred_data['prediction_type'],
                    platform=platform
                ).first()

                if existing:
                    # Update existing prediction
                    existing.predicted_risk_score = pred_data['predicted_risk_score']
                    existing.confidence_level = pred_data['confidence_level']
                    existing.contributing_factors = pred_data['contributing_factors']
                    existing.recommended_actions = pred_data['recommended_actions']
                    existing.save()
                else:
                    # Create new prediction
                    RegressionPrediction.objects.create(
                        prediction_type=pred_data['prediction_type'],
                        app_version=app_version,
                        build_number=build_number or '',
                        platform=platform,
                        risk_level=pred_data['risk_level'],
                        predicted_risk_score=pred_data['predicted_risk_score'],
                        confidence_level=pred_data['confidence_level'],
                        title=pred_data['title'],
                        description=pred_data['description'],
                        contributing_factors=pred_data['contributing_factors'],
                        model_used=pred_data['model_used'],
                        model_version='1.0',
                        feature_importance=self.feature_importance.get(
                            f"{pred_data['model_used']}_{pred_data['prediction_type']}", {}
                        ),
                        recommended_actions=pred_data['recommended_actions'],
                        suggested_tests=[]  # Could be populated from test synthesizer
                    )

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error storing predictions: {str(e)}")

    def _log_model_performance(self, model_name: str, prediction_type: str,
                             X_test: np.ndarray, y_test: np.ndarray, y_pred: np.ndarray):
        """Log model performance metrics to database"""
        try:
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, average='weighted', zero_division=0)
            recall = recall_score(y_test, y_pred, average='weighted', zero_division=0)
            f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)

            # Calculate false positive/negative rates
            from sklearn.metrics import confusion_matrix
            cm = confusion_matrix(y_test, y_pred)
            if cm.shape == (2, 2):
                tn, fp, fn, tp = cm.ravel()
                fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
                fnr = fn / (fn + tp) if (fn + tp) > 0 else 0
            else:
                fpr = fnr = 0

            ModelPerformanceMetrics.objects.create(
                model_name=model_name,
                model_version='1.0',
                prediction_type=prediction_type,
                accuracy_score=accuracy,
                precision_score=precision,
                recall_score=recall,
                f1_score=f1,
                training_samples=len(X_test) * 4,  # Assuming 80/20 split
                validation_samples=len(X_test),
                feature_count=X_test.shape[1],
                false_positive_rate=fpr,
                false_negative_rate=fnr
            )

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error logging model performance: {str(e)}")

    def get_release_readiness_analysis(self, app_version: str, platform: str = 'all') -> Dict[str, Any]:
        """Get comprehensive release readiness analysis"""
        try:
            # Get existing predictions
            predictions = RegressionPrediction.objects.filter(
                app_version=app_version,
                platform=platform,
                status='pending'
            )

            # Calculate overall readiness score
            readiness_score = RegressionPrediction.get_release_readiness_score(app_version, platform)

            # Identify critical risks
            critical_risks = predictions.filter(risk_level='critical')
            high_risks = predictions.filter(risk_level='high')

            # Generate recommendations
            recommendations = []
            if critical_risks.exists():
                recommendations.append("Address critical risks before release")
            if high_risks.count() > 2:
                recommendations.append("Consider additional testing for high-risk areas")
            if readiness_score < 70:
                recommendations.append("Release readiness below threshold - recommend delay")

            return {
                'app_version': app_version,
                'platform': platform,
                'readiness_score': readiness_score,
                'risk_summary': {
                    'critical': critical_risks.count(),
                    'high': high_risks.count(),
                    'medium': predictions.filter(risk_level='medium').count(),
                    'low': predictions.filter(risk_level='low').count()
                },
                'critical_risks': list(critical_risks.values(
                    'prediction_type', 'predicted_risk_score', 'title', 'description'
                )),
                'recommendations': recommendations,
                'total_predictions': predictions.count(),
                'analysis_timestamp': timezone.now().isoformat()
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error generating release readiness analysis: {str(e)}")
            return {'error': str(e)}

    def retrain_models(self, force: bool = False) -> Dict[str, Any]:
        """Retrain ML models with latest data"""
        try:
            logger.info("Starting model retraining...")

            # Clear existing models if forced
            if force:
                self.trained_models = {}
                self.feature_importance = {}

            # Retrain models
            self._train_models()

            return {
                'status': 'success',
                'models_trained': len(self.trained_models),
                'retrained_at': timezone.now().isoformat()
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError) as e:
            logger.error(f"Error retraining models: {str(e)}")
            return {'status': 'error', 'message': str(e)}