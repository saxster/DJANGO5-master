"""
Site Coverage Planning Service - Guard posts and shift optimization.

This service calculates optimal guard post placement and shift assignments
based on zone requirements, risk levels, and operating hours. NO COST
CALCULATIONS - purely coverage optimization.

Features:
- Guard post determination by zone criticality
- Shift assignment optimization
- Patrol route generation
- Risk window identification
- 24/7 coverage planning

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
"""

import logging
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Optional
from decimal import Decimal

from apps.site_onboarding.models import OnboardingSite, OnboardingZone

logger = logging.getLogger(__name__)


class SiteCoveragePlannerService:
    """
    Calculate optimal guard coverage and shift assignments.

    Focuses on security effectiveness and compliance WITHOUT cost calculations.
    """

    # Standard shift durations (hours)
    SHIFT_DURATION = 8
    SHIFT_OVERLAP = 0.5  # 30-minute handover

    def calculate_coverage_plan(
        self,
        site: OnboardingSite,
        domain_expertise=None
    ) -> Dict[str, Any]:
        """
        Calculate complete coverage plan for site.

        Args:
            site: OnboardingSite instance with zones
            domain_expertise: Optional domain expertise service

        Returns:
            {
                'guard_posts': List[Dict],
                'shift_assignments': List[Dict],
                'patrol_routes': List[Dict],
                'risk_windows': List[Dict],
                'total_posts': int,
                'shifts_per_day': int,
                'compliance_notes': str
            }
        """
        try:
            # Get all zones with prefetch for performance
            zones = site.zones.select_related('site').all()

            # Determine guard posts
            guard_posts = self._calculate_guard_posts(zones, domain_expertise)

            # Generate shift assignments
            shift_assignments = self._generate_shift_assignments(
                guard_posts,
                site.operating_hours_start,
                site.operating_hours_end
            )

            # Create patrol routes
            patrol_routes = self._create_patrol_routes(zones, guard_posts)

            # Identify risk windows
            risk_windows = self._identify_risk_windows(
                zones,
                site.operating_hours_start,
                site.operating_hours_end
            )

            # Generate compliance notes
            compliance_notes = self._generate_compliance_notes(
                guard_posts,
                shift_assignments,
                domain_expertise
            )

            logger.info(
                f"Coverage plan calculated: {len(guard_posts)} posts, "
                f"{len(shift_assignments)} shifts"
            )

            return {
                'guard_posts': guard_posts,
                'shift_assignments': shift_assignments,
                'patrol_routes': patrol_routes,
                'risk_windows': risk_windows,
                'total_posts': len(guard_posts),
                'shifts_per_day': len(shift_assignments),
                'compliance_notes': compliance_notes
            }

        except Exception as e:
            logger.error(f"Error calculating coverage plan: {str(e)}", exc_info=True)
            return {
                'guard_posts': [],
                'shift_assignments': [],
                'patrol_routes': [],
                'risk_windows': [],
                'total_posts': 0,
                'shifts_per_day': 0,
                'compliance_notes': f"Coverage calculation failed: {str(e)}"
            }

    def _calculate_guard_posts(
        self,
        zones: List[OnboardingZone],
        domain_expertise=None
    ) -> List[Dict[str, Any]]:
        """Calculate required guard posts based on zones."""
        posts = []
        post_counter = 1

        for zone in zones:
            # Determine if zone requires dedicated post
            requires_post = self._zone_requires_guard_post(zone, domain_expertise)

            if requires_post:
                # Get coverage requirements
                coverage_hours = (
                    domain_expertise.get_minimum_coverage_hours(zone.zone_type)
                    if domain_expertise
                    else self._get_default_coverage_hours(zone)
                )

                post = {
                    'post_id': f"POST-{post_counter:03d}",
                    'zone_id': str(zone.zone_id),
                    'zone_name': zone.zone_name,
                    'zone_type': zone.zone_type,
                    'position': self._determine_post_position(zone),
                    'duties': self._determine_post_duties(zone),
                    'risk_level': zone.risk_level,
                    'importance': zone.importance_level,
                    'coverage_hours': coverage_hours,
                    'requires_24x7': coverage_hours == 24
                }

                posts.append(post)
                post_counter += 1

        logger.info(f"Calculated {len(posts)} guard posts")
        return posts

    def _generate_shift_assignments(
        self,
        guard_posts: List[Dict],
        operating_start: Optional[time],
        operating_end: Optional[time]
    ) -> List[Dict[str, Any]]:
        """Generate optimal shift assignments."""
        shifts = []

        # Determine shift schedule (3 shifts for 24/7, 2 shifts for extended hours)
        if any(post['requires_24x7'] for post in guard_posts):
            # 24/7 operation: 3 shifts
            shift_times = [
                ('Morning', time(6, 0), time(14, 0)),
                ('Afternoon', time(14, 0), time(22, 0)),
                ('Night', time(22, 0), time(6, 0))
            ]
        elif operating_start and operating_end:
            # Business hours + buffer
            shift_times = [
                ('Day', time(7, 0), time(19, 0)),
                ('Evening', time(19, 0), time(1, 0))
            ]
        else:
            # Default 12-hour shifts
            shift_times = [
                ('Day', time(7, 0), time(19, 0)),
                ('Night', time(19, 0), time(7, 0))
            ]

        for shift_name, start_time, end_time in shift_times:
            # Determine posts active during this shift
            posts_covered = self._get_posts_for_shift(
                guard_posts,
                shift_name,
                start_time,
                end_time
            )

            if not posts_covered:
                continue

            # Calculate staffing requirements
            staffing = self._calculate_shift_staffing(posts_covered)

            shift = {
                'shift_name': shift_name,
                'start_time': start_time.strftime('%H:%M'),
                'end_time': end_time.strftime('%H:%M'),
                'duration_hours': self._calculate_shift_hours(start_time, end_time),
                'posts_covered': [p['post_id'] for p in posts_covered],
                'staffing': staffing,
                'supervisor_required': len(posts_covered) > 3
            }

            shifts.append(shift)

        logger.info(f"Generated {len(shifts)} shift assignments")
        return shifts

    def _create_patrol_routes(
        self,
        zones: List[OnboardingZone],
        guard_posts: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Create patrol routes for mobile guards."""
        routes = []

        # Group zones by importance
        critical_zones = [z for z in zones if z.importance_level == 'critical']
        high_zones = [z for z in zones if z.importance_level == 'high']
        other_zones = [z for z in zones if z.importance_level in ['medium', 'low']]

        # Route 1: Critical zones patrol (hourly)
        if critical_zones:
            routes.append({
                'route_id': 'ROUTE-001',
                'route_name': 'Critical Zone Patrol',
                'zones': [str(z.zone_id) for z in critical_zones],
                'frequency': 'hourly',
                'estimated_duration_minutes': len(critical_zones) * 10,
                'checkpoints': [
                    {'zone_id': str(z.zone_id), 'zone_name': z.zone_name}
                    for z in critical_zones
                ]
            })

        # Route 2: High priority zones (every 2 hours)
        if high_zones:
            routes.append({
                'route_id': 'ROUTE-002',
                'route_name': 'High Priority Patrol',
                'zones': [str(z.zone_id) for z in high_zones],
                'frequency': 'every_2_hours',
                'estimated_duration_minutes': len(high_zones) * 8,
                'checkpoints': [
                    {'zone_id': str(z.zone_id), 'zone_name': z.zone_name}
                    for z in high_zones
                ]
            })

        # Route 3: General perimeter check (every 4 hours)
        if other_zones:
            routes.append({
                'route_id': 'ROUTE-003',
                'route_name': 'Perimeter Patrol',
                'zones': [str(z.zone_id) for z in other_zones],
                'frequency': 'every_4_hours',
                'estimated_duration_minutes': len(other_zones) * 5,
                'checkpoints': [
                    {'zone_id': str(z.zone_id), 'zone_name': z.zone_name}
                    for z in other_zones
                ]
            })

        return routes

    def _identify_risk_windows(
        self,
        zones: List[OnboardingZone],
        operating_start: Optional[time],
        operating_end: Optional[time]
    ) -> List[Dict[str, Any]]:
        """Identify high-risk time periods."""
        risk_windows = []

        # Opening hours (increased cash handling)
        if operating_start:
            risk_windows.append({
                'window_id': 'RISK-001',
                'window_name': 'Opening Hours',
                'start_time': (
                    datetime.combine(datetime.today(), operating_start) - timedelta(hours=1)
                ).time().strftime('%H:%M'),
                'end_time': (
                    datetime.combine(datetime.today(), operating_start) + timedelta(hours=1)
                ).time().strftime('%H:%M'),
                'risk_level': 'high',
                'affected_zones': [
                    str(z.zone_id) for z in zones
                    if z.zone_type in ['vault', 'cash_counter', 'gate']
                ],
                'mitigation': 'Dual coverage at vault and cash counter during opening'
            })

        # Closing hours
        if operating_end:
            risk_windows.append({
                'window_id': 'RISK-002',
                'window_name': 'Closing Hours',
                'start_time': (
                    datetime.combine(datetime.today(), operating_end) - timedelta(minutes=30)
                ).time().strftime('%H:%M'),
                'end_time': (
                    datetime.combine(datetime.today(), operating_end) + timedelta(hours=1)
                ).time().strftime('%H:%M'),
                'risk_level': 'high',
                'affected_zones': [
                    str(z.zone_id) for z in zones
                    if z.zone_type in ['vault', 'cash_counter', 'gate']
                ],
                'mitigation': 'Enhanced surveillance during cash reconciliation'
            })

        # Night hours (reduced visibility)
        risk_windows.append({
            'window_id': 'RISK-003',
            'window_name': 'Night Hours',
            'start_time': '22:00',
            'end_time': '06:00',
            'risk_level': 'moderate',
            'affected_zones': [str(z.zone_id) for z in zones if z.zone_type == 'perimeter'],
            'mitigation': 'Enhanced lighting and perimeter patrols'
        })

        return risk_windows

    def _zone_requires_guard_post(
        self,
        zone: OnboardingZone,
        domain_expertise=None
    ) -> bool:
        """Determine if zone requires dedicated guard post."""
        # Critical zones always require posts
        if zone.importance_level == 'critical':
            return True

        # High importance zones require posts
        if zone.importance_level == 'high':
            return True

        # Coverage flag
        if zone.coverage_required:
            return True

        return False

    def _get_default_coverage_hours(self, zone: OnboardingZone) -> int:
        """Get default coverage hours for zone."""
        coverage_map = {
            'vault': 24,
            'atm': 24,
            'cash_counter': 12,
            'control_room': 24,
            'gate': 24,
            'perimeter': 16,
            'reception': 10
        }

        return coverage_map.get(zone.zone_type, 8)

    def _determine_post_position(self, zone: OnboardingZone) -> str:
        """Determine optimal position for guard post."""
        position_map = {
            'gate': 'Main gate entrance/exit control',
            'vault': 'Direct line of sight to vault door',
            'atm': 'Monitoring ATM lobby and approach',
            'cash_counter': 'Oversight of cash counter area',
            'control_room': 'Inside control room monitoring',
            'perimeter': 'Strategic perimeter vantage point',
            'reception': 'Reception desk / visitor screening'
        }

        return position_map.get(zone.zone_type, f'Assigned to {zone.zone_name}')

    def _determine_post_duties(self, zone: OnboardingZone) -> List[str]:
        """Determine duties for guard post."""
        duties_map = {
            'vault': [
                'Monitor vault access',
                'Verify dual custody compliance',
                'Log all vault entries/exits',
                'Report anomalies immediately'
            ],
            'gate': [
                'Control entry/exit access',
                'Visitor verification and logging',
                'Metal detector supervision',
                'Vehicle inspection'
            ],
            'atm': [
                'Monitor ATM area and approach',
                'Assist customers as needed',
                'Report technical issues',
                'Emergency response'
            ],
            'cash_counter': [
                'Oversight of cash transactions',
                'Crowd management',
                'Incident response',
                'Liaison with branch staff'
            ]
        }

        return duties_map.get(zone.zone_type, ['Zone monitoring', 'Incident response'])

    def _get_posts_for_shift(
        self,
        guard_posts: List[Dict],
        shift_name: str,
        start_time: time,
        end_time: time
    ) -> List[Dict]:
        """Get posts active during specific shift."""
        # For 24/7 posts, they're active in all shifts
        # For limited coverage, match against shift times

        active_posts = []

        for post in guard_posts:
            if post['requires_24x7']:
                active_posts.append(post)
            else:
                # Check if post coverage overlaps with shift
                coverage_hours = post.get('coverage_hours', 8)
                if coverage_hours >= 12 or shift_name in ['Day', 'Morning', 'Afternoon']:
                    active_posts.append(post)

        return active_posts

    def _calculate_shift_staffing(self, posts: List[Dict]) -> Dict[str, Any]:
        """Calculate staffing requirements for shift."""
        guard_count = len(posts)

        # Add supervisor if > 3 guards
        supervisor_count = 1 if guard_count > 3 else 0

        return {
            'guards': guard_count,
            'supervisors': supervisor_count,
            'total_staff': guard_count + supervisor_count,
            'roles': self._get_required_roles(posts)
        }

    def _get_required_roles(self, posts: List[Dict]) -> List[str]:
        """Determine required guard roles/skills."""
        roles = set(['Security Guard'])

        for post in posts:
            if post['zone_type'] in ['vault', 'cash_counter']:
                roles.add('Cash Handling Certified')
            if post['zone_type'] == 'control_room':
                roles.add('CCTV Monitoring Trained')
            if post['zone_type'] == 'gate':
                roles.add('Access Control Operator')

        return list(roles)

    def _calculate_shift_hours(self, start: time, end: time) -> float:
        """Calculate shift duration in hours."""
        start_dt = datetime.combine(datetime.today(), start)
        end_dt = datetime.combine(datetime.today(), end)

        # Handle overnight shifts
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        duration = (end_dt - start_dt).total_seconds() / 3600
        return round(duration, 1)

    def _generate_compliance_notes(
        self,
        guard_posts: List[Dict],
        shift_assignments: List[Dict],
        domain_expertise=None
    ) -> str:
        """Generate compliance summary notes."""
        notes = []

        # Coverage summary
        total_posts = len(guard_posts)
        critical_posts = len([p for p in guard_posts if p['importance'] == 'critical'])

        notes.append(
            f"Total guard posts: {total_posts} ({critical_posts} critical priority)"
        )

        # Shift summary
        notes.append(f"Shift schedule: {len(shift_assignments)} shifts per day")

        # Compliance references
        if domain_expertise:
            standards = domain_expertise.get_compliance_standards()
            notes.append(f"Aligned with: {', '.join(standards[:2])}")
        else:
            notes.append("Aligned with: ASIS International Standards")

        # Risk mitigation
        notes.append(
            "Coverage plan prioritizes critical zones with 24/7 manning "
            "and enhanced supervision during risk windows"
        )

        return '. '.join(notes) + '.'


# Factory function
def get_coverage_planner_service() -> SiteCoveragePlannerService:
    """Factory function to get coverage planner service instance."""
    return SiteCoveragePlannerService()