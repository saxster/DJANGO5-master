"""
Help Desk Natural Language Query Examples.

Comprehensive examples organized by category for:
- Testing query parsing accuracy
- Documentation and user guides
- Training LLM for query understanding

Part of NL Query Platform Expansion - Module 1.
Business Value: $450k+/year productivity gains.
"""

HELPDESK_QUERY_EXAMPLES = {
    'status': [
        {
            'query': 'Show me all open tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'status': ['OPEN']},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Basic status filter - open tickets'
        },
        {
            'query': 'Find resolved tickets from last week',
            'structured': {
                'query_type': 'tickets',
                'filters': {'status': ['RESOLVED']},
                'time_range': {'days': 7},
                'output_format': 'summary'
            },
            'description': 'Status filter with time range'
        },
        {
            'query': 'Show me new and open tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'status': ['NEW', 'OPEN']},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Multiple status values'
        },
        {
            'query': 'What tickets are on hold?',
            'structured': {
                'query_type': 'tickets',
                'filters': {'status': ['ONHOLD']},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'On-hold tickets'
        },
        {
            'query': 'Show me cancelled tickets with attachments',
            'structured': {
                'query_type': 'tickets',
                'filters': {'status': ['CANCELLED']},
                'time_range': {'days': 30},
                'output_format': 'detailed'
            },
            'description': 'Cancelled tickets (detailed view for attachments)'
        },
    ],

    'priority': [
        {
            'query': 'Show high-priority tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'priority': ['HIGH']},
                'time_range': {'days': 30},
                'aggregation': {'order_by': 'priority'},
                'output_format': 'summary'
            },
            'description': 'High priority tickets only'
        },
        {
            'query': 'Critical tickets for Site X',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'priority': ['HIGH'],
                    'site_name': 'Site X'
                },
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Priority + site filter combination'
        },
        {
            'query': 'Show me low and medium priority tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'priority': ['LOW', 'MEDIUM']},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Multiple priority levels'
        },
    ],

    'assignment': [
        {
            'query': 'Show my tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'assignment_type': 'my_tickets'},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Tickets assigned to current user'
        },
        {
            'query': 'What tickets are assigned to my groups?',
            'structured': {
                'query_type': 'tickets',
                'filters': {'assignment_type': 'my_groups'},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Tickets assigned to user\'s groups'
        },
        {
            'query': 'Show unassigned tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'assignment_type': 'unassigned'},
                'time_range': {'days': 7},
                'output_format': 'summary'
            },
            'description': 'Tickets with no assignment'
        },
        {
            'query': 'What are my open tickets?',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'assignment_type': 'my_tickets',
                    'status': ['OPEN', 'NEW']
                },
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'My tickets + status filter'
        },
    ],

    'sla': [
        {
            'query': 'Show overdue tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'sla_status': 'overdue'},
                'time_range': {'days': 30},
                'aggregation': {'order_by': 'sla'},
                'output_format': 'summary'
            },
            'description': 'Tickets past SLA deadline'
        },
        {
            'query': 'Which tickets are approaching SLA?',
            'structured': {
                'query_type': 'tickets',
                'filters': {'sla_status': 'approaching'},
                'time_range': {'days': 7},
                'aggregation': {'order_by': 'sla'},
                'output_format': 'summary'
            },
            'description': 'Tickets within 2 hours of SLA breach'
        },
        {
            'query': 'Show me overdue high-priority tickets for Site Y',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'sla_status': 'overdue',
                    'priority': ['HIGH'],
                    'site_name': 'Site Y'
                },
                'time_range': {'days': 30},
                'aggregation': {'order_by': 'sla'},
                'output_format': 'detailed'
            },
            'description': 'Complex SLA + priority + site filter'
        },
    ],

    'escalation': [
        {
            'query': 'Show escalated tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'escalation': {'is_escalated': True}
                },
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'All escalated tickets'
        },
        {
            'query': 'Which tickets are at escalation level 2?',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'escalation': {'level': 2}
                },
                'time_range': {'days': 30},
                'output_format': 'detailed'
            },
            'description': 'Specific escalation level'
        },
        {
            'query': 'Show me tickets that have been escalated but not resolved',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'escalation': {'is_escalated': True},
                    'status': ['NEW', 'OPEN', 'ASSIGNED']
                },
                'time_range': {'days': 30},
                'output_format': 'detailed'
            },
            'description': 'Escalated + unresolved tickets'
        },
    ],

    'source': [
        {
            'query': 'Show system-generated tickets',
            'structured': {
                'query_type': 'tickets',
                'filters': {'source': 'SYSTEMGENERATED'},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Auto-generated tickets from monitoring'
        },
        {
            'query': 'What user-created tickets do we have?',
            'structured': {
                'query_type': 'tickets',
                'filters': {'source': 'USERDEFINED'},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Manually created tickets'
        },
    ],

    'site': [
        {
            'query': 'Show tickets for Site X',
            'structured': {
                'query_type': 'tickets',
                'filters': {'site_name': 'Site X'},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Site-specific tickets'
        },
        {
            'query': 'What are the high-priority open tickets at headquarters?',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'site_name': 'headquarters',
                    'priority': ['HIGH'],
                    'status': ['OPEN', 'NEW']
                },
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Complex site + priority + status filter'
        },
    ],

    'time_range': [
        {
            'query': 'Show tickets from the last 24 hours',
            'structured': {
                'query_type': 'tickets',
                'filters': {},
                'time_range': {'hours': 24},
                'output_format': 'summary'
            },
            'description': 'Recent tickets (last day)'
        },
        {
            'query': 'What tickets were created this week?',
            'structured': {
                'query_type': 'tickets',
                'filters': {},
                'time_range': {'days': 7},
                'output_format': 'summary'
            },
            'description': 'Weekly ticket creation'
        },
        {
            'query': 'Show me tickets from last month',
            'structured': {
                'query_type': 'tickets',
                'filters': {},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Monthly ticket history'
        },
    ],

    'complex': [
        {
            'query': 'Show me high-priority overdue tickets for Site X that are assigned to my groups',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'priority': ['HIGH'],
                    'sla_status': 'overdue',
                    'site_name': 'Site X',
                    'assignment_type': 'my_groups'
                },
                'time_range': {'days': 30},
                'aggregation': {'order_by': 'sla'},
                'output_format': 'detailed'
            },
            'description': 'Multi-dimensional query (priority + SLA + site + assignment)'
        },
        {
            'query': 'What are my escalated high-priority tickets that are still open?',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'assignment_type': 'my_tickets',
                    'escalation': {'is_escalated': True},
                    'priority': ['HIGH'],
                    'status': ['OPEN', 'NEW']
                },
                'time_range': {'days': 30},
                'output_format': 'detailed'
            },
            'description': 'Complex assignment + escalation + priority + status'
        },
        {
            'query': 'Show me system-generated tickets that are overdue and unassigned',
            'structured': {
                'query_type': 'tickets',
                'filters': {
                    'source': 'SYSTEMGENERATED',
                    'sla_status': 'overdue',
                    'assignment_type': 'unassigned'
                },
                'time_range': {'days': 7},
                'aggregation': {'order_by': 'sla'},
                'output_format': 'detailed'
            },
            'description': 'Source + SLA + assignment combination'
        },
    ],

    'analytics': [
        {
            'query': 'What is the average resolution time for high-priority tickets?',
            'structured': {
                'query_type': 'tickets',
                'filters': {'priority': ['HIGH'], 'status': ['RESOLVED', 'CLOSED']},
                'time_range': {'days': 30},
                'output_format': 'summary'
            },
            'description': 'Resolution time analytics (requires workflow data)'
        },
        {
            'query': 'Show me ticket volume by site this quarter',
            'structured': {
                'query_type': 'tickets',
                'filters': {},
                'time_range': {'days': 90},
                'aggregation': {'group_by': ['site']},
                'output_format': 'table'
            },
            'description': 'Site-based ticket volume analysis'
        },
        {
            'query': 'What are the top 5 ticket categories by volume?',
            'structured': {
                'query_type': 'tickets',
                'filters': {},
                'time_range': {'days': 30},
                'aggregation': {'group_by': ['category'], 'limit': 5},
                'output_format': 'table'
            },
            'description': 'Category-based volume ranking'
        },
    ],
}


def get_all_examples():
    """
    Get all examples flattened into a single list.

    Returns:
        List of all query examples with metadata
    """
    all_examples = []
    for category, examples in HELPDESK_QUERY_EXAMPLES.items():
        for example in examples:
            example['category'] = category
            all_examples.append(example)
    return all_examples


def get_examples_by_category(category: str):
    """
    Get examples for a specific category.

    Args:
        category: Category name (status, priority, assignment, etc.)

    Returns:
        List of examples in that category
    """
    return HELPDESK_QUERY_EXAMPLES.get(category, [])


def get_example_queries():
    """
    Get just the query text for all examples.

    Returns:
        List of query strings
    """
    return [
        example['query']
        for examples in HELPDESK_QUERY_EXAMPLES.values()
        for example in examples
    ]


# Summary statistics
TOTAL_EXAMPLES = sum(len(examples) for examples in HELPDESK_QUERY_EXAMPLES.values())
CATEGORIES = list(HELPDESK_QUERY_EXAMPLES.keys())

if __name__ == '__main__':
    print(f"Help Desk NL Query Examples")
    print(f"Total Examples: {TOTAL_EXAMPLES}")
    print(f"Categories: {', '.join(CATEGORIES)}")
    print(f"\nSample queries:")
    for category in CATEGORIES[:3]:
        examples = HELPDESK_QUERY_EXAMPLES[category]
        print(f"\n{category.upper()}:")
        for example in examples[:2]:
            print(f"  - {example['query']}")
