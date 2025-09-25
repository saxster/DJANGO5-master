# Site Map & Information Architecture

## Visual Site Structure

```
YOUTILITY3 Application
│
├── 🏠 Dashboard [/dashboard/]
│   └── Main overview page with widgets and metrics
│
├── 📋 Operations [/operations/]
│   ├── Tasks [/operations/tasks/]
│   │   ├── List all tasks
│   │   ├── Create new task
│   │   └── Task details/edit
│   ├── Tours [/operations/tours/]
│   │   ├── Internal tours
│   │   ├── External tours
│   │   └── Adhoc tours
│   ├── Schedules [/operations/schedules/]
│   │   ├── Task schedules
│   │   ├── Tour schedules
│   │   └── PPM schedules
│   └── Work Orders [/operations/work-orders/]
│       ├── Work order list
│       ├── Work permits
│       └── Vendor performance
│
├── 🏭 Assets [/assets/]
│   ├── Management [/assets/]
│   │   ├── Asset list
│   │   ├── Create/edit assets
│   │   └── QR codes
│   ├── Maintenance [/assets/maintenance/]
│   │   ├── Maintenance logs
│   │   ├── PPM planning
│   │   └── Asset audit
│   ├── Comparisons [/assets/compare/]
│   │   ├── Asset comparison
│   │   └── Parameter comparison
│   └── Locations [/assets/locations/]
│       ├── Location list
│       ├── Checkpoints
│       └── Geofences
│
├── 👥 People [/people/]
│   ├── Directory [/people/]
│   │   ├── Employee list
│   │   ├── Employee details
│   │   └── Capabilities
│   ├── Attendance [/people/attendance/]
│   │   ├── Attendance records
│   │   ├── Time tracking
│   │   └── Leave management
│   ├── Tracking [/people/tracking/]
│   │   ├── Geofence tracking
│   │   ├── Mobile user logs
│   │   └── People near assets
│   ├── Groups [/people/groups/]
│   │   └── People groups management
│   └── Site Groups [/people/site-groups/]
│       └── Site group assignments
│
├── 🎫 Help Desk [/help-desk/]
│   ├── Tickets [/help-desk/tickets/]
│   │   ├── Ticket list
│   │   ├── Create ticket
│   │   └── Ticket details
│   ├── Escalations [/help-desk/escalations/]
│   │   └── Escalation matrix
│   ├── Requests [/help-desk/requests/]
│   │   ├── Posting orders
│   │   └── Uniform requests
│   └── SLA Management [/help-desk/sla/]
│
├── 📊 Reports [/reports/]
│   ├── Download [/reports/download/]
│   │   └── Report generation wizard
│   ├── Schedule [/reports/schedule/]
│   │   └── Automated report scheduling
│   ├── Site Reports [/reports/site-reports/]
│   ├── Incident Reports [/reports/incident-reports/]
│   └── Custom Reports [/reports/custom/]
│
├── ⚙️ Administration [/admin/]
│   ├── Organization [/admin/organization/]
│   │   ├── Business units
│   │   ├── Contracts
│   │   └── Clients
│   ├── System [/admin/system/]
│   │   ├── Type definitions
│   │   ├── Questions/Checklists
│   │   ├── Shifts
│   │   └── Features
│   ├── Data [/admin/data/]
│   │   ├── Import
│   │   ├── Export
│   │   └── Bulk update
│   └── Security [/admin/security/]
│       ├── User management
│       ├── Roles & permissions
│       └── Audit logs
│
└── 🔐 Super Admin [/super-admin/]
    ├── Capabilities
    ├── Client management
    ├── Feature flags
    └── Django admin panel
```

## Navigation Flow

### Primary User Journeys

#### 1. Daily Operations Flow
```
Dashboard → Operations → Tasks → Create Task → Assign → Complete
         ↓
    View KPIs → Reports → Download daily report
```

#### 2. Asset Management Flow
```
Assets → Asset List → Select Asset → View Details
    ↓                                      ↓
Create QR Code                    Schedule Maintenance
    ↓                                      ↓
Print Labels                      Create Work Order
```

#### 3. People Management Flow
```
People → Directory → Select Employee → View Profile
    ↓                                      ↓
Attendance Records                    Assign to Group
    ↓                                      ↓
Generate Report                      Update Permissions
```

## Page Hierarchy & Templates

### Template Inheritance Structure
```
base.html
├── base_list.html
│   ├── people/people_list.html
│   ├── activity/asset_list.html
│   ├── schedhuler/task_list.html
│   └── reports/report_list.html
├── base_form.html
│   ├── people/people_form.html
│   ├── activity/asset_form.html
│   ├── schedhuler/task_form.html
│   └── onboarding/bu_form.html
├── base_detail.html
│   ├── people/people_detail.html
│   ├── activity/asset_detail.html
│   └── schedhuler/task_detail.html
└── base_dashboard.html
    └── dashboard/main_dashboard.html
```

## Access Control Matrix

| Section | Public | User | Manager | Admin | Super Admin |
|---------|--------|------|---------|-------|-------------|
| Dashboard | ❌ | ✅ | ✅ | ✅ | ✅ |
| Operations | ❌ | View | Full | Full | Full |
| Assets | ❌ | View | Edit | Full | Full |
| People | ❌ | Self | Team | Full | Full |
| Help Desk | ❌ | Create | Manage | Full | Full |
| Reports | ❌ | Basic | Advanced | Full | Full |
| Admin | ❌ | ❌ | ❌ | ✅ | ✅ |
| Super Admin | ❌ | ❌ | ❌ | ❌ | ✅ |

## Mobile Navigation Structure

For mobile devices, the navigation collapses into a hamburger menu with these priorities:

1. **Quick Actions** (floating action button)
   - Create Task
   - Report Issue
   - Check In/Out

2. **Bottom Navigation** (most used)
   - Dashboard
   - Tasks
   - Assets
   - Reports
   - More

3. **Hamburger Menu** (complete navigation)
   - Full site structure as listed above

## Search Architecture

Global search indexes these entities:
- People (name, email, employee ID)
- Assets (name, code, location)
- Tasks (title, description, status)
- Tickets (number, subject, status)
- Reports (name, type, date)

## Performance Optimizations

1. **Lazy Loading**
   - Menu sections load on demand
   - Dashboard widgets load asynchronously
   - Large lists use pagination

2. **Caching Strategy**
   - Navigation structure cached per role
   - Dashboard data cached for 5 minutes
   - Report results cached for 1 hour

3. **Progressive Enhancement**
   - Core navigation works without JavaScript
   - Enhanced features added via JS
   - Offline support for critical paths