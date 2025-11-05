"""
ML Training Data Platform Models Package.

Backward-compatible imports for refactored model structure.

Following .claude/rules.md:
- Rule #7: Model classes < 150 lines (split into focused models)
- Maintains backward compatibility for existing imports
"""

from .enums import (
    DatasetType,
    DatasetStatus,
    ExampleType,
    LabelingStatus,
    TaskType,
    TaskStatus,
)
from .dataset import TrainingDataset
from .training_example import TrainingExample
from .labeling_task import LabelingTask

# Export all models and enums for backward compatibility
__all__ = [
    # Models
    'TrainingDataset',
    'TrainingExample',
    'LabelingTask',
    # Enums
    'DatasetType',
    'DatasetStatus',
    'ExampleType',
    'LabelingStatus',
    'TaskType',
    'TaskStatus',
]
