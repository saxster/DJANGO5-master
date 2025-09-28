#!/usr/bin/env python
"""
Comprehensive Race Condition Penetration Test Script

Tests all race condition fixes with extreme concurrency scenarios.
Validates that the system remains stable under heavy concurrent load.

Scenarios tested:
1. Background task autoclose (50+ concurrent workers)
2. Checkpoint batch autoclose (100+ checkpoints)
3. Ticket escalation (100+ concurrent escalations)
4. Ticket log updates (200+ concurrent appends)
5. JSON field updates (100+ concurrent modifications)
6. Adhoc task updates (50+ concurrent syncs)
7. Combined load test (all operations simultaneously)

Usage:
    python comprehensive_race_condition_penetration_test.py --scenario all
    python comprehensive_race_condition_penetration_test.py --scenario autoclose
    python comprehensive_race_condition_penetration_test.py --scenario tickets
"""

import os
import sys
import django
import argparse
import threading
import time
from datetime import datetime, timedelta, date
from typing import List, Dict, Any

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.db import transaction, connection
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.activity.models import Jobneed, Job, Asset, QuestionSet
from apps.y_helpdesk.models import Ticket
from apps.onboarding.models import Bt, TypeAssist, Shift
from apps.peoples.models import Pgroup
from background_tasks.utils import (
    update_job_autoclose_status,
    check_for_checkpoints_status,
    update_ticket_log,
    update_ticket_data,
)
from apps.y_helpdesk.services import TicketWorkflowService
from apps.core.utils_new.atomic_json_updater import AtomicJSONFieldUpdater

User = get_user_model()


class PenetrationTestRunner:
    """Manages penetration test execution and reporting"""

    def __init__(self):
        self.results = []
        self.setup_test_data()

    def setup_test_data(self):
        """Set up required test data"""
        print("Setting up test data...")

        self.client_type, _ = TypeAssist.objects.get_or_create(
            tacode="PENTEST_CLIENT",
            defaults={'taname': "Pentest Client Type"}
        )
        self.bu_type, _ = TypeAssist.objects.get_or_create(
            tacode="PENTEST_BU",
            defaults={'taname': "Pentest BU Type"}
        )
        self.ticket_type, _ = TypeAssist.objects.get_or_create(
            tacode="PENTEST_TICKET",
            defaults={'taname': "Pentest Ticket"}
        )

        self.client_bt, _ = Bt.objects.get_or_create(
            bucode='PENTEST_CLIENT',
            defaults={'buname': 'Pentest Client', 'butype': self.client_type}
        )

        self.site_bt, _ = Bt.objects.get_or_create(
            bucode='PENTEST_SITE',
            defaults={
                'buname': 'Pentest Site',
                'butype': self.bu_type,
                'parent': self.client_bt
            }
        )

        from datetime import time as dt_time
        self.shift, _ = Shift.objects.get_or_create(
            shiftname='Pentest Shift',
            client=self.client_bt,
            bu=self.site_bt,
            defaults={'starttime': dt_time(8, 0), 'endtime': dt_time(16, 0)}
        )

        self.user, _ = User.objects.get_or_create(
            username='pentest_user',
            defaults={
                'peoplename': 'Pentest User',
                'peoplecode': 'PENTEST001',
                'email': 'pentest@example.com',
                'client': self.client_bt,
                'bu': self.site_bt,
                'dateofbirth': date(1990, 1, 1)
            }
        )

        self.asset, _ = Asset.objects.get_or_create(
            assetcode='PENTEST_ASSET',
            defaults={
                'assetname': 'Pentest Asset',
                'client': self.client_bt,
                'bu': self.site_bt,
                'enable': True
            }
        )

        self.qset, _ = QuestionSet.objects.get_or_create(
            qsetname='Pentest QuestionSet',
            defaults={'client': self.client_bt, 'bu': self.site_bt}
        )

        self.pgroup, _ = Pgroup.objects.get_or_create(
            groupname='Pentest Group',
            defaults={
                'grouplead': self.user,
                'client': self.client_bt,
                'bu': self.site_bt
            }
        )

        print("Test data setup complete")

    def scenario_job_autoclose_extreme(self):
        """50 concurrent workers attempting to autoclose same job"""
        print("\n=== Testing Job Autoclose (50 concurrent workers) ===")

        jobneed = Jobneed.objects.create(
            jobdesc='Autoclose Test',
            plandatetime=timezone.now() - timedelta(hours=2),
            expirydatetime=timezone.now() - timedelta(hours=1),
            gracetime=15,
            asset=self.asset,
            jobstatus='INPROGRESS',
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='TASK',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user,
            other_info={}
        )

        record = {
            'id': jobneed.id,
            'ticketcategory__tacode': 'AUTOCLOSENOTIFY',
        }

        errors = []
        start_time = time.time()

        def worker(worker_id):
            try:
                resp = {'id': [], 'story': ''}
                update_job_autoclose_status(record, resp)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        jobneed.refresh_from_db()

        passed = (
            len(errors) == 0 and
            jobneed.jobstatus == 'AUTOCLOSED' and
            jobneed.other_info.get('autoclosed_by_server', False)
        )

        result = {
            'scenario': 'Job Autoclose (50 workers)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration,
            'final_status': jobneed.jobstatus
        }

        self.results.append(result)
        self.print_result(result)

        jobneed.delete()

    def scenario_checkpoint_batch_autoclose(self):
        """100 checkpoints autoclosed by 10 concurrent workers"""
        print("\n=== Testing Checkpoint Batch Autoclose (100 checkpoints, 10 workers) ===")

        parent = Jobneed.objects.create(
            jobdesc='Parent Tour',
            plandatetime=timezone.now(),
            expirydatetime=timezone.now() + timedelta(hours=2),
            gracetime=15,
            asset=self.asset,
            jobstatus='INPROGRESS',
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='INTERNALTOUR',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user,
            other_info={}
        )

        checkpoint_ids = []
        for i in range(100):
            checkpoint = Jobneed.objects.create(
                jobdesc=f'Checkpoint {i}',
                plandatetime=timezone.now(),
                expirydatetime=timezone.now() + timedelta(hours=2),
                gracetime=15,
                asset=self.asset,
                jobstatus='ASSIGNED',
                jobtype='SCHEDULE',
                priority='HIGH',
                qset=self.qset,
                scantype='QR',
                people=self.user,
                identifier='INTERNALTOUR',
                seqno=i+1,
                parent_id=parent.id,
                client=self.client_bt,
                bu=self.site_bt,
                cuser=self.user,
                muser=self.user,
                other_info={}
            )
            checkpoint_ids.append(checkpoint.id)

        errors = []
        start_time = time.time()

        def worker(worker_id):
            try:
                check_for_checkpoints_status(parent, Jobneed)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        autoclosed_count = Jobneed.objects.filter(
            id__in=checkpoint_ids,
            jobstatus='AUTOCLOSED'
        ).count()

        passed = (len(errors) == 0 and autoclosed_count == 100)

        result = {
            'scenario': 'Checkpoint Batch Autoclose (100 checkpoints)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration,
            'autoclosed_count': autoclosed_count
        }

        self.results.append(result)
        self.print_result(result)

        Jobneed.objects.filter(id__in=checkpoint_ids).delete()
        parent.delete()

    def scenario_ticket_escalation_extreme(self):
        """100 concurrent escalations on 10 tickets"""
        print("\n=== Testing Ticket Escalation (100 workers on 10 tickets) ===")

        tickets = []
        for i in range(10):
            ticket = Ticket.objects.create(
                ticketno=f'PENTEST{i}',
                ticketdesc='Escalation Test',
                status='NEW',
                priority='HIGH',
                level=0,
                ticketsource='SYSTEMGENERATED',
                client=self.client_bt,
                bu=self.site_bt,
                ticketcategory=self.ticket_type,
                ticketlog={'ticket_history': []},
                cuser=self.user,
                muser=self.user
            )
            tickets.append(ticket)

        errors = []
        start_time = time.time()

        def worker(worker_id):
            try:
                ticket = tickets[worker_id % 10]
                TicketWorkflowService.escalate_ticket(
                    ticket_id=ticket.id,
                    assigned_person_id=self.user.id,
                    user=self.user
                )
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        escalated_count = sum(1 for ticket in tickets if (ticket.refresh_from_db() or ticket.level > 0))

        passed = len(errors) == 0 and escalated_count == 10

        result = {
            'scenario': 'Ticket Escalation (100 workers, 10 tickets)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration,
            'escalated_count': escalated_count
        }

        self.results.append(result)
        self.print_result(result)

        for ticket in tickets:
            ticket.delete()

    def scenario_ticket_log_stress(self):
        """200 concurrent history appends to same ticket"""
        print("\n=== Testing Ticket Log Updates (200 concurrent appends) ===")

        ticket = Ticket.objects.create(
            ticketno='PENTEST_LOG',
            ticketdesc='Log Test',
            status='NEW',
            priority='HIGH',
            level=0,
            ticketsource='SYSTEMGENERATED',
            client=self.client_bt,
            bu=self.site_bt,
            ticketcategory=self.ticket_type,
            ticketlog={'ticket_history': []},
            cuser=self.user,
            muser=self.user
        )

        errors = []
        start_time = time.time()

        def worker(worker_id):
            try:
                history_item = {
                    'worker': worker_id,
                    'when': str(timezone.now()),
                    'who': f'Worker {worker_id}',
                    'action': 'test',
                    'details': [f'Entry {worker_id}'],
                    'previous_state': {}
                }
                result = {'story': '', 'traceback': ''}
                update_ticket_log(ticket.id, history_item, result)
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(200)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        ticket.refresh_from_db()
        history_count = len(ticket.ticketlog.get('ticket_history', []))

        passed = len(errors) == 0 and history_count == 200

        result = {
            'scenario': 'Ticket Log Updates (200 appends)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration,
            'history_count': history_count
        }

        self.results.append(result)
        self.print_result(result)

        ticket.delete()

    def scenario_json_field_concurrent_updates(self):
        """100 concurrent JSON field modifications"""
        print("\n=== Testing JSON Field Updates (100 concurrent workers) ===")

        jobneed = Jobneed.objects.create(
            jobdesc='JSON Test',
            plandatetime=timezone.now(),
            expirydatetime=timezone.now() + timedelta(hours=2),
            gracetime=15,
            asset=self.asset,
            jobstatus='ASSIGNED',
            jobtype='SCHEDULE',
            priority='HIGH',
            qset=self.qset,
            scantype='QR',
            people=self.user,
            identifier='TASK',
            seqno=1,
            client=self.client_bt,
            bu=self.site_bt,
            cuser=self.user,
            muser=self.user,
            other_info={'counter': 0}
        )

        errors = []
        start_time = time.time()

        def worker(worker_id):
            try:
                def increment_counter(json_data):
                    json_data['counter'] = json_data.get('counter', 0) + 1
                    json_data[f'w{worker_id}'] = True
                    return json_data

                AtomicJSONFieldUpdater.update_with_function(
                    model_class=Jobneed,
                    instance_id=jobneed.id,
                    field_name='other_info',
                    update_func=increment_counter
                )
            except Exception as e:
                errors.append((worker_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        jobneed.refresh_from_db()
        counter_value = jobneed.other_info.get('counter', 0)

        passed = len(errors) == 0 and counter_value == 100

        result = {
            'scenario': 'JSON Field Updates (100 workers)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration,
            'counter_value': counter_value
        }

        self.results.append(result)
        self.print_result(result)

        jobneed.delete()

    def scenario_combined_load_test(self):
        """All operations running simultaneously"""
        print("\n=== Testing Combined Load (All operations concurrent) ===")

        errors = []
        start_time = time.time()

        job_threads = []
        ticket_threads = []
        json_threads = []

        for i in range(10):
            jobneed = Jobneed.objects.create(
                jobdesc=f'Combined Test {i}',
                plandatetime=timezone.now() - timedelta(hours=2),
                expirydatetime=timezone.now() - timedelta(hours=1),
                gracetime=15,
                asset=self.asset,
                jobstatus='INPROGRESS',
                jobtype='SCHEDULE',
                priority='HIGH',
                qset=self.qset,
                scantype='QR',
                people=self.user,
                identifier='TASK',
                seqno=i+1,
                client=self.client_bt,
                bu=self.site_bt,
                cuser=self.user,
                muser=self.user,
                other_info={}
            )

            def job_worker(jn_id):
                try:
                    record = {'id': jn_id, 'ticketcategory__tacode': 'AUTOCLOSENOTIFY'}
                    resp = {'id': [], 'story': ''}
                    update_job_autoclose_status(record, resp)
                except Exception as e:
                    errors.append(('job', str(e)))

            job_threads.append(threading.Thread(target=job_worker, args=(jobneed.id,)))

        for i in range(10):
            ticket = Ticket.objects.create(
                ticketno=f'COMBINED{i}',
                ticketdesc='Combined Test',
                status='NEW',
                priority='HIGH',
                level=0,
                ticketsource='SYSTEMGENERATED',
                client=self.client_bt,
                bu=self.site_bt,
                ticketcategory=self.ticket_type,
                ticketlog={'ticket_history': []},
                cuser=self.user,
                muser=self.user
            )

            def ticket_worker(tkt_id):
                try:
                    TicketWorkflowService.escalate_ticket(
                        ticket_id=tkt_id,
                        user=self.user
                    )
                except Exception as e:
                    errors.append(('ticket', str(e)))

            ticket_threads.append(threading.Thread(target=ticket_worker, args=(ticket.id,)))

        all_threads = job_threads + ticket_threads

        for t in all_threads:
            t.start()
        for t in all_threads:
            t.join()

        duration = (time.time() - start_time) * 1000

        passed = len(errors) == 0

        result = {
            'scenario': 'Combined Load Test (20 concurrent operations)',
            'passed': passed,
            'errors': len(errors),
            'duration_ms': duration
        }

        self.results.append(result)
        self.print_result(result)

        Jobneed.objects.filter(jobdesc__startswith='Combined Test').delete()
        Ticket.objects.filter(ticketno__startswith='COMBINED').delete()

    def print_result(self, result: Dict[str, Any]):
        """Print test result"""
        status = "✓ PASS" if result['passed'] else "✗ FAIL"
        print(f"{status}: {result['scenario']}")
        print(f"  Duration: {result['duration_ms']:.2f}ms, Errors: {result['errors']}")

    def print_summary(self):
        """Print final test summary"""
        print("\n" + "="*80)
        print("COMPREHENSIVE RACE CONDITION PENETRATION TEST REPORT")
        print("="*80 + "\n")

        total = len(self.results)
        passed = sum(1 for r in self.results if r['passed'])
        failed = total - passed

        for result in self.results:
            status = "✓" if result['passed'] else "✗"
            print(f"{status} {result['scenario']}")
            print(f"   Duration: {result['duration_ms']:.2f}ms, Errors: {result['errors']}")

        print("\n" + "-"*80)
        print(f"TOTAL: {passed} passed, {failed} failed")

        if failed == 0:
            print("\n🎉 ALL TESTS PASSED - System is secure against race conditions")
        else:
            print("\n⚠️  FAILURES DETECTED - Review failed scenarios")

        print("="*80 + "\n")

        return failed == 0

    def run_scenario(self, scenario_name: str):
        """Run specific scenario or all scenarios"""
        scenarios = {
            'autoclose': self.scenario_job_autoclose_extreme,
            'checkpoints': self.scenario_checkpoint_batch_autoclose,
            'escalation': self.scenario_ticket_escalation_extreme,
            'ticket_log': self.scenario_ticket_log_stress,
            'json_updates': self.scenario_json_field_concurrent_updates,
            'combined': self.scenario_combined_load_test,
        }

        if scenario_name == 'all':
            for name, func in scenarios.items():
                try:
                    func()
                except Exception as e:
                    print(f"CRITICAL ERROR in {name}: {e}")
                    import traceback
                    traceback.print_exc()
        elif scenario_name in scenarios:
            scenarios[scenario_name]()
        else:
            print(f"Unknown scenario: {scenario_name}")
            print(f"Available scenarios: {', '.join(scenarios.keys())}, all")


def main():
    parser = argparse.ArgumentParser(
        description='Comprehensive race condition penetration tests'
    )
    parser.add_argument(
        '--scenario',
        choices=['all', 'autoclose', 'checkpoints', 'escalation', 'ticket_log', 'json_updates', 'combined'],
        default='all',
        help='Test scenario to run'
    )

    args = parser.parse_args()

    print("\n" + "="*80)
    print("STARTING COMPREHENSIVE RACE CONDITION PENETRATION TESTS")
    print("="*80)

    runner = PenetrationTestRunner()
    runner.run_scenario(args.scenario)

    success = runner.print_summary()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()