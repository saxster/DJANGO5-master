#!/usr/bin/env python3
"""Split reports/forms.py into logical modules."""

from pathlib import Path

# Read original file
original_file = Path("apps/reports/forms.py")
with open(original_file, 'r') as f:
    lines = f.readlines()

# Find line numbers for each form class
form_starts = {}
for i, line in enumerate(lines, 1):
    if line.startswith('class ') and 'Form' in line:
        form_name = line.split('(')[0].replace('class ', '').strip()
        form_starts[form_name] = i

print("Found forms:", list(form_starts.keys()))

# Extract imports (lines before first class)
first_class_line = min(form_starts.values())
imports = ''.join(lines[:first_class_line-1])

# Create forms directory
forms_dir = Path("apps/reports/forms")
forms_dir.mkdir(exist_ok=True)

# Define splits
splits = {
    'builder_forms.py': ['TestForm', 'ReportBuilderForm'],
    'report_forms.py': ['ReportForm'],
    'email_forms.py': ['EmailReportForm'],
    'pdf_forms.py': ['GeneratePDFForm'],
}

# Extract each section
form_lines_map = {}
form_names = list(form_starts.keys())
for i, form_name in enumerate(form_names):
    start_line = form_starts[form_name]
    # Find end: next form or end of file
    if i < len(form_names) - 1:
        end_line = form_starts[form_names[i+1]] - 1
    else:
        end_line = len(lines)
    
    form_content = ''.join(lines[start_line-1:end_line])
    form_lines_map[form_name] = form_content

# Write split files
for filename, form_list in splits.items():
    output_file = forms_dir / filename
    with open(output_file, 'w') as f:
        f.write(imports)
        f.write('\n\n')
        for form_name in form_list:
            if form_name in form_lines_map:
                f.write(form_lines_map[form_name])
                f.write('\n\n')
    
    line_count = len(open(output_file).readlines())
    print(f"Created {output_file} ({line_count} lines)")

# Create __init__.py
init_content = '''"""
Reports forms module - split for maintainability.

Exports all forms for backward compatibility.
"""

from .builder_forms import TestForm, ReportBuilderForm
from .report_forms import ReportForm
from .email_forms import EmailReportForm
from .pdf_forms import GeneratePDFForm

__all__ = [
    'TestForm',
    'ReportBuilderForm',
    'ReportForm',
    'EmailReportForm',
    'GeneratePDFForm',
]
'''

with open(forms_dir / '__init__.py', 'w') as f:
    f.write(init_content)

print(f"Created {forms_dir / '__init__.py'}")

# Rename original
backup_file = Path("apps/reports/forms.py.backup")
original_file.rename(backup_file)
print(f"Backed up original to {backup_file}")

print("\n✅ Split complete!")
