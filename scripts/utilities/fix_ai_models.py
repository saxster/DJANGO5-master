#!/usr/bin/env python3
"""
Script to fix all AI app models by removing TenantAwareModel inheritance
and adding proper client field relationships
"""

import os
import re

# AI apps that need fixing
AI_APPS = [
    'mindsdb_engine',
    'ai_orchestrator', 
    'smart_dashboard',
    'insights_engine',
    'nlp_engine',
    'voice_recognition'
]

def fix_model_file(filepath):
    """Fix a single model file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if file needs fixing
    if 'TenantAwareModel' not in content:
        return False
    
    original_content = content
    
    # Remove TenantAwareModel import if it's the only import from tenants.models
    content = re.sub(
        r'from apps\.tenants\.models import TenantAwareModel\n',
        '',
        content
    )
    
    # Remove TenantAwareModel from import statements with multiple imports
    content = re.sub(
        r'from apps\.tenants\.models import (.*?), ?TenantAwareModel(.*?)\n',
        r'from apps.tenants.models import \1\2\n',
        content
    )
    content = re.sub(
        r'from apps\.tenants\.models import TenantAwareModel, ?(.*?)\n',
        r'from apps.tenants.models import \1\n',
        content
    )
    
    # Find all class definitions that inherit from both BaseModel and TenantAwareModel
    class_pattern = r'class (\w+)\(BaseModel, TenantAwareModel\):'
    
    classes_to_fix = re.findall(class_pattern, content)
    
    for class_name in classes_to_fix:
        # Remove TenantAwareModel from class inheritance
        content = re.sub(
            f'class {class_name}\\(BaseModel, TenantAwareModel\\):',
            f'class {class_name}(BaseModel):',
            content
        )
        
        # Find the class definition and add client field after the first few fields
        # Look for the first field definition after the class
        class_start_pattern = f'class {class_name}\\(BaseModel\\):(.*?)(?=\\n    [a-zA-Z_])'
        match = re.search(class_start_pattern, content, re.DOTALL)
        
        if match:
            # Check if this class already has a client field
            class_def_end = match.end()
            # Find next class or end of file
            next_class = re.search(r'\nclass ', content[class_def_end:])
            if next_class:
                class_body = content[class_def_end:class_def_end + next_class.start()]
            else:
                class_body = content[class_def_end:]
            
            if 'client = models.ForeignKey' not in class_body:
                # Find a good place to insert the client field
                # Look for the first field definition
                field_pattern = r'\n    ([a-zA-Z_][a-zA-Z0-9_]*) = models\.'
                first_field = re.search(field_pattern, content[match.start():])
                
                if first_field:
                    # Find the end of the first field definition
                    insert_pos = match.start() + first_field.end()
                    # Find the end of this field (next field or next method)
                    next_item = re.search(r'\n    [a-zA-Z_]', content[insert_pos:])
                    if next_item:
                        insert_pos = insert_pos + next_item.start()
                        
                        # Insert client field
                        client_field = '''
    
    # Client relationship
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name="Client",
        null=True,
        blank=True,
        on_delete=models.RESTRICT,
        related_name="{}_set",
    )'''.format(class_name.lower())
                        
                        content = content[:insert_pos] + client_field + content[insert_pos:]
    
    # Only write if changes were made
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    
    return False

def main():
    base_path = '/home/jarvis/DJANGO5/YOUTILITY5/apps'
    
    for app in AI_APPS:
        model_file = os.path.join(base_path, app, 'models.py')
        
        if os.path.exists(model_file):
            print(f"Processing {app}/models.py...")
            if fix_model_file(model_file):
                print(f"  ✓ Fixed {app}/models.py")
            else:
                print(f"  - No changes needed for {app}/models.py")
        else:
            print(f"  ✗ {app}/models.py not found")

if __name__ == '__main__':
    main()