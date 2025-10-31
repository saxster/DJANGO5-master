"""
JupyterLab configuration for Django project
"""
import os
import sys

# Configuration for JupyterLab
c = get_config()

# Set notebook directory
c.ServerApp.root_dir = './notebooks'

# Add startup code for new kernels
startup_code = """
import os
import sys

# Add project directory to path
project_dir = os.path.dirname(os.getcwd())
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings.development")

try:
    import django
    django.setup()
    print("✅ Django environment loaded!")
except Exception as e:
    print(f"⚠️ Django setup failed: {e}")
"""

# Create custom kernel with Django pre-loaded
import os
os.makedirs('notebooks', exist_ok=True)
