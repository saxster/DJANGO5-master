# Fraud Detection Operations Guide for Managers

**Audience**: Managers, Supervisors, HR Personnel
**Purpose**: How to handle fraud alerts and investigate suspicious attendance
**Updated**: November 3, 2025

---

## 📋 OVERVIEW

The attendance system now includes AI-powered fraud detection that automatically flags suspicious activity. This guide explains what alerts mean and how to investigate them.

---

## 🚨 UNDERSTANDING FRAUD ALERTS

### Alert Severity Levels

| Severity | Risk Score | What It Means | Action Required |
|----------|------------|---------------|-----------------|
| **CRITICAL** | 80-100 | Very high confidence fraud | Immediate investigation + block attendance |
| **HIGH** | 60-79 | Likely fraudulent | Investigate before approving |
| **MEDIUM** | 40-59 | Unusual but may be legitimate | Monitor and verify |
| **LOW** | 20-39 | Minor deviation from normal | Awareness only |

### Common Alert Types

1. **BUDDY_PUNCHING**
   - **What**: One employee clocking in for another
   - **Indicators**: Device sharing, photo mismatch, multiple employees same device
   - **Example**: Employee A's device used to clock in Employee B

2. **GPS_SPOOFING**
   - **What**: Fake GPS location
   - **Indicators**: (0,0) coordinates, impossible accuracy, location jumps
   - **Example**: GPS shows (0,0) or perfect 1m accuracy (unrealistic)

3. **IMPOSSIBLE_TRAVEL**
   - **What**: Employee couldn't physically travel between locations in time
   - **Indicators**: Velocity exceeds physical limits
   - **Example**: 100 miles in 30 minutes (200+ mph)

4. **DEVICE_SHARING**
   - **What**: Same device used by multiple employees
   - **Indicators**: Device ID used by 2+ people within 30 minutes
   - **Example**: Device-123 used by Alice at 9:00 AM, Bob at 9:15 AM

5. **UNUSUAL_PATTERN**
   - **What**: Employee behaving differently than normal
   - **Indicators**: Different time, location, or device than baseline
   - **Example**: Employee normally works 9-5 but clocks in at 2 AM

---

## 📊 HOW TO ACCESS FRAUD ALERTS

### Via Dashboard

1. Navigate to: `/attendance/fraud-alerts/`
2. Filter by:
   - Severity (CRITICAL, HIGH, MEDIUM, LOW)
   - Status (PENDING, INVESTIGATING, RESOLVED)
   - Employee
   - Date range

### Via API

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  "https://your-domain.com/api/v1/attendance/audit-logs/?is_suspicious=true"
```

### Email Notifications

CRITICAL and HIGH severity alerts automatically email the employee's manager.

---

## 🔍 HOW TO INVESTIGATE AN ALERT

### Step 1: Review Alert Details

Click on the alert to see:
- **Employee**: Who triggered the alert
- **Attendance Record**: When and where
- **Fraud Score**: 0-1 scale (higher = more suspicious)
- **Anomalies Detected**: List of suspicious patterns
- **Evidence**: Detailed analysis from each detector

### Step 2: Check Historical Pattern

**Questions to Ask:**
- Has this employee triggered alerts before?
- What's their baseline behavior?
- Is there a legitimate explanation?

**Check:**
```
User Activity → View Last 30 Days
Pattern Analysis → Check typical times/locations/devices
```

### Step 3: Verify with Employee

**For LOW/MEDIUM Alerts:**
- Send email/message: "We noticed unusual attendance on [date]. Can you confirm?"
- Examples:
  - "You clocked in at 2 AM. Were you scheduled for night shift?"
  - "You checked in from a new location. Were you assigned to a different site?"

**For HIGH/CRITICAL Alerts:**
- **Require in-person or video verification**
- **Do not approve attendance until verified**

### Step 4: Make Decision

#### If Legitimate:
1. Click "Resolve as Legitimate"
2. Add notes explaining why (e.g., "Employee assigned to emergency night shift")
3. Mark alert as FALSE_POSITIVE if detection was incorrect
4. Approve attendance

#### If Fraudulent:
1. Click "Resolve as Fraud"
2. Document evidence
3. Reject attendance
4. Follow company disciplinary procedures
5. Consider:
   - Warning
   - Suspension
   - Termination (for repeat offenses)

#### If Unsure:
1. Click "Escalate"
2. Assign to senior manager or HR
3. Request additional evidence from employee

---

## 📈 COMMON SCENARIOS & HOW TO HANDLE

### Scenario 1: Device Sharing Alert

**Alert**: "Device device-abc-123 shared between Alice and Bob"

**Investigation:**
1. Check time gap: If >4 hours, likely legitimate (employees on different shifts)
2. If <30 minutes, likely buddy punching
3. Ask both employees: "Were you at work at [time]?"
4. Check other evidence: Photos, GPS locations

**Resolution:**
- **Legitimate**: Different shifts using same company device → Resolve as legitimate
- **Fraud**: Buddy punching confirmed → Reject both attendances, document violation

### Scenario 2: Impossible Travel

**Alert**: "Traveled 50 miles in 15 minutes (200 mph)"

**Investigation:**
1. Check GPS accuracy: Poor accuracy can cause jumps
2. Check if GPS was disabled then re-enabled
3. Ask employee: "Where were you at [previous time] and [current time]?"

**Resolution:**
- **GPS Error**: Legitimate but poor GPS → Resolve as legitimate, note GPS issue
- **Spoofing**: Employee using fake GPS → Reject attendance, investigate fraud

### Scenario 3: Unusual Time (2 AM Check-In)

**Alert**: "Check-in at 2:00 AM (typical: 9:00 AM)"

**Investigation:**
1. Check schedule: Was employee assigned night shift?
2. Check previous alerts: Is this a pattern?
3. Verify with scheduling system

**Resolution:**
- **Scheduled Night Shift**: Legitimate → Resolve, update employee baseline
- **Unauthorized**: Not scheduled → Investigate why employee was working

### Scenario 4: Photo Mismatch

**Alert**: "Photo does not match enrolled template (confidence: 0.35)"

**Investigation:**
1. Review captured photo quality
2. Check if employee changed appearance (haircut, glasses, facial hair)
3. Compare with recent photos

**Resolution:**
- **Appearance Change**: Re-enroll biometric template, resolve as legitimate
- **Different Person**: Likely buddy punching → Reject, investigate fraud

---

## 📊 FRAUD DETECTION METRICS

### Dashboard Metrics

Monitor these metrics weekly:

1. **Alert Volume**: Number of alerts per week
   - **Normal**: 5-10 alerts per 1000 check-ins
   - **High**: >20 alerts per 1000 check-ins
   - **Action**: If high, review fraud thresholds

2. **False Positive Rate**: Alerts marked as false positives
   - **Target**: <10%
   - **Action**: If >20%, retrain baselines or adjust thresholds

3. **Resolution Time**: Time from alert to resolution
   - **Target**: <24 hours for HIGH/CRITICAL
   - **Action**: If slow, assign more investigators or automate

4. **Confirmed Fraud Rate**: Alerts confirmed as actual fraud
   - **Typical**: 20-40% of alerts are real fraud
   - **Action**: Track patterns to identify repeat offenders

---

## ⚙️ MANAGING FALSE POSITIVES

### Common False Positive Causes

1. **Insufficient Baseline**: Employee has <30 attendance records
   - **Solution**: Wait for more data, approve manually in meantime

2. **Schedule Changes**: Employee moved to different shift
   - **Solution**: Mark as legitimate, baseline will adapt

3. **New Assignment**: Employee assigned to new site
   - **Solution**: Mark as legitimate, new location will be learned

4. **GPS Accuracy Issues**: Rural areas with poor GPS
   - **Solution**: Note GPS issues, consider increasing accuracy threshold for that site

### Improving Detection Accuracy

**If Too Many False Positives:**
1. Adjust thresholds: Increase `FRAUD_RISK_HIGH_THRESHOLD` from 0.6 to 0.7
2. Retrain baselines: Run `python manage.py train_fraud_baselines --force-retrain`
3. Mark false positives: System learns from your feedback

**If Missing Real Fraud:**
1. Lower thresholds: Decrease thresholds to catch more
2. Review dismissed alerts: Check if fraud was missed
3. Enable additional detectors: Enable stricter rules

---

## 📋 INVESTIGATION CHECKLIST

Use this checklist for each alert:

### Basic Information
- [ ] Employee name and ID
- [ ] Date and time of attendance
- [ ] Alert type and severity
- [ ] Fraud score and risk level

### Evidence Review
- [ ] Anomalies detected (list each one)
- [ ] Photo captured? Quality acceptable?
- [ ] GPS location reasonable?
- [ ] Device recognized?
- [ ] Time matches schedule?

### Historical Context
- [ ] Check employee's attendance history (last 30 days)
- [ ] Check for previous fraud alerts
- [ ] Review employee's typical patterns
- [ ] Check if recent schedule changes

### Verification
- [ ] Contact employee for explanation
- [ ] Verify with scheduling system
- [ ] Check with other managers/witnesses
- [ ] Review any additional evidence

### Decision
- [ ] Decision made: LEGITIMATE / FRAUD / ESCALATE
- [ ] Notes documented
- [ ] Employee notified of outcome
- [ ] Attendance approved or rejected
- [ ] If fraud: Disciplinary action initiated

---

## 🔧 MANAGER TOOLS & COMMANDS

### View Employee's Typical Pattern

```
Dashboard → Employees → [Select Employee] → Behavior Profile
```

Shows:
- Typical check-in time
- Typical locations
- Typical devices
- Work days pattern

### View Employee's Audit Trail

```
Dashboard → Audit Logs → Filter by Employee
```

Shows:
- Who accessed employee's attendance data
- When and from where
- What changes were made

### Export Fraud Report

```
Dashboard → Reports → Fraud Detection Report
Date Range: [Start] to [End]
```

Generates CSV with:
- All fraud alerts
- Resolution status
- Fraud types
- Employees involved

---

## 🎓 TRAINING SCENARIOS

### Training Scenario 1: Legitimate Alert

**Situation**: Employee John triggers HIGH alert for unusual time (6 PM instead of 9 AM)

**Investigation**:
- Check schedule: John was assigned to cover evening shift
- No other anomalies
- John confirms he was scheduled

**Action**:
- Resolve as LEGITIMATE
- Add note: "Covering evening shift for sick colleague"
- Approve attendance
- **Result**: System learns evening shifts are normal for John

### Training Scenario 2: Confirmed Fraud

**Situation**: Employee Sarah triggers CRITICAL alert for device sharing

**Investigation**:
- Device-789 used by Sarah at 9:00 AM and Mike at 9:05 AM
- Sarah's GPS: Office building
- Mike's GPS: Same office building
- Photos: Sarah's photo looks like Mike

**Action**:
- Resolve as FRAUD_CONFIRMED
- Reject both attendances
- Document: "Mike clocked in Sarah using her device"
- Initiate disciplinary process

**Result**: Both employees flagged for monitoring

---

## 💡 BEST PRACTICES

### DO:
- ✅ Investigate all CRITICAL and HIGH alerts within 24 hours
- ✅ Document your investigation notes
- ✅ Communicate with employees about alerts
- ✅ Look for patterns (repeat offenders)
- ✅ Update baselines after legitimate pattern changes
- ✅ Provide feedback (mark false positives)

### DON'T:
- ❌ Ignore alerts (they're there for a reason)
- ❌ Auto-approve without investigation
- ❌ Assume all alerts are fraud (many are legitimate)
- ❌ Punish employees for false positives
- ❌ Disable fraud detection (fix thresholds instead)

---

## 📞 ESCALATION & SUPPORT

### When to Escalate

Escalate to HR or Security if:
- Repeated fraud by same employee (3+ incidents)
- Organized fraud (multiple employees colluding)
- Security concerns (unauthorized site access)
- System issues (many false positives)

### Support Contacts

- **Technical Issues**: IT Helpdesk
- **System Configuration**: System Administrator
- **Policy Questions**: HR Department
- **Security Concerns**: Security Team

---

## 📊 WEEKLY MANAGER CHECKLIST

Every Monday:
- [ ] Review last week's fraud alerts
- [ ] Check unresolved alerts (>24 hours old)
- [ ] Review team's fraud alert trends
- [ ] Investigate any patterns or repeat offenders
- [ ] Update team on any attendance policy changes

Every Month:
- [ ] Review false positive rate (target: <10%)
- [ ] Check if any employees need baseline retraining
- [ ] Review overall fraud detection effectiveness
- [ ] Provide feedback to improve detection accuracy

---

## 🎯 SUCCESS METRICS

**Good Fraud Detection Program:**
- Alert resolution time: <24 hours average
- False positive rate: <15%
- Confirmed fraud detection rate: >80%
- Employee satisfaction: No complaints about unfair alerts
- Time theft prevention: <2% of workforce

**If metrics are off:**
- Too many alerts: Adjust thresholds or retrain baselines
- Too few alerts: Lower thresholds or enable stricter rules
- High false positives: Manager training or threshold adjustment needed

---

**Questions?** Contact your system administrator or HR department.

**This guide empowers you to effectively use fraud detection while being fair to employees.**
