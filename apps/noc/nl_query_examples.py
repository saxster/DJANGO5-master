
import logging
logger = logging.getLogger(__name__)

"""
NOC Natural Language Query Examples.

20+ example queries demonstrating the natural language query interface.
Use these examples for testing, documentation, and user training.
"""

__all__ = ['EXAMPLE_QUERIES']


EXAMPLE_QUERIES = [
    # Alert Queries
    {
        'category': 'Alerts',
        'query': 'Show me critical alerts from the last 24 hours',
        'description': 'Retrieves all CRITICAL severity alerts within the past day',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {'severity': ['CRITICAL']},
            'time_range': {'hours': 24},
        }
    },
    {
        'category': 'Alerts',
        'query': 'Find high and critical alerts that are still open',
        'description': 'Retrieves unresolved high-priority alerts',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {
                'severity': ['CRITICAL', 'HIGH'],
                'status': ['NEW', 'ACKNOWLEDGED']
            },
        }
    },
    {
        'category': 'Alerts',
        'query': 'What SLA breach alerts occurred today?',
        'description': 'Retrieves SLA breach alerts from the current day',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {'alert_type': ['SLA_BREACH']},
            'time_range': {'hours': 24},
        }
    },
    {
        'category': 'Alerts',
        'query': 'Show me all alerts for Site ID 123',
        'description': 'Retrieves alerts for a specific site',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {'site_id': 123},
        }
    },
    {
        'category': 'Alerts',
        'query': 'List the top 10 most recent alerts',
        'description': 'Retrieves the 10 newest alerts across all sites',
        'expected_params': {
            'query_type': 'alerts',
            'aggregation': {'limit': 10, 'order_by': 'timestamp'},
        }
    },

    # Incident Queries
    {
        'category': 'Incidents',
        'query': 'Show me open incidents',
        'description': 'Retrieves all incidents that are not yet resolved',
        'expected_params': {
            'query_type': 'incidents',
            'filters': {
                'status': ['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS']
            },
        }
    },
    {
        'category': 'Incidents',
        'query': 'Find critical incidents from the last week',
        'description': 'Retrieves high-severity incidents from the past 7 days',
        'expected_params': {
            'query_type': 'incidents',
            'filters': {'severity': ['CRITICAL']},
            'time_range': {'days': 7},
        }
    },
    {
        'category': 'Incidents',
        'query': 'What incidents were resolved today?',
        'description': 'Retrieves resolved incidents from the current day',
        'expected_params': {
            'query_type': 'incidents',
            'filters': {'status': ['RESOLVED', 'CLOSED']},
            'time_range': {'hours': 24},
        }
    },

    # Metric Queries
    {
        'category': 'Metrics',
        'query': 'Show me metrics for the last hour',
        'description': 'Retrieves telemetry metrics from the past hour',
        'expected_params': {
            'query_type': 'metrics',
            'time_range': {'hours': 1},
        }
    },
    {
        'category': 'Metrics',
        'query': 'Get metrics for client 456',
        'description': 'Retrieves metrics for a specific client organization',
        'expected_params': {
            'query_type': 'metrics',
            'filters': {'client_id': 456},
        }
    },

    # Fraud/Security Queries
    {
        'category': 'Fraud Detection',
        'query': 'Show me fraud alerts from today',
        'description': 'Retrieves security anomaly alerts',
        'expected_params': {
            'query_type': 'fraud',
            'time_range': {'hours': 24},
        }
    },
    {
        'category': 'Fraud Detection',
        'query': 'Find high-risk fraud scores',
        'description': 'Retrieves fraud detection results with high risk scores',
        'expected_params': {
            'query_type': 'fraud',
            'filters': {'severity': ['HIGH', 'CRITICAL']},
        }
    },

    # Trend Analysis Queries
    {
        'category': 'Trends',
        'query': 'Show me alert trends by severity for the last 7 days',
        'description': 'Aggregates alerts by severity level over the past week',
        'expected_params': {
            'query_type': 'trends',
            'time_range': {'days': 7},
            'aggregation': {'group_by': ['severity']},
        }
    },
    {
        'category': 'Trends',
        'query': 'What are the most common alert types this week?',
        'description': 'Aggregates alerts by type to identify patterns',
        'expected_params': {
            'query_type': 'trends',
            'time_range': {'days': 7},
            'aggregation': {'group_by': ['alert_type'], 'order_by': 'count'},
        }
    },
    {
        'category': 'Trends',
        'query': 'Show me hourly alert counts for today',
        'description': 'Aggregates alerts by hour to identify peak times',
        'expected_params': {
            'query_type': 'trends',
            'time_range': {'hours': 24},
            'aggregation': {'group_by': ['hour']},
        }
    },
    {
        'category': 'Trends',
        'query': 'Which sites have the most alerts?',
        'description': 'Ranks sites by alert volume',
        'expected_params': {
            'query_type': 'trends',
            'aggregation': {'group_by': ['site'], 'order_by': 'count'},
        }
    },

    # Predictive Queries
    {
        'category': 'Predictions',
        'query': 'Show me predictive alerts from the ML model',
        'description': 'Retrieves ML-generated predictive alerts',
        'expected_params': {
            'query_type': 'predictions',
        }
    },
    {
        'category': 'Predictions',
        'query': 'What SLA breaches are predicted for tomorrow?',
        'description': 'Retrieves predictive alerts for SLA breach risk',
        'expected_params': {
            'query_type': 'predictions',
            'filters': {'alert_type': ['PREDICTIVE_SLA_BREACH']},
        }
    },

    # Complex Queries
    {
        'category': 'Complex',
        'query': 'Show me detailed critical alerts from Site 789 in the last 2 hours',
        'description': 'Multi-filter query with specific output format',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {
                'severity': ['CRITICAL'],
                'site_id': 789,
            },
            'time_range': {'hours': 2},
            'output_format': 'detailed',
        }
    },
    {
        'category': 'Complex',
        'query': 'Give me a table of all unresolved incidents grouped by site',
        'description': 'Tabular output with grouping',
        'expected_params': {
            'query_type': 'incidents',
            'filters': {'status': ['NEW', 'ACKNOWLEDGED', 'IN_PROGRESS']},
            'output_format': 'table',
            'aggregation': {'group_by': ['site']},
        }
    },

    # Natural Language Variations
    {
        'category': 'Natural Language',
        'query': 'Are there any critical problems right now?',
        'description': 'Conversational query for current critical alerts',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {'severity': ['CRITICAL']},
            'time_range': {'hours': 1},
        }
    },
    {
        'category': 'Natural Language',
        'query': 'What went wrong at Site Alpha today?',
        'description': 'Natural language query with site name',
        'expected_params': {
            'query_type': 'alerts',
            'filters': {'site_name': 'Alpha'},
            'time_range': {'hours': 24},
        }
    },
    {
        'category': 'Natural Language',
        'query': 'How many alerts have we had this week?',
        'description': 'Counting query in natural language',
        'expected_params': {
            'query_type': 'trends',
            'time_range': {'days': 7},
            'aggregation': {'order_by': 'count'},
        }
    },
]


def get_examples_by_category(category: str) -> list:
    """
    Get example queries by category.

    Args:
        category: Category name (Alerts, Incidents, Metrics, etc.)

    Returns:
        List of example query dicts
    """
    return [q for q in EXAMPLE_QUERIES if q['category'] == category]


def get_all_categories() -> list:
    """
    Get list of all example categories.

    Returns:
        List of category names
    """
    return sorted(set(q['category'] for q in EXAMPLE_QUERIES))


def print_examples():
    """Print all example queries grouped by category."""
    for category in get_all_categories():
        logger.debug(f"\n{'=' * 60}")
        logger.debug(f"{category} Queries")
        logger.debug('=' * 60)

        examples = get_examples_by_category(category)
        for i, example in enumerate(examples, 1):


if __name__ == '__main__':
    print_examples()
