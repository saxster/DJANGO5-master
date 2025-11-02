#!/bin/bash
# Batch update onboarding URL references to Django Admin URLs
# This script replaces all placeholder onboarding URLs with Django Admin equivalents

set -e

echo "Starting batch URL replacement..."

# Define template directories
FRONTEND_TEMPLATES="/Users/amar/Desktop/MyCode/DJANGO5-master/frontend/templates"

# Function to replace URLs in files
replace_urls() {
    local file="$1"
    echo "Processing: $file"

    # Backup original file
    cp "$file" "$file.bak"

    # Replace onboarding URLs with Django Admin URLs
    # Using both {% url %} and {{ url() }} syntaxes

    # TypeAssist
    sed -i '' "s|{% url 'onboarding:typeassist' %}[^\"]*|{% url 'admin:onboarding_typeassist_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:typeassist') }}[^\"]*|{{ url('admin:onboarding_typeassist_changelist') }}|g" "$file"

    # Shift
    sed -i '' "s|{% url 'onboarding:shift' %}[^\"]*|{% url 'admin:onboarding_shift_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:shift') }}[^\"]*|{{ url('admin:onboarding_shift_changelist') }}|g" "$file"

    # Geofence
    sed -i '' "s|{% url 'onboarding:geofence' %}[^\"]*|{% url 'admin:onboarding_geofencemaster_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:geofence') }}[^\"]*|{{ url('admin:onboarding_geofencemaster_changelist') }}|g" "$file"

    # Client
    sed -i '' "s|{% url 'onboarding:client' %}[^\"]*|{% url 'admin:onboarding_client_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:client') }}[^\"]*|{{ url('admin:onboarding_client_changelist') }}|g" "$file"

    # Business Unit (bu)
    sed -i '' "s|{% url 'onboarding:bu' %}[^\"]*|{% url 'admin:onboarding_bt_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:bu') }}[^\"]*|{{ url('admin:onboarding_bt_changelist') }}|g" "$file"
    sed -i '' "s|{% url 'onboarding:bu_list' %}[^\"]*|{% url 'admin:onboarding_bt_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:bu_list') }}[^\"]*|{{ url('admin:onboarding_bt_changelist') }}|g" "$file"

    # Contract
    sed -i '' "s|{% url 'onboarding:contract' %}[^\"]*|{% url 'admin:onboarding_contract_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:contract') }}[^\"]*|{{ url('admin:onboarding_contract_changelist') }}|g" "$file"

    # Import/Export
    sed -i '' "s|{% url 'onboarding:import' %}[^\"]*|{% url 'admin:onboarding_typeassist_import' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:import') }}[^\"]*|{{ url('admin:onboarding_typeassist_import') }}|g" "$file"
    sed -i '' "s|{% url 'onboarding:import_update' %}[^\"]*|{% url 'admin:onboarding_typeassist_import' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:import_update') }}[^\"]*|{{ url('admin:onboarding_typeassist_import') }}|g" "$file"

    # Editor TypeAssist
    sed -i '' "s|{% url 'onboarding:editortypeassist' %}[^\"]*|{% url 'admin:onboarding_typeassist_changelist' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:editortypeassist') }}[^\"]*|{{ url('admin:onboarding_typeassist_changelist') }}|g" "$file"

    # File Upload
    sed -i '' "s|{% url 'onboarding:file_upload' %}[^\"]*|{% url 'admin:onboarding_typeassist_import' %}|g" "$file"
    sed -i '' "s|{{ url('onboarding:file_upload') }}[^\"]*|{{ url('admin:onboarding_typeassist_import') }}|g" "$file"

    echo "Completed: $file"
}

# Find and process all template files with onboarding URL references
find "$FRONTEND_TEMPLATES" -type f -name "*.html" | while read file; do
    if grep -q "onboarding:typeassist\|onboarding:shift\|onboarding:geofence\|onboarding:import\|onboarding:client\|onboarding:bu\|onboarding:contract\|onboarding:import_update\|onboarding:file_upload\|onboarding:editortypeassist" "$file"; then
        replace_urls "$file"
    fi
done

echo "Batch URL replacement complete!"
echo "Backup files created with .bak extension"
echo ""
echo "To verify changes, run:"
echo "  grep -r 'onboarding:typeassist\|onboarding:shift\|onboarding:geofence' $FRONTEND_TEMPLATES --include='*.html'"
echo ""
echo "To remove backups if changes look good:"
echo "  find $FRONTEND_TEMPLATES -name '*.bak' -delete"
