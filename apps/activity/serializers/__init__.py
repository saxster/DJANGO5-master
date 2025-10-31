# Backward compatibility wrapper
# Both serializers.py file and serializers/ directory exist
# Import from parent serializers.py file for backward compatibility

import sys
import os
import importlib.util

# Get the parent directory (apps/activity/)
parent_dir = os.path.dirname(os.path.dirname(__file__))
serializers_file = os.path.join(parent_dir, 'serializers.py')

# Import using absolute import workaround
spec = importlib.util.spec_from_file_location("activity_serializers_legacy", serializers_file)
serializers_legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serializers_legacy)

# Export all serializers from legacy module dynamically
# Get all classes ending with 'Serializer' from the legacy module
for name in dir(serializers_legacy):
    if name.endswith('Serializer'):
        globals()[name] = getattr(serializers_legacy, name)

# Common serializers that are typically imported
AttachmentSerializer = getattr(serializers_legacy, 'AttachmentSerializer', None)
AssetSerializer = getattr(serializers_legacy, 'AssetSerializer', None)
JobSerializer = getattr(serializers_legacy, 'JobSerializer', None)
JobneedSerializer = getattr(serializers_legacy, 'JobneedSerializer', None)
LocationSerializer = getattr(serializers_legacy, 'LocationSerializer', None)
QuestionSerializer = getattr(serializers_legacy, 'QuestionSerializer', None)
QuestionSetSerializer = getattr(serializers_legacy, 'QuestionSetSerializer', None)

__all__ = [name for name in dir(serializers_legacy) if name.endswith('Serializer')]
