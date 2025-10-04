"""
Redis Sentinel health checks and cluster monitoring.
Provides comprehensive monitoring for Redis Sentinel high availability setup.
"""

import time
import logging
from typing import Dict, List, Any
from .utils import timeout_check, format_check_result

logger = logging.getLogger(__name__)

__all__ = [
    'check_sentinel_cluster_health',
    'check_master_replica_status',
    'check_sentinel_failover_capability',
    'check_sentinel_quorum',
]


@timeout_check(timeout_seconds=15)
def check_sentinel_cluster_health() -> Dict[str, Any]:
    """
    Check overall Redis Sentinel cluster health.

    Returns:
        Health check result with Sentinel cluster status
    """
    start_time = time.time()

    try:
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
        import redis.sentinel

        sentinel_settings = get_sentinel_settings()

        # Create Sentinel connection
        sentinel = redis.sentinel.Sentinel(
            sentinel_settings['sentinels'],
            sentinel_kwargs=sentinel_settings['sentinel_kwargs']
        )

        cluster_info = {
            'total_sentinels': len(sentinel_settings['sentinels']),
            'connected_sentinels': 0,
            'master_info': None,
            'replica_count': 0,
            'quorum_status': 'unknown',
            'failover_capability': 'unknown'
        }

        # Test each Sentinel node
        sentinel_statuses = []
        for i, (host, port) in enumerate(sentinel_settings['sentinels'], 1):
            try:
                sentinel_client = redis.Redis(
                    host=host,
                    port=port,
                    password=sentinel_settings['sentinel_kwargs'].get('password'),
                    socket_timeout=5
                )

                # Test connection
                sentinel_client.ping()

                # Get Sentinel info
                info = sentinel_client.info()

                sentinel_status = {
                    'node': i,
                    'host': host,
                    'port': port,
                    'status': 'connected',
                    'uptime_seconds': info.get('uptime_in_seconds', 0),
                    'sentinel_masters': info.get('sentinel_masters', 0),
                    'sentinel_running_scripts': info.get('sentinel_running_scripts', 0)
                }

                cluster_info['connected_sentinels'] += 1

            except Exception as e:
                sentinel_status = {
                    'node': i,
                    'host': host,
                    'port': port,
                    'status': 'failed',
                    'error': str(e)
                }

            sentinel_statuses.append(sentinel_status)

        # Check master discovery
        try:
            master = sentinel.master_for(
                sentinel_settings['service_name'],
                **sentinel_settings['redis_kwargs']
            )

            master.ping()

            master_info = sentinel.sentinel_masters()[0]  # Get master info from Sentinel
            cluster_info['master_info'] = {
                'name': master_info.get('name'),
                'ip': master_info.get('ip'),
                'port': master_info.get('port'),
                'status': master_info.get('flags'),
                'last_ping_reply': master_info.get('last-ping-reply'),
                'num_slaves': master_info.get('num-slaves', 0)
            }

            cluster_info['replica_count'] = master_info.get('num-slaves', 0)

        except Exception as e:
            logger.error(f"Master discovery failed: {e}")

        # Determine quorum status
        if cluster_info['connected_sentinels'] >= 2:  # Majority of 3
            cluster_info['quorum_status'] = 'healthy'
            cluster_info['failover_capability'] = 'available'
        else:
            cluster_info['quorum_status'] = 'insufficient'
            cluster_info['failover_capability'] = 'unavailable'

        # Determine overall status
        status = "healthy"
        if cluster_info['connected_sentinels'] < 2:
            status = "error"
            message = f"Sentinel quorum lost: {cluster_info['connected_sentinels']}/3 nodes"
        elif cluster_info['master_info'] is None:
            status = "error"
            message = "Master discovery failed"
        elif cluster_info['replica_count'] == 0:
            status = "degraded"
            message = "No replicas configured - no failover targets"
        else:
            status = "healthy"
            message = f"Sentinel cluster healthy: {cluster_info['connected_sentinels']}/3 nodes"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details={
                **cluster_info,
                'sentinel_nodes': sentinel_statuses
            },
            duration_ms=duration,
        )

    except ImportError:
        return format_check_result(
            status="degraded",
            message="Redis Sentinel not available - using standalone Redis",
            details={"note": "Sentinel support not configured"},
            duration_ms=(time.time() - start_time) * 1000,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Sentinel cluster health check error: {e}")
        return format_check_result(
            status="error",
            message=f"Sentinel health check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=10)
def check_master_replica_status() -> Dict[str, Any]:
    """
    Check Redis master and replica status through Sentinel.

    Returns:
        Health check result with replication status
    """
    start_time = time.time()

    try:
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
        import redis.sentinel

        sentinel_settings = get_sentinel_settings()

        # Create Sentinel connection
        sentinel = redis.sentinel.Sentinel(
            sentinel_settings['sentinels'],
            sentinel_kwargs=sentinel_settings['sentinel_kwargs']
        )

        # Get master and replica info
        master_info = sentinel.sentinel_masters()[0]
        replica_info = sentinel.sentinel_slaves(sentinel_settings['service_name'])

        replication_status = {
            'master': {
                'name': master_info.get('name'),
                'ip': master_info.get('ip'),
                'port': master_info.get('port'),
                'status': master_info.get('flags'),
                'last_ping_reply': master_info.get('last-ping-reply'),
                'info_refresh': master_info.get('info-refresh'),
                'role_reported': master_info.get('role-reported'),
                'num_slaves': master_info.get('num-slaves', 0)
            },
            'replicas': []
        }

        # Check each replica
        for replica in replica_info:
            replica_status = {
                'name': replica.get('name'),
                'ip': replica.get('ip'),
                'port': replica.get('port'),
                'status': replica.get('flags'),
                'last_ping_reply': replica.get('last-ping-reply'),
                'master_link_down_time': replica.get('master-link-down-time'),
                'replica_priority': replica.get('slave-priority'),
                'replica_repl_offset': replica.get('slave-repl-offset')
            }
            replication_status['replicas'].append(replica_status)

        # Analyze replication health
        issues = []

        # Check master status
        if 'down' in master_info.get('flags', '').lower():
            issues.append("Master is down")

        # Check replica status
        healthy_replicas = 0
        for replica in replica_info:
            if 'down' not in replica.get('flags', '').lower():
                healthy_replicas += 1
            else:
                issues.append(f"Replica {replica.get('ip')}:{replica.get('port')} is down")

        # Determine status
        if issues:
            if 'Master is down' in str(issues):
                status = "error"
                message = f"Master failure detected: {', '.join(issues)}"
            else:
                status = "degraded"
                message = f"Replication issues: {', '.join(issues)}"
        else:
            status = "healthy"
            message = f"Replication healthy: master + {healthy_replicas} replica(s)"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details=replication_status,
            duration_ms=duration,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Master/replica status check error: {e}")
        return format_check_result(
            status="error",
            message=f"Replication status check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=5)
def check_sentinel_quorum() -> Dict[str, Any]:
    """
    Check if Sentinel cluster has sufficient quorum for failover decisions.

    Returns:
        Health check result with quorum status
    """
    start_time = time.time()

    try:
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
        import redis.sentinel

        sentinel_settings = get_sentinel_settings()

        # Test each Sentinel for quorum information
        quorum_info = {
            'configured_quorum': 2,  # From configuration
            'total_sentinels': len(sentinel_settings['sentinels']),
            'available_sentinels': 0,
            'quorum_met': False,
            'sentinel_responses': []
        }

        for i, (host, port) in enumerate(sentinel_settings['sentinels'], 1):
            try:
                sentinel_client = redis.Redis(
                    host=host,
                    port=port,
                    password=sentinel_settings['sentinel_kwargs'].get('password'),
                    socket_timeout=3
                )

                # Test Sentinel response
                pong = sentinel_client.ping()

                if pong:
                    quorum_info['available_sentinels'] += 1
                    quorum_info['sentinel_responses'].append({
                        'node': i,
                        'host': host,
                        'port': port,
                        'response': 'ok'
                    })

            except Exception as e:
                quorum_info['sentinel_responses'].append({
                    'node': i,
                    'host': host,
                    'port': port,
                    'response': 'failed',
                    'error': str(e)
                })

        # Check if quorum is met
        quorum_info['quorum_met'] = quorum_info['available_sentinels'] >= quorum_info['configured_quorum']

        # Determine status
        if quorum_info['quorum_met']:
            status = "healthy"
            message = f"Sentinel quorum healthy: {quorum_info['available_sentinels']}/{quorum_info['total_sentinels']}"
        else:
            status = "error"
            message = f"Sentinel quorum lost: {quorum_info['available_sentinels']}/{quorum_info['total_sentinels']} (need {quorum_info['configured_quorum']})"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details=quorum_info,
            duration_ms=duration,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Sentinel quorum check error: {e}")
        return format_check_result(
            status="error",
            message=f"Quorum check failed: {str(e)}",
            duration_ms=duration,
        )


@timeout_check(timeout_seconds=10)
def check_sentinel_failover_capability() -> Dict[str, Any]:
    """
    Test Sentinel's ability to perform failover (simulation).

    Returns:
        Health check result with failover capability assessment
    """
    start_time = time.time()

    try:
        from intelliwiz_config.settings.redis_sentinel import get_sentinel_settings
        import redis.sentinel

        sentinel_settings = get_sentinel_settings()

        # Create Sentinel connection
        sentinel = redis.sentinel.Sentinel(
            sentinel_settings['sentinels'],
            sentinel_kwargs=sentinel_settings['sentinel_kwargs']
        )

        failover_status = {
            'can_discover_master': False,
            'can_discover_replicas': False,
            'sufficient_replicas': False,
            'quorum_available': False,
            'failover_ready': False
        }

        # Test master discovery
        try:
            master = sentinel.master_for(
                sentinel_settings['service_name'],
                **sentinel_settings['redis_kwargs']
            )
            master.ping()
            failover_status['can_discover_master'] = True
        except Exception as e:
            logger.warning(f"Master discovery failed: {e}")

        # Test replica discovery
        try:
            replicas = sentinel.slave_for(
                sentinel_settings['service_name'],
                **sentinel_settings['redis_kwargs']
            )
            if replicas:
                replicas.ping()
                failover_status['can_discover_replicas'] = True
        except Exception as e:
            logger.warning(f"Replica discovery failed: {e}")

        # Check if we have sufficient replicas for failover
        try:
            replica_list = sentinel.sentinel_slaves(sentinel_settings['service_name'])
            healthy_replicas = len([r for r in replica_list if 'down' not in r.get('flags', '')])
            failover_status['sufficient_replicas'] = healthy_replicas > 0
        except Exception as e:
            logger.warning(f"Replica count check failed: {e}")

        # Check quorum (from previous check)
        quorum_result = check_sentinel_quorum()
        failover_status['quorum_available'] = quorum_result['status'] == 'healthy'

        # Overall failover readiness
        failover_status['failover_ready'] = all([
            failover_status['can_discover_master'],
            failover_status['can_discover_replicas'],
            failover_status['sufficient_replicas'],
            failover_status['quorum_available']
        ])

        # Determine status
        if failover_status['failover_ready']:
            status = "healthy"
            message = "Sentinel failover capability ready"
        elif not failover_status['quorum_available']:
            status = "error"
            message = "Sentinel quorum insufficient for failover"
        elif not failover_status['sufficient_replicas']:
            status = "degraded"
            message = "No healthy replicas available for failover"
        else:
            status = "degraded"
            message = "Failover capability degraded"

        duration = (time.time() - start_time) * 1000

        return format_check_result(
            status=status,
            message=message,
            details=failover_status,
            duration_ms=duration,
        )

    except ImportError:
        return format_check_result(
            status="degraded",
            message="Sentinel not configured - using standalone Redis",
            details={"note": "High availability not available"},
            duration_ms=(time.time() - start_time) * 1000,
        )

    except Exception as e:
        duration = (time.time() - start_time) * 1000
        logger.error(f"Sentinel failover capability check error: {e}")
        return format_check_result(
            status="error",
            message=f"Failover capability check failed: {str(e)}",
            duration_ms=duration,
        )