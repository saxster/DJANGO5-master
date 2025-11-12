"""
Management Command to Seed Admin Help Topics

Populates the database with user-friendly help content using simple,
non-technical language that's easy to understand.

Usage:
    python manage.py seed_admin_help
    python manage.py seed_admin_help --clear-existing
    python manage.py seed_admin_help --dry-run

Compliance:
- Rule #11: Specific exception handling
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core.models.admin_help import AdminHelpTopic
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


class Command(BaseCommand):
    """Seed admin help topics with friendly, user-focused content."""

    help = 'Populate admin help system with user-friendly content'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear all existing help topics before seeding'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without making changes'
        )

    def handle(self, *args, **options):
        if options['clear_existing'] and not options['dry_run']:
            self.stdout.write("Clearing existing help topics...")
            try:
                AdminHelpTopic.objects.all().delete()
                self.stdout.write(self.style.SUCCESS("✓ Cleared existing topics"))
            except DATABASE_EXCEPTIONS as e:
                self.stdout.write(
                    self.style.ERROR(f"✗ Failed to clear topics: {e}")
                )
                return

        help_topics = self.get_help_topics_data()

        try:
            with transaction.atomic():
                created_count = 0

                for topic_data in help_topics:
                    if options['dry_run']:
                        self.stdout.write(
                            f"DRY RUN: Would create '{topic_data['feature_name']}'"
                        )
                        continue

                    topic, created = AdminHelpTopic.objects.get_or_create(
                        category=topic_data['category'],
                        feature_name=topic_data['feature_name'],
                        defaults={
                            'short_description': topic_data['short_description'],
                            'detailed_explanation': topic_data['detailed_explanation'],
                            'use_cases': topic_data.get('use_cases', []),
                            'advantages': topic_data.get('advantages', []),
                            'how_to_use': topic_data.get('how_to_use', ''),
                            'video_url': topic_data.get('video_url', ''),
                            'keywords': topic_data.get('keywords', []),
                            'difficulty_level': topic_data.get('difficulty_level', 'beginner'),
                            'is_active': True,
                        }
                    )

                    if created:
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(f"✓ Created: {topic_data['feature_name']}")
                        )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"→ Already exists: {topic_data['feature_name']}")
                        )

            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nDRY RUN: Would create {len(help_topics)} topics"
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n✓ Successfully created {created_count} new help topics"
                    )
                )

        except DATABASE_EXCEPTIONS as e:
            self.stdout.write(
                self.style.ERROR(f"\n✗ Database error: {e}")
            )

    def get_help_topics_data(self):
        """Return help topics with friendly, user-focused language."""
        return [
            {
                'category': 'command_center',
                'feature_name': 'Quick Actions',
                'short_description': 'Do common tasks with just one click instead of navigating through multiple pages.',
                'detailed_explanation': '''Quick Actions are like shortcuts on your phone - they let you do things faster!
                
Instead of clicking through menus to do routine tasks, you can set up one-click buttons right on your dashboard. For example, "Approve All Pending Requests" or "Send Weekly Report" - tasks that normally take several clicks can be done with just one.

Think of it like having speed dial for your most common work tasks. You set it up once, then use it over and over to save time.''',
                'use_cases': [
                    'Approve multiple time-off requests at once instead of one by one',
                    'Send your daily report with one click instead of filling out forms',
                    'Mark all new notifications as read',
                    'Export this month\'s data to Excel',
                ],
                'advantages': [
                    'Save time on repetitive tasks',
                    'Reduce mistakes from clicking the wrong buttons',
                    'Get your work done faster',
                    'Less training needed for new team members',
                ],
                'how_to_use': '''1. Find the "Quick Actions" button at the top of your dashboard
2. Click "Add New Quick Action"
3. Choose what you want the button to do from the list
4. Give it a friendly name like "Send Daily Report"
5. Click "Save" and your new button appears on your dashboard

Now whenever you need to do that task, just click your Quick Action button!''',
                'keywords': ['playbook', 'automation', 'shortcut', 'one-click', 'fast', 'quick'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'views',
                'feature_name': 'My Saved Views',
                'short_description': 'Save your favorite filters and searches so you can find things quickly without setting them up every time.',
                'detailed_explanation': '''Have you ever spent time setting up the perfect filter to find exactly what you need, then had to do it all over again the next day?

My Saved Views lets you save those filters! It's like bookmarking your favorite searches. Once you set up a filter that works great, just save it with a name like "This Week's Tasks" or "Overdue Items" - then you can use it again and again with just one click.

No more re-typing dates, re-selecting options, or trying to remember exactly how you filtered things last time.''',
                'use_cases': [
                    'Save "This Week\'s Schedule" so you don\'t have to select dates every day',
                    'Create "My Team\'s Tasks" to quickly see what your team is working on',
                    'Set up "Urgent Items" to see high-priority work at a glance',
                    'Make "Completed This Month" to review what got done',
                ],
                'advantages': [
                    'No more repeating the same filter setup',
                    'Find what you need in seconds instead of minutes',
                    'Share useful views with your teammates',
                    'Consistent way to look at your data',
                ],
                'how_to_use': '''1. Set up your filters the way you like them (date range, status, etc.)
2. Click the "Save Current View" button at the top
3. Give it a memorable name like "This Month's Tasks"
4. Check "Share with team" if you want others to use it too
5. Click "Save"

Next time you need that view, just select it from the "My Saved Views" dropdown!''',
                'keywords': ['filter', 'search', 'bookmark', 'admin view', 'saved search'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'notifications',
                'feature_name': 'Priority Alerts',
                'short_description': 'Get notified before deadlines so you have time to fix issues instead of finding out too late.',
                'detailed_explanation': '''Nobody likes surprises when it comes to deadlines!

Priority Alerts watches your tasks and sends you friendly reminders before things become urgent. It's like having a helpful assistant who taps you on the shoulder and says "Hey, this is due soon - you might want to check on it."

Instead of missing deadlines and then scrambling to fix things, you get advance warning so you can handle issues calmly and on time.''',
                'use_cases': [
                    'Get notified 2 days before a project deadline',
                    'Warning when a task is taking longer than expected',
                    'Alert when approval requests are waiting too long',
                    'Heads up when inventory is running low',
                ],
                'advantages': [
                    'Never miss important deadlines',
                    'Time to fix problems before they become emergencies',
                    'Less stress and last-minute rushing',
                    'Better on-time completion rates',
                ],
                'how_to_use': '''1. Go to Settings → Notifications
2. Turn on "Priority Alerts"
3. Choose how much advance warning you want (1 day, 2 days, etc.)
4. Pick how you want to be notified (email, app notification, both)
5. Save your settings

Now you'll get helpful reminders before things become urgent!''',
                'keywords': ['alert', 'notification', 'deadline', 'sla', 'breach', 'reminder', 'warning'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'workflows',
                'feature_name': 'Smart Assignment',
                'short_description': 'Automatically send tasks to the right person based on their skills and availability.',
                'detailed_explanation': '''Tired of manually figuring out who should handle each new task?

Smart Assignment is like having a really good office manager who knows everyone's skills and workload. When a new task comes in, it automatically assigns it to the best person - someone who has the right skills and actually has time to do it.

No more guessing, no more overloading one person while others have free time. The system learns from your team's past work and gets smarter over time.''',
                'use_cases': [
                    'New support tickets go to whoever is available and knows that topic',
                    'Maintenance requests go to technicians with the right skills',
                    'Tasks are balanced so nobody gets overwhelmed',
                    'Emergency items go to the person on duty',
                ],
                'advantages': [
                    'Fair distribution of work across your team',
                    'Tasks get to the right expert faster',
                    'Less time managing assignments manually',
                    'Better team morale from balanced workloads',
                ],
                'how_to_use': '''1. Go to Settings → Smart Assignment
2. Set up team member skills and areas of expertise
3. Choose assignment rules (balance workload, match skills, etc.)
4. Turn on "Auto-assign new tasks"
5. Review and adjust assignments if needed

The system will now suggest or auto-assign tasks to the best person!''',
                'keywords': ['routing', 'assignment', 'distribution', 'intelligent', 'automatic'],
                'difficulty_level': 'intermediate',
            },
            {
                'category': 'approvals',
                'feature_name': 'Approval Requests',
                'short_description': 'Submit and track approval requests without chasing people down or losing track of who approved what.',
                'detailed_explanation': '''Remember the days of emailing people for approval, then waiting and wondering if they saw it?

Approval Requests makes this super simple. You submit what needs approval, it goes to the right person automatically, and you can see exactly where it is in the process. No more "Did you get my email?" or "Who approved this?" questions.

You get notifications when it's approved, and everything is documented so you have a clear record. It's like having a really organized secretary handling all your approvals.''',
                'use_cases': [
                    'Get manager approval for time off requests',
                    'Submit purchase orders for finance approval',
                    'Request approval for schedule changes',
                    'Get sign-off on completed work',
                ],
                'advantages': [
                    'Clear tracking of all approval requests',
                    'No more lost or forgotten approvals',
                    'Automatic reminders if approval is delayed',
                    'Complete audit trail of who approved what and when',
                ],
                'how_to_use': '''1. Click "New Approval Request" on your dashboard
2. Choose what type of approval you need
3. Fill in the details (amount, dates, reason, etc.)
4. The system automatically sends it to the right approver
5. Track the status in "My Requests"

You'll get notified when it's approved or if they have questions!''',
                'keywords': ['approval', 'authorization', 'request', 'permission', 'sign-off'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'team',
                'feature_name': 'Activity Timeline',
                'short_description': 'See everything that happened with a project, person, or task - all in one place, like a story of what happened.',
                'detailed_explanation': '''Ever wonder "What happened with this project?" or "Who did what and when?"

Activity Timeline shows you the complete story of anything in the system. It's like reading a diary of everything that happened - who created it, who made changes, what was updated, when deadlines were extended, etc.

Instead of digging through emails and asking around, you just open the Activity Timeline and see the whole history at a glance. Perfect for understanding what happened or catching up on a project you've been away from.''',
                'use_cases': [
                    'See all changes made to a work order',
                    'Review what happened during an employee\'s shift',
                    'Track the history of a maintenance issue',
                    'Understand why a deadline was changed',
                ],
                'advantages': [
                    'Complete visibility into what happened',
                    'Quick catch-up on projects you missed',
                    'Better accountability and transparency',
                    'Easy to find when something changed and why',
                ],
                'how_to_use': '''1. Open any task, project, or person's profile
2. Click the "Activity Timeline" tab
3. Scroll through to see what happened
4. Use filters to show only certain types of activities
5. Click any entry to see full details

You can even export the timeline for reports or documentation!''',
                'keywords': ['history', 'timeline', 'activity', 'audit', 'changes', '360', 'entity'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'command_center',
                'feature_name': 'Team Dashboard',
                'short_description': 'See all your team\'s work in one place instead of checking multiple pages and systems.',
                'detailed_explanation': '''Wouldn't it be nice to see everything your team is working on without opening a dozen different pages?

Team Dashboard brings it all together in one screen. See who's working on what, what's due soon, what's overdue, what's completed - everything at a glance.

It's like having a bird's eye view of your whole operation. No more clicking around wondering if you're missing something important. Everything you need to manage your day is right there.''',
                'use_cases': [
                    'Morning check-in to see what your team has today',
                    'Quick status update for your manager',
                    'Spot tasks that need attention',
                    'See if anyone needs help with their workload',
                ],
                'advantages': [
                    'Everything in one place - no more switching between pages',
                    'Quickly spot issues before they become problems',
                    'Better team coordination and awareness',
                    'Save time on status meetings',
                ],
                'how_to_use': '''1. Click "Team Dashboard" in the main menu
2. Your team's work appears automatically
3. Use the filters to focus on what matters (today, urgent, by person, etc.)
4. Click any task to see details or make updates
5. Customize what you see with the "Dashboard Settings" button

Your dashboard remembers your preferences for next time!''',
                'keywords': ['dashboard', 'overview', 'queue', 'operations', 'unified', 'workload'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'reports',
                'feature_name': 'One-Click Reports',
                'short_description': 'Generate common reports instantly without setting up complicated filters or exporting data.',
                'detailed_explanation': '''Reports don't have to be complicated!

One-Click Reports are pre-built reports for the things you check regularly. Instead of setting up filters, choosing date ranges, and exporting data every time, just click the report you want and it's ready in seconds.

We've created the most common reports people need - you just click and get the information. Need a custom report? Set it up once and save it as your own One-Click Report.''',
                'use_cases': [
                    'Weekly performance summary for your team meeting',
                    'Monthly completion rates for upper management',
                    'Today\'s attendance at a glance',
                    'This quarter\'s budget vs. actual spending',
                ],
                'advantages': [
                    'Save hours of report preparation time',
                    'Consistent report format every time',
                    'No training needed - just click and go',
                    'Always use the latest data automatically',
                ],
                'how_to_use': '''1. Go to Reports → One-Click Reports
2. Browse the available reports or search by name
3. Click the report you want
4. It generates instantly with current data
5. Download as PDF or Excel if you need to share it

Create your own by clicking "Save as One-Click Report" on any custom report!''',
                'keywords': ['report', 'analytics', 'export', 'summary', 'statistics'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'scheduling',
                'feature_name': 'Easy Scheduling',
                'short_description': 'Create and manage schedules visually with drag-and-drop instead of filling out forms.',
                'detailed_explanation': '''Scheduling should be simple!

Easy Scheduling lets you create schedules by dragging and dropping, just like moving appointments in your calendar. See your whole team's schedule at once, spot conflicts instantly, and make changes in seconds.

No more complex forms or wondering if you double-booked someone. Just drag, drop, and you're done. The system warns you about conflicts and makes sure everyone gets their required breaks and days off.''',
                'use_cases': [
                    'Create next week\'s shift schedule in minutes',
                    'Swap shifts by dragging them to different people',
                    'See who\'s available to cover a last-minute absence',
                    'Plan schedules around known events and time off',
                ],
                'advantages': [
                    'Visual scheduling is faster and less error-prone',
                    'See conflicts before they become problems',
                    'Easy to make changes when plans shift',
                    'Team members can see their schedules on their phones',
                ],
                'how_to_use': '''1. Go to Scheduling → Calendar View
2. Click and drag to create a shift block
3. Drag it onto the person who should work that shift
4. Adjust the time by dragging the edges
5. Click "Publish Schedule" when ready

Team members get notified automatically and can view on their mobile app!''',
                'keywords': ['schedule', 'calendar', 'shift', 'roster', 'planning'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'settings',
                'feature_name': 'Simple Settings',
                'short_description': 'Customize how the system works for you with easy-to-understand options instead of technical configurations.',
                'detailed_explanation': '''We know settings can be overwhelming with lots of technical terms and confusing options.

Simple Settings organizes everything into plain English categories with helpful explanations. You don't need to be a tech expert - each setting explains what it does and when you'd want to use it.

Plus, we've already set good defaults, so you only need to change things that matter to your specific needs. Most people never touch 90% of the settings!''',
                'use_cases': [
                    'Turn on email notifications for urgent tasks',
                    'Set your working hours so tasks are scheduled correctly',
                    'Choose what appears on your dashboard',
                    'Set up automatic reminders for deadlines',
                ],
                'advantages': [
                    'No technical knowledge required',
                    'Can\'t accidentally break anything - safe to experiment',
                    'Changes take effect immediately so you can see what they do',
                    'Tooltips explain everything in simple language',
                ],
                'how_to_use': '''1. Click your name in the top right → Settings
2. Browse the categories (Notifications, Display, Preferences, etc.)
3. Hover over any option to see what it does
4. Make changes and click "Save"
5. See the changes right away in the system

Don't like it? Just change it back - nothing is permanent!''',
                'keywords': ['settings', 'preferences', 'configuration', 'customize', 'options'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'workflows',
                'feature_name': 'Automated Reminders',
                'short_description': 'Set up automatic reminders so you never forget important tasks or deadlines.',
                'detailed_explanation': '''We all forget things sometimes, especially when we're busy!

Automated Reminders are like having a personal assistant who remembers things for you. Set them up once, and you'll automatically get reminded about recurring tasks, upcoming deadlines, or anything that needs regular attention.

Perfect for those "oh no, I forgot!" moments that happen to everyone. Let the system remember so you can focus on getting work done.''',
                'use_cases': [
                    'Weekly reminder to submit timesheets',
                    'Monthly reminder to review team performance',
                    'Daily reminder to check the morning checklist',
                    'Reminder 3 days before equipment maintenance is due',
                ],
                'advantages': [
                    'Never forget recurring tasks',
                    'Reduce missed deadlines and rushed work',
                    'Build consistent habits and routines',
                    'Customize reminders for your schedule',
                ],
                'how_to_use': '''1. Go to any task or create a new one
2. Click "Add Reminder"
3. Choose when you want to be reminded (time and frequency)
4. Pick how to be notified (email, app notification, SMS)
5. Save it and forget it!

The system will remind you automatically - you don't have to remember!''',
                'keywords': ['reminder', 'notification', 'recurring', 'automatic', 'alert'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'team',
                'feature_name': 'Team Chat',
                'short_description': 'Quick messages with your team right in the system - no need to switch to email or another app.',
                'detailed_explanation': '''Sometimes you just need to ask a quick question or give a heads up to a teammate.

Team Chat lets you send quick messages without leaving what you're working on. It's built right into the system, so you can chat about a specific task, share updates, or ask questions - all in one place.

Everything is organized by task or project, so you can always find the conversation later. No more digging through emails trying to remember where someone said something important.''',
                'use_cases': [
                    'Quick question about a task without sending a formal email',
                    'Let someone know you completed something',
                    'Ask for help with an issue you\'re stuck on',
                    'Coordinate with teammates in real-time',
                ],
                'advantages': [
                    'Faster than email for quick communications',
                    'Everything stays organized by task/project',
                    'See when teammates read your messages',
                    'Works on desktop and mobile',
                ],
                'how_to_use': '''1. Open any task or project
2. Click the "Chat" tab
3. Type your message and hit Enter
4. @ mention someone to make sure they see it
5. They'll get notified and can reply right away

All messages are saved so you can review the conversation anytime!''',
                'keywords': ['chat', 'message', 'communication', 'collaboration', 'team'],
                'difficulty_level': 'beginner',
            },
            {
                'category': 'views',
                'feature_name': 'Custom Columns',
                'short_description': 'Show only the information you care about in lists and tables - hide the rest to reduce clutter.',
                'detailed_explanation': '''Default views often show way more information than you actually need, making it hard to find what matters.

Custom Columns lets you choose exactly what information to show in your lists and tables. Hide the stuff you don't use and keep the important things front and center.

It's like reorganizing your desk drawer - keep what you use frequently, put away what you rarely need. Makes everything cleaner and easier to scan.''',
                'use_cases': [
                    'Show only task name, due date, and assigned person',
                    'Add a completion percentage column to track progress',
                    'Hide technical fields you don\'t understand or use',
                    'Reorder columns to put most important info first',
                ],
                'advantages': [
                    'Less clutter = easier to find what you need',
                    'Faster scanning through lists',
                    'Different views for different purposes',
                    'Works on any list or table in the system',
                ],
                'how_to_use': '''1. Go to any list or table view
2. Click the "Columns" button (usually near the search)
3. Check/uncheck which columns to show
4. Drag columns to reorder them
5. Click "Save" to keep this layout

You can always reset to default if you want to start over!''',
                'keywords': ['columns', 'fields', 'customize', 'table', 'list', 'view'],
                'difficulty_level': 'intermediate',
            },
            {
                'category': 'notifications',
                'feature_name': 'Smart Notifications',
                'short_description': 'Get notified about important things without being overwhelmed by constant alerts.',
                'detailed_explanation': '''Nobody wants to be bombarded with notifications all day!

Smart Notifications learns what's actually important to you and filters out the noise. Instead of getting 50 notifications, you get the 3 that really matter.

You control what you're notified about, when, and how. Want emails for urgent stuff but app notifications for regular updates? No problem. Only want notifications during work hours? Easy. The system adapts to how you work.''',
                'use_cases': [
                    'Only notify about tasks assigned directly to you',
                    'Alert for urgent items only, summarize the rest daily',
                    'Silence notifications during meetings or after hours',
                    'Different notification rules for different types of tasks',
                ],
                'advantages': [
                    'Stay informed without being overwhelmed',
                    'Focus on what actually needs your attention',
                    'Reduce notification fatigue and stress',
                    'Customize for your personal work style',
                ],
                'how_to_use': '''1. Go to Settings → Notifications
2. Choose what events you want to be notified about
3. Set priority levels (immediate, daily digest, never)
4. Pick notification methods (email, app, SMS)
5. Set quiet hours if needed

The system will remember your preferences and notify accordingly!''',
                'keywords': ['notifications', 'alerts', 'smart', 'filter', 'quiet hours'],
                'difficulty_level': 'intermediate',
            },
            {
                'category': 'reports',
                'feature_name': 'Visual Dashboards',
                'short_description': 'See your data as charts and graphs that are easy to understand at a glance.',
                'detailed_explanation': '''Numbers in tables are fine, but sometimes you need to see the big picture!

Visual Dashboards turn your data into colorful charts and graphs that tell a story. See trends, spot patterns, and understand performance without analyzing spreadsheets.

Charts are automatically generated from your data - no manual work needed. They update in real-time, so you're always looking at current information.''',
                'use_cases': [
                    'See this month\'s task completion as a progress chart',
                    'Track team performance trends over time',
                    'Compare different teams or locations visually',
                    'Spot unusual patterns that need attention',
                ],
                'advantages': [
                    'Understand data faster with visual representations',
                    'Easy to spot trends and patterns',
                    'Great for presentations and meetings',
                    'Updates automatically - always current',
                ],
                'how_to_use': '''1. Go to Reports → Visual Dashboards
2. Choose a pre-built dashboard or create custom
3. Click any chart to see the underlying data
4. Use date filters to focus on specific time periods
5. Export charts for presentations or reports

Dashboards refresh automatically when new data comes in!''',
                'keywords': ['dashboard', 'charts', 'graphs', 'visualization', 'analytics'],
                'difficulty_level': 'beginner',
            },
        ]
