# Security & Facility Mentor - Operator Quick Reference Guide

**Version:** 1.0 (Phase 1 + 2 Complete)
**Last Updated:** October 4, 2025
**Audience:** Control Desk Operators, Security Supervisors, Client Managers

---

## 🎯 Quick Start

### Access the Scorecard
1. **Web UI:** `http://localhost:8000/helpbot/security_scorecard/`
2. **API:** `curl http://localhost:8000/helpbot/api/v1/scorecard/ -H "Authorization: Token <your-token>"`
3. **Chat:** Start HelpBot session with type "security_facility"

### Daily Workflow
1. **6:00 AM:** System auto-generates scorecards for all clients
2. **6:15 AM:** Review scorecard - check overall health status
3. **If RED:** Immediate action required - review violations
4. **If AMBER:** Plan fixes within 24 hours
5. **If GREEN:** Continue monitoring, routine operations

---

## 🚦 Understanding Status Colors

| Color | Status | Meaning | Action |
|-------|--------|---------|--------|
| 🟢 **GREEN** | Compliant | All targets met | Continue monitoring |
| 🟡 **AMBER** | Minor Issues | Some targets missed | Review & fix within 24h |
| 🔴 **RED** | Critical | Serious violations | Immediate action required |

---

## 📊 The 7 Non-Negotiable Pillars

### Pillar 1: Right Guard at Right Post
**What It Means:** Guards are scheduled correctly without conflicts or gaps

**GREEN:** Schedule health ≥90%
- All posts covered
- No schedule hotspots
- Optimal load distribution

**AMBER:** Schedule health 70-89%
- Minor scheduling conflicts
- Some load imbalances
- Action: Review schedule distribution

**RED:** Schedule health <70%
- Critical coverage gaps
- Major hotspots detected
- **Action:** Add relief guards, redistribute loads immediately

**Common Violations:**
- `SCHEDULE_HOTSPOT` - Too many tasks at same time

---

### Pillar 2: Supervise Relentlessly
**What It Means:** Guards complete mandatory tours and scan all checkpoints

**GREEN:** All tours complete, 100% checkpoint coverage
- All mandatory tours completed on time
- Checkpoint coverage ≥80%
- No overdue tours

**AMBER:** 1-2 tours delayed or low coverage
- Minor checkpoint coverage issues
- Action: Remind guards of tour requirements

**RED:** 3+ tour violations or critical delays
- Multiple tours overdue
- Critical checkpoint failures
- **Action:** Supervisor intervention required immediately

**Common Violations:**
- `TOUR_OVERDUE` - Tour not completed within grace period (default: 30 min)
- `CHECKPOINT_COVERAGE_LOW` - Average coverage <80%

---

### Pillar 3: 24/7 Control Desk
**What It Means:** Alerts are acknowledged and acted on within SLA

**GREEN:** All alerts acknowledged within SLA
- CRITICAL alerts ack'd ≤15 minutes
- HIGH alerts ack'd ≤30 minutes
- No stale alerts

**AMBER:** 1-2 SLA breaches, no CRITICAL delays
- Minor acknowledgment delays
- Action: Review control desk procedures

**RED:** Any CRITICAL alert SLA breach
- CRITICAL alert not ack'd in 15 min
- Multiple HIGH alert delays
- **Action:** Escalate to management, review staffing

**SLA Targets:**
- CRITICAL: ≤15 minutes
- HIGH: ≤30 minutes
- MEDIUM: ≤60 minutes

**Common Violations:**
- `ALERT_NOT_ACKNOWLEDGED` - Alert never acknowledged
- `ALERT_ACK_SLA_BREACH` - Late acknowledgment

---

### Pillar 4: Legal & Professional
**What It Means:** Compliance reports (PF/ESIC/UAN, payroll) generated on time

**GREEN:** All compliance reports current
- PEOPLEATTENDANCESUMMARY generated on check_date
- No missing reports

**AMBER:** 1 report delayed
- Action: Generate report immediately

**RED:** Multiple or never-generated reports
- **Action:** URGENT - Legal risk exposure, generate all reports

**Required Reports:**
- People Attendance Summary (payroll/compliance)
- Additional reports configurable per client

**Common Violations:**
- `COMPLIANCE_REPORT_MISSING` - Report not generated on expected date
- `COMPLIANCE_REPORT_NEVER_GENERATED` - Report never been run

---

### Pillar 5: Support the Field
**What It Means:** Guards receive uniforms, equipment, and support promptly

**GREEN:** All tickets resolved within 72 hours
- No overdue field support tickets
- Responsive logistics

**AMBER:** 1-3 tickets overdue
- Action: Prioritize ticket resolution

**RED:** >10 tickets overdue
- Guards lacking critical resources
- **Action:** Emergency resource allocation

**Ticket Age Thresholds:**
- <72 hours: Normal
- 72-120 hours: MEDIUM severity
- >120 hours: HIGH severity

**Common Violations:**
- `FIELD_SUPPORT_DELAYED` - Ticket open >72 hours

---

### Pillar 6: Record Everything
**What It Means:** Daily, weekly, monthly reports generated and delivered

**GREEN:** All reports current
- Daily reports generated on check_date
- No missing documentation

**AMBER:** 1-2 reports delayed
- Action: Check background task execution

**RED:** >5 reports missing
- Audit risk exposure
- **Action:** Review reporting automation

**Report Types Monitored:**
- Daily operational reports
- Weekly summaries
- Monthly analytics

**Common Violations:**
- `DAILY_REPORT_MISSING` - Expected daily report not generated

---

### Pillar 7: Respond to Emergencies
**What It Means:** Crisis events trigger immediate escalation and response

**GREEN:** Perfect emergency response
- All crisis tickets assigned within 5 minutes
- Escalation within 2 minutes if needed
- Zero delays

**RED:** ANY emergency delay detected
- Crisis ticket escalation >2 minutes
- Unassigned crisis ticket >5 minutes
- **Action:** Escalate to senior management - life safety risk
- **Note:** No AMBER state - emergency response is binary (perfect or failure)

**SLA Targets:**
- Crisis ticket assignment: ≤5 minutes
- Crisis ticket escalation: ≤2 minutes
- Response time: Immediate

**Common Violations:**
- `EMERGENCY_ESCALATION_DELAYED` - Escalation >2 min
- `EMERGENCY_TICKET_UNASSIGNED` - Crisis ticket unassigned >5 min

---

## 🚨 Violation Severity Interpretation

### CRITICAL (🔴 Immediate Action)
- **Life safety risk** or **legal liability**
- Examples: Emergency response delay, compliance report never generated
- **Action:** Drop everything, address immediately
- **Response Time:** <15 minutes
- **Escalation:** Automatic to on-call manager

### HIGH (🟠 Urgent)
- **Operational risk** or **SLA breach**
- Examples: Tour overdue, alert not ack'd, field support delayed
- **Action:** Address within 2 hours
- **Response Time:** <2 hours
- **Escalation:** Manual if not resolved in 4 hours

### MEDIUM (🟡 Important)
- **Process issue** or **minor breach**
- Examples: Report delayed, ticket aging, low checkpoint coverage
- **Action:** Address within 24 hours
- **Response Time:** <1 day
- **Escalation:** If pattern emerges (3+ occurrences)

### LOW (ℹ️ Informational)
- **Advisory** or **optimization opportunity**
- Examples: Schedule optimization suggestions
- **Action:** Note for planning, address when convenient
- **Response Time:** <1 week

---

## 💡 Interpreting Recommendations

### Types of Recommendations:

**1. Immediate Actions:**
- "URGENT: Multiple tour violations - supervisor intervention required"
- **Do:** Contact supervisor, assign to investigate violations
- **Timeline:** <1 hour

**2. Process Improvements:**
- "Distribute schedule loads to avoid worker contention"
- **Do:** Review schedule with operations manager
- **Timeline:** <1 week

**3. Preventive Measures:**
- "Improve checkpoint coverage - current 75%, required 80%"
- **Do:** Train guards on checkpoint scanning
- **Timeline:** <2 weeks

**4. Escalation Triggers:**
- "Escalate to senior management - life safety risk"
- **Do:** Immediately notify management, document incident
- **Timeline:** Immediate

---

## 🔧 Common Issues & Solutions

### Issue: Scorecard Shows RED but No Obvious Problem
**Investigation Steps:**
1. Click on RED pillar to see violations
2. Review violation descriptions
3. Check original data source (tours, alerts, tickets)
4. Verify timestamps and SLA calculations

**Common Causes:**
- Old violation from earlier in day (system catches it)
- SLA threshold configured too strictly
- Legitimate issue that wasn't noticed

**Solution:**
- Address the violation or adjust SLA if justified

---

### Issue: AMBER Status Persists Multiple Days
**Investigation Steps:**
1. Check if same violation or different each day
2. Review recommendations for root cause
3. Verify fixes were applied

**Common Causes:**
- Fix applied but not reflected in data
- Systematic issue (schedule design, understaffing)
- Configuration issue (wrong SLA threshold)

**Solution:**
- If systematic: Escalate to operations manager
- If data lag: Wait for next daily evaluation
- If config: Adjust TaskComplianceConfig

---

### Issue: Too Many Alerts Generated
**Investigation Steps:**
1. Check auto_escalated_alerts count in scorecard
2. Review alert severity distribution
3. Verify deduplication is working

**Common Causes:**
- Alert storm (many violations at once)
- Deduplication failure
- Overly strict SLA thresholds

**Solution:**
- Review SLA thresholds in TaskComplianceConfig
- Check AlertCorrelationService deduplication
- Consider adjusting severity levels

---

## 📈 Using the Scorecard for Performance Management

### Daily Review (Every Morning 6:15 AM):
1. Check overall health status
2. If RED: Address immediately
3. If AMBER: Add to daily task list
4. If GREEN: Note trends (are we staying GREEN?)

### Weekly Review (Every Monday):
1. Compare this week vs last week scores
2. Identify recurring violations (systematic issues)
3. Review recommendations that weren't addressed
4. Plan process improvements

### Monthly Review (First Monday of Month):
1. Average health score for the month
2. Pillar-by-pillar trend analysis
3. Client scorecard (if client-facing)
4. Update SLA thresholds based on performance

---

## 🎓 Training New Operators

### Day 1: Understanding the 7 Pillars
- Review this guide
- Understand what each pillar measures
- Learn GREEN/AMBER/RED criteria

### Day 2: Scorecard Interpretation
- Generate sample scorecards
- Practice violation drill-down
- Understand recommendations

### Day 3: Taking Action
- Address AMBER violations (supervised)
- Practice escalation procedures
- Document resolutions

### Week 1: Independent Operation
- Daily scorecard review (mentored)
- Handle RED violations (supervised)
- Weekly performance review

### Week 2: Full Independence
- Solo daily reviews
- Escalation decisions
- Process improvement suggestions

---

## 📞 Escalation Matrix

| Severity | Escalate To | When | How |
|----------|-------------|------|-----|
| **CRITICAL** | On-call Manager | Immediately | Phone call |
| **HIGH** | Day Supervisor | <2 hours | Email + Chat |
| **MEDIUM** | Operations Manager | <24 hours | Email |
| **LOW** | Weekly Review | Next meeting | Add to agenda |

---

## 🔗 Quick Links & Resources

**Documentation:**
- Full Implementation: `SECURITY_FACILITY_MENTOR_PHASE2_COMPLETE.md`
- Phase 1 Summary: `SECURITY_FACILITY_MENTOR_PHASE1_COMPLETE.md`
- API Reference: See Phase 2 doc, Section "API Reference"

**Key Files:**
- Service Logic: `apps/noc/security_intelligence/services/non_negotiables_service.py`
- Model: `apps/noc/security_intelligence/models/non_negotiables_scorecard.py`
- Celery Task: `background_tasks/non_negotiables_tasks.py`

**Management Commands:**
```bash
# Generate scorecard manually
python manage.py shell
>>> from apps.noc.security_intelligence.services import NonNegotiablesService
>>> service = NonNegotiablesService()
>>> scorecard = service.generate_scorecard(tenant, client)

# Run daily task manually
>>> from background_tasks.non_negotiables_tasks import evaluate_non_negotiables
>>> result = evaluate_non_negotiables.delay()
```

---

## 📋 Daily Checklist

### Morning (6:15 AM):
- [ ] Check overall health status
- [ ] Review any RED pillars
- [ ] Read violation descriptions
- [ ] Check auto-escalated alerts in NOC
- [ ] Action CRITICAL violations immediately

### Midday (12:00 PM):
- [ ] Re-check scorecard after morning actions
- [ ] Verify CRITICAL violations resolved
- [ ] Update AMBER violation status

### Evening (5:00 PM):
- [ ] Final scorecard check
- [ ] Document unresolved issues
- [ ] Handoff to night shift if RED/AMBER
- [ ] Prepare briefing for next day

---

## ❓ FAQs

**Q: How often is the scorecard updated?**
A: Daily at 6:00 AM automatically. Can be refreshed on-demand via API or web UI.

**Q: What happens if I see RED status?**
A: Check violations immediately, address CRITICAL items first, escalate if needed.

**Q: Can I change SLA thresholds?**
A: Yes, via TaskComplianceConfig model. Requires admin access.

**Q: Why is Pillar 7 always GREEN or RED (no AMBER)?**
A: Emergency response is binary - either perfect or failure. No middle ground for life safety.

**Q: How do I know if alerts were created?**
A: Check `auto_escalated_alerts` field in scorecard or view NOC alert dashboard.

**Q: Can I run scorecard for past dates?**
A: Yes, use `check_date` parameter: `/api/scorecard/?check_date=2025-10-03`

**Q: What if scorecard generation fails?**
A: Check logs, verify TaskComplianceConfig exists, contact support if persistent.

---

## 📞 Support Contacts

**Technical Issues:** Check logs at `/var/log/django/noc_security_intelligence.log`
**Configuration:** Contact NOC Administrator
**Training:** Review this guide and Phase 2 documentation
**Escalation:** Follow escalation matrix above

---

**🛡️ Protecting What Matters - The 7 Non-Negotiables, Monitored 24/7**
