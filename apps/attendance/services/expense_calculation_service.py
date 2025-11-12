"""
Expense Calculation Service

Calculates travel expenses and allowances based on distance and transport mode.

Features:
- Distance-based reimbursement
- Tiered rate structures
- Transport mode specific rates
- Per-client rate configuration
- Automatic calculation on clock-out
- Integration with payroll

Rates:
- Configurable per client/BU
- Support for tiered rates (first X km @ rate1, remaining @ rate2)
- Different rates by transport mode
"""

from typing import Dict, Any, Optional, Tuple
from decimal import Decimal
from django.db import models
from apps.attendance.models import PeopleEventlog
from apps.attendance.exceptions import AttendanceValidationError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
import logging

logger = logging.getLogger(__name__)


class ReimbursementRate(models.Model):
    """
    Reimbursement rate configuration per client and transport mode.
    """

    client = models.ForeignKey(
        'client_onboarding.Bt',
        on_delete=models.CASCADE,
        related_name='reimbursement_rates',
        help_text="Client this rate applies to"
    )

    transport_mode = models.CharField(
        max_length=50,
        choices=PeopleEventlog.TransportMode.choices,
        help_text="Transport mode for this rate"
    )

    # Base rate
    rate_per_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Reimbursement rate per kilometer"
    )

    # Tiered rates (optional)
    tier1_max_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum km for tier 1 rate (e.g., first 10km)"
    )

    tier2_rate_per_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Rate for tier 2 (beyond tier1_max_km)"
    )

    # Allowances
    daily_allowance = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Fixed daily allowance regardless of distance"
    )

    minimum_distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Minimum distance before reimbursement applies"
    )

    maximum_daily_reimbursement = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Maximum total reimbursement per day"
    )

    # Metadata
    effective_date = models.DateField(help_text="When this rate becomes effective")
    expiration_date = models.DateField(
        null=True,
        blank=True,
        help_text="When this rate expires"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'reimbursement_rate'
        verbose_name = 'Reimbursement Rate'
        verbose_name_plural = 'Reimbursement Rates'
        unique_together = [['client', 'transport_mode', 'effective_date']]
        indexes = [
            models.Index(fields=['client', 'is_active'], name='rr_client_active_idx'),
            models.Index(fields=['effective_date'], name='rr_effective_idx'),
        ]

    def __str__(self):
        return f"{self.client.name} - {self.transport_mode}: ${self.rate_per_km}/km"


class ExpenseCalculationService:
    """
    Service for calculating travel expenses and reimbursements.
    """

    @classmethod
    def calculate_expense(
        cls,
        attendance_record: PeopleEventlog,
        force_recalculate: bool = False
    ) -> Decimal:
        """
        Calculate total expense for attendance record.

        Args:
            attendance_record: PeopleEventlog instance
            force_recalculate: Recalculate even if already calculated

        Returns:
            Total expense amount

        Calculation:
            Total = Distance-based reimbursement + Daily allowance
        """
        # Skip if already calculated (unless force)
        if attendance_record.expamt and attendance_record.expamt > 0 and not force_recalculate:
            logger.debug(f"Expense already calculated for record {attendance_record.id}")
            return Decimal(str(attendance_record.expamt))

        try:
            # Get distance
            distance_km = attendance_record.distance
            if not distance_km or distance_km <= 0:
                logger.debug(f"No distance recorded for attendance {attendance_record.id}")
                return Decimal('0.00')

            # Get primary transport mode
            transport_mode = cls._get_primary_transport_mode(attendance_record)

            # Get applicable rate
            rate = cls._get_rate(
                client_id=attendance_record.client_id,
                transport_mode=transport_mode,
                date=attendance_record.datefor
            )

            if not rate:
                logger.warning(f"No reimbursement rate found for {transport_mode}")
                return Decimal('0.00')

            # Check minimum distance
            if distance_km < rate.minimum_distance_km:
                logger.debug(f"Distance {distance_km}km below minimum {rate.minimum_distance_km}km")
                expense = rate.daily_allowance
            else:
                # Calculate distance-based reimbursement
                distance_based = cls._calculate_distance_reimbursement(distance_km, rate)

                # Add daily allowance
                expense = distance_based + rate.daily_allowance

            # Apply maximum cap if configured
            if rate.maximum_daily_reimbursement:
                expense = min(expense, rate.maximum_daily_reimbursement)

            # Update attendance record
            attendance_record.expamt = float(expense)
            attendance_record.save(update_fields=['expamt'])

            logger.info(
                f"Calculated expense for attendance {attendance_record.id}: "
                f"${expense} ({distance_km}km @ {rate.rate_per_km}/km)"
            )

            return expense

        except (ValueError, TypeError, ArithmeticError) as e:
            logger.error(f"Expense calculation failed for record {attendance_record.id}: {e}", exc_info=True)
            return Decimal('0.00')

    @staticmethod
    def _get_primary_transport_mode(attendance_record: PeopleEventlog) -> str:
        """Get primary transport mode from record"""
        if attendance_record.transportmodes and len(attendance_record.transportmodes) > 0:
            # Return first non-NONE mode
            for mode in attendance_record.transportmodes:
                if mode != 'NONE':
                    return mode

        return 'NONE'  # Default to walking

    @staticmethod
    def _get_rate(
        client_id: int,
        transport_mode: str,
        date
    ) -> Optional[ReimbursementRate]:
        """
        Get applicable reimbursement rate.

        Args:
            client_id: Client ID
            transport_mode: Transport mode
            date: Date for rate lookup

        Returns:
            ReimbursementRate or None
        """
        try:
            from django.db.models import Q

            # Find rate effective for this date
            rate = ReimbursementRate.objects.filter(
                client_id=client_id,
                transport_mode=transport_mode,
                is_active=True,
                effective_date__lte=date
            ).filter(
                Q(expiration_date__isnull=True) | Q(expiration_date__gte=date)
            ).order_by('-effective_date').first()

            return rate

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to fetch reimbursement rate: {e}")
            return None

    @staticmethod
    def _calculate_distance_reimbursement(
        distance_km: float,
        rate: ReimbursementRate
    ) -> Decimal:
        """
        Calculate distance-based reimbursement with tiered rates.

        Args:
            distance_km: Distance traveled
            rate: ReimbursementRate configuration

        Returns:
            Reimbursement amount
        """
        distance_decimal = Decimal(str(distance_km))

        # Check if tiered rates apply
        if rate.tier1_max_km and rate.tier2_rate_per_km:
            # Tiered calculation
            tier1_km = min(distance_decimal, rate.tier1_max_km)
            tier2_km = max(Decimal('0'), distance_decimal - rate.tier1_max_km)

            reimbursement = (
                tier1_km * rate.rate_per_km +
                tier2_km * rate.tier2_rate_per_km
            )
        else:
            # Simple rate
            reimbursement = distance_decimal * rate.rate_per_km

        return reimbursement.quantize(Decimal('0.01'))  # Round to 2 decimal places

    @classmethod
    def bulk_calculate_expenses(
        cls,
        start_date,
        end_date,
        client_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Calculate expenses for multiple records in date range.

        Args:
            start_date: Start date
            end_date: End date
            client_id: Optional client filter

        Returns:
            Calculation statistics
        """
        queryset = PeopleEventlog.objects.filter(
            datefor__gte=start_date,
            datefor__lte=end_date,
            distance__gt=0
        )

        if client_id:
            queryset = queryset.filter(client_id=client_id)

        total_records = queryset.count()
        calculated = 0
        total_amount = Decimal('0.00')

        for record in queryset.iterator():
            expense = cls.calculate_expense(record)
            if expense > 0:
                calculated += 1
                total_amount += expense

        return {
            'total_records': total_records,
            'calculated': calculated,
            'total_amount': float(total_amount),
            'average_per_record': float(total_amount / calculated) if calculated > 0 else 0.0,
        }
