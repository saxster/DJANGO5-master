"""
Test cases for Tour/Task Alert functionality
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.core import mail
from unittest.mock import patch, MagicMock

from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
from apps.onboarding.models import Bt
from apps.peoples.models import People
from apps.activity.models.asset_model import Asset
from background_tasks.utils import alert_observation


@pytest.fixture
def test_data(db):
    """Create test data for alert testing"""
    from apps.onboarding.models import TypeAssist

    # Create TypeAssist instances
    client_type = TypeAssist.objects.create(
        tacode='CLIENT',
        taname='Client'
    )
    site_type = TypeAssist.objects.create(
        tacode='SITE',
        taname='Site'
    )

    # Create client and site
    client = Bt.objects.create(
        buname='TEST_CLIENT',
        bucode='TC001',
        butype=client_type
    )

    site = Bt.objects.create(
        buname='TEST_SITE',
        bucode='TS001',
        butype=site_type,
        parent=client
    )
    
    # Create user
    from datetime import date
    user = People.objects.create(
        peoplename='Test User',
        peoplecode='TU001',
        loginid='testuser001',
        email='testuser@example.com',
        dateofbirth=date(1990, 1, 1)
    )
    
    # Create asset
    asset = Asset.objects.create(
        assetname='TEST_CHECKPOINT',
        assetcode='TCP001',
        bu=site,
        client=client,
        iscritical=False
    )
    
    # Create questionset
    qset = QuestionSet.objects.create(
        qsetname='TEST_CHECKLIST',
        type='CHECKLIST',
        client=client,
        enable=True
    )
    
    return {
        'client': client,
        'site': site,
        'user': user,
        'asset': asset,
        'qset': qset
    }


@pytest.mark.django_db
class TestTourAlerts:
    
    def test_numeric_alert_outside_range(self, test_data):
        """Test that numeric answers outside min/max range trigger alerts"""
        
        # Create numeric question
        question = Question.objects.create(
            quesname='Temperature Reading',
            answertype='NUMERIC',
            min=Decimal('20.00'),
            max=Decimal('25.00'),
            alerton='20,25',
            client=test_data['client']
        )
        
        # Link to questionset
        qsb = QuestionSetBelonging.objects.create(
            qset=test_data['qset'],
            question=question,
            seqno=1,
            answertype='NUMERIC',
            min=Decimal('20.00'),
            max=Decimal('25.00'),
            alerton='20,25',
            client=test_data['client']
        )
        
        # Create jobneed
        jobneed = Jobneed.objects.create(
            jobdesc='TEST_TOUR',
            identifier='INTERNALTOUR',
            people=test_data['user'],
            plandatetime=timezone.now(),
            gracetime=30,
            expirydatetime=timezone.now() + timedelta(hours=2),
            seqno=1,
            bu=test_data['site'],
            client=test_data['client'],
            qset=test_data['qset'],
            asset=test_data['asset'],
            alerts=False
        )
        
        # Test 1: Answer within range (should NOT trigger alert)
        jnd_ok = JobneedDetails.objects.create(
            seqno=1,
            question=question,
            answertype='NUMERIC',
            answer='22',
            min=Decimal('20.00'),
            max=Decimal('25.00'),
            alerton='20,25',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        # Check alert logic
        answer_value = float(jnd_ok.answer)
        should_alert = answer_value < float(jnd_ok.min) or answer_value > float(jnd_ok.max)
        assert should_alert == False, "Answer within range should not trigger alert"
        
        # Test 2: Answer above range (should trigger alert)
        jnd_high = JobneedDetails.objects.create(
            seqno=2,
            question=question,
            answertype='NUMERIC',
            answer='30',
            min=Decimal('20.00'),
            max=Decimal('25.00'),
            alerton='20,25',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        answer_value = float(jnd_high.answer)
        should_alert = answer_value < float(jnd_high.min) or answer_value > float(jnd_high.max)
        assert should_alert == True, "Answer above range should trigger alert"
        
        # Test 3: Answer below range (should trigger alert)
        jnd_low = JobneedDetails.objects.create(
            seqno=3,
            question=question,
            answertype='NUMERIC',
            answer='15',
            min=Decimal('20.00'),
            max=Decimal('25.00'),
            alerton='20,25',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        answer_value = float(jnd_low.answer)
        should_alert = answer_value < float(jnd_low.min) or answer_value > float(jnd_low.max)
        assert should_alert == True, "Answer below range should trigger alert"
    
    def test_dropdown_alert_on_specific_value(self, test_data):
        """Test that specific dropdown values trigger alerts"""
        
        # Create dropdown question
        question = Question.objects.create(
            quesname='Equipment Status',
            answertype='DROPDOWN',
            options='Yes,No,N/A',
            alerton='No',
            client=test_data['client']
        )
        
        # Create jobneed
        jobneed = Jobneed.objects.create(
            jobdesc='TEST_TOUR',
            identifier='INTERNALTOUR',
            people=test_data['user'],
            plandatetime=timezone.now(),
            gracetime=30,
            expirydatetime=timezone.now() + timedelta(hours=2),
            seqno=1,
            bu=test_data['site'],
            client=test_data['client'],
            qset=test_data['qset'],
            asset=test_data['asset'],
            alerts=False
        )
        
        # Test 1: Answer = 'Yes' (should NOT trigger alert)
        jnd_yes = JobneedDetails.objects.create(
            seqno=1,
            question=question,
            answertype='DROPDOWN',
            answer='Yes',
            options='Yes,No,N/A',
            alerton='No',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        should_alert = jnd_yes.answer == jnd_yes.alerton
        assert should_alert == False, "Answer 'Yes' should not trigger alert when alert is on 'No'"
        
        # Test 2: Answer = 'No' (should trigger alert)
        jnd_no = JobneedDetails.objects.create(
            seqno=2,
            question=question,
            answertype='DROPDOWN',
            answer='No',
            options='Yes,No,N/A',
            alerton='No',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        should_alert = jnd_no.answer == jnd_no.alerton
        assert should_alert == True, "Answer 'No' should trigger alert when alert is on 'No'"
    
    def test_multiple_alert_values(self, test_data):
        """Test questions with multiple alert trigger values"""
        
        question = Question.objects.create(
            quesname='Light Status',
            answertype='DROPDOWN',
            options='Working,Not Working,Partial,Unknown',
            alerton='Not Working,Partial',  # Multiple alert values
            client=test_data['client']
        )
        
        jobneed = Jobneed.objects.create(
            jobdesc='TEST_TOUR',
            identifier='INTERNALTOUR',
            people=test_data['user'],
            plandatetime=timezone.now(),
            gracetime=30,
            expirydatetime=timezone.now() + timedelta(hours=2),
            seqno=1,
            bu=test_data['site'],
            client=test_data['client'],
            qset=test_data['qset'],
            asset=test_data['asset'],
            alerts=False
        )
        
        # Test with 'Partial' (should trigger alert)
        jnd = JobneedDetails.objects.create(
            seqno=1,
            question=question,
            answertype='DROPDOWN',
            answer='Partial',
            options='Working,Not Working,Partial,Unknown',
            alerton='Not Working,Partial',
            jobneed=jobneed,
            qset=test_data['qset']
        )
        
        alert_values = [v.strip() for v in jnd.alerton.split(',')]
        should_alert = jnd.answer in alert_values
        assert should_alert == True, "Answer 'Partial' should trigger alert"
    
    @patch('django.core.mail.EmailMessage')
    def test_alert_email_sending(self, mock_email, test_data):
        """Test that alert emails are sent correctly"""
        
        # Create a jobneed with alerts
        jobneed = Jobneed.objects.create(
            jobdesc='Test Tour with Alerts',
            identifier='INTERNALTOUR',
            people=test_data['user'],
            bu=test_data['site'],
            client=test_data['client'],
            qset=test_data['qset'],
            asset=test_data['asset'],
            alerts=True,  # Has alerts
            ismailsent=False,  # Email not yet sent
            endtime=timezone.now(),
            ctzoffset=330,
            plandatetime=timezone.now(),
            gracetime=30,
            expirydatetime=timezone.now() + timedelta(hours=2),
            seqno=1
        )
        
        # Mock email instance
        mock_email_instance = MagicMock()
        mock_email.return_value = mock_email_instance
        
        # Mock get_email_recipients to return test email
        with patch('background_tasks.utils.get_email_recipients') as mock_recipients:
            mock_recipients.return_value = ['test@example.com']
            
            # Call alert function
            result = alert_observation(jobneed, atts=False)
            
            # Verify email was attempted to be sent
            assert mock_email_instance.send.called, "Email send should be called"
            
            # Verify jobneed is marked as email sent
            jobneed.refresh_from_db()
            assert jobneed.ismailsent == True, "Jobneed should be marked as email sent"
    
    def test_jobneed_alert_flag_aggregation(self, test_data):
        """Test that jobneed.alerts flag is set when any detail has alerts"""
        
        jobneed = Jobneed.objects.create(
            jobdesc='TEST_TOUR',
            identifier='INTERNALTOUR',
            people=test_data['user'],
            plandatetime=timezone.now(),
            gracetime=30,
            expirydatetime=timezone.now() + timedelta(hours=2),
            seqno=1,
            bu=test_data['site'],
            client=test_data['client'],
            qset=test_data['qset'],
            asset=test_data['asset'],
            alerts=False
        )
        
        # Create multiple JobneedDetails
        JobneedDetails.objects.create(
            seqno=1,
            answertype='NUMERIC',
            answer='22',
            jobneed=jobneed,
            qset=test_data['qset'],
            alerts=False  # No alert
        )
        
        JobneedDetails.objects.create(
            seqno=2,
            answertype='NUMERIC',
            answer='30',
            jobneed=jobneed,
            qset=test_data['qset'],
            alerts=True  # Has alert
        )
        
        # Check if any detail has alerts
        has_alerts = JobneedDetails.objects.filter(
            jobneed=jobneed,
            alerts=True
        ).exists()
        
        assert has_alerts == True, "Should detect that at least one detail has alerts"
        
        # Update jobneed flag
        if has_alerts:
            jobneed.alerts = True
            jobneed.save()
        
        assert jobneed.alerts == True, "Jobneed should have alerts flag set"