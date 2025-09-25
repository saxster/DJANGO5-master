#!/usr/bin/env python3
"""
Create initial migrations for txtai_engine app
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.core.management import call_command

# Create migrations
print("Creating migrations for txtai_engine...")
try:
    call_command('makemigrations', 'txtai_engine')
    print("Migrations created successfully!")
except Exception as e:
    print(f"Error creating migrations: {e}")