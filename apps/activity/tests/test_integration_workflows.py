"""
Integration tests for critical Activity app workflows
Tests end-to-end scenarios including Job creation, assignment, and completion
"""
import pytest
from django.test import Client, TransactionTestCase
from django.utils import timezone
from apps.peoples.models import People, Pgroup, Pgbelonging
from apps.activity.models.job_model import Job, Jobneed, JobneedDetails
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet, Question, QuestionSetBelonging
from apps.onboarding.models import Bt, TypeAssist, Shift
from datetime import date


@pytest.mark.django_db
@pytest.mark.integration
class TestJobWorkflow(TransactionTestCase):
    """Test complete job workflow from creation to completion"""

    def setUp(self):
        """Setup test data"""
        # Create TypeAssist instances for butype
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit"
        )

        # Create client and business unit
        self.client_org = Bt.objects.create(
            bucode="CLIENT001",
            buname="Test Client",
            butype=self.client_type
        )

        self.bu = Bt.objects.create(
            bucode="BU001",
            buname="Test Business Unit",
            butype=self.bu_type,
            parent=self.client_org
        )

        # Create shift
        from datetime import time
        self.shift = Shift.objects.create(
            shiftname="Day Shift",
            client=self.client_org,
            bu=self.bu,
            starttime=time(8, 0),  # 8 AM
            endtime=time(16, 0)    # 4 PM
        )

        # Create asset
        self.asset = Asset.objects.create(
            assetcode="ASSET001",
            assetname="Test Equipment",
            client=self.client_org,
            bu=self.bu,
            iscritical=True,
            enable=True
        )

        # Create question set with questions
        self.qset = QuestionSet.objects.create(
            qsetname="Daily Inspection",
            client=self.client_org,
            bu=self.bu
        )

        # Create questions
        self.question1 = Question.objects.create(
            quesname="Is equipment operational?",
            answertype="SINGLELINE",
            client=self.client_org
        )

        self.question2 = Question.objects.create(
            quesname="Any visible damage?",
            answertype="DROPDOWN",
            options="Yes,No,Not Sure",
            client=self.client_org
        )

        # Link questions to question set
        QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=self.question1,
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        QuestionSetBelonging.objects.create(
            qset=self.qset,
            question=self.question2,
            seqno=2,
            client=self.client_org,
            bu=self.bu
        )

        # Create users
        self.supervisor = People.objects.create_user(
            loginid="supervisor",
            peoplecode="SUP001",
            peoplename="Test Supervisor",
            email="supervisor@test.com",
            password="SuperPass123!",
            client=self.client_org,
            bu=self.bu,
            isadmin=True,
            is_staff=True,
            dateofbirth=date(1980, 1, 1)
        )

        self.technician = People.objects.create_user(
            loginid="technician",
            peoplecode="TECH001",
            peoplename="Test Technician",
            email="tech@test.com",
            password="TechPass123!",
            client=self.client_org,
            bu=self.bu,
            dateofbirth=date(1990, 1, 1)
        )

        # Create people group
        self.pgroup = Pgroup.objects.create(
            groupname="Maintenance Team",
            grouplead=self.supervisor,
            client=self.client_org,
            bu=self.bu
        )

        # Add technician to group
        Pgbelonging.objects.create(
            pgroup=self.pgroup,
            people=self.technician,
            client=self.client_org,
            bu=self.bu
        )

        # Create test client
        self.test_client = Client()

    def test_complete_job_lifecycle(self):
        """Test complete job lifecycle from creation to completion"""
        # Step 1: Login as supervisor
        self.test_client.force_login(self.supervisor)

        # Step 2: Create a job
        now = timezone.now()
        job = Job.objects.create(
            jobname="Daily Equipment Check",
            jobdesc="Check equipment status daily",
            fromdate=now,
            uptodate=now + timedelta(days=30),
            cron="0 9 * * *",  # Daily at 9 AM
            identifier="TASK",
            planduration=30,  # 30 minutes
            gracetime=15,
            expirytime=60,
            asset=self.asset,
            priority="HIGH",
            qset=self.qset,
            pgroup=self.pgroup,
            shift=self.shift,
            scantype="QR",
            frequency="DAILY",
            seqno=1,
            client=self.client_org,
            bu=self.bu,
            enable=True
        )

        assert job.id is not None
        assert job.jobname == "Daily Equipment Check"

        # Step 3: Generate jobneed (task instance)
        jobneed = Jobneed.objects.create(
            jobdesc=job.jobdesc,
            plandatetime=now + timedelta(hours=1),
            expirydatetime=now + timedelta(hours=2),
            gracetime=job.gracetime,
            asset=job.asset,
            job=job,
            jobstatus="ASSIGNED",
            jobtype="SCHEDULE",
            priority=job.priority,
            qset=job.qset,
            scantype=job.scantype,
            people=self.technician,
            pgroup=job.pgroup,
            identifier=job.identifier,
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        assert jobneed.id is not None
        assert jobneed.jobstatus == "ASSIGNED"
        assert jobneed.people == self.technician

        # Step 4: Create jobneed details (questions to answer)
        detail1 = JobneedDetails.objects.create(
            seqno=1,
            question=self.question1,
            answertype="SINGLELINE",
            qset=self.qset,
            jobneed=jobneed,
            ismandatory=True
        )

        detail2 = JobneedDetails.objects.create(
            seqno=2,
            question=self.question2,
            answertype="DROPDOWN",
            options="Yes,No,Not Sure",
            qset=self.qset,
            jobneed=jobneed,
            ismandatory=True
        )

        # Step 5: Login as technician
        self.test_client.force_login(self.technician)

        # Step 6: Start the job
        jobneed.jobstatus = "INPROGRESS"
        jobneed.starttime = timezone.now()
        jobneed.save()

        assert jobneed.jobstatus == "INPROGRESS"

        # Step 7: Answer questions
        detail1.answer = "Yes, operational"
        detail1.save()

        detail2.answer = "No"
        detail2.save()

        # Step 8: Complete the job
        jobneed.jobstatus = "COMPLETED"
        jobneed.endtime = timezone.now()
        jobneed.remarks = "All checks completed successfully"
        jobneed.save()

        assert jobneed.jobstatus == "COMPLETED"
        assert jobneed.endtime is not None

        # Step 9: Verify completion
        completed_jobneed = Jobneed.objects.get(id=jobneed.id)
        assert completed_jobneed.jobstatus == "COMPLETED"

        # Check that answers are saved
        answers = JobneedDetails.objects.filter(jobneed=jobneed)
        assert answers.count() == 2
        assert answers.get(question=self.question1).answer == "Yes, operational"
        assert answers.get(question=self.question2).answer == "No"

    def test_job_assignment_to_group(self):
        """Test job assignment to a group of people"""
        # Create job assigned to group
        job = Job.objects.create(
            jobname="Group Task",
            jobdesc="Task for entire group",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=7),
            identifier="TASK",
            planduration=60,
            gracetime=30,
            expirytime=120,
            priority="MEDIUM",
            pgroup=self.pgroup,  # Assigned to group
            shift=self.shift,
            scantype="SKIP",
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        # Generate jobneeds for group members
        group_members = Pgbelonging.objects.filter(pgroup=self.pgroup)

        for member_relation in group_members:
            jobneed = Jobneed.objects.create(
                jobdesc=job.jobdesc,
                plandatetime=timezone.now() + timedelta(hours=1),
                expirydatetime=timezone.now() + timedelta(hours=3),
                gracetime=job.gracetime,
                job=job,
                jobstatus="ASSIGNED",
                jobtype="SCHEDULE",
                priority=job.priority,
                people=member_relation.people,
                pgroup=job.pgroup,
                identifier=job.identifier,
                seqno=1,
                client=self.client_org,
                bu=self.bu
            )

            assert jobneed.people == member_relation.people

        # Verify all group members have tasks
        assigned_tasks = Jobneed.objects.filter(job=job)
        assert assigned_tasks.count() == group_members.count()

    def test_job_escalation_on_expiry(self):
        """Test job escalation when task expires"""
        past_time = timezone.now() - timedelta(hours=2)
        expired_time = timezone.now() - timedelta(hours=1)

        # Create an expired job
        job = Job.objects.create(
            jobname="Urgent Task",
            jobdesc="This task should have been completed",
            fromdate=past_time,
            uptodate=timezone.now() + timedelta(days=1),
            identifier="TASK",
            planduration=30,
            gracetime=15,
            expirytime=60,
            priority="HIGH",
            people=self.technician,
            shift=self.shift,
            scantype="QR",
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        # Create expired jobneed
        jobneed = Jobneed.objects.create(
            jobdesc=job.jobdesc,
            plandatetime=past_time,
            expirydatetime=expired_time,
            gracetime=job.gracetime,
            job=job,
            jobstatus="ASSIGNED",
            jobtype="SCHEDULE",
            priority=job.priority,
            people=self.technician,
            identifier=job.identifier,
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        # Check if task is expired
        current_time = timezone.now()
        is_expired = jobneed.expirydatetime < current_time

        assert is_expired is True

        # Simulate escalation
        if is_expired and jobneed.jobstatus != "COMPLETED":
            # Mark as auto-closed
            jobneed.jobstatus = "AUTOCLOSED"
            jobneed.other_info = {
                "autoclosed_by_server": True,
                "escalation_sent": True,
                "escalated_to": self.supervisor.peoplecode
            }
            jobneed.save()

        assert jobneed.jobstatus == "AUTOCLOSED"
        assert jobneed.other_info["autoclosed_by_server"] is True


@pytest.mark.django_db
@pytest.mark.integration
class TestAssetMaintenanceWorkflow(TransactionTestCase):
    """Test asset maintenance workflow"""

    def setUp(self):
        """Setup test data for asset maintenance"""
        # Create TypeAssist instances for butype
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit"
        )

        # Create basic data
        self.client_org = Bt.objects.create(
            bucode="CLIENT002",
            buname="Maintenance Client",
            butype=self.client_type
        )

        self.bu = Bt.objects.create(
            bucode="BU002",
            buname="Maintenance BU",
            butype=self.bu_type,
            parent=self.client_org
        )

        # Create asset hierarchy
        self.parent_asset = Asset.objects.create(
            assetcode="BUILDING001",
            assetname="Main Building",
            client=self.client_org,
            bu=self.bu,
            identifier="ASSET",
            iscritical=True
        )

        self.child_asset1 = Asset.objects.create(
            assetcode="HVAC001",
            assetname="HVAC System",
            parent=self.parent_asset,
            client=self.client_org,
            bu=self.bu,
            identifier="ASSET",
            iscritical=True,
            runningstatus="WORKING"
        )

        self.child_asset2 = Asset.objects.create(
            assetcode="ELEC001",
            assetname="Electrical Panel",
            parent=self.parent_asset,
            client=self.client_org,
            bu=self.bu,
            identifier="ASSET",
            iscritical=True,
            runningstatus="WORKING"
        )

        # Create maintenance team
        self.maintenance_lead = People.objects.create_user(
            loginid="maintlead",
            peoplecode="ML001",
            peoplename="Maintenance Lead",
            email="maintlead@test.com",
            password="MaintPass123!",
            client=self.client_org,
            bu=self.bu,
            dateofbirth=date(1985, 1, 1)
        )

    def test_asset_status_change_workflow(self):
        """Test asset status change and logging"""
        from apps.activity.models.asset_model import AssetLog

        # Initial status
        initial_status = self.child_asset1.runningstatus
        assert initial_status == "WORKING"

        # Change status to maintenance
        old_status = self.child_asset1.runningstatus
        self.child_asset1.runningstatus = "MAINTENANCE"
        self.child_asset1.save()

        # Create log entry
        log = AssetLog.objects.create(
            oldstatus=old_status,
            newstatus=self.child_asset1.runningstatus,
            asset=self.child_asset1,
            people=self.maintenance_lead,
            bu=self.bu,
            client=self.client_org,
            cdtz=timezone.now()
        )

        assert log.oldstatus == "WORKING"
        assert log.newstatus == "MAINTENANCE"

        # Verify status change
        self.child_asset1.refresh_from_db()
        assert self.child_asset1.runningstatus == "MAINTENANCE"

        # Change back to working
        old_status = self.child_asset1.runningstatus
        self.child_asset1.runningstatus = "WORKING"
        self.child_asset1.save()

        # Create another log entry
        log2 = AssetLog.objects.create(
            oldstatus=old_status,
            newstatus=self.child_asset1.runningstatus,
            asset=self.child_asset1,
            people=self.maintenance_lead,
            bu=self.bu,
            client=self.client_org,
            cdtz=timezone.now()
        )

        # Check maintenance history
        maintenance_logs = AssetLog.objects.filter(
            asset=self.child_asset1
        ).order_by('-cdtz')

        # Check that we have at least the 2 logs we created
        assert maintenance_logs.count() >= 2

        # Find our specific logs by looking for the transitions we made
        working_to_maintenance = maintenance_logs.filter(
            oldstatus="WORKING",
            newstatus="MAINTENANCE"
        ).first()
        maintenance_to_working = maintenance_logs.filter(
            oldstatus="MAINTENANCE",
            newstatus="WORKING"
        ).first()

        assert working_to_maintenance is not None
        assert maintenance_to_working is not None

    def test_preventive_maintenance_schedule(self):
        """Test preventive maintenance scheduling"""
        # Create maintenance schedule
        maintenance_job = Job.objects.create(
            jobname="Monthly HVAC Maintenance",
            jobdesc="Preventive maintenance for HVAC system",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=365),
            cron="0 9 1 * *",  # First day of each month at 9 AM
            identifier="PPM",  # Preventive Planned Maintenance
            planduration=120,
            gracetime=60,
            expirytime=240,
            asset=self.child_asset1,
            priority="MEDIUM",
            frequency="MONTHLY",
            people=self.maintenance_lead,
            seqno=1,
            client=self.client_org,
            bu=self.bu,
            enable=True
        )

        assert maintenance_job.identifier == "PPM"
        assert maintenance_job.frequency == "MONTHLY"

        # Generate maintenance tasks for next 3 months
        maintenance_tasks = []
        for month in range(3):
            task_date = timezone.now() + timedelta(days=30 * month)

            jobneed = Jobneed.objects.create(
                jobdesc=maintenance_job.jobdesc,
                plandatetime=task_date.replace(day=1, hour=9, minute=0),
                expirydatetime=task_date.replace(day=1, hour=13, minute=0),
                gracetime=maintenance_job.gracetime,
                asset=maintenance_job.asset,
                job=maintenance_job,
                jobstatus="ASSIGNED",
                jobtype="SCHEDULE",
                frequency="MONTHLY",
                priority=maintenance_job.priority,
                people=self.maintenance_lead,
                identifier="PPM",
                seqno=month + 1,
                client=self.client_org,
                bu=self.bu
            )

            maintenance_tasks.append(jobneed)

        assert len(maintenance_tasks) == 3

        # Verify all tasks are scheduled
        scheduled_ppm = Jobneed.objects.filter(
            job=maintenance_job,
            identifier="PPM"
        )
        assert scheduled_ppm.count() == 3

    def test_critical_asset_priority(self):
        """Test that critical assets get high priority"""
        # Create jobs for critical and non-critical assets
        non_critical_asset = Asset.objects.create(
            assetcode="STORAGE001",
            assetname="Storage Room",
            client=self.client_org,
            bu=self.bu,
            iscritical=False
        )

        # Job for critical asset
        critical_job = Job.objects.create(
            jobname="Critical Asset Check",
            jobdesc="Check critical asset",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=1),
            identifier="TASK",
            planduration=30,
            gracetime=10,
            expirytime=30,
            asset=self.child_asset1,  # Critical asset
            priority="HIGH",
            seqno=1,
            client=self.client_org,
            bu=self.bu
        )

        # Job for non-critical asset
        normal_job = Job.objects.create(
            jobname="Storage Check",
            jobdesc="Check storage room",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=1),
            identifier="TASK",
            planduration=30,
            gracetime=60,
            expirytime=120,
            asset=non_critical_asset,
            priority="LOW",
            seqno=2,
            client=self.client_org,
            bu=self.bu
        )

        # Verify priority settings
        assert critical_job.asset.iscritical is True
        assert critical_job.priority == "HIGH"
        assert critical_job.gracetime < normal_job.gracetime

        assert normal_job.asset.iscritical is False
        assert normal_job.priority == "LOW"


@pytest.mark.django_db
@pytest.mark.integration
class TestReportingWorkflow(TransactionTestCase):
    """Test reporting and analytics workflow"""

    def setUp(self):
        """Setup test data for reporting"""
        # Create TypeAssist instances for butype
        self.client_type = TypeAssist.objects.create(
            tacode="CLIENT",
            taname="Client"
        )
        self.bu_type = TypeAssist.objects.create(
            tacode="BU",
            taname="Business Unit"
        )

        self.client_org = Bt.objects.create(
            bucode="CLIENT003",
            buname="Reporting Client",
            butype=self.client_type
        )

        self.bu = Bt.objects.create(
            bucode="BU003",
            buname="Reporting BU",
            butype=self.bu_type,
            parent=self.client_org
        )

        # Create multiple users
        self.users = []
        for i in range(5):
            user = People.objects.create_user(
                loginid=f"user{i}",
                peoplecode=f"USR{i:03d}",
                peoplename=f"User {i}",
                email=f"user{i}@test.com",
                password="UserPass123!",
                client=self.client_org,
                bu=self.bu,
                dateofbirth=date(1990, 1, 1)
            )
            self.users.append(user)

    def test_task_completion_metrics(self):
        """Test generation of task completion metrics"""
        # Create completed and pending tasks
        completed_count = 0
        pending_count = 0

        for i in range(20):
            status = "COMPLETED" if i % 3 == 0 else "ASSIGNED"

            jobneed = Jobneed.objects.create(
                jobdesc=f"Task {i}",
                plandatetime=timezone.now() - timedelta(hours=i),
                expirydatetime=timezone.now() + timedelta(hours=1),
                gracetime=30,
                jobstatus=status,
                jobtype="ADHOC",
                priority="MEDIUM",
                people=self.users[i % 5],
                identifier="TASK",
                seqno=i,
                client=self.client_org,
                bu=self.bu
            )

            if status == "COMPLETED":
                completed_count += 1
                jobneed.endtime = timezone.now()
                jobneed.save()
            else:
                pending_count += 1

        # Calculate metrics
        total_tasks = Jobneed.objects.filter(client=self.client_org).count()
        completed_tasks = Jobneed.objects.filter(
            client=self.client_org,
            jobstatus="COMPLETED"
        ).count()
        pending_tasks = Jobneed.objects.filter(
            client=self.client_org,
            jobstatus="ASSIGNED"
        ).count()

        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0

        assert total_tasks == 20
        assert completed_tasks == completed_count
        assert pending_tasks == pending_count
        assert completion_rate > 0

        # Test per-user metrics
        for user in self.users:
            user_tasks = Jobneed.objects.filter(people=user)
            user_completed = user_tasks.filter(jobstatus="COMPLETED").count()
            user_pending = user_tasks.filter(jobstatus="ASSIGNED").count()

            assert user_tasks.count() > 0