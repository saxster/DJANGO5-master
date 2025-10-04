"""
Entity-specific search adapters

Each adapter handles search for a specific domain:
- Knows how to query the entity
- Applies entity-specific permissions
- Formats results with appropriate actions
"""

__all__ = [
    'BaseSearchAdapter',
    'PeopleAdapter',
    'WorkOrderAdapter',
    'TicketAdapter',
    'AssetAdapter',
    'TaskAdapter',
    'KnowledgeAdapter',
]