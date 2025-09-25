#!/bin/bash
# Set local environment variables for report generation

export ONDEMAND_REPORTS_GENERATED="/home/satyam/Documents/DJANGO5/YOUTILITY3/ondemand_reports"
export TEMP_REPORTS_GENERATED="/home/satyam/Documents/DJANGO5/YOUTILITY3/tmp_reports"

echo "Report paths set:"
echo "  ONDEMAND_REPORTS_GENERATED=$ONDEMAND_REPORTS_GENERATED"
echo "  TEMP_REPORTS_GENERATED=$TEMP_REPORTS_GENERATED"

# Create directories if they don't exist
mkdir -p "$ONDEMAND_REPORTS_GENERATED"
mkdir -p "$TEMP_REPORTS_GENERATED"

echo ""
echo "Directories created. Now run:"
echo "  python manage.py runserver"