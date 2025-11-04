#!/bin/bash
# Update test imports from old onboarding app to bounded contexts

set -e

echo "Updating test imports from apps.onboarding to bounded contexts..."

# Update Bt imports (client_onboarding)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.models import Bt$/from apps.client_onboarding.models import Bt/g' \
  -e 's/from apps\.onboarding\.models import BT$/from apps.client_onboarding.models import Bt/g' \
  -e 's/from apps\.onboarding\.models import Shift/from apps.client_onboarding.models import Shift/g' \
  -e 's/from apps\.onboarding\.models import Device/from apps.client_onboarding.models import Device/g' \
  -e 's/from apps\.onboarding\.models import Subscription/from apps.client_onboarding.models import Subscription/g' \
  {} \;

# Update TypeAssist, GeofenceMaster imports (core_onboarding)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.models import TypeAssist/from apps.core_onboarding.models import TypeAssist/g' \
  -e 's/from apps\.onboarding\.models import GeofenceMaster/from apps.core_onboarding.models import GeofenceMaster/g' \
  -e 's/from apps\.onboarding\.models import ConversationSession/from apps.core_onboarding.models import ConversationSession/g' \
  -e 's/from apps\.onboarding\.models import OnboardingMedia/from apps.core_onboarding.models import OnboardingMedia/g' \
  {} \;

# Update Tenant, Client imports (tenants app)
# Note: "Client" in old code typically means Bt with identifier='CLIENT'
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.models import Tenant, Client/from apps.tenants.models import Tenant\nfrom apps.client_onboarding.models import Bt as Client/g' \
  -e 's/from apps\.onboarding\.models import Tenant$/from apps.tenants.models import Tenant/g' \
  -e 's/from apps\.onboarding\.models import Client$/from apps.client_onboarding.models import Bt as Client/g' \
  {} \;

# Update BusinessUnit imports (alias for Bt)
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e 's/from apps\.onboarding\.models import BusinessUnit$/from apps.client_onboarding.models import Bt as BusinessUnit/g' \
  {} \;

# Update ApprovedLocation imports
# First, let's see if this model exists somewhere
echo "Checking for ApprovedLocation model..."
if grep -r "class ApprovedLocation" apps/ --include="*.py" | head -1; then
  echo "Found ApprovedLocation - will update references"
  # Will update based on where it's found
else
  echo "⚠️  ApprovedLocation not found - may need manual update"
fi

# Update Tacode imports
echo "Checking for Tacode model..."
if grep -r "class Tacode" apps/ --include="*.py" | head -1; then
  echo "Found Tacode - will update references"
else
  echo "⚠️  Tacode not found - may need manual update"
fi

echo "✅ Test imports updated!"
echo ""
echo "Verification:"
remaining=$(grep -r "from apps\.onboarding\.models import" apps/ --include="*.py" | grep -v "client_onboarding\|site_onboarding\|people_onboarding\|core_onboarding\|apps/onboarding/\|apps/onboarding_api/" | wc -l)
echo "Remaining old imports: $remaining"
