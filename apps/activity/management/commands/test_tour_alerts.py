"""
Management command to test Tour/Task alert functionality.
Usage: python manage.py test_tour_alerts
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal
import json

class Command(BaseCommand):
    help = 'Test Tour/Task alert functionality by creating a tour with test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            default='test@example.com',
            help='Email address to send test alerts to'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without actually sending emails'
        )

    def handle(self, *args, **options):
        from apps.activity.models.job_model import Jobneed, JobneedDetails
        from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
        from apps.onboarding.models import Bt
        from apps.peoples.models import People
        from apps.activity.models.asset_model import Asset
        from background_tasks.utils import alert_observation
        
        self.stdout.write(self.style.WARNING('Starting Tour Alert Test...'))
        
        try:
            # Get or create test data
            from apps.onboarding.models import TypeAssist
            
            # Find CLIENT and SITE TypeAssist records
            client_type = TypeAssist.objects.filter(taname='Client').first()
            site_type = TypeAssist.objects.filter(taname='Site').first()
            
            if not client_type:
                # Try to create if doesn't exist
                self.stdout.write(self.style.WARNING('No CLIENT type found, creating one...'))
                client_type = TypeAssist.objects.create(
                    tacode='CLIENT_TEST',
                    taname='Client'
                )
                
            if not site_type:
                # Try to create if doesn't exist  
                self.stdout.write(self.style.WARNING('No SITE type found, creating one...'))
                site_type = TypeAssist.objects.create(
                    tacode='SITE_TEST',
                    taname='Site'
                )
            
            client = Bt.objects.filter(butype=client_type).first()
            if not client:
                self.stdout.write(self.style.WARNING('No CLIENT found in Bt table, creating test client...'))
                client = Bt.objects.create(
                    bucode='TEST_CLIENT_001',
                    buname='Test Client for Alerts',
                    butype=client_type,
                    enable=True
                )
            
            site = Bt.objects.filter(butype=site_type, parent=client).first()
            if not site:
                # Try to find any site under this client
                site = Bt.objects.filter(butype=site_type).first()
                if not site:
                    self.stdout.write(self.style.WARNING('No SITE found, creating test site...'))
                    site = Bt.objects.create(
                        bucode='TEST_SITE_001',
                        buname='Test Site for Alerts',
                        butype=site_type,
                        parent=client,
                        enable=True
                    )
                
            user = People.objects.filter(enable=True).exclude(id=1).first()
            if not user:
                self.stdout.write(self.style.WARNING('No active user found, creating test user...'))
                user = People.objects.create(
                    peoplecode='TEST_USER_001',
                    peoplename='Test User for Alerts',
                    email='testuser@example.com',
                    enable=True
                )
            
            # Create test asset
            asset, _ = Asset.objects.get_or_create(
                assetname='TEST_CHECKPOINT_ALERT',
                assetcode='TCP_ALERT_001',
                bu=site,
                client=client,
                defaults={
                    'enable': True,
                    'iscritical': False
                }
            )
            
            # Create test questions with alert conditions
            with transaction.atomic():
                # Create QuestionSet for testing
                qset, _ = QuestionSet.objects.get_or_create(
                    qsetname='TEST_ALERT_CHECKLIST',
                    type='CHECKLIST',
                    client=client,
                    defaults={'enable': True}
                )
                
                # Question 1: Numeric with range alert
                q1, _ = Question.objects.get_or_create(
                    quesname='Temperature Reading (Should be 20-25°C)',
                    answertype='NUMERIC',
                    client=client,
                    defaults={
                        'min': Decimal('20.00'),
                        'max': Decimal('25.00'),
                        'alerton': '20,25',  # Alert if outside this range
                        'enable': True
                    }
                )
                
                # Question 2: Dropdown with specific value alert
                q2, _ = Question.objects.get_or_create(
                    quesname='Is Equipment Working?',
                    answertype='DROPDOWN',
                    client=client,
                    defaults={
                        'options': 'Yes,No,N/A',
                        'alerton': 'No',  # Alert on 'No'
                        'enable': True
                    }
                )
                
                # Question 3: Another dropdown
                q3, _ = Question.objects.get_or_create(
                    quesname='Are Lights Functional?',
                    answertype='DROPDOWN',
                    client=client,
                    defaults={
                        'options': 'Yes,No,Partial',
                        'alerton': 'No,Partial',  # Alert on 'No' or 'Partial'
                        'enable': True
                    }
                )
                
                # Link questions to questionset
                qsb1, _ = QuestionSetBelonging.objects.get_or_create(
                    qset=qset,
                    question=q1,
                    client=client,
                    defaults={
                        'seqno': 1,
                        'answertype': 'NUMERIC',
                        'min': Decimal('20.00'),
                        'max': Decimal('25.00'),
                        'alerton': '20,25',
                        'ismandatory': True
                    }
                )
                
                qsb2, _ = QuestionSetBelonging.objects.get_or_create(
                    qset=qset,
                    question=q2,
                    client=client,
                    defaults={
                        'seqno': 2,
                        'answertype': 'DROPDOWN',
                        'options': 'Yes,No,N/A',
                        'alerton': 'No',
                        'ismandatory': True
                    }
                )
                
                qsb3, _ = QuestionSetBelonging.objects.get_or_create(
                    qset=qset,
                    question=q3,
                    client=client,
                    defaults={
                        'seqno': 3,
                        'answertype': 'DROPDOWN',
                        'options': 'Yes,No,Partial',
                        'alerton': 'No,Partial',
                        'ismandatory': True
                    }
                )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Created test QuestionSet: {qset.qsetname}'))
                
                # Create test Jobneed (Tour)
                jobneed = Jobneed.objects.create(
                    jobdesc='Test Tour for Alert Verification',
                    identifier='INTERNALTOUR',
                    jobtype='SCHEDULE',
                    jobstatus='COMPLETED',
                    seqno=1,  # Sequence number
                    gracetime=30,  # 30 minutes grace time
                    plandatetime=timezone.now() - timedelta(hours=1),
                    starttime=timezone.now() - timedelta(hours=1),
                    endtime=timezone.now(),
                    performedby=user,
                    people=user,
                    asset=asset,
                    bu=site,
                    client=client,
                    qset=qset,
                    alerts=False,  # Will be set based on answers
                    ismailsent=False,
                    ctzoffset=330  # IST offset
                )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Created test Jobneed: {jobneed.jobdesc}'))
                
                # Create JobneedDetails with answers that trigger alerts
                alerts_triggered = False
                
                # Answer 1: Temperature = 30 (outside 20-25 range) - SHOULD TRIGGER ALERT
                jnd1 = JobneedDetails.objects.create(
                    seqno=1,
                    question=q1,
                    answertype='NUMERIC',
                    answer='30',  # Outside range!
                    min=Decimal('20.00'),
                    max=Decimal('25.00'),
                    alerton='20,25',
                    qset=qset,
                    jobneed=jobneed,
                    alerts=True  # This should trigger alert
                )
                alerts_triggered = True
                self.stdout.write(self.style.WARNING(f'  Answer 1: Temperature=30°C (Range: 20-25°C) - ALERT!'))
                
                # Answer 2: Equipment = No - SHOULD TRIGGER ALERT
                jnd2 = JobneedDetails.objects.create(
                    seqno=2,
                    question=q2,
                    answertype='DROPDOWN',
                    answer='No',  # Matches alert condition!
                    options='Yes,No,N/A',
                    alerton='No',
                    qset=qset,
                    jobneed=jobneed,
                    alerts=True  # This should trigger alert
                )
                self.stdout.write(self.style.WARNING(f'  Answer 2: Equipment=No (Alert on: No) - ALERT!'))
                
                # Answer 3: Lights = Yes - Should NOT trigger alert
                jnd3 = JobneedDetails.objects.create(
                    seqno=3,
                    question=q3,
                    answertype='DROPDOWN',
                    answer='Yes',  # Does not match alert condition
                    options='Yes,No,Partial',
                    alerton='No,Partial',
                    qset=qset,
                    jobneed=jobneed,
                    alerts=False  # This should NOT trigger alert
                )
                self.stdout.write(self.style.SUCCESS(f'  Answer 3: Lights=Yes (Alert on: No,Partial) - OK'))
                
                # Update jobneed alerts flag
                if alerts_triggered:
                    jobneed.alerts = True
                    jobneed.save()
                    self.stdout.write(self.style.WARNING(f'\n✓ Alerts triggered on Jobneed'))
                
                # Test email sending
                if not options['dry_run']:
                    self.stdout.write(self.style.WARNING(f'\nAttempting to send alert email...'))
                    
                    # Call the alert function
                    result = alert_observation(jobneed, atts=False)
                    
                    if 'Mail sent' in result.get('story', ''):
                        self.stdout.write(self.style.SUCCESS(f'✓ Alert email sent successfully!'))
                        self.stdout.write(f"  Story: {result['story']}")
                    else:
                        self.stdout.write(self.style.ERROR(f'✗ Alert email failed'))
                        self.stdout.write(f"  Story: {result.get('story', 'No story')}")
                        if result.get('traceback'):
                            self.stdout.write(self.style.ERROR(f"  Error: {result['traceback']}"))
                else:
                    self.stdout.write(self.style.WARNING(f'\n--dry-run mode: Email sending skipped'))
                
                # Display summary
                self.stdout.write(self.style.SUCCESS(f'\n' + '='*60))
                self.stdout.write(self.style.SUCCESS('TEST SUMMARY:'))
                self.stdout.write(f'  Jobneed ID: {jobneed.id}')
                self.stdout.write(f'  Tour Type: {jobneed.identifier}')
                self.stdout.write(f'  Site: {site.buname}')
                self.stdout.write(f'  Asset: {asset.assetname}')
                self.stdout.write(f'  Performed By: {user.peoplename}')
                self.stdout.write(f'  Alerts Triggered: {jobneed.alerts}')
                self.stdout.write(f'  Email Sent: {jobneed.ismailsent}')
                
                # Check if alerts are properly stored in database
                alert_count = JobneedDetails.objects.filter(
                    jobneed=jobneed,
                    alerts=True
                ).count()
                self.stdout.write(f'  Alert Details Count: {alert_count}')
                
                self.stdout.write(self.style.SUCCESS('='*60))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))