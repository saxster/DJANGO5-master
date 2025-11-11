#!/usr/bin/env python3
"""
Fix multi-line imports from apps.onboarding to bounded context apps.

This script specifically handles multi-line imports that update_onboarding_imports.py skipped.
"""

import re
import sys
from pathlib import Path

# Model mapping (same as update_onboarding_imports.py)
MODEL_TO_APP = {
    'Bt': 'client_onboarding',
    'BusinessUnit': 'client_onboarding',
    'Bu': 'client_onboarding',
    'Shift': 'client_onboarding',
    'Device': 'client_onboarding',
    'Subscription': 'client_onboarding',
    'DownTimeHistory': 'client_onboarding',
    'bu_defaults': 'client_onboarding',
    'shiftdata_json': 'client_onboarding',

    'ConversationSession': 'core_onboarding',
    'LLMRecommendation': 'core_onboarding',
    'AuthoritativeKnowledge': 'core_onboarding',
    'AuthoritativeKnowledgeChunk': 'core_onboarding',
    'AIChangeSet': 'core_onboarding',
    'AIChangeRecord': 'core_onboarding',
    'ChangeSetApproval': 'core_onboarding',
    'TypeAssist': 'core_onboarding',
    'GeofenceMaster': 'core_onboarding',
    'OnboardingObservation': 'core_onboarding',
    'Observation': 'core_onboarding',

    'OnboardingSite': 'site_onboarding',
    'OnboardingZone': 'site_onboarding',
    'SitePhoto': 'site_onboarding',
    'Asset': 'site_onboarding',
    'Checkpoint': 'site_onboarding',
    'MeterPoint': 'site_onboarding',
    'SOP': 'site_onboarding',
    'CoveragePlan': 'site_onboarding',
}


def fix_multiline_import(filepath):
    """Fix multi-line imports in a file."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content

    # Find multi-line imports: from apps.onboarding.models import (\n...\n)
    pattern = r'from apps\.onboarding\.models import \(\s*\n(.*?)\n\s*\)'

    def replace_import(match):
        models_text = match.group(1)
        # Extract model names (handle comments, trailing commas)
        lines = models_text.split('\n')
        models = []
        for line in lines:
            # Remove comments
            line = line.split('#')[0].strip()
            if not line:
                continue
            # Split by comma and clean
            for model in line.split(','):
                model = model.strip()
                if model:
                    models.append(model)

        # Group by target app
        app_groups = {}
        for model in models:
            base_model = model.split(' as ')[0].strip()
            target_app = MODEL_TO_APP.get(base_model, 'client_onboarding')
            if target_app not in app_groups:
                app_groups[target_app] = []
            app_groups[target_app].append(model)

        # Generate new imports
        result_lines = []
        for app_name in sorted(app_groups.keys()):
            app_models = app_groups[app_name]
            if len(app_models) == 1:
                result_lines.append(f"from apps.{app_name}.models import {app_models[0]}")
            else:
                models_str = ',\n    '.join(app_models)
                result_lines.append(f"from apps.{app_name}.models import (\n    {models_str}\n)")

        return '\n'.join(result_lines)

    content = re.sub(pattern, replace_import, content, flags=re.DOTALL)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    return False


def main():
    """Main entry point."""
    # Find all files with multi-line imports
    base_dir = Path(__file__).parent

    python_files = []
    for pattern in ['**/*.py']:
        for filepath in base_dir.glob(pattern):
            if any(x in str(filepath) for x in ['migrations', '__pycache__', 'venv', '.git']):
                continue
            python_files.append(filepath)

    print(f"Scanning {len(python_files)} Python files for multi-line imports...")

    updated = 0
    for filepath in python_files:
        if fix_multiline_import(filepath):
            print(f"Updated: {filepath}")
            updated += 1

    print(f"\nUpdated {updated} files with multi-line imports")


if __name__ == '__main__':
    main()
