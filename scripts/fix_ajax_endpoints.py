#!/usr/bin/env python3
"""
Comprehensive AJAX Endpoint Migration Script

Replaces all onboarding AJAX URLs with REST API or Django Admin equivalents.
Handles complex patterns that sed couldn't match (multiline, nested quotes, etc.)

Usage:
    python scripts/fix_ajax_endpoints.py --dry-run  # Preview changes
    python scripts/fix_ajax_endpoints.py            # Apply changes
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple

# Base directory
BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "frontend" / "templates"


class AJAXEndpointFixer:
    """Fix AJAX endpoints in template files"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.changes_made = 0
        self.files_modified = 0

    def fix_ajax_list_endpoints(self, content: str, template_name: str) -> Tuple[str, int]:
        """Fix AJAX calls with ?action=list to REST API"""
        changes = 0

        # Pattern 1: DataTables ajax.url
        patterns = [
            # $.ajax({ url: '{{ url("onboarding:X") }}?action=list'
            (
                r"url:\s*['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist)['\"].*\).*}}['\"]?\?action=list",
                lambda m: self._get_rest_api_url(m.group(1))
            ),
            # ajax:{ url: '{{ url("onboarding:X") }}?action=list'
            (
                r"ajax\s*:\s*{\s*url\s*:\s*['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist)['\"].*\).*}}['\"]?\?action=list",
                lambda m: f"ajax: {{ url: '{self._get_rest_api_url(m.group(1))}'"
            ),
            # Direct AJAX URL assignment
            (
                r"let\s+url\s*=\s*['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist)['\"].*\).*}}['\"]?\?action=list",
                lambda m: f"let url = '{self._get_rest_api_url(m.group(1))}'  // Migrated from onboarding:{m.group(1)}"
            ),
        ]

        for pattern, replacement in patterns:
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                changes += count
                print(f"  ✓ Fixed {count} AJAX list endpoint(s)")

        return content, changes

    def fix_navigation_links(self, content: str, template_name: str) -> Tuple[str, int]:
        """Fix navigation links (?action=form, ?id=X) to Django Admin"""
        changes = 0

        # Pattern 1: ?action=form → Django Admin add
        patterns = [
            (
                r"{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist|client)['\"].*\).*}}['\"]?\?action=form",
                lambda m: f"{{% url 'admin:onboarding_{self._get_model_name(m.group(1))}_add' %}}'"
            ),
            # Pattern 2: location.href = '{{ url("onboarding:X") }}?action=form'
            (
                r"location\.href\s*=\s*['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist|client)['\"].*\).*}}['\"]?\?action=form['\"]",
                lambda m: f"location.href = '{{% url 'admin:onboarding_{self._get_model_name(m.group(1))}_add' %}}'"
            ),
            # Pattern 3: window.location.href = ...
            (
                r"window\.location\.href\s*=\s*['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist|client)['\"].*\).*}}['\"]?\?action=form['\"]",
                lambda m: f"window.location.href = '{{% url 'admin:onboarding_{self._get_model_name(m.group(1))}_add' %}}'"
            ),
        ]

        for pattern, replacement in patterns:
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                changes += count
                print(f"  ✓ Fixed {count} navigation link(s) to Django Admin")

        return content, changes

    def fix_import_urls(self, content: str, template_name: str) -> Tuple[str, int]:
        """Fix import/import_update URL references"""
        changes = 0

        # const urlname = '{{ url("onboarding:import") }}'
        pattern = r"const\s+urlname\s*=\s*['\"]{{.*url\(['\"]onboarding:(import|import_update)['\"].*\).*}}['\"]"
        replacement = "const urlname = '{% url 'admin:onboarding_typeassist_import' %}'"

        new_content, count = re.subn(pattern, replacement, content)
        if count > 0:
            content = new_content
            changes += count
            print(f"  ✓ Fixed {count} import URL(s)")

        return content, changes

    def fix_datatable_ajax(self, content: str, template_name: str) -> Tuple[str, int]:
        """Fix DataTables ajax configuration"""
        changes = 0

        # table = $(table_id).DataTable({ ajax:{ url: '{{ url("onboarding:X") }}?action=list',
        pattern = r"(DataTable\s*\(\s*{[^}]*ajax\s*:\s*{[^}]*url\s*:\s*)['\"]{{.*url\(['\"]onboarding:(shift|bu|geofence|contract|typeassist)['\"].*\).*}}['\"]?\?action=list"

        def replacement(match):
            prefix = match.group(1)
            model = match.group(2)
            api_url = self._get_rest_api_url(model)
            return f"{prefix}'{api_url}', dataSrc: 'results'  // Migrated from onboarding:{model}"

        new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
        if count > 0:
            content = new_content
            changes += count
            print(f"  ✓ Fixed {count} DataTable ajax config(s)")

        return content, changes

    def _get_rest_api_url(self, model: str) -> str:
        """Map model names to REST API endpoints"""
        mapping = {
            'shift': '/api/v1/admin/config/shifts/',
            'bu': '/api/v1/admin/config/business-units/',
            'geofence': '/api/v1/admin/config/geofences/',
            'contract': '/api/v1/admin/config/contracts/',
            'typeassist': '/api/v1/admin/config/type-assist/',
            'client': '/api/v1/admin/config/clients/',
        }
        return mapping.get(model, f'/api/v1/admin/config/{model}/')

    def _get_model_name(self, url_name: str) -> str:
        """Map URL names to Django model names"""
        mapping = {
            'shift': 'shift',
            'bu': 'bt',
            'geofence': 'geofencemaster',
            'contract': 'contract',
            'typeassist': 'typeassist',
            'client': 'client',
        }
        return mapping.get(url_name, url_name)

    def process_file(self, file_path: Path) -> bool:
        """Process a single template file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            content = original_content
            total_changes = 0

            # Apply all fixes
            content, changes = self.fix_ajax_list_endpoints(content, file_path.name)
            total_changes += changes

            content, changes = self.fix_navigation_links(content, file_path.name)
            total_changes += changes

            content, changes = self.fix_import_urls(content, file_path.name)
            total_changes += changes

            content, changes = self.fix_datatable_ajax(content, file_path.name)
            total_changes += changes

            if total_changes > 0:
                if not self.dry_run:
                    # Backup original
                    backup_path = file_path.with_suffix(file_path.suffix + '.ajax_backup')
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(original_content)

                    # Write fixed content
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)

                self.changes_made += total_changes
                self.files_modified += 1
                return True

            return False

        except Exception as e:
            print(f"  ✗ Error processing {file_path.name}: {e}")
            return False

    def process_templates(self) -> None:
        """Process all affected template files"""
        affected_files = [
            "onboarding/shift_modern.html",
            "onboarding/bu_list_modern.html",
            "onboarding/geofence_list_modern.html",
            "onboarding/contract_list_modern.html",
            "onboarding/geofence_form.html",
            "onboarding/geofence_list.html",
            "onboarding/typeassist.html",
            "onboarding/shift.html",
            "onboarding/contract_list.html",
            "onboarding/client_bulist.html",
            "onboarding/import.html",
            "onboarding/import_update.html",
            "activity/testCalendar.html",
        ]

        print(f"\n{'=' * 60}")
        print(f"AJAX Endpoint Migration {'(DRY RUN)' if self.dry_run else ''}")
        print(f"{'=' * 60}\n")

        for template_path in affected_files:
            full_path = TEMPLATES_DIR / template_path
            if not full_path.exists():
                print(f"⚠ Skipping {template_path} (not found)")
                continue

            print(f"\nProcessing: {template_path}")
            if self.process_file(full_path):
                print(f"  ✓ Updated successfully")
            else:
                print(f"  ℹ No changes needed")

        print(f"\n{'=' * 60}")
        print(f"Summary")
        print(f"{'=' * 60}")
        print(f"Files modified: {self.files_modified}")
        print(f"Total changes: {self.changes_made}")

        if self.dry_run:
            print(f"\n⚠ DRY RUN - No files were actually modified")
            print(f"Run without --dry-run to apply changes")
        else:
            print(f"\n✓ Changes applied successfully!")
            print(f"Backup files created with .ajax_backup extension")


def main():
    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv

    fixer = AJAXEndpointFixer(dry_run=dry_run)
    fixer.process_templates()


if __name__ == '__main__':
    main()
