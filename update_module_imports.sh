#!/bin/bash
# Update module-level imports from apps.onboarding

set -e

echo "Updating module-level imports..."

# Pattern 1: from apps.onboarding import models as om
# These files use om.Bt, om.TypeAssist, etc.
# We'll update to import from client_onboarding and core_onboarding directly

files_with_om=(
  "apps/core/widgets.py"
  "apps/peoples/admin/import_export_resources.py"
  "apps/peoples/admin/base.py"
  "apps/scheduler/import_export_resources.py"
  "apps/work_order_management/forms.py"
  "apps/work_order_management/admin.py"
  "apps/reports/forms.py"
)

for file in "${files_with_om[@]}"; do
  if [ -f "$file" ]; then
    echo "Updating $file..."
    sed -i '' \
      -e 's/from apps\.onboarding import models as om/from apps.client_onboarding import models as om_client\nfrom apps.core_onboarding import models as om_core/g' \
      -e 's/om\.Bt/om_client.Bt/g' \
      -e 's/om\.TypeAssist/om_core.TypeAssist/g' \
      -e 's/om\.GeofenceMaster/om_core.GeofenceMaster/g' \
      -e 's/om\.Shift/om_client.Shift/g' \
      -e 's/om\.Device/om_client.Device/g' \
      "$file"
  fi
done

# Pattern 2: apps.onboarding import models as on
if [ -f "apps/reports/views/base.py" ]; then
  echo "Updating apps/reports/views/base.py..."
  sed -i '' \
    -e 's/from apps\.onboarding import models as on/from apps.client_onboarding import models as on_client\nfrom apps.core_onboarding import models as on_core/g' \
    -e 's/\bon\.Bt/on_client.Bt/g' \
    -e 's/\bon\.TypeAssist/on_core.TypeAssist/g' \
    -e 's/\bon\.GeofenceMaster/on_core.GeofenceMaster/g' \
    "apps/reports/views/base.py"
fi

# Pattern 3: apps.onboarding import models as ob_models
if [ -f "apps/service/rest_service/views.py" ]; then
  echo "Updating apps/service/rest_service/views.py..."
  sed -i '' \
    -e 's/from apps\.onboarding import models as ob_models/from apps.client_onboarding import models as ob_models_client\nfrom apps.core_onboarding import models as ob_models_core/g' \
    -e 's/ob_models\.Bt/ob_models_client.Bt/g' \
    -e 's/ob_models\.TypeAssist/ob_models_core.TypeAssist/g' \
    "apps/service/rest_service/views.py"
fi

echo "✅ Module imports updated!"
echo ""
echo "Verification:"
remaining=$(grep -r "from apps\.onboarding import\|from apps\.onboarding\.models import" apps/ --include="*.py" | grep -v "client_onboarding\|site_onboarding\|people_onboarding\|core_onboarding\|apps/onboarding/\|apps/onboarding_api/" | wc -l)
echo "Remaining old imports: $remaining"
