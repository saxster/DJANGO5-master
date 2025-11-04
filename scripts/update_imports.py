#!/usr/bin/env python3
"""
Update imports from apps.onboarding.models to new contexts.

Mapping:
- Bt → apps.client_onboarding.models.Bt
- OnboardingSite → apps.site_onboarding.models.OnboardingSite
- ConversationSession → apps.core_onboarding.models.ConversationSession
- etc.
"""
import re
import sys
from pathlib import Path

IMPORT_MAPPINGS = {
    # Client context
    'Bt': 'apps.client_onboarding.models',
    'Shift': 'apps.client_onboarding.models',

    # Site context
    'OnboardingSite': 'apps.site_onboarding.models',
    'OnboardingZone': 'apps.site_onboarding.models',
    'Asset': 'apps.site_onboarding.models',
    'Checkpoint': 'apps.site_onboarding.models',
    'MeterPoint': 'apps.site_onboarding.models',
    'SOP': 'apps.site_onboarding.models',
    'CoveragePlan': 'apps.site_onboarding.models',
    'SitePhoto': 'apps.site_onboarding.models',
    'SiteVideo': 'apps.site_onboarding.models',

    # Core context (shared kernel)
    'ConversationSession': 'apps.core_onboarding.models',
    'OnboardingObservation': 'apps.core_onboarding.models',
    'OnboardingMedia': 'apps.core_onboarding.models',
    'LLMRecommendation': 'apps.core_onboarding.models',
    'AuthoritativeKnowledge': 'apps.core_onboarding.models',
    'AuthoritativeKnowledgeChunk': 'apps.core_onboarding.models',
    'AIChangeSet': 'apps.core_onboarding.models',
    'AIChangeRecord': 'apps.core_onboarding.models',
    'TypeAssist': 'apps.core_onboarding.models',
    'GeofenceMaster': 'apps.core_onboarding.models',
    'KnowledgeSource': 'apps.core_onboarding.models',
    'KnowledgeIngestionJob': 'apps.core_onboarding.models',
    'KnowledgeReview': 'apps.core_onboarding.models',

    # Worker context
    'OnboardingRequest': 'apps.people_onboarding.models',
    'OnboardingTask': 'apps.people_onboarding.models',
    'WorkerDocument': 'apps.people_onboarding.models',
}


def update_file_imports(filepath: Path) -> int:
    """Update imports in a single file. Returns number of changes."""
    content = filepath.read_text()
    original = content
    changes = 0

    # Pattern: from apps.onboarding.models import X, Y, Z
    pattern = r'from apps\.onboarding\.models import ([^;\n]+)'

    def replace_import(match):
        nonlocal changes
        imports_str = match.group(1)

        # Parse imported names
        imports = [i.strip() for i in imports_str.split(',')]

        # Group by destination module
        by_module = {}
        for imp in imports:
            # Handle "X as Y" syntax
            if ' as ' in imp:
                name = imp.split(' as ')[0].strip()
                alias = imp.split(' as ')[1].strip()
            else:
                name = imp.strip()
                alias = None

            dest_module = IMPORT_MAPPINGS.get(name, 'apps.onboarding.models')

            if dest_module not in by_module:
                by_module[dest_module] = []

            by_module[dest_module].append((name, alias))

        # Generate new import statements
        new_imports = []
        for module, items in sorted(by_module.items()):
            import_list = ', '.join(
                f"{name} as {alias}" if alias else name
                for name, alias in items
            )
            new_imports.append(f"from {module} import {import_list}")

        changes += 1
        return '\n'.join(new_imports)

    content = re.sub(pattern, replace_import, content)

    if content != original:
        filepath.write_text(content)
        return changes

    return 0


def main():
    files_to_update = sys.argv[1:] if len(sys.argv) > 1 else []

    if not files_to_update:
        print("Usage: python scripts/update_imports.py <file1> <file2> ...")
        return

    total_changes = 0
    for filepath_str in files_to_update:
        filepath = Path(filepath_str)
        if filepath.exists():
            changes = update_file_imports(filepath)
            if changes > 0:
                print(f"✅ Updated {filepath}: {changes} import statements")
                total_changes += changes

    print(f"\nTotal: {total_changes} import statements updated across {len(files_to_update)} files")


if __name__ == '__main__':
    main()
