#!/bin/bash
# Update all FK string references from old onboarding app to bounded contexts

set -e

echo "Updating FK references from 'onboarding.' to bounded contexts..."

# client_onboarding models: Bt, Shift, Device, Subscription
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e "s/'onboarding\.Bt'/'client_onboarding.Bt'/g" \
  -e "s/'onboarding\.bt'/'client_onboarding.bt'/g" \
  -e "s/'onboarding\.Shift'/'client_onboarding.Shift'/g" \
  -e "s/'onboarding\.shift'/'client_onboarding.shift'/g" \
  -e "s/'onboarding\.Device'/'client_onboarding.Device'/g" \
  -e "s/'onboarding\.device'/'client_onboarding.device'/g" \
  -e "s/'onboarding\.Subscription'/'client_onboarding.Subscription'/g" \
  -e "s/'onboarding\.subscription'/'client_onboarding.subscription'/g" \
  {} \;

# core_onboarding models: TypeAssist, GeofenceMaster, ConversationSession, OnboardingMedia, etc.
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e "s/'onboarding\.TypeAssist'/'core_onboarding.TypeAssist'/g" \
  -e "s/'onboarding\.typeassist'/'core_onboarding.typeassist'/g" \
  -e "s/'onboarding\.GeofenceMaster'/'core_onboarding.GeofenceMaster'/g" \
  -e "s/'onboarding\.geofencemaster'/'core_onboarding.geofencemaster'/g" \
  -e "s/'onboarding\.ConversationSession'/'core_onboarding.ConversationSession'/g" \
  -e "s/'onboarding\.conversationsession'/'core_onboarding.conversationsession'/g" \
  -e "s/'onboarding\.OnboardingMedia'/'core_onboarding.OnboardingMedia'/g" \
  -e "s/'onboarding\.onboardingmedia'/'core_onboarding.onboardingmedia'/g" \
  -e "s/'onboarding\.OnboardingObservation'/'core_onboarding.OnboardingObservation'/g" \
  -e "s/'onboarding\.LLMRecommendation'/'core_onboarding.LLMRecommendation'/g" \
  -e "s/'onboarding\.AuthoritativeKnowledge'/'core_onboarding.AuthoritativeKnowledge'/g" \
  {} \;

# site_onboarding models: OnboardingSite, OnboardingZone, Asset, Checkpoint, etc.
find apps/ -name "*.py" -type f -exec sed -i '' \
  -e "s/'onboarding\.OnboardingSite'/'site_onboarding.OnboardingSite'/g" \
  -e "s/'onboarding\.onboardingsite'/'site_onboarding.onboardingsite'/g" \
  -e "s/'onboarding\.OnboardingZone'/'site_onboarding.OnboardingZone'/g" \
  -e "s/'onboarding\.Asset'/'site_onboarding.Asset'/g" \
  -e "s/'onboarding\.Checkpoint'/'site_onboarding.Checkpoint'/g" \
  -e "s/'onboarding\.MeterPoint'/'site_onboarding.MeterPoint'/g" \
  -e "s/'onboarding\.SOP'/'site_onboarding.SOP'/g" \
  -e "s/'onboarding\.CoveragePlan'/'site_onboarding.CoveragePlan'/g" \
  -e "s/'onboarding\.SitePhoto'/'site_onboarding.SitePhoto'/g" \
  -e "s/'onboarding\.SiteVideo'/'site_onboarding.SiteVideo'/g" \
  {} \;

echo "✅ FK string references updated!"
echo ""
echo "Verification:"
remaining=$(grep -r "'onboarding\." apps/ --include="*.py" | grep -v "client_onboarding\|site_onboarding\|people_onboarding\|core_onboarding" | wc -l)
echo "Remaining old references: $remaining"
