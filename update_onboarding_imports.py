#!/usr/bin/env python3
"""
Script to update imports from apps.onboarding to the new bounded context apps.

Maps models to their new locations:
- apps.client_onboarding: Bt, Shift, Device, Subscription, DownTimeHistory
- apps.core_onboarding: AI/Knowledge/Conversation models
- apps.site_onboarding: Site audit models
"""

import re
import sys
from pathlib import Path

# Mapping of models to their new apps
MODEL_TO_APP = {
    # Client onboarding models
    'Bt': 'client_onboarding',
    'BusinessUnit': 'client_onboarding',  # Alias for Bt
    'Bu': 'client_onboarding',  # Alias for Bt
    'bu_defaults': 'client_onboarding',
    'Shift': 'client_onboarding',
    'shiftdata_json': 'client_onboarding',
    'Device': 'client_onboarding',
    'Subscription': 'client_onboarding',
    'DownTimeHistory': 'client_onboarding',

    # Core onboarding models (AI/Knowledge/Conversation)
    'ConversationSession': 'core_onboarding',
    'LLMRecommendation': 'core_onboarding',
    'AuthoritativeKnowledge': 'core_onboarding',
    'AuthoritativeKnowledgeChunk': 'core_onboarding',
    'UserFeedbackLearning': 'core_onboarding',
    'AIChangeSet': 'core_onboarding',
    'AIChangeRecord': 'core_onboarding',
    'ChangeSetApproval': 'core_onboarding',
    'TypeAssist': 'core_onboarding',
    'GeofenceMaster': 'core_onboarding',
    'KnowledgeSource': 'core_onboarding',
    'KnowledgeIngestionJob': 'core_onboarding',
    'KnowledgeReview': 'core_onboarding',
    'ApprovedLocation': 'core_onboarding',
    'OnboardingMedia': 'core_onboarding',
    'OnboardingObservation': 'core_onboarding',
    'Observation': 'core_onboarding',  # Alias for OnboardingObservation

    # Site onboarding models
    'OnboardingSite': 'site_onboarding',
    'OnboardingZone': 'site_onboarding',
    'SitePhoto': 'site_onboarding',
    'SiteVideo': 'site_onboarding',
    'Asset': 'site_onboarding',
    'Checkpoint': 'site_onboarding',
    'MeterPoint': 'site_onboarding',
    'SOP': 'site_onboarding',
    'CoveragePlan': 'site_onboarding',
}


def update_imports_in_file(filepath):
    """Update imports in a single file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return False

    original_content = content
    modified = False

    # Pattern 1: from apps.onboarding.models import Model1, Model2
    # Pattern 2: from apps.onboarding.models import (Model1, Model2, ...)
    # Pattern 3: from apps.onboarding import models
    # Pattern 4: from apps.onboarding.something import ...

    # Find all lines with "from apps.onboarding"
    lines = content.split('\n')
    new_lines = []

    for line in lines:
        # Skip if this is not an import from apps.onboarding
        if 'from apps.onboarding' not in line:
            new_lines.append(line)
            continue

        # Handle: from apps.onboarding.models import ...
        if re.match(r'^\s*from apps\.onboarding\.models import', line):
            # Extract the models being imported
            # Handle both single-line and multi-line imports
            if '(' in line:
                # Multi-line import - we'll handle this separately
                new_lines.append(line)
                continue

            match = re.match(r'^(\s*)from apps\.onboarding\.models import (.+)$', line)
            if match:
                indent = match.group(1)
                imports = match.group(2).strip()

                # Parse the imports
                model_names = [m.strip() for m in imports.split(',')]

                # Group models by their target app
                app_groups = {}
                for model in model_names:
                    # Handle "Model as alias" syntax
                    base_model = model.split(' as ')[0].strip()
                    target_app = MODEL_TO_APP.get(base_model, 'client_onboarding')
                    if target_app not in app_groups:
                        app_groups[target_app] = []
                    app_groups[target_app].append(model)

                # Generate new import lines
                for app_name in sorted(app_groups.keys()):
                    models = ', '.join(app_groups[app_name])
                    new_line = f"{indent}from apps.{app_name}.models import {models}"
                    new_lines.append(new_line)
                    modified = True
                continue

        # Handle other forms of imports (non-models)
        # from apps.onboarding.utils import ...
        # from apps.onboarding.managers import ...
        # etc. - map to client_onboarding
        if re.match(r'^\s*from apps\.onboarding\.', line):
            new_line = line.replace('apps.onboarding.', 'apps.client_onboarding.')
            new_lines.append(new_line)
            if new_line != line:
                modified = True
            continue

        # Default: keep the line as-is
        new_lines.append(line)

    if modified:
        new_content = '\n'.join(new_lines)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {filepath}")
            return True
        except Exception as e:
            print(f"Error writing {filepath}: {e}", file=sys.stderr)
            return False

    return False


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent

    # Find all Python files (excluding migrations and pycache)
    python_files = []
    for pattern in ['**/*.py']:
        for filepath in base_dir.glob(pattern):
            # Skip migrations, pycache, venv
            if any(x in str(filepath) for x in ['migrations', '__pycache__', 'venv', '.git']):
                continue
            python_files.append(filepath)

    print(f"Found {len(python_files)} Python files to process")

    updated_count = 0
    for filepath in python_files:
        if update_imports_in_file(filepath):
            updated_count += 1

    print(f"\nUpdated {updated_count} files")


if __name__ == '__main__':
    main()
