from django.db import models
from apps.peoples.models import BaseModel
from apps.tenants.models import TenantAwareModel
from django.utils.translation import gettext_lazy as _
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.postgres.fields import ArrayField
from apps.activity.managers.question_manager import (
    QuestionManager,
    QuestionSetManager,
    QsetBlngManager,
)
from apps.activity.enums import AnswerType as UnifiedAnswerType, AvptType as UnifiedAvptType, QuestionSetType as UnifiedQuestionSetType
import warnings


class Question(BaseModel, TenantAwareModel):
    # Backward compatibility: Proxy to centralized enums
    # DEPRECATION WARNING: Direct use of Question.AnswerType is deprecated.
    # Use apps.activity.enums.AnswerType instead.
    class AnswerType(models.TextChoices):
        """
        DEPRECATED: Use apps.activity.enums.AnswerType instead.

        This class is maintained for backward compatibility only.
        All values proxy to the centralized enum.
        """
        CHECKBOX = UnifiedAnswerType.CHECKBOX
        DATE = UnifiedAnswerType.DATE
        DROPDOWN = UnifiedAnswerType.DROPDOWN
        EMAILID = UnifiedAnswerType.EMAILID
        MULTILINE = UnifiedAnswerType.MULTILINE
        NUMERIC = UnifiedAnswerType.NUMERIC
        SIGNATURE = UnifiedAnswerType.SIGNATURE
        SINGLELINE = UnifiedAnswerType.SINGLELINE
        TIME = UnifiedAnswerType.TIME
        RATING = UnifiedAnswerType.RATING
        PEOPLELIST = UnifiedAnswerType.PEOPLELIST
        SITELIST = UnifiedAnswerType.SITELIST
        METERREADING = UnifiedAnswerType.METERREADING
        MULTISELECT = UnifiedAnswerType.MULTISELECT
        GPSLOCATION = UnifiedAnswerType.GPSLOCATION

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            warnings.warn(
                "Question.AnswerType is deprecated. Use apps.activity.enums.AnswerType instead.",
                DeprecationWarning,
                stacklevel=2
            )

    class AvptType(models.TextChoices):
        """
        DEPRECATED: Use apps.activity.enums.AvptType instead.

        This class is maintained for backward compatibility only.
        All values proxy to the centralized enum.
        """
        NONE = UnifiedAvptType.NONE
        BACKCAMPIC = UnifiedAvptType.BACKCAMPIC
        FRONTCAMPIC = UnifiedAvptType.FRONTCAMPIC
        AUDIO = UnifiedAvptType.AUDIO
        VIDEO = UnifiedAvptType.VIDEO

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            warnings.warn(
                "Question.AvptType is deprecated. Use apps.activity.enums.AvptType instead.",
                DeprecationWarning,
                stacklevel=2
            )

    quesname = models.CharField(_("Name"), max_length=500)

    # TEXT FIELDS (DEPRECATED - will be removed in future release)
    options = models.TextField(
        _("Options (Text - DEPRECATED)"),
        max_length=2000,
        null=True,
        help_text="DEPRECATED: Use options_json instead. Maintained for backward compatibility."
    )
    alerton = models.CharField(
        _("Alert On (Text - DEPRECATED)"),
        max_length=300,
        null=True,
        help_text="DEPRECATED: Use alert_config instead. Maintained for backward compatibility."
    )

    # JSON FIELDS (NEW - Preferred)
    options_json = models.JSONField(
        _("Options (JSON)"),
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text='Structured options array. Format: ["Option1", "Option2", "Option3"]'
    )
    alert_config = models.JSONField(
        _("Alert Configuration"),
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text='Structured alert configuration. Format: {"numeric": {"below": 10.5, "above": 90.0}, "choice": ["Alert1"], "enabled": true}'
    )

    # NUMERIC FIELDS
    min = models.DecimalField(
        _("Min"), null=True, blank=True, max_digits=18, decimal_places=2, default=0.00
    )
    max = models.DecimalField(
        _("Max"), null=True, blank=True, max_digits=18, decimal_places=2, default=0.00
    )
    answertype = models.CharField(
        verbose_name=_("Type"),
        choices=AnswerType.choices,
        default="NUMERIC",
        max_length=55,
    )  # type in previous
    unit = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Unit"),
        on_delete=models.RESTRICT,
        related_name="unit_types",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    isworkflow = models.BooleanField(_("WorkFlow"), default=False)
    enable = models.BooleanField(_("Enable"), default=True)
    category = models.ForeignKey(
        "onboarding.TypeAssist",
        verbose_name=_("Category"),
        on_delete=models.RESTRICT,
        related_name="category_types",
        null=True,
        blank=True,
    )
    avpttype = models.CharField(
        _("Attachment Type"),
        max_length=50,
        choices=AvptType.choices,
        null=True,
        blank=True,
    )
    isavpt = models.BooleanField(_("Attachment Required"), default=False)

    objects = QuestionManager()

    class Meta(BaseModel.Meta):
        db_table = "question"
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        constraints = [
            models.UniqueConstraint(
                fields=["quesname", "answertype", "client"],
                name="ques_name_type_client_uk",
            )
        ]

    def __str__(self) -> str:
        return f"{self.quesname} | {self.answertype}"


def site_grp_includes():
    return {"sitegrp__id": ""}  # save this variable as <sitegrp__id> eg: abcd__12


def site_type_includes():
    return {"sitetype__id": ""}  # save this variable as <sitetype__id> eg: abcd__12


# will save on client level


class QuestionSet(BaseModel, TenantAwareModel):
    # Backward compatibility: Proxy to centralized enums
    # DEPRECATION WARNING: Direct use of QuestionSet.Type is deprecated.
    # Use apps.activity.enums.QuestionSetType instead.
    class Type(models.TextChoices):
        """
        DEPRECATED: Use apps.activity.enums.QuestionSetType instead.

        This class is maintained for backward compatibility only.
        All values proxy to the centralized enum with standardized labels.
        """
        ASSET = UnifiedQuestionSetType.ASSET
        QUESTIONSET = UnifiedQuestionSetType.QUESTIONSET
        CHECKLIST = UnifiedQuestionSetType.CHECKLIST
        RPCHECKLIST = UnifiedQuestionSetType.RPCHECKLIST
        INCIDENTREPORTTEMPLATE = UnifiedQuestionSetType.INCIDENTREPORT
        SITEREPORTTEMPLATE = UnifiedQuestionSetType.SITEREPORT
        WORKPERMITTEMPLATE = UnifiedQuestionSetType.WORKPERMIT
        RETURNWORKPERMITTEMPLATE = UnifiedQuestionSetType.RETURN_WORK_PERMIT
        KPITEMPLATE = UnifiedQuestionSetType.KPI_TEMPLATE  # Standardized label
        SCRAPPEDTEMPLATE = UnifiedQuestionSetType.SCRAPPEDTEMPLATE
        ASSETAUDIT = UnifiedQuestionSetType.ASSETAUDIT
        ASSETMAINTENANCE = UnifiedQuestionSetType.ASSETMAINTENANCE
        WORKORDER = UnifiedQuestionSetType.WORK_ORDER
        SLA_TEMPLATE = UnifiedQuestionSetType.SLA_TEMPLATE
        POSTINGORDER = UnifiedQuestionSetType.POSTING_ORDER
        SITESURVEY = UnifiedQuestionSetType.SITESURVEY

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            warnings.warn(
                "QuestionSet.Type is deprecated. Use apps.activity.enums.QuestionSetType instead.",
                DeprecationWarning,
                stacklevel=2
            )

    qsetname = models.CharField(_("QuestionSet Name"), max_length=200)
    enable = models.BooleanField(_("Enable"), default=True)
    assetincludes = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Asset Includes"),
    )
    buincludes = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Bu Includes"),
    )
    seqno = models.SmallIntegerField(_("Sl No."), default=1)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("Belongs To"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    type = models.CharField(_("Type"), choices=Type.choices, null=True, max_length=50)
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        related_name="qset_bus",
        null=True,
        blank=True,
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        related_name="qset_clients",
        null=True,
        blank=True,
    )
    site_grp_includes = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Site Group Includes"),
    )
    site_type_includes = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Site Type Includes"),
    )
    show_to_all_sites = models.BooleanField(_("Applicable to all sites"), default=False)
    url = models.CharField(
        _("Url"), max_length=250, null=True, blank=True, default="NONE"
    )

    objects = QuestionSetManager()

    class Meta(BaseModel.Meta):
        db_table = "questionset"
        verbose_name = "QuestionSet"
        verbose_name_plural = "QuestionSets"
        constraints = [
            models.UniqueConstraint(
                fields=["qsetname", "parent", "type", "client", "bu"],
                name="name_type_parent_type_client_bu_uk",
            ),
            models.CheckConstraint(
                condition=models.Q(seqno__gte=0), name="slno_gte_0_ck"
            ),
        ]

    def __str__(self) -> str:
        return self.qsetname


def alertmails_sendto():
    return {"id__code": []}


class QuestionSetBelonging(BaseModel, TenantAwareModel):
    # Backward compatibility: Proxy to centralized enums
    # DEPRECATION WARNING: Direct use of QuestionSetBelonging.AnswerType is deprecated.
    # Use apps.activity.enums.AnswerType instead.
    class AnswerType(models.TextChoices):
        """
        DEPRECATED: Use apps.activity.enums.AnswerType instead.

        This class is maintained for backward compatibility only.
        All values proxy to the centralized enum.
        Camera types (BACKCAMERA, FRONTCAMERA) are deprecated - use AVPT instead.
        """
        CHECKBOX = UnifiedAnswerType.CHECKBOX
        DATE = UnifiedAnswerType.DATE
        DROPDOWN = UnifiedAnswerType.DROPDOWN
        EMAILID = UnifiedAnswerType.EMAILID
        MULTILINE = UnifiedAnswerType.MULTILINE
        NUMERIC = UnifiedAnswerType.NUMERIC
        SIGNATURE = UnifiedAnswerType.SIGNATURE
        SINGLELINE = UnifiedAnswerType.SINGLELINE
        TIME = UnifiedAnswerType.TIME
        RATING = UnifiedAnswerType.RATING
        # Deprecated camera types - maintained for backward compatibility
        BACKCAMERA = UnifiedAnswerType.BACKCAMERA
        FRONTCAMERA = UnifiedAnswerType.FRONTCAMERA
        PEOPLELIST = UnifiedAnswerType.PEOPLELIST
        SITELIST = UnifiedAnswerType.SITELIST
        NONE = UnifiedAnswerType.NONE
        MULTISELECT = UnifiedAnswerType.MULTISELECT

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            warnings.warn(
                "QuestionSetBelonging.AnswerType is deprecated. Use apps.activity.enums.AnswerType instead.",
                DeprecationWarning,
                stacklevel=2
            )

    class AvptType(models.TextChoices):
        """
        DEPRECATED: Use apps.activity.enums.AvptType instead.

        This class is maintained for backward compatibility only.
        All values proxy to the centralized enum.
        """
        BACKCAMPIC = UnifiedAvptType.BACKCAMPIC
        FRONTCAMPIC = UnifiedAvptType.FRONTCAMPIC
        AUDIO = UnifiedAvptType.AUDIO
        VIDEO = UnifiedAvptType.VIDEO
        NONE = UnifiedAvptType.NONE

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            warnings.warn(
                "QuestionSetBelonging.AvptType is deprecated. Use apps.activity.enums.AvptType instead.",
                DeprecationWarning,
                stacklevel=2
            )

    # id               = models.BigIntegerField(_("QSB Id"), primary_key = True)
    ismandatory = models.BooleanField(_("Mandatory"), default=True)
    isavpt = models.BooleanField(_("Attachment Required"), default=False)
    seqno = models.SmallIntegerField(_("Seq No."))
    qset = models.ForeignKey(
        "activity.QuestionSet",
        verbose_name=_("Question Set"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
    )
    question = models.ForeignKey(
        "activity.Question",
        verbose_name=_("Question"),
        null=True,
        blank=False,
        on_delete=models.RESTRICT,
    )
    answertype = models.CharField(
        _("Question Type"), max_length=50, choices=AnswerType.choices
    )
    avpttype = models.CharField(
        _("Attachment Type"),
        max_length=50,
        choices=AvptType.choices,
        null=True,
        blank=True,
    )

    # NUMERIC FIELDS
    max = models.DecimalField(
        _("Max"), null=True, blank=True, max_digits=18, decimal_places=2, default=0.00
    )
    min = models.DecimalField(
        _("Min"), null=True, blank=True, max_digits=18, decimal_places=2, default=0.00
    )

    # TEXT FIELDS (DEPRECATED - will be removed in future release)
    alerton = models.CharField(
        _("Alert On (Text - DEPRECATED)"),
        null=True,
        blank=True,
        max_length=300,
        help_text="DEPRECATED: Use alert_config instead. Maintained for backward compatibility."
    )
    options = models.CharField(
        _("Options (Text - DEPRECATED)"),
        max_length=2000,
        null=True,
        blank=True,
        help_text="DEPRECATED: Use options_json instead. Maintained for backward compatibility."
    )

    # JSON FIELDS (NEW - Preferred)
    options_json = models.JSONField(
        _("Options (JSON)"),
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text='Structured options array. Format: ["Option1", "Option2", "Option3"]'
    )
    alert_config = models.JSONField(
        _("Alert Configuration"),
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        help_text='Structured alert configuration. Format: {"numeric": {"below": 10.5, "above": 90.0}, "choice": ["Alert1"], "enabled": true}'
    )
    client = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Client"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="qsetbelong_client",
    )
    alertmails_sendto = models.JSONField(
        _("Alert mails send to"), encoder=DjangoJSONEncoder, default=alertmails_sendto
    )
    
    # New field for conditional display logic
    display_conditions = models.JSONField(
        _("Display Conditions"),
        encoder=DjangoJSONEncoder,
        null=True,
        blank=True,
        default=dict,
        help_text="JSON structure for conditional display logic"
    )
    # Structure example:
    # {
    #     "depends_on": {
    #         "question_id": 123,  # ID of the QuestionSetBelonging record this depends on
    #         "operator": "EQUALS",  # EQUALS, NOT_EQUALS, CONTAINS, IN, GT, LT
    #         "values": ["Yes"],  # Array of values to match
    #     },
    #     "show_if": true,  # true = show when condition met, false = hide when condition met
    #     "cascade_hide": true,  # hide dependent questions if this is hidden
    #     "group": "labour_work"  # optional grouping for related questions
    # }
    bu = models.ForeignKey(
        "onboarding.Bt",
        verbose_name=_("Site"),
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="qsetbelong_bu",
    )
    buincludes = ArrayField(
        models.CharField(max_length=100, blank=True),
        null=True,
        blank=True,
        verbose_name=_("Bu Includes"),
    )

    objects = QsetBlngManager()

    class Meta(BaseModel.Meta):
        db_table = "questionsetbelonging"
        verbose_name = "QuestionSetBelonging"
        verbose_name_plural = "QuestionSetBelongings"
        constraints = [
            models.UniqueConstraint(
                fields=["qset", "question", "client", "bu"],
                name="qset_question_client_bu_uk",
            )
        ]

    def __str__(self) -> str:
        return f"{self.question.quesname if self.question else 'Unknown'} ({self.answertype})"

    def clean(self):
        """
        Validate display_conditions using Pydantic validator.

        Following .claude/rules.md Rule #9: Validate and sanitize all user inputs
        """
        from django.core.exceptions import ValidationError
        from apps.activity.validators import validate_display_conditions

        super().clean()

        # Validate display_conditions if present
        if self.display_conditions:
            try:
                # Validate using Pydantic schema with database checks
                validated = validate_display_conditions(
                    data=self.display_conditions,
                    qsb_id=self.pk,
                    qset_id=self.qset_id if self.qset_id else None,
                    seqno=self.seqno
                )

                # Update with validated/sanitized data
                # Convert Pydantic model back to dict for JSON field
                self.display_conditions = validated.model_dump(
                    by_alias=True,  # Use 'question_id' alias for backward compatibility
                    exclude_none=True
                )

                # Log validation success for monitoring
                if validated.depends_on:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(
                        f"QuestionSetBelonging {self.pk} validated dependency on QSB ID {validated.depends_on.qsb_id}",
                        extra={
                            'qsb_id': self.pk,
                            'dependency_id': validated.depends_on.qsb_id,
                            'operator': validated.depends_on.operator
                        }
                    )

            except ValueError as e:
                raise ValidationError({
                    'display_conditions': f"Invalid conditional logic: {str(e)}"
                }) from e
            except (ValueError, TypeError, AttributeError) as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"Unexpected error validating display_conditions for QSB {self.pk}: {e}",
                    exc_info=True
                )
                raise ValidationError({
                    'display_conditions': "Failed to validate conditional logic. Please check the format."
                }) from e

    def save(self, *args, **kwargs):
        """
        Override save to run validation before saving.

        Following .claude/rules.md Rule #17: Transaction management
        """
        # Run validation
        self.full_clean()

        # Call parent save
        super().save(*args, **kwargs)
