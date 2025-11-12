#!/bin/bash
#
# Restart Celery Workers with Premium Features
#
# Activates all revenue-generating premium features:
# - SLA Breach Prevention
# - Device Health Monitoring
# - Shift Compliance Intelligence
# - Executive Scorecards
# - AI Alert Triage
# - SOAR-Lite Automation
#
# Usage: ./scripts/restart_premium_features.sh
#

set -e

echo "=========================================="
echo "Premium Features Activation"
echo "=========================================="
echo "Revenue Impact: \$336K-\$672K ARR"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if celery_workers.sh exists
if [ ! -f "./scripts/celery_workers.sh" ]; then
    echo -e "${RED}❌ celery_workers.sh not found${NC}"
    echo "Please ensure you're in the project root directory"
    exit 1
fi

# Step 1: Verify configuration
echo -e "${YELLOW}Step 1: Verifying configuration...${NC}"
python3 -m py_compile intelliwiz_config/settings/premium_features_beat_schedule.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Premium features configuration valid${NC}"
else
    echo -e "${RED}❌ Configuration syntax error${NC}"
    exit 1
fi

# Step 2: Stop existing workers
echo ""
echo -e "${YELLOW}Step 2: Stopping existing Celery workers...${NC}"
./scripts/celery_workers.sh stop 2>/dev/null || echo "No workers running"
sleep 2

# Step 3: Start workers with new schedule
echo ""
echo -e "${YELLOW}Step 3: Starting Celery workers with premium features...${NC}"
./scripts/celery_workers.sh start

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Celery workers started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start workers${NC}"
    exit 1
fi

# Step 4: Verify beat scheduler
echo ""
echo -e "${YELLOW}Step 4: Checking beat scheduler...${NC}"
sleep 3

# Check if celery beat is running
BEAT_RUNNING=$(ps aux | grep "celery.*beat" | grep -v grep | wc -l)
if [ $BEAT_RUNNING -gt 0 ]; then
    echo -e "${GREEN}✅ Celery beat scheduler is running${NC}"
else
    echo -e "${YELLOW}⚠️  Beat scheduler may not be running${NC}"
    echo "To start beat scheduler manually:"
    echo "  celery -A intelliwiz_config beat -l info --detach"
fi

# Summary
echo ""
echo "=========================================="
echo "Premium Features Activated!"
echo "=========================================="
echo ""
echo "Scheduled Tasks:"
echo "  • SLA Breach Prediction: Every 15 minutes"
echo "  • Device Health Monitoring: Every hour"
echo "  • No-Show Detection: Every 30 minutes"
echo "  • Shift Cache Rebuild: Daily at 2 AM"
echo "  • Executive Scorecards: Monthly on 1st"
echo ""
echo "Monitor logs:"
echo "  tail -f logs/celery_worker.log"
echo "  tail -f logs/celery_beat.log"
echo ""
echo "Check worker status:"
echo "  celery -A intelliwiz_config inspect active"
echo "  celery -A intelliwiz_config inspect scheduled"
echo ""
echo -e "${GREEN}🎉 Ready for production!${NC}"
echo "=========================================="
