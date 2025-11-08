#!/usr/bin/env python
"""
Verification script for Top 20 God File Refactoring Initiative.

Tracks progress, validates refactorings, and generates reports.

Usage:
    python scripts/verify_top20_refactoring.py --report
    python scripts/verify_top20_refactoring.py --file apps/journal/ml/analytics_engine.py
    python scripts/verify_top20_refactoring.py --summary
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse
import json
from datetime import datetime

# Top 20 files to refactor (from analysis)
TOP_20_FILES = [
    {
        "path": "apps/journal/ml/analytics_engine.py",
        "current_lines": 1503,
        "target_lines": 150,
        "type": "ML Service",
        "priority": 1,
        "split_plan": [
            "apps/journal/ml/analytics_engine.py",
            "apps/journal/ml/feature_extractors.py",
            "apps/journal/ml/model_trainers.py",
            "apps/journal/ml/predictors.py",
        ]
    },
    {
        "path": "apps/face_recognition/ai_enhanced_engine.py",
        "current_lines": 1481,
        "target_lines": 150,
        "type": "AI Service",
        "priority": 2,
        "split_plan": [
            "apps/face_recognition/ai_enhanced_engine.py",
            "apps/face_recognition/embeddings.py",
            "apps/face_recognition/recognition_pipeline.py",
            "apps/face_recognition/quality_checks.py",
        ]
    },
    {
        "path": "apps/core_onboarding/background_tasks/conversation_tasks.py",
        "current_lines": 1447,
        "target_lines": 100,
        "type": "Celery Tasks",
        "priority": 4,
        "split_plan": [
            "apps/core_onboarding/background_tasks/conversation_tasks.py",
            "apps/core_onboarding/background_tasks/nlp_tasks.py",
            "apps/core_onboarding/background_tasks/notification_tasks.py",
            "apps/core_onboarding/background_tasks/analytics_tasks.py",
        ]
    },
    {
        "path": "apps/scheduler/import_export_resources.py",
        "current_lines": 1312,
        "target_lines": 150,
        "type": "Resources",
        "priority": 5,
        "split_plan": [
            "apps/scheduler/resources/task_resource.py",
            "apps/scheduler/resources/schedule_resource.py",
            "apps/scheduler/resources/shift_resource.py",
            "apps/scheduler/resources/report_resource.py",
        ]
    },
    {
        "path": "apps/wellness/services/crisis_prevention_system.py",
        "current_lines": 1254,
        "target_lines": 150,
        "type": "Service",
        "priority": 7,
        "split_plan": [
            "apps/wellness/services/crisis_prevention/detection.py",
            "apps/wellness/services/crisis_prevention/escalation.py",
            "apps/wellness/services/crisis_prevention/intervention.py",
        ]
    },
    {
        "path": "apps/api/mobile_consumers.py",
        "current_lines": 1250,
        "target_lines": 150,
        "type": "WebSocket",
        "priority": 9,
        "split_plan": [
            "apps/api/consumers/mobile_base.py",
            "apps/api/consumers/chat_consumer.py",
            "apps/api/consumers/notification_consumer.py",
            "apps/api/consumers/location_consumer.py",
        ]
    },
    {
        "path": "apps/attendance/managers.py",
        "current_lines": 1234,
        "target_lines": 100,
        "type": "Managers",
        "priority": 10,
        "split_plan": [
            "apps/attendance/managers/base.py",
            "apps/attendance/managers/attendance_manager.py",
            "apps/attendance/managers/shift_manager.py",
            "apps/attendance/managers/leave_manager.py",
            "apps/attendance/managers/reporting_manager.py",
        ]
    },
    {
        "path": "apps/face_recognition/enhanced_engine.py",
        "current_lines": 1151,
        "target_lines": 150,
        "type": "AI Service",
        "priority": 11,
        "split_plan": [
            "apps/face_recognition/enhanced_engine.py",
            "apps/face_recognition/detection_pipeline.py",
            "apps/face_recognition/verification_service.py",
        ]
    },
    {
        "path": "apps/wellness/services/intervention_response_tracker.py",
        "current_lines": 1148,
        "target_lines": 150,
        "type": "Service",
        "priority": 12,
        "split_plan": [
            "apps/wellness/services/intervention_response/tracker.py",
            "apps/wellness/services/intervention_response/analytics.py",
        ]
    },
    {
        "path": "apps/journal/services/analytics_service.py",
        "current_lines": 1144,
        "target_lines": 150,
        "type": "Service",
        "priority": 13,
        "split_plan": [
            "apps/journal/services/analytics_service.py",
            "apps/journal/services/metrics_calculator.py",
            "apps/journal/services/trend_analyzer.py",
        ]
    },
    {
        "path": "apps/onboarding_api/knowledge_views.py",
        "current_lines": 1122,
        "target_lines": 100,
        "type": "Views",
        "priority": 14,
        "split_plan": [
            "apps/onboarding_api/views/knowledge/search_views.py",
            "apps/onboarding_api/views/knowledge/content_views.py",
            "apps/onboarding_api/views/knowledge/category_views.py",
        ]
    },
    {
        "path": "apps/onboarding_api/integration/mapper.py",
        "current_lines": 1105,
        "target_lines": 150,
        "type": "Mapper",
        "priority": 15,
        "split_plan": [
            "apps/onboarding_api/integration/mappers/user_mapper.py",
            "apps/onboarding_api/integration/mappers/content_mapper.py",
            "apps/onboarding_api/integration/mappers/workflow_mapper.py",
        ]
    },
    {
        "path": "apps/core/validation.py",
        "current_lines": 1070,
        "target_lines": 100,
        "type": "Validators",
        "priority": 16,
        "split_plan": [
            "apps/core/validation/form_validators.py",
            "apps/core/validation/model_validators.py",
            "apps/core/validation/business_rules.py",
            "apps/core/validation/security_validators.py",
        ]
    },
    {
        "path": "apps/journal/services/pattern_analyzer.py",
        "current_lines": 1058,
        "target_lines": 150,
        "type": "Service",
        "priority": 17,
        "split_plan": [
            "apps/journal/services/pattern_analyzer.py",
            "apps/journal/services/pattern_detection.py",
            "apps/journal/services/anomaly_detection.py",
        ]
    },
    {
        "path": "apps/core/decorators.py",
        "current_lines": 1048,
        "target_lines": 50,
        "type": "Decorators",
        "priority": 18,
        "split_plan": [
            "apps/core/decorators/auth_decorators.py",
            "apps/core/decorators/cache_decorators.py",
            "apps/core/decorators/logging_decorators.py",
            "apps/core/decorators/permission_decorators.py",
        ]
    },
    {
        "path": "apps/wellness/services/content_delivery.py",
        "current_lines": 1044,
        "target_lines": 150,
        "type": "Service",
        "priority": 19,
        "split_plan": [
            "apps/wellness/services/content_delivery.py",
            "apps/wellness/services/content_selector.py",
            "apps/wellness/services/personalization_engine.py",
        ]
    },
    {
        "path": "apps/journal/sync.py",
        "current_lines": 1034,
        "target_lines": 150,
        "type": "Sync Service",
        "priority": 20,
        "split_plan": [
            "apps/journal/sync/sync_manager.py",
            "apps/journal/sync/conflict_resolver.py",
            "apps/journal/sync/batch_processor.py",
        ]
    },
]


def count_lines(filepath: Path) -> int:
    """Count non-empty, non-comment lines in a Python file."""
    if not filepath.exists():
        return 0
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Count non-empty, non-comment lines
        count = 0
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                count += 1
        return count
    except Exception:
        return 0


def check_file_status(base_path: Path, file_info: Dict) -> Dict:
    """Check the refactoring status of a single file."""
    original_path = base_path / file_info["path"]
    
    status = {
        "path": file_info["path"],
        "priority": file_info["priority"],
        "type": file_info["type"],
        "original_lines": count_lines(original_path),
        "target_lines": file_info["target_lines"],
        "split_files_exist": [],
        "split_files_lines": {},
        "status": "pending",
        "completion_percentage": 0,
    }
    
    # Check if original file exists
    if not original_path.exists():
        status["status"] = "missing"
        return status
    
    # Check if file already meets target
    if status["original_lines"] <= file_info["target_lines"]:
        status["status"] = "complete"
        status["completion_percentage"] = 100
        return status
    
    # Check split files
    for split_file in file_info["split_plan"]:
        split_path = base_path / split_file
        if split_path.exists():
            status["split_files_exist"].append(split_file)
            status["split_files_lines"][split_file] = count_lines(split_path)
    
    # Determine status
    if len(status["split_files_exist"]) == 0:
        status["status"] = "pending"
        status["completion_percentage"] = 0
    elif len(status["split_files_exist"]) == len(file_info["split_plan"]):
        # Check if all split files meet targets
        all_meet_target = all(
            lines <= file_info["target_lines"]
            for lines in status["split_files_lines"].values()
        )
        if all_meet_target:
            status["status"] = "complete"
            status["completion_percentage"] = 100
        else:
            status["status"] = "in_progress"
            status["completion_percentage"] = 75
    else:
        status["status"] = "in_progress"
        status["completion_percentage"] = int(
            (len(status["split_files_exist"]) / len(file_info["split_plan"])) * 100
        )
    
    return status


def generate_report(base_path: Path) -> None:
    """Generate comprehensive refactoring progress report."""
    print("=" * 80)
    print("TOP 20 GOD FILE REFACTORING - PROGRESS REPORT")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    results = []
    for file_info in TOP_20_FILES:
        result = check_file_status(base_path, file_info)
        results.append(result)
    
    # Summary statistics
    total = len(results)
    complete = sum(1 for r in results if r["status"] == "complete")
    in_progress = sum(1 for r in results if r["status"] == "in_progress")
    pending = sum(1 for r in results if r["status"] == "pending")
    missing = sum(1 for r in results if r["status"] == "missing")
    
    print("SUMMARY")
    print("-" * 80)
    print(f"Total Files:       {total}")
    print(f"✅ Complete:       {complete} ({complete/total*100:.1f}%)")
    print(f"🚧 In Progress:    {in_progress} ({in_progress/total*100:.1f}%)")
    print(f"⏳ Pending:        {pending} ({pending/total*100:.1f}%)")
    print(f"❌ Missing:        {missing} ({missing/total*100:.1f}%)")
    print()
    
    # Overall progress
    avg_progress = sum(r["completion_percentage"] for r in results) / total
    print(f"Overall Progress: {avg_progress:.1f}%")
    print()
    
    # Detailed status
    print("DETAILED STATUS")
    print("-" * 80)
    print(f"{'Priority':<10} {'Status':<12} {'Type':<15} {'Progress':<10} {'File'}")
    print("-" * 80)
    
    for result in sorted(results, key=lambda x: x["priority"]):
        status_emoji = {
            "complete": "✅",
            "in_progress": "🚧",
            "pending": "⏳",
            "missing": "❌",
        }.get(result["status"], "❓")
        
        print(
            f"{result['priority']:<10} "
            f"{status_emoji} {result['status']:<10} "
            f"{result['type']:<15} "
            f"{result['completion_percentage']:>3}% "
            f"{result['path']}"
        )
    
    print()
    
    # Files in progress details
    in_progress_files = [r for r in results if r["status"] == "in_progress"]
    if in_progress_files:
        print("IN-PROGRESS FILES DETAIL")
        print("-" * 80)
        for result in in_progress_files:
            print(f"\n{result['path']} (Priority {result['priority']})")
            print(f"  Original: {result['original_lines']} lines")
            print(f"  Target: {result['target_lines']} lines per file")
            print(f"  Split files created: {len(result['split_files_exist'])}")
            for split_file, lines in result["split_files_lines"].items():
                status = "✅" if lines <= result["target_lines"] else "⚠️"
                print(f"    {status} {split_file}: {lines} lines")
        print()
    
    # Next steps
    print("NEXT STEPS")
    print("-" * 80)
    pending_files = [r for r in results if r["status"] == "pending"][:5]
    if pending_files:
        print("Top 5 files to refactor next (by priority):")
        for result in pending_files:
            print(f"  {result['priority']}. {result['path']}")
            print(f"     Type: {result['type']}, {result['original_lines']} lines → {result['target_lines']} lines")
    else:
        print("🎉 All files are complete or in progress!")
    print()
    
    # Save JSON report
    report_path = base_path / "TOP20_REFACTORING_REPORT.json"
    with open(report_path, 'w') as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "complete": complete,
                "in_progress": in_progress,
                "pending": pending,
                "missing": missing,
                "overall_progress": avg_progress,
            },
            "files": results,
        }, f, indent=2)
    
    print(f"Full report saved to: {report_path}")
    print()


def check_specific_file(base_path: Path, filepath: str) -> None:
    """Check status of a specific file."""
    file_info = next((f for f in TOP_20_FILES if f["path"] == filepath), None)
    
    if not file_info:
        print(f"Error: {filepath} not found in Top 20 list")
        sys.exit(1)
    
    result = check_file_status(base_path, file_info)
    
    print("=" * 80)
    print(f"FILE REFACTORING STATUS: {filepath}")
    print("=" * 80)
    print()
    print(f"Priority:          {result['priority']}")
    print(f"Type:              {result['type']}")
    print(f"Status:            {result['status']}")
    print(f"Progress:          {result['completion_percentage']}%")
    print()
    print(f"Original Lines:    {result['original_lines']}")
    print(f"Target Lines:      {result['target_lines']}")
    print()
    print("Split Plan:")
    for split_file in file_info["split_plan"]:
        exists = split_file in result["split_files_exist"]
        lines = result["split_files_lines"].get(split_file, 0)
        status = "✅" if exists and lines <= file_info["target_lines"] else ("⚠️" if exists else "⏳")
        print(f"  {status} {split_file}")
        if exists:
            print(f"      {lines} lines")
    print()


def print_summary(base_path: Path) -> None:
    """Print quick summary."""
    results = [check_file_status(base_path, f) for f in TOP_20_FILES]
    
    complete = sum(1 for r in results if r["status"] == "complete")
    total = len(results)
    avg_progress = sum(r["completion_percentage"] for r in results) / total
    
    print(f"Top 20 Refactoring Progress: {complete}/{total} complete ({avg_progress:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Verify Top 20 God File Refactoring Progress"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate full progress report"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Check status of specific file"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print quick summary"
    )
    
    args = parser.parse_args()
    
    # Determine base path
    base_path = Path(__file__).parent.parent
    
    if args.file:
        check_specific_file(base_path, args.file)
    elif args.summary:
        print_summary(base_path)
    elif args.report:
        generate_report(base_path)
    else:
        # Default: show summary
        print_summary(base_path)
        print("\nFor detailed report, run: python scripts/verify_top20_refactoring.py --report")


if __name__ == "__main__":
    main()
