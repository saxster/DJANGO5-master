# Monitoring Metrics Reference

Complete reference of all metrics collected by the monitoring system.

## GraphQL Metrics

### Query Validation Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `graphql_query_validation` | Counter | `status` | Total query validations (accepted/rejected) |
| `graphql_query_complexity` | Histogram | - | Query complexity distribution |
| `graphql_query_depth` | Histogram | - | Query depth distribution |
| `graphql_field_count` | Histogram | - | Field count distribution |
| `graphql_validation_time` | Histogram | - | Validation time in milliseconds |
| `graphql_rejection` | Counter | `rejection_reason` | Rejections by reason |

**Rejection Reasons**:
- `complexity_exceeded` - Query complexity > 1000 (production)
- `depth_exceeded` - Query depth > 10 (production)
- `timeout` - Validation timeout exceeded
- `invalid_syntax` - Invalid GraphQL syntax

**Example Prometheus Queries**:
```promql
# Query rejection rate
rate(graphql_query_validation{status="rejected"}[5m]) / rate(graphql_query_validation[5m])

# P95 query complexity
histogram_quantile(0.95, sum(rate(graphql_query_complexity_bucket[5m])) by (le))

# Rejection reasons breakdown
sum(rate(graphql_rejection[5m])) by (rejection_reason)
```

## WebSocket Metrics

### Connection Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `websocket_connection_attempt` | Counter | `accepted`, `user_type` | Connection attempts |
| `websocket_connections_active` | Gauge | `user_type` | Currently active connections |
| `websocket_connection_duration` | Histogram | `user_type` | Connection duration in seconds |
| `websocket_messages_sent` | Counter | `user_type` | Messages sent to clients |
| `websocket_messages_received` | Counter | `user_type` | Messages received from clients |
| `websocket_throttle_hit` | Counter | `user_type` | Throttle limit hits |

**User Types**:
- `anonymous` - Unauthenticated connections
- `authenticated` - Authenticated regular users
- `staff` - Staff/admin users

**Connection Rejection Reasons**:
- `rate_limit_exceeded` - Connection limit per user/IP exceeded
- `auth_failed` - Authentication failed
- `invalid_origin` - Origin not in whitelist
- `capacity_full` - Server at capacity

**Example Prometheus Queries**:
```promql
# Active connections by user type
sum(websocket_connections_active) by (user_type)

# Connection rejection rate
rate(websocket_connection_attempt{accepted="false"}[5m]) / rate(websocket_connection_attempt[5m])

# Average connection duration
avg(websocket_connection_duration_seconds)

# Messages per second
rate(websocket_messages_sent_total[5m]) + rate(websocket_messages_received_total[5m])
```

## Performance Metrics

### Request Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `request_duration` | Histogram | `method`, `endpoint`, `status` | Request duration in milliseconds |
| `request_count` | Counter | `method`, `endpoint`, `status` | Total requests |
| `request_size` | Histogram | `method`, `endpoint` | Request size in bytes |
| `response_size` | Histogram | `method`, `endpoint` | Response size in bytes |

### Database Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `database_query_time` | Histogram | `operation` | Query execution time |
| `database_query_count` | Counter | `operation` | Total queries executed |
| `database_connection_pool_size` | Gauge | - | Active DB connections |
| `database_slow_queries` | Counter | - | Slow queries (>1s) |

**Operations**:
- `SELECT`, `INSERT`, `UPDATE`, `DELETE`

### Cache Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `cache_hits` | Counter | `cache_name` | Cache hits |
| `cache_misses` | Counter | `cache_name` | Cache misses |
| `cache_hit_rate` | Gauge | `cache_name` | Hit rate (0-1) |
| `cache_operation_time` | Histogram | `operation` | Cache operation duration |

**Example Prometheus Queries**:
```promql
# P95 request duration
histogram_quantile(0.95, sum(rate(request_duration_bucket[5m])) by (le, endpoint))

# Error rate
rate(request_count{status=~"5.."}[5m]) / rate(request_count[5m])

# Cache hit rate
sum(rate(cache_hits_total[5m])) / (sum(rate(cache_hits_total[5m])) + sum(rate(cache_misses_total[5m])))

# Slow query rate
rate(database_slow_queries_total[5m])
```

## Anomaly Detection Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `anomaly_detected` | Counter | `metric_name`, `detection_method`, `severity` | Anomalies detected |
| `anomaly_severity` | Gauge | `metric_name` | Current anomaly severity |
| `anomaly_false_positive` | Counter | `metric_name` | False positive anomalies |

**Detection Methods**:
- `z_score` - Z-score (standard deviation) method
- `iqr` - Interquartile range method
- `spike` - Sudden spike/drop detection

**Severity Levels**:
- `low` - Minor deviation (1.5-2x threshold)
- `medium` - Moderate deviation (2-3x threshold)
- `high` - Significant deviation (3-5x threshold)
- `critical` - Extreme deviation (>5x threshold)

**Example Prometheus Queries**:
```promql
# Anomalies by severity
sum(rate(anomaly_detected[5m])) by (severity)

# Critical anomalies
sum(rate(anomaly_detected{severity="critical"}[5m]))

# Anomalies by detection method
sum(rate(anomaly_detected[5m])) by (detection_method)
```

## Security Metrics

### Threat Detection

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `security_event` | Counter | `threat_type`, `severity` | Security events detected |
| `ip_reputation_threat_score` | Gauge | `ip_address` | IP threat score (0-200) |
| `ip_blocked` | Counter | `reason` | IPs blocked |
| `attack_pattern_detected` | Counter | `attack_type` | Attack patterns detected |

**Threat Types**:
- `graphql_bomb` - GraphQL complexity bomb attack
- `ws_flood` - WebSocket connection flood
- `bruteforce` - Brute force authentication
- `dos` - Denial of service attempt

**Attack Types**:
- `complexity_bomb` - High complexity GraphQL queries
- `deep_nesting` - Deep nesting attack
- `alias_overload` - Alias overload attack
- `connection_flood` - WebSocket flood

**Example Prometheus Queries**:
```promql
# Security events by type
sum(rate(security_event_total[5m])) by (threat_type)

# IPs with high threat score
count(ip_reputation_threat_score > 100)

# Attack detection rate
sum(rate(attack_pattern_detected[5m])) by (attack_type)

# Blocked IPs trend
increase(ip_blocked_total[1h])
```

## Alert Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `alert_created` | Counter | `severity`, `source` | Alerts created |
| `alert_suppressed` | Counter | `reason` | Alerts suppressed |
| `alert_grouped` | Counter | `group` | Alerts grouped |
| `alert_sent` | Counter | `destination` | Alerts sent externally |

**Alert Sources**:
- `graphql_monitoring`
- `websocket_monitoring`
- `anomaly_detection`
- `performance_analysis`
- `security_intelligence`

**Suppression Reasons**:
- `duplicate` - Duplicate within dedup window (5 min)
- `storm` - Alert storm prevention triggered
- `low_priority` - Below threshold for alerting

**Example Prometheus Queries**:
```promql
# Alert rate by severity
sum(rate(alert_created[5m])) by (severity)

# Suppression rate
rate(alert_suppressed_total[5m]) / rate(alert_created_total[5m])

# Alerts by source
sum(rate(alert_created[5m])) by (source)
```

## Performance Baseline Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `performance_baseline` | Gauge | `metric_name`, `percentile` | Performance baseline values |
| `performance_regression` | Counter | `metric_name` | Regressions detected |
| `performance_improvement` | Counter | `metric_name` | Improvements detected |

**Percentiles Tracked**:
- `p50` - Median (50th percentile)
- `p95` - 95th percentile
- `p99` - 99th percentile

**Example Prometheus Queries**:
```promql
# Regression detection
(request_duration_p95 - request_duration_baseline_p95) / request_duration_baseline_p95 > 0.20

# Performance improvement rate
rate(performance_improvement_total[1h])

# Current vs baseline comparison
request_duration_p95 / request_duration_baseline_p95
```

## System Health Metrics

| Metric Name | Type | Labels | Description |
|-------------|------|--------|-------------|
| `monitoring_system_up` | Gauge | - | Monitoring system health (0/1) |
| `metrics_collection_time` | Histogram | `collector` | Time to collect metrics |
| `metrics_export_time` | Histogram | - | Time to export to Prometheus |
| `background_task_duration` | Histogram | `task_name` | Background task duration |
| `background_task_success` | Counter | `task_name` | Successful task executions |
| `background_task_failure` | Counter | `task_name`, `error_type` | Failed task executions |

**Background Tasks**:
- `detect_anomalies` - Anomaly detection task
- `analyze_performance` - Performance analysis task
- `scan_security_threats` - Security scanning task
- `update_baselines` - Baseline update task
- `cleanup_old_metrics` - Metric cleanup task

**Example Prometheus Queries**:
```promql
# Monitoring system uptime
avg_over_time(monitoring_system_up[24h])

# Background task failure rate
rate(background_task_failure_total[5m]) / rate(background_task_success_total[5m] + background_task_failure_total[5m])

# Slow metric collection
histogram_quantile(0.95, sum(rate(metrics_collection_time_bucket[5m])) by (le, collector))
```

## Metric Retention

| Time Range | Resolution | Retention |
|------------|-----------|-----------|
| 0-6 hours | 15s | 6 hours |
| 6-24 hours | 1m | 24 hours |
| 1-7 days | 5m | 7 days |
| 7-30 days | 1h | 30 days |

## Metric Export Formats

### Prometheus Format

**Endpoint**: `/monitoring/metrics/`

**Format**:
```
# HELP graphql_query_validation Total GraphQL query validations
# TYPE graphql_query_validation counter
graphql_query_validation{status="accepted"} 1234
graphql_query_validation{status="rejected"} 56

# HELP request_duration_seconds Request duration in seconds
# TYPE request_duration_seconds histogram
request_duration_seconds_bucket{le="0.1"} 1000
request_duration_seconds_bucket{le="0.5"} 2000
request_duration_seconds_bucket{le="+Inf"} 2500
request_duration_seconds_sum 750.5
request_duration_seconds_count 2500
```

### JSON Format

**Endpoint**: `/monitoring/graphql/` or `/monitoring/websocket/`

**Format**:
```json
{
  "window_minutes": 60,
  "metrics": {
    "total_validations": 1234,
    "accepted_count": 1100,
    "rejected_count": 134,
    "acceptance_rate": 0.89
  },
  "timestamp": "2024-01-01T12:00:00Z",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

## Dashboarding Guidelines

### Key Performance Indicators (KPIs)

**Availability**:
- Uptime: `avg_over_time(up[24h])` → Target: >99.9%
- Error rate: `rate(errors[5m])` → Target: <0.1%

**Performance**:
- P95 latency: `histogram_quantile(0.95, request_duration)` → Target: <200ms
- Cache hit rate: `cache_hits / (cache_hits + cache_misses)` → Target: >80%

**Security**:
- Threat detection rate: `rate(security_event[5m])` → Target: <1 event/min
- Blocked IPs: `count(ip_blocked)` → Monitor for patterns

**Quality**:
- Anomaly rate: `rate(anomaly_detected[5m])` → Target: <5 anomalies/hour
- Alert noise: `alert_suppressed / alert_created` → Target: <20%

### Dashboard Refresh Rates

| Dashboard Type | Refresh Rate | Reason |
|----------------|-------------|---------|
| Real-time monitoring | 5-10s | Immediate issue detection |
| Performance overview | 30s | Balance freshness vs load |
| Security dashboard | 10-15s | Quick threat response |
| Historical analysis | 5m | Reduce query load |

## Metric Cardinality

**High Cardinality** (>1000 unique values):
- `ip_address` - Use aggregation
- `user_id` - Sample or aggregate
- `correlation_id` - Short retention

**Medium Cardinality** (100-1000 unique values):
- `endpoint` - Acceptable
- `client_ip` (top N) - Limit to top 100

**Low Cardinality** (<100 unique values):
- `status` - Ideal
- `user_type` - Ideal
- `severity` - Ideal

## Troubleshooting Metrics

### Missing Metrics Checklist

1. Check metric collection enabled: `MONITORING_ENABLED = True`
2. Verify Prometheus scrape config
3. Check metric name spelling
4. Verify labels match query
5. Check time range (metrics may have expired)

### High Cardinality Issues

**Symptoms**:
- Prometheus memory usage high
- Query timeouts
- Scrape duration >15s

**Solutions**:
- Reduce label cardinality
- Enable metric sampling
- Increase Prometheus memory
- Reduce retention period

## Metric Best Practices

1. **Use Histograms for Timing**: Always use histograms for duration/latency metrics
2. **Counter for Events**: Use counters for event counts (always increasing)
3. **Gauge for State**: Use gauges for current state (can go up/down)
4. **Limit Label Cardinality**: Keep unique label combinations <10,000
5. **Consistent Naming**: Follow `component_metric_unit` pattern
6. **Add Units**: Include units in metric names (seconds, bytes, requests)
