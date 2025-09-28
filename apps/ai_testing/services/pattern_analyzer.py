"""
Pattern Analyzer Service
ML-powered analysis of anomaly patterns to identify test coverage gaps and generate insights
"""

import hashlib
import json
import logging
from collections import defaultdict, Counter

import numpy as np

from apps.issue_tracker.models import AnomalySignature, AnomalyOccurrence
from apps.ai_testing.models import TestCoverageGap, TestCoveragePattern

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """
    Analyzes anomaly patterns to identify test coverage gaps and clustering insights
    """

    def __init__(self):
        self.min_cluster_size = 3
        self.pattern_confidence_threshold = 0.7
        self.similarity_threshold = 0.8

    def analyze_anomaly_patterns(self, days: int = 30) -> Dict[str, Any]:
        """
        Main method to analyze anomaly patterns and identify coverage gaps

        Args:
            days: Number of days to analyze

        Returns:
            Dict containing pattern analysis results
        """
        logger.info(f"Starting anomaly pattern analysis for last {days} days")

        # Get recent anomaly data
        since_date = timezone.now() - timedelta(days=days)
        anomaly_signatures = AnomalySignature.objects.filter(
            last_seen__gte=since_date,
            status='active'
        )

        if not anomaly_signatures.exists():
            return {'status': 'no_data', 'message': 'No active anomalies found'}

        # Perform clustering analysis
        clusters = self._cluster_anomalies(anomaly_signatures)

        # Identify test coverage gaps
        coverage_gaps = self._identify_coverage_gaps(clusters, anomaly_signatures)

        # Detect recurring patterns
        patterns = self._detect_recurring_patterns(anomaly_signatures)

        # Generate recommendations
        recommendations = self._generate_recommendations(clusters, coverage_gaps, patterns)

        results = {
            'status': 'success',
            'analysis_period_days': days,
            'total_anomalies': anomaly_signatures.count(),
            'clusters_found': len(clusters),
            'coverage_gaps_identified': len(coverage_gaps),
            'patterns_detected': len(patterns),
            'clusters': clusters,
            'coverage_gaps': coverage_gaps,
            'patterns': patterns,
            'recommendations': recommendations,
            'analyzed_at': timezone.now().isoformat()
        }

        # Store results in database
        self._store_analysis_results(results)

        logger.info(f"Pattern analysis completed: {len(clusters)} clusters, {len(coverage_gaps)} gaps")
        return results

    def _cluster_anomalies(self, anomaly_signatures) -> List[Dict[str, Any]]:
        """Cluster anomalies based on similarity patterns"""
        if anomaly_signatures.count() < 2:
            return []

        # Extract features for clustering
        features = []
        signature_data = []

        for signature in anomaly_signatures:
            feature_vector = self._extract_anomaly_features(signature)
            features.append(feature_vector)
            signature_data.append({
                'id': str(signature.id),
                'anomaly_type': signature.anomaly_type,
                'endpoint_pattern': signature.endpoint_pattern,
                'severity': signature.severity,
                'occurrence_count': signature.occurrence_count
            })

        if len(features) < self.min_cluster_size:
            return []

        # Perform DBSCAN clustering
        features_array = np.array(features)
        clustering = DBSCAN(eps=0.5, min_samples=2).fit(features_array)

        # Process clusters
        clusters = []
        for cluster_id in set(clustering.labels_):
            if cluster_id == -1:  # Noise points
                continue

            cluster_indices = np.where(clustering.labels_ == cluster_id)[0]
            cluster_signatures = [signature_data[i] for i in cluster_indices]

            if len(cluster_signatures) >= self.min_cluster_size:
                cluster_analysis = self._analyze_cluster(cluster_signatures, anomaly_signatures)
                clusters.append({
                    'cluster_id': cluster_id,
                    'size': len(cluster_signatures),
                    'signatures': cluster_signatures,
                    'analysis': cluster_analysis
                })

        return sorted(clusters, key=lambda x: x['size'], reverse=True)

    def _extract_anomaly_features(self, signature: AnomalySignature) -> List[float]:
        """Extract feature vector from anomaly signature for clustering"""
        features = []

        # Categorical features (one-hot encoded)
        anomaly_types = ['latency', 'error', 'schema', 'network', 'memory', 'crash']
        features.extend([1.0 if signature.anomaly_type == at else 0.0 for at in anomaly_types])

        severities = ['info', 'warning', 'error', 'critical']
        features.extend([1.0 if signature.severity == s else 0.0 for s in severities])

        # Numerical features (normalized)
        features.append(min(signature.occurrence_count / 100.0, 1.0))  # Normalized occurrence count
        features.append(signature.severity_score / 4.0)  # Normalized severity score

        # Endpoint pattern features
        endpoint_features = self._extract_endpoint_features(signature.endpoint_pattern)
        features.extend(endpoint_features)

        # Temporal features
        now = timezone.now()
        days_since_first_seen = (now - signature.first_seen).days
        days_since_last_seen = (now - signature.last_seen).days

        features.append(min(days_since_first_seen / 30.0, 1.0))  # Normalized age
        features.append(min(days_since_last_seen / 7.0, 1.0))   # Normalized recency

        return features

    def _extract_endpoint_features(self, endpoint_pattern: str) -> List[float]:
        """Extract features from endpoint pattern"""
        features = []

        # Common endpoint patterns
        patterns = ['/api/', '/graphql/', '/health', '/auth', '/user', '/admin', '/ws/', '/mqtt/']
        for pattern in patterns:
            features.append(1.0 if pattern in endpoint_pattern.lower() else 0.0)

        # HTTP methods (if included in pattern)
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        for method in methods:
            features.append(1.0 if method in endpoint_pattern.upper() else 0.0)

        # Path depth (approximate)
        path_depth = endpoint_pattern.count('/') if endpoint_pattern else 0
        features.append(min(path_depth / 10.0, 1.0))  # Normalized path depth

        return features

    def _analyze_cluster(self, cluster_signatures: List[Dict], all_signatures) -> Dict[str, Any]:
        """Analyze a cluster of similar anomalies"""
        # Common patterns in the cluster
        anomaly_types = [sig['anomaly_type'] for sig in cluster_signatures]
        severity_levels = [sig['severity'] for sig in cluster_signatures]
        endpoints = [sig['endpoint_pattern'] for sig in cluster_signatures]

        most_common_type = Counter(anomaly_types).most_common(1)[0]
        most_common_severity = Counter(severity_levels).most_common(1)[0]

        # Calculate cluster statistics
        total_occurrences = sum(sig['occurrence_count'] for sig in cluster_signatures)
        avg_occurrences = total_occurrences / len(cluster_signatures)

        # Identify common endpoint patterns
        common_patterns = self._find_common_patterns(endpoints)

        return {
            'dominant_anomaly_type': most_common_type[0],
            'type_frequency': most_common_type[1],
            'dominant_severity': most_common_severity[0],
            'severity_frequency': most_common_severity[1],
            'total_occurrences': total_occurrences,
            'average_occurrences': round(avg_occurrences, 2),
            'common_endpoint_patterns': common_patterns,
            'cluster_confidence': self._calculate_cluster_confidence(cluster_signatures)
        }

    def _find_common_patterns(self, endpoints: List[str]) -> List[str]:
        """Find common patterns in endpoint URLs"""
        if not endpoints:
            return []

        # Simple pattern extraction - find common substrings
        patterns = []
        for endpoint in endpoints:
            parts = endpoint.split('/')
            for i, part in enumerate(parts):
                if len(part) > 3 and not part.isdigit():  # Skip short parts and numeric IDs
                    pattern = '/'.join(parts[:i+1])
                    if pattern not in patterns:
                        patterns.append(pattern)

        # Count pattern frequencies
        pattern_counts = Counter()
        for endpoint in endpoints:
            for pattern in patterns:
                if pattern in endpoint:
                    pattern_counts[pattern] += 1

        # Return patterns that appear in at least 50% of endpoints
        threshold = len(endpoints) * 0.5
        common_patterns = [pattern for pattern, count in pattern_counts.items() if count >= threshold]

        return sorted(common_patterns, key=lambda x: pattern_counts[x], reverse=True)[:5]

    def _calculate_cluster_confidence(self, cluster_signatures: List[Dict]) -> float:
        """Calculate confidence score for a cluster"""
        if not cluster_signatures:
            return 0.0

        # Factors that increase confidence:
        # 1. Higher occurrence counts
        # 2. More similar anomaly types
        # 3. Consistent severity levels
        # 4. Recent activity

        total_occurrences = sum(sig['occurrence_count'] for sig in cluster_signatures)
        occurrence_score = min(total_occurrences / 100.0, 1.0)

        # Type consistency
        types = [sig['anomaly_type'] for sig in cluster_signatures]
        most_common_type_count = Counter(types).most_common(1)[0][1]
        type_consistency = most_common_type_count / len(types)

        # Severity consistency
        severities = [sig['severity'] for sig in cluster_signatures]
        most_common_severity_count = Counter(severities).most_common(1)[0][1]
        severity_consistency = most_common_severity_count / len(severities)

        # Weighted confidence score
        confidence = (
            occurrence_score * 0.4 +
            type_consistency * 0.3 +
            severity_consistency * 0.3
        )

        return round(confidence, 3)

    def _identify_coverage_gaps(self, clusters: List[Dict], all_signatures) -> List[Dict[str, Any]]:
        """Identify test coverage gaps based on anomaly patterns"""
        coverage_gaps = []

        for cluster in clusters:
            if cluster['analysis']['cluster_confidence'] < self.pattern_confidence_threshold:
                continue

            # Analyze cluster for potential coverage gaps
            gap_analysis = self._analyze_cluster_for_gaps(cluster, all_signatures)

            if gap_analysis['confidence'] > 0.6:
                coverage_gaps.append(gap_analysis)

        # Also analyze individual high-impact anomalies
        high_impact_anomalies = all_signatures.filter(
            occurrence_count__gte=5,
            severity__in=['error', 'critical']
        )

        for signature in high_impact_anomalies:
            gap_analysis = self._analyze_signature_for_gaps(signature)
            if gap_analysis and gap_analysis['confidence'] > 0.7:
                coverage_gaps.append(gap_analysis)

        return sorted(coverage_gaps, key=lambda x: x['priority_score'], reverse=True)

    def _analyze_cluster_for_gaps(self, cluster: Dict, all_signatures) -> Dict[str, Any]:
        """Analyze a cluster to identify potential coverage gaps"""
        cluster_analysis = cluster['analysis']
        dominant_type = cluster_analysis['dominant_anomaly_type']

        # Determine coverage gap type based on anomaly patterns
        coverage_type = self._map_anomaly_to_coverage_type(dominant_type)

        # Calculate gap priority
        priority_score = (
            cluster['size'] * 0.3 +  # Cluster size
            cluster_analysis['total_occurrences'] * 0.001 +  # Total occurrences (scaled)
            cluster_analysis['cluster_confidence'] * 0.4  # Confidence
        )

        # Generate description
        description = self._generate_gap_description(cluster, coverage_type)

        # Affected endpoints
        affected_endpoints = list(set(
            sig['endpoint_pattern'] for sig in cluster['signatures']
        ))

        return {
            'type': 'cluster',
            'coverage_type': coverage_type,
            'title': f"{coverage_type.replace('_', ' ').title()} Gap in {dominant_type.title()} Handling",
            'description': description,
            'confidence': cluster_analysis['cluster_confidence'],
            'priority_score': min(priority_score, 10.0),
            'impact_score': min(cluster_analysis['total_occurrences'] / 10.0, 10.0),
            'affected_endpoints': affected_endpoints[:10],  # Limit to first 10
            'cluster_id': cluster['cluster_id'],
            'supporting_evidence': {
                'cluster_size': cluster['size'],
                'total_occurrences': cluster_analysis['total_occurrences'],
                'dominant_anomaly_type': dominant_type,
                'affected_components': len(affected_endpoints)
            }
        }

    def _analyze_signature_for_gaps(self, signature: AnomalySignature) -> Optional[Dict[str, Any]]:
        """Analyze individual signature for coverage gaps"""
        # Skip if already part of a cluster or low impact
        if signature.occurrence_count < 5:
            return None

        coverage_type = self._map_anomaly_to_coverage_type(signature.anomaly_type)

        # Check if we already have a coverage gap for this signature
        existing_gap = TestCoverageGap.objects.filter(
            anomaly_signature=signature,
            status__in=['identified', 'test_generated', 'test_implemented']
        ).first()

        if existing_gap:
            return None  # Already identified

        priority_score = min(
            signature.occurrence_count * 0.1 +
            signature.severity_score * 2.0,
            10.0
        )

        return {
            'type': 'individual',
            'coverage_type': coverage_type,
            'title': f"{coverage_type.replace('_', ' ').title()} Gap for {signature.anomaly_type.title()}",
            'description': f"Recurring {signature.anomaly_type} issues in {signature.endpoint_pattern} suggest missing test coverage",
            'confidence': min(signature.occurrence_count / 20.0, 1.0),
            'priority_score': priority_score,
            'impact_score': min(signature.occurrence_count / 5.0, 10.0),
            'affected_endpoints': [signature.endpoint_pattern],
            'signature_id': str(signature.id),
            'supporting_evidence': {
                'occurrence_count': signature.occurrence_count,
                'severity': signature.severity,
                'first_seen': signature.first_seen.isoformat(),
                'last_seen': signature.last_seen.isoformat()
            }
        }

    def _map_anomaly_to_coverage_type(self, anomaly_type: str) -> str:
        """Map anomaly types to test coverage types"""
        mapping = {
            'latency': 'performance',
            'error': 'error_handling',
            'schema': 'api_contract',
            'network': 'network_condition',
            'memory': 'performance',
            'crash': 'edge_case',
            'timeout': 'network_condition',
            'validation': 'functional',
            'security': 'functional'
        }
        return mapping.get(anomaly_type, 'functional')

    def _generate_gap_description(self, cluster: Dict, coverage_type: str) -> str:
        """Generate human-readable description for coverage gap"""
        analysis = cluster['analysis']
        dominant_type = analysis['dominant_anomaly_type']
        endpoint_count = len(set(sig['endpoint_pattern'] for sig in cluster['signatures']))

        return (
            f"Analysis of {cluster['size']} similar {dominant_type} anomalies across "
            f"{endpoint_count} endpoints suggests insufficient {coverage_type.replace('_', ' ')} "
            f"test coverage. These anomalies have occurred {analysis['total_occurrences']} times "
            f"collectively, indicating a systematic gap in testing scenarios."
        )

    def _detect_recurring_patterns(self, anomaly_signatures) -> List[Dict[str, Any]]:
        """Detect recurring patterns across anomalies"""
        patterns = []

        # Pattern 1: Endpoint-based patterns
        endpoint_patterns = self._detect_endpoint_patterns(anomaly_signatures)
        patterns.extend(endpoint_patterns)

        # Pattern 2: Time-based patterns
        temporal_patterns = self._detect_temporal_patterns(anomaly_signatures)
        patterns.extend(temporal_patterns)

        # Pattern 3: Version-based patterns
        version_patterns = self._detect_version_patterns(anomaly_signatures)
        patterns.extend(version_patterns)

        return patterns

    def _detect_endpoint_patterns(self, anomaly_signatures) -> List[Dict[str, Any]]:
        """Detect patterns based on endpoint analysis"""
        endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'anomaly_types': set(),
            'severities': set(),
            'signatures': []
        })

        for signature in anomaly_signatures:
            endpoint_stats[signature.endpoint_pattern]['count'] += signature.occurrence_count
            endpoint_stats[signature.endpoint_pattern]['anomaly_types'].add(signature.anomaly_type)
            endpoint_stats[signature.endpoint_pattern]['severities'].add(signature.severity)
            endpoint_stats[signature.endpoint_pattern]['signatures'].append(signature)

        patterns = []
        for endpoint, stats in endpoint_stats.items():
            if stats['count'] > 10 and len(stats['signatures']) >= 2:
                patterns.append({
                    'pattern_type': 'recurring_endpoint',
                    'title': f"Recurring Issues in {endpoint}",
                    'description': f"Multiple anomaly types affecting {endpoint}",
                    'confidence': min(stats['count'] / 50.0, 1.0),
                    'occurrence_count': len(stats['signatures']),
                    'pattern_data': {
                        'endpoint': endpoint,
                        'total_occurrences': stats['count'],
                        'anomaly_types': list(stats['anomaly_types']),
                        'severities': list(stats['severities'])
                    }
                })

        return patterns

    def _detect_temporal_patterns(self, anomaly_signatures) -> List[Dict[str, Any]]:
        """Detect time-based patterns in anomalies"""
        # This would implement temporal pattern detection
        # For now, return empty list - full implementation would analyze:
        # - Hourly patterns (peak hours)
        # - Daily patterns (weekday vs weekend)
        # - Weekly patterns
        # - Seasonal patterns
        return []

    def _detect_version_patterns(self, anomaly_signatures) -> List[Dict[str, Any]]:
        """Detect version-specific patterns"""
        # Analyze version trends from AnomalyOccurrence data
        patterns = []

        for signature in anomaly_signatures:
            version_analysis = AnomalyOccurrence.version_trend_analysis(
                signature_id=signature.id,
                days=30
            )

            # Look for version regressions
            if version_analysis.get('version_regression_analysis'):
                for version_data in version_analysis['version_regression_analysis']:
                    if (version_data['change_percent'] > 200 and  # 200% increase
                        version_data['current_count'] > 5):

                        patterns.append({
                            'pattern_type': 'platform_specific',
                            'title': f"Regression in App Version {version_data['version']}",
                            'description': f"{version_data['change_percent']}% increase in {signature.anomaly_type} issues",
                            'confidence': 0.9,
                            'occurrence_count': version_data['current_count'],
                            'pattern_data': {
                                'app_version': version_data['version'],
                                'anomaly_type': signature.anomaly_type,
                                'change_percent': version_data['change_percent'],
                                'current_count': version_data['current_count'],
                                'previous_count': version_data['previous_count']
                            }
                        })

        return patterns

    def _generate_recommendations(self, clusters: List[Dict], coverage_gaps: List[Dict],
                                patterns: List[Dict]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []

        # High priority coverage gaps
        high_priority_gaps = [gap for gap in coverage_gaps if gap['priority_score'] > 7.0]
        if high_priority_gaps:
            recommendations.append({
                'type': 'urgent_action',
                'title': f"Address {len(high_priority_gaps)} High-Priority Test Coverage Gaps",
                'description': "Critical gaps that require immediate attention",
                'priority': 'critical',
                'action_items': [
                    f"Implement {gap['coverage_type']} tests for {gap['title']}"
                    for gap in high_priority_gaps[:5]
                ]
            })

        # Large clusters that need attention
        large_clusters = [cluster for cluster in clusters if cluster['size'] > 5]
        if large_clusters:
            recommendations.append({
                'type': 'systematic_improvement',
                'title': f"Systematic Issues Found in {len(large_clusters)} Areas",
                'description': "Large clusters of similar anomalies suggest systematic problems",
                'priority': 'high',
                'action_items': [
                    f"Review {cluster['analysis']['dominant_anomaly_type']} handling in "
                    f"{len(cluster['signatures'])} similar endpoints"
                    for cluster in large_clusters[:3]
                ]
            })

        # Pattern-based recommendations
        recurring_patterns = [p for p in patterns if p['occurrence_count'] > 3]
        if recurring_patterns:
            recommendations.append({
                'type': 'pattern_mitigation',
                'title': f"Address {len(recurring_patterns)} Recurring Patterns",
                'description': "Identified patterns that suggest preventable issues",
                'priority': 'medium',
                'action_items': [
                    f"Investigate pattern: {pattern['title']}"
                    for pattern in recurring_patterns[:3]
                ]
            })

        return recommendations

    def _store_analysis_results(self, results: Dict[str, Any]) -> None:
        """Store analysis results in database for future reference"""
        try:
            # Store coverage gaps
            for gap_data in results['coverage_gaps']:
                if gap_data['type'] == 'individual':
                    # Find the signature
                    signature = AnomalySignature.objects.get(id=gap_data['signature_id'])

                    # Create or update coverage gap
                    gap, created = TestCoverageGap.objects.get_or_create(
                        anomaly_signature=signature,
                        coverage_type=gap_data['coverage_type'],
                        defaults={
                            'title': gap_data['title'],
                            'description': gap_data['description'],
                            'priority': self._score_to_priority(gap_data['priority_score']),
                            'confidence_score': gap_data['confidence'],
                            'impact_score': gap_data['impact_score'],
                            'affected_endpoints': gap_data['affected_endpoints'],
                        }
                    )

                    if created:
                        logger.info(f"Created new test coverage gap: {gap.title}")

            # Store patterns
            for pattern_data in results['patterns']:
                pattern_signature = hashlib.sha256(
                    json.dumps(pattern_data['pattern_data'], sort_keys=True).encode()
                ).hexdigest()

                pattern, created = TestCoveragePattern.objects.get_or_create(
                    pattern_type=pattern_data['pattern_type'],
                    pattern_signature=pattern_signature,
                    defaults={
                        'title': pattern_data['title'],
                        'description': pattern_data['description'],
                        'confidence_score': pattern_data['confidence'],
                        'occurrence_count': pattern_data['occurrence_count'],
                        'pattern_criteria': pattern_data['pattern_data']
                    }
                )

                if not created:
                    # Update existing pattern
                    pattern.occurrence_count = pattern_data['occurrence_count']
                    pattern.last_seen = timezone.now()
                    pattern.save()

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error storing analysis results: {str(e)}")

    def _score_to_priority(self, score: float) -> str:
        """Convert numeric score to priority level"""
        if score >= 8.0:
            return 'critical'
        elif score >= 6.0:
            return 'high'
        elif score >= 4.0:
            return 'medium'
        else:
            return 'low'

    def get_cluster_by_id(self, cluster_id: int, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific cluster"""
        results = self.analyze_anomaly_patterns(days)
        for cluster in results.get('clusters', []):
            if cluster['cluster_id'] == cluster_id:
                return cluster
        return None

    def suggest_tests_for_gap(self, gap_id: str) -> List[Dict[str, Any]]:
        """Suggest specific tests for a coverage gap"""
        try:
            gap = TestCoverageGap.objects.get(id=gap_id)

            # Use test synthesizer to generate test suggestions
            from apps.ai_testing.services.test_synthesizer import TestSynthesizer
            synthesizer = TestSynthesizer()

            return synthesizer.suggest_tests_for_gap(gap)

        except TestCoverageGap.DoesNotExist:
            logger.error(f"Coverage gap not found: {gap_id}")
            return []