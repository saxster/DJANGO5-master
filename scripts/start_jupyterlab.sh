#!/bin/bash

echo "🚀 Starting JupyterLab with Django..."
echo ""
echo "📝 IMPORTANT: In your first notebook cell, run:"
echo "----------------------------------------"
echo "import os, sys, django"
echo "sys.path.insert(0, '/home/satyam/Documents/DJANGO5/YOUTILITY3')"
echo "os.environ['DJANGO_SETTINGS_MODULE'] = 'intelliwiz_config.settings'"
echo "django.setup()"
echo "----------------------------------------"
echo ""
echo "Or simply open: notebooks/django_setup.ipynb"
echo ""

# Set Django environment variable
export DJANGO_SETTINGS_MODULE=intelliwiz_config.settings
export PYTHONPATH=/home/satyam/Documents/DJANGO5/YOUTILITY3:$PYTHONPATH

# Start JupyterLab
cd notebooks 2>/dev/null || mkdir notebooks && cd notebooks
jupyter lab