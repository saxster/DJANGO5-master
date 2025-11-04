#!/bin/bash
# Update non-model imports from apps.onboarding

set -e

echo "Updating non-model imports..."

# Update BtManager imports (moved to client_onboarding)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.managers import BtManager/from apps.client_onboarding.managers import BtManager/g' \
  -e 's/from apps\.onboarding\.bt_manager_orm import BtManagerORM/from apps.client_onboarding.managers import BtManagerORM/g' \
  {} \;

# Update TypeAssistForm (moved to core_onboarding)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.forms import TypeAssistForm/from apps.core_onboarding.forms import TypeAssistForm/g' \
  {} \;

# Update BusinessUnitViewSet (moved to client_onboarding)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.api\.viewsets import BusinessUnitViewSet/from apps.client_onboarding.api.viewsets import BusinessUnitViewSet/g' \
  {} \;

echo "✅ Non-model imports updated!"
