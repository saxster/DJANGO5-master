"""
Monitoring and analytics tests for API.

Tests health checks, metrics collection, anomaly detection, and dashboard functionality.
"""

import pytest
import json
import time
from unittest.mock import patch, Mock
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestAPIHealthCheck:
    """Test API health check functionality."""
    
    def test_health_check_endpoint_public(self, api_client):
        """Test that health check is publicly accessible."""
        response = api_client.get('/api/monitoring/health/')
        
        assert response.status_code == 200
        assert 'status' in response.data
        assert 'score' in response.data
        assert 'timestamp' in response.data
        assert 'version' in response.data
        assert 'uptime' in response.data
    
    def test_health_check_response_format(self, api_client):
        """Test health check response format."""
        response = api_client.get('/api/monitoring/health/')
        
        data = response.data
        
        # Status should be one of expected values
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']
        
        # Score should be 0-100
        assert 0 <= data['score'] <= 100
        
        # Version should be present
        assert data['version'] == 'v1'
        
        # Uptime should be a percentage string
        assert '%' in data['uptime']
    
    def test_health_check_with_poor_performance(self, api_client):
        """Test health check with poor API performance."""
        # Mock poor health score
        with patch('apps.api.monitoring.analytics.api_analytics._calculate_health_score') as mock_score:
            mock_score.return_value = 45  # Unhealthy score
            
            response = api_client.get('/api/monitoring/health/')
            
            assert response.data['status'] == 'unhealthy'
            assert response.data['score'] == 45
    
    def test_health_check_with_degraded_performance(self, api_client):
        """Test health check with degraded performance."""
        with patch('apps.api.monitoring.analytics.api_analytics._calculate_health_score') as mock_score:
            mock_score.return_value = 65  # Degraded score
            
            response = api_client.get('/api/monitoring/health/')
            
            assert response.data['status'] == 'degraded'
            assert response.data['score'] == 65


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestAPIDashboard:
    """Test API monitoring dashboard."""
    
    def test_dashboard_requires_admin(self, api_client, authenticated_client, admin_client):
        """Test that dashboard requires admin access."""
        # Unauthenticated should fail
        response = api_client.get('/api/monitoring/dashboard/')
        assert response.status_code == 401
        
        # Regular user should fail
        response = authenticated_client.get('/api/monitoring/dashboard/')
        assert response.status_code == 403
        
        # Admin should succeed
        response = admin_client.get('/api/monitoring/dashboard/')
        assert response.status_code == 200
    
    def test_dashboard_data_structure(self, admin_client):
        """Test dashboard data structure."""
        response = admin_client.get('/api/monitoring/dashboard/')
        
        data = response.data
        
        # Should have main sections
        expected_sections = [
            'real_time',
            'today',
            'last_hour',
            'last_24h',
            'last_7d',
            'top_endpoints',
            'error_rate',
            'performance',
            'users',
            'health_score'
        ]
        
        for section in expected_sections:
            assert section in data
    
    def test_dashboard_real_time_stats(self, admin_client):
        """Test real-time statistics."""
        response = admin_client.get('/api/monitoring/dashboard/')
        
        real_time = response.data['real_time']
        
        assert 'requests_per_minute' in real_time
        assert 'active_users' in real_time
        assert 'avg_response_time' in real_time
        assert 'error_rate' in real_time
        assert 'top_endpoint' in real_time
        
        # Values should be reasonable
        assert real_time['requests_per_minute'] >= 0
        assert real_time['active_users'] >= 0
        assert real_time['avg_response_time'] >= 0
        assert 0 <= real_time['error_rate'] <= 1
    
    def test_dashboard_performance_stats(self, admin_client):
        """Test performance statistics."""
        response = admin_client.get('/api/monitoring/dashboard/')
        
        performance = response.data['performance']
        
        assert 'p50_response_time' in performance
        assert 'p95_response_time' in performance
        assert 'p99_response_time' in performance
        assert 'slowest_endpoints' in performance
        assert 'fastest_endpoints' in performance
        
        # Response times should be in logical order
        assert performance['p50_response_time'] <= performance['p95_response_time']
        assert performance['p95_response_time'] <= performance['p99_response_time']


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestAPIMetrics:
    """Test API metrics collection."""
    
    def test_metrics_endpoint_access(self, admin_client):
        """Test metrics endpoint access."""
        response = admin_client.get('/api/monitoring/metrics/')
        
        assert response.status_code == 200
        assert isinstance(response.data, dict)
    
    def test_metrics_by_type(self, admin_client):
        """Test different metric types."""
        # Test summary metrics
        response = admin_client.get('/api/monitoring/metrics/?type=summary')
        assert response.status_code == 200
        
        # Test endpoint metrics
        response = admin_client.get('/api/monitoring/metrics/?type=endpoints')
        assert response.status_code == 200
        
        # Test user metrics
        response = admin_client.get('/api/monitoring/metrics/?type=users')
        assert response.status_code == 200
        
        # Test performance metrics
        response = admin_client.get('/api/monitoring/metrics/?type=performance')
        assert response.status_code == 200
    
    def test_metrics_time_filtering(self, admin_client):
        """Test metrics time filtering."""
        now = timezone.now()
        start_date = (now - timedelta(days=1)).isoformat()
        end_date = now.isoformat()
        
        response = admin_client.get('/api/monitoring/metrics/', {
            'type': 'performance',
            'start_date': start_date,
            'end_date': end_date
        })
        
        assert response.status_code == 200
        assert isinstance(response.data, dict)
    
    def test_user_specific_metrics(self, admin_client, test_user):
        """Test user-specific metrics."""
        response = admin_client.get('/api/monitoring/metrics/', {
            'type': 'users',
            'user_id': test_user.id
        })
        
        assert response.status_code == 200
        
        if response.data:
            user_metrics = response.data
            expected_fields = [
                'total_requests',
                'endpoints_accessed',
                'avg_response_time',
                'error_count'
            ]
            
            for field in expected_fields:
                assert field in user_metrics


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestAnomalyDetection:
    """Test API anomaly detection."""
    
    def test_anomalies_endpoint(self, admin_client):
        """Test anomalies endpoint."""
        response = admin_client.get('/api/monitoring/anomalies/')
        
        assert response.status_code == 200
        assert 'anomalies' in response.data
        assert 'count' in response.data
        assert 'period_hours' in response.data
        
        assert isinstance(response.data['anomalies'], list)
        assert response.data['count'] >= 0
        assert response.data['period_hours'] == 24  # Default
    
    def test_anomalies_time_filtering(self, admin_client):
        """Test anomaly time filtering."""
        # Test different time periods
        for hours in [1, 6, 12, 24, 48]:
            response = admin_client.get('/api/monitoring/anomalies/', {'hours': hours})
            
            assert response.status_code == 200
            assert response.data['period_hours'] == hours
    
    @patch('apps.api.monitoring.analytics.cache')
    def test_anomaly_detection_logic(self, mock_cache, admin_client):
        """Test anomaly detection logic."""
        # Mock anomalies in cache
        mock_anomalies = [
            {
                'type': 'slow_response',
                'severity': 'warning',
                'message': 'Response time 2.5s is 3x slower than average',
                'timestamp': timezone.now().isoformat(),
                'endpoint': '/api/v1/people/'
            },
            {
                'type': 'high_error_rate',
                'severity': 'critical',
                'message': 'Error rate is 15.0%',
                'timestamp': timezone.now().isoformat(),
                'endpoint': '/api/v1/bulk_update/'
            }
        ]
        
        mock_cache.get.return_value = mock_anomalies
        
        response = admin_client.get('/api/monitoring/anomalies/')
        
        assert response.status_code == 200
        anomalies = response.data['anomalies']
        
        assert len(anomalies) == 2
        
        # Check anomaly structure
        for anomaly in anomalies:
            assert 'type' in anomaly
            assert 'severity' in anomaly
            assert 'message' in anomaly
            assert 'timestamp' in anomaly
            assert 'endpoint' in anomaly
            assert anomaly['severity'] in ['warning', 'critical']


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestAPIRecommendations:
    """Test API optimization recommendations."""
    
    def test_recommendations_endpoint(self, admin_client):
        """Test recommendations endpoint."""
        response = admin_client.get('/api/monitoring/recommendations/')
        
        assert response.status_code == 200
        assert 'recommendations' in response.data
        assert 'generated_at' in response.data
        
        assert isinstance(response.data['recommendations'], list)
    
    @patch('apps.api.monitoring.analytics.api_analytics._get_slowest_endpoints')
    @patch('apps.api.monitoring.analytics.api_analytics._get_error_rate')
    def test_performance_recommendations(self, mock_error_rate, mock_slow_endpoints, admin_client):
        """Test performance-based recommendations."""
        # Mock slow endpoints
        mock_slow_endpoints.return_value = [
            {
                'endpoint': '/api/v1/people/',
                'avg_time': 2.5,
                'count': 1000
            }
        ]
        
        # Mock low error rate
        mock_error_rate.return_value = 0.02  # 2%
        
        response = admin_client.get('/api/monitoring/recommendations/')
        
        recommendations = response.data['recommendations']
        
        # Should recommend optimizing slow endpoint
        slow_endpoint_rec = next(
            (r for r in recommendations if 'optimize endpoint' in r['message'].lower()),
            None
        )
        
        if slow_endpoint_rec:
            assert slow_endpoint_rec['type'] == 'performance'
            assert slow_endpoint_rec['priority'] == 'high'
            assert '/api/v1/people/' in slow_endpoint_rec['message']
    
    @patch('apps.api.monitoring.analytics.api_analytics._get_error_rate')
    def test_reliability_recommendations(self, mock_error_rate, admin_client):
        """Test reliability-based recommendations."""
        # Mock high error rate
        mock_error_rate.return_value = 0.08  # 8%
        
        response = admin_client.get('/api/monitoring/recommendations/')
        
        recommendations = response.data['recommendations']
        
        # Should recommend fixing errors
        error_rec = next(
            (r for r in recommendations if 'error rate' in r['message'].lower()),
            None
        )
        
        if error_rec:
            assert error_rec['type'] == 'reliability'
            assert error_rec['priority'] == 'critical'
    
    @patch('apps.api.monitoring.analytics.api_analytics._get_top_endpoints')
    def test_caching_recommendations(self, mock_top_endpoints, admin_client):
        """Test caching recommendations."""
        # Mock endpoints that could benefit from caching
        mock_top_endpoints.return_value = [
            {
                'endpoint': '/api/v1/people/:GET',
                'avg_time': 0.8,
                'count': 5000
            }
        ]
        
        response = admin_client.get('/api/monitoring/recommendations/')
        
        recommendations = response.data['recommendations']
        
        # Should recommend caching
        cache_rec = next(
            (r for r in recommendations if 'caching' in r['message'].lower()),
            None
        )
        
        if cache_rec:
            assert cache_rec['type'] == 'caching'
            assert cache_rec['priority'] == 'medium'


@pytest.mark.integration
@pytest.mark.monitoring
@pytest.mark.api
class TestMetricsCollection:
    """Test automatic metrics collection."""
    
    @patch('apps.api.monitoring.analytics.api_analytics.record_request')
    def test_metrics_recorded_on_request(self, mock_record, authenticated_client, people_factory):
        """Test that metrics are recorded on API requests."""
        people_factory.create_batch(5)
        
        response = authenticated_client.get('/api/v1/people/')
        
        assert response.status_code == 200
        
        # Should record metrics
        mock_record.assert_called_once()
        
        # Check call arguments
        call_args = mock_record.call_args[0]
        request, response_obj, execution_time = call_args
        
        assert request.path == '/api/v1/people/'
        assert request.method == 'GET'
        assert execution_time >= 0
    
    def test_metrics_in_response_headers(self, authenticated_client, people_factory):
        """Test that metrics are included in response headers."""
        people_factory.create_batch(5)
        
        response = authenticated_client.get('/api/v1/people/')
        
        assert response.status_code == 200
        
        # Should have performance headers
        assert 'X-Response-Time' in response
        assert 'X-API-Version' in response
        
        # Response time should be valid
        response_time = response['X-Response-Time']
        assert response_time.endswith('s')
        time_value = float(response_time[:-1])
        assert time_value >= 0
    
    def test_error_metrics_collection(self, authenticated_client):
        """Test that error metrics are collected."""
        with patch('apps.api.monitoring.analytics.api_analytics.record_request') as mock_record:
            # Make request that causes 404
            response = authenticated_client.get('/api/v1/people/99999/')
            
            assert response.status_code == 404
            
            # Should still record metrics
            mock_record.assert_called_once()
            
            # Check error recording
            call_args = mock_record.call_args[0]
            request, response_obj, execution_time = call_args
            
            assert response_obj.status_code == 404
    
    def test_slow_request_logging(self, authenticated_client):
        """Test that slow requests are logged."""
        with patch('time.time') as mock_time:
            # Mock slow request (2 seconds)
            mock_time.side_effect = [1000.0, 1002.0]
            
            with patch('apps.api.middleware.logger') as mock_logger:
                response = authenticated_client.get('/api/v1/people/')
                
                # Should log slow request
                mock_logger.warning.assert_called_once()
                log_message = mock_logger.warning.call_args[0][0]
                assert 'slow api request' in log_message.lower()
                assert '2.000s' in log_message


@pytest.mark.integration
@pytest.mark.e2e
@pytest.mark.api
class TestEndToEndAPIWorkflows:
    """Test complete end-to-end API workflows."""
    
    def test_complete_user_journey(self, api_client):
        """Test complete user journey from authentication to data operations."""
        # 1. User authentication
        auth_response = api_client.post('/api/v1/auth/token/', {
            'username': 'testuser',
            'password': 'TestPassword123!'
        })
        
        if auth_response.status_code == 200:
            token = auth_response.data['access']
            api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            
            # 2. Get initial data
            list_response = api_client.get('/api/v1/people/')
            initial_count = len(list_response.data['results']) if list_response.status_code == 200 else 0
            
            # 3. Create new resource
            create_response = api_client.post('/api/v1/people/', {
                'first_name': 'E2E',
                'last_name': 'Test',
                'email': 'e2e@example.com',
                'employee_code': 'E2E001'
            }, format='json')
            
            if create_response.status_code == 201:
                person_id = create_response.data['id']
                
                # 4. Verify creation
                list_response = api_client.get('/api/v1/people/')
                if list_response.status_code == 200:
                    assert len(list_response.data['results']) == initial_count + 1
                
                # 5. Update resource
                update_response = api_client.patch(f'/api/v1/people/{person_id}/', {
                    'first_name': 'Updated E2E'
                }, format='json')
                
                if update_response.status_code == 200:
                    assert update_response.data['first_name'] == 'Updated E2E'
                
                # 6. Delete resource
                delete_response = api_client.delete(f'/api/v1/people/{person_id}/')
                assert delete_response.status_code == 204
                
                # 7. Verify deletion
                get_response = api_client.get(f'/api/v1/people/{person_id}/')
                assert get_response.status_code == 404
    
    def test_bulk_operations_workflow(self, authenticated_client):
        """Test bulk operations workflow."""
        # 1. Bulk create
        create_data = [
            {
                'first_name': f'Bulk{i}',
                'last_name': 'Test',
                'email': f'bulk{i}@example.com',
                'employee_code': f'BULK{i:03d}'
            }
            for i in range(5)
        ]
        
        bulk_create_response = authenticated_client.post(
            '/api/v1/people/bulk_create/',
            create_data,
            format='json'
        )
        
        if bulk_create_response.status_code == 201:
            created_people = bulk_create_response.data
            ids = [person['id'] for person in created_people]
            
            # 2. Bulk update
            bulk_update_response = authenticated_client.put('/api/v1/people/bulk_update/', {
                'ids': ids,
                'updates': {'last_name': 'BulkUpdated'}
            }, format='json')
            
            if bulk_update_response.status_code == 200:
                # Verify updates
                for person in bulk_update_response.data:
                    assert person['last_name'] == 'BulkUpdated'
            
            # 3. Bulk delete
            bulk_delete_response = authenticated_client.delete('/api/v1/people/bulk_delete/', {
                'ids': ids
            }, format='json')
            
            assert bulk_delete_response.status_code == 204
            
            # 4. Verify deletions
            from apps.peoples.models import People
            remaining = People.objects.filter(id__in=ids).count()
            assert remaining == 0
    
    def test_graphql_workflow(self, graphql_client):
        """Test GraphQL workflow."""
        # 1. Query existing data
        list_query = """
        query {
            allPeople {
                edges {
                    node {
                        id
                        firstName
                    }
                }
            }
        }
        """
        
        list_result = graphql_client.execute(list_query)
        assert 'errors' not in list_result
        
        # 2. Create via mutation
        create_mutation = """
        mutation {
            createPerson(
                firstName: "GraphQL E2E"
                lastName: "Test"
                email: "graphql-e2e@example.com"
                employeeCode: "GQL001"
            ) {
                person {
                    id
                    firstName
                }
                success
            }
        }
        """
        
        create_result = graphql_client.execute(create_mutation)
        
        if 'errors' not in create_result and create_result['data']['createPerson']['success']:
            person_id = create_result['data']['createPerson']['person']['id']
            
            # 3. Query specific person
            detail_query = f"""
            query {{
                person(id: {person_id}) {{
                    id
                    firstName
                    lastName
                }}
            }}
            """
            
            detail_result = graphql_client.execute(detail_query)
            assert 'errors' not in detail_result
            assert detail_result['data']['person']['firstName'] == 'GraphQL E2E'
            
            # 4. Update via mutation
            update_mutation = f"""
            mutation {{
                updatePerson(
                    id: {person_id}
                    firstName: "Updated GraphQL E2E"
                ) {{
                    person {{
                        firstName
                    }}
                    success
                }}
            }}
            """
            
            update_result = graphql_client.execute(update_mutation)
            
            if 'errors' not in update_result and update_result['data']['updatePerson']['success']:
                assert update_result['data']['updatePerson']['person']['firstName'] == 'Updated GraphQL E2E'
            
            # 5. Delete via mutation
            delete_mutation = f"""
            mutation {{
                deletePerson(id: {person_id}) {{
                    success
                }}
            }}
            """
            
            delete_result = graphql_client.execute(delete_mutation)
            assert 'errors' not in delete_result
            assert delete_result['data']['deletePerson']['success'] is True
    
    def test_mobile_sync_workflow(self, mobile_client, people_factory):
        """Test mobile sync workflow."""
        # Create some server data
        people_factory.create_batch(3)
        
        # 1. Initial sync
        sync_response = mobile_client.post('/api/v1/mobile/sync/', {
            'last_sync': None,
            'client_id': 'e2e-device',
            'changes': {'create': [], 'update': [], 'delete': []}
        }, format='json')
        
        assert sync_response.status_code == 200
        
        initial_data = sync_response.data['data']
        last_sync = sync_response.data['last_sync']
        
        # Should receive server data
        assert 'people' in initial_data
        assert len(initial_data['people']) >= 3
        
        # 2. Sync with client changes
        sync_with_changes = mobile_client.post('/api/v1/mobile/sync/', {
            'last_sync': last_sync,
            'client_id': 'e2e-device',
            'changes': {
                'create': [{
                    'model': 'people',
                    'temp_id': 'temp_1',
                    'data': {
                        'first_name': 'Mobile',
                        'last_name': 'User',
                        'email': 'mobile@example.com',
                        'employee_code': 'MOB001'
                    }
                }],
                'update': [],
                'delete': []
            }
        }, format='json')
        
        assert sync_with_changes.status_code == 200
        
        # Should create the person and return mapping
        created = sync_with_changes.data.get('created', [])
        assert len(created) == 1
        assert created[0]['temp_id'] == 'temp_1'
        assert 'real_id' in created[0]
    
    def test_error_handling_workflow(self, authenticated_client):
        """Test error handling throughout API workflow."""
        # 1. Test validation errors
        invalid_create = authenticated_client.post('/api/v1/people/', {
            'first_name': 'Invalid',
            # Missing required fields
        }, format='json')
        
        assert invalid_create.status_code == 400
        assert 'email' in invalid_create.data
        
        # 2. Test not found errors
        not_found = authenticated_client.get('/api/v1/people/99999/')
        assert not_found.status_code == 404
        
        # 3. Test method not allowed
        invalid_method = authenticated_client.put('/api/monitoring/health/')
        assert invalid_method.status_code in [405, 404]
        
        # 4. Test permission errors (if applicable)
        # This would depend on specific permission setup
        
        # All errors should return proper JSON responses
        for response in [invalid_create, not_found]:
            if hasattr(response, 'data'):
                assert isinstance(response.data, (dict, list))
    
    def test_performance_monitoring_workflow(self, authenticated_client, admin_client, people_factory):
        """Test that performance monitoring works throughout workflow."""
        # Create test data
        people_factory.create_batch(10)
        
        # 1. Make several API calls
        responses = []
        for _ in range(5):
            response = authenticated_client.get('/api/v1/people/')
            responses.append(response)
            time.sleep(0.1)  # Small delay between requests
        
        # All should succeed and have timing headers
        for response in responses:
            assert response.status_code == 200
            assert 'X-Response-Time' in response
        
        # 2. Check monitoring dashboard (admin only)
        dashboard_response = admin_client.get('/api/monitoring/dashboard/')
        
        if dashboard_response.status_code == 200:
            dashboard_data = dashboard_response.data
            
            # Should show some activity
            real_time = dashboard_data['real_time']
            assert real_time['requests_per_minute'] >= 0
            
            # Health score should be reasonable
            assert dashboard_data['health_score'] >= 0