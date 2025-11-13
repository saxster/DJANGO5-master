"""
Factory definitions for y_helpdesk app testing.

Uses factory_boy for generating Ticket, EscalationMatrix, SLAPolicy,
and related data with realistic workflow and escalation scenarios.

Complies with .claude/rules.md standards.
"""
import factory
from datetime import datetime, timezone as dt_timezone, timedelta
from factory.django import DjangoModelFactory
from apps.y_helpdesk.models import Ticket, EscalationMatrix, SLAPolicy


class BtFactory(DjangoModelFactory):
    """Factory for creating test tenants (business units)."""

    class Meta:
        model = "client_onboarding.Bt"
        django_get_or_create = ("bucode",)

    bucode = factory.Sequence(lambda n: f"HELP{n:03d}")
    buname = factory.LazyAttribute(lambda obj: f"Helpdesk Tenant {obj.bucode}")
    enable = True


class PeopleFactory(DjangoModelFactory):
    """Factory for creating test users."""

    class Meta:
        model = "peoples.People"
        django_get_or_create = ("loginid",)

    peoplecode = factory.Sequence(lambda n: f"HELPUSR{n:04d}")
    peoplename = factory.Faker("name")
    loginid = factory.LazyAttribute(lambda obj: obj.peoplename.lower().replace(" ", "_"))
    email = factory.LazyAttribute(lambda obj: f"{obj.loginid}@example.com")
    mobno = factory.Faker("numerify", text="##########")
    password = factory.django.Password("TestPass123!")
    client = factory.SubFactory(BtFactory)
    enable = True


class PgroupFactory(DjangoModelFactory):
    """Factory for creating permission groups."""

    class Meta:
        model = "peoples.Pgroup"
        django_get_or_create = ("groupcode",)

    groupname = factory.Sequence(lambda n: f"Support Group {n}")
    groupcode = factory.Sequence(lambda n: f"SUPGRP{n:03d}")
    description = factory.LazyAttribute(lambda obj: f"Description for {obj.groupname}")
    client = factory.SubFactory(BtFactory)


class TypeAssistFactory(DjangoModelFactory):
    """Factory for creating TypeAssist entries (ticket categories)."""

    class Meta:
        model = "core_onboarding.TypeAssist"

    typename = "TicketCategory"
    typeval = factory.Sequence(lambda n: f"Category {n}")
    client = factory.SubFactory(BtFactory)
    enable = True


class LocationFactory(DjangoModelFactory):
    """Factory for creating test locations."""

    class Meta:
        model = "activity.Location"
        django_get_or_create = ("site", "location")

    site = factory.Sequence(lambda n: f"HELPSITE{n:03d}")
    location = factory.Sequence(lambda n: f"Location {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")


class AssetFactory(DjangoModelFactory):
    """Factory for creating test assets."""

    class Meta:
        model = "activity.Asset"
        django_get_or_create = ("assetcode", "client")

    assetname = factory.Sequence(lambda n: f"Asset {n}")
    assetcode = factory.Sequence(lambda n: f"ASSET{n:04d}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    enable = True


class QuestionSetFactory(DjangoModelFactory):
    """Factory for creating question sets for ticket checklists."""

    class Meta:
        model = "activity.QuestionSet"

    qsetname = factory.Sequence(lambda n: f"Ticket Checklist {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    enable = True


class TicketFactory(DjangoModelFactory):
    """
    Factory for creating Ticket instances.

    Generates realistic helpdesk tickets with:
    - Priority-based assignment
    - Multi-tenant support
    - Workflow integration
    - Sentiment analysis tracking
    - SLA compliance
    """

    class Meta:
        model = Ticket

    tenant = factory.SubFactory(BtFactory)
    ticketno = factory.Sequence(lambda n: f"T{n:05d}")
    ticketdesc = factory.Faker("text", max_nb_chars=300)
    identifier = Ticket.Identifier.TICKET
    bu = factory.LazyAttribute(lambda obj: obj.tenant)
    client = factory.SelfAttribute("tenant")

    assignedtopeople = factory.SubFactory(PeopleFactory, client=factory.SelfAttribute("..client"))
    assignedtogroup = factory.SubFactory(PgroupFactory, client=factory.SelfAttribute("..client"))

    comments = factory.Faker("sentence")
    priority = factory.Iterator([
        Ticket.Priority.LOW,
        Ticket.Priority.MEDIUM,
        Ticket.Priority.HIGH,
    ])
    ticketcategory = factory.SubFactory(TypeAssistFactory, client=factory.SelfAttribute("..client"))
    location = factory.SubFactory(LocationFactory, client=factory.SelfAttribute("..client"))
    asset = factory.SubFactory(AssetFactory, client=factory.SelfAttribute("..client"))
    qset = factory.SubFactory(QuestionSetFactory, client=factory.SelfAttribute("..client"))

    status = factory.Iterator([
        Ticket.Status.NEW,
        Ticket.Status.OPEN,
        Ticket.Status.RESOLVED,
    ])
    original_language = "en"
    performedby = factory.SubFactory(PeopleFactory, client=factory.SelfAttribute("..client"))
    ticketsource = Ticket.TicketSource.USERDEFINED
    attachmentcount = factory.Faker("random_int", min=0, max=5)

    # Sentiment analysis fields
    sentiment_score = factory.Faker("pyfloat", min_value=0.0, max_value=10.0, right_digits=1)
    sentiment_label = factory.LazyAttribute(lambda obj: {
        range(0, 3): 'very_negative',
        range(3, 5): 'negative',
        range(5, 6): 'neutral',
        range(6, 8): 'positive',
        range(8, 11): 'very_positive',
    }.get(next(r for r in [range(0, 3), range(3, 5), range(5, 6), range(6, 8), range(8, 11)] if int(obj.sentiment_score) in r), 'neutral'))
    emotion_detected = factory.LazyFunction(lambda: {
        "frustration": factory.Faker("pyfloat", min_value=0.0, max_value=1.0, right_digits=2).evaluate(None, None, {}),
        "urgency": factory.Faker("pyfloat", min_value=0.0, max_value=1.0, right_digits=2).evaluate(None, None, {}),
        "satisfaction": factory.Faker("pyfloat", min_value=0.0, max_value=1.0, right_digits=2).evaluate(None, None, {}),
    })
    sentiment_analyzed_at = factory.LazyFunction(lambda: datetime.now(dt_timezone.utc))


class NewTicketFactory(TicketFactory):
    """Factory for creating new unassigned tickets."""

    status = Ticket.Status.NEW
    assignedtopeople = None
    assignedtogroup = None
    sentiment_score = factory.Faker("pyfloat", min_value=3.0, max_value=7.0, right_digits=1)
    sentiment_label = "neutral"


class HighPriorityTicketFactory(TicketFactory):
    """Factory for creating high-priority tickets."""

    priority = Ticket.Priority.HIGH
    status = Ticket.Status.OPEN
    sentiment_score = factory.Faker("pyfloat", min_value=0.0, max_value=4.0, right_digits=1)
    sentiment_label = factory.Iterator(['very_negative', 'negative'])
    emotion_detected = factory.LazyFunction(lambda: {
        "frustration": factory.Faker("pyfloat", min_value=0.6, max_value=1.0, right_digits=2).evaluate(None, None, {}),
        "urgency": factory.Faker("pyfloat", min_value=0.7, max_value=1.0, right_digits=2).evaluate(None, None, {}),
        "anger": factory.Faker("pyfloat", min_value=0.5, max_value=0.9, right_digits=2).evaluate(None, None, {}),
    })


class ResolvedTicketFactory(TicketFactory):
    """Factory for creating resolved tickets."""

    status = Ticket.Status.RESOLVED
    sentiment_score = factory.Faker("pyfloat", min_value=6.0, max_value=10.0, right_digits=1)
    sentiment_label = factory.Iterator(['positive', 'very_positive'])
    emotion_detected = factory.LazyFunction(lambda: {
        "satisfaction": factory.Faker("pyfloat", min_value=0.6, max_value=1.0, right_digits=2).evaluate(None, None, {}),
        "gratitude": factory.Faker("pyfloat", min_value=0.5, max_value=0.9, right_digits=2).evaluate(None, None, {}),
    })


class CancelledTicketFactory(TicketFactory):
    """Factory for creating cancelled tickets."""

    status = Ticket.Status.CANCEL


class JobFactory(DjangoModelFactory):
    """Factory for creating test jobs for escalation matrix."""

    class Meta:
        model = "activity.Job"

    jobname = factory.Sequence(lambda n: f"Job {n}")
    client = factory.SubFactory(BtFactory)
    bu = factory.SelfAttribute("client")
    identifier = "TASK"
    enable = True


class EscalationMatrixFactory(DjangoModelFactory):
    """
    Factory for creating EscalationMatrix instances.

    Generates realistic escalation rules with:
    - Job/task type associations
    - Time-based escalation thresholds
    - Multi-level escalation chains
    - Person and group assignments
    - Email notification rules
    """

    class Meta:
        model = EscalationMatrix

    tenant = factory.SubFactory(BtFactory)
    body = factory.Faker("sentence", nb_words=10)
    job = factory.SubFactory(JobFactory, client=factory.SelfAttribute("..tenant"))
    level = factory.Faker("random_int", min=1, max=5)
    frequency = factory.Iterator([
        EscalationMatrix.Frequency.MINUTE,
        EscalationMatrix.Frequency.HOUR,
        EscalationMatrix.Frequency.DAY,
    ])
    frequencyvalue = factory.Faker("random_int", min=1, max=10)
    assignedfor = factory.Iterator(["person", "group"])
    assignedperson = factory.SubFactory(PeopleFactory, client=factory.SelfAttribute("..tenant"))
    assignedgroup = factory.SubFactory(PgroupFactory, client=factory.SelfAttribute("..tenant"))
    bu = factory.LazyAttribute(lambda obj: obj.tenant)
    client = factory.SelfAttribute("tenant")
    notify = factory.Faker("email")


class Level1EscalationFactory(EscalationMatrixFactory):
    """Factory for Level 1 escalation (first tier)."""

    level = 1
    frequency = EscalationMatrix.Frequency.HOUR
    frequencyvalue = 2  # Escalate after 2 hours


class Level2EscalationFactory(EscalationMatrixFactory):
    """Factory for Level 2 escalation (second tier)."""

    level = 2
    frequency = EscalationMatrix.Frequency.HOUR
    frequencyvalue = 4  # Escalate after 4 hours


class Level3EscalationFactory(EscalationMatrixFactory):
    """Factory for Level 3 escalation (management tier)."""

    level = 3
    frequency = EscalationMatrix.Frequency.DAY
    frequencyvalue = 1  # Escalate after 1 day


class SLAPolicyFactory(DjangoModelFactory):
    """
    Factory for creating SLAPolicy instances.

    Generates realistic SLA policies with:
    - Priority-based response and resolution targets
    - Penalty tracking for breaches
    - Multi-tenant support
    """

    class Meta:
        model = SLAPolicy

    tenant = factory.SubFactory(BtFactory)
    name = factory.Sequence(lambda n: f"SLA Policy {n}")
    description = factory.Faker("sentence", nb_words=15)
    priority = factory.Iterator([
        Ticket.Priority.LOW,
        Ticket.Priority.MEDIUM,
        Ticket.Priority.HIGH,
    ])

    # Response time targets (in hours)
    response_time_hours = factory.LazyAttribute(lambda obj: {
        Ticket.Priority.LOW: 24,
        Ticket.Priority.MEDIUM: 8,
        Ticket.Priority.HIGH: 2,
    }.get(obj.priority, 8))

    # Resolution time targets (in hours)
    resolution_time_hours = factory.LazyAttribute(lambda obj: {
        Ticket.Priority.LOW: 72,
        Ticket.Priority.MEDIUM: 24,
        Ticket.Priority.HIGH: 4,
    }.get(obj.priority, 24))

    penalty_amount = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    is_active = True
    bu = factory.LazyAttribute(lambda obj: obj.tenant)
    client = factory.SelfAttribute("tenant")


class HighPrioritySLAFactory(SLAPolicyFactory):
    """Factory for creating high-priority SLA policies."""

    priority = Ticket.Priority.HIGH
    response_time_hours = 2
    resolution_time_hours = 4
    penalty_amount = factory.Faker("pydecimal", left_digits=5, right_digits=2, positive=True)


class MediumPrioritySLAFactory(SLAPolicyFactory):
    """Factory for creating medium-priority SLA policies."""

    priority = Ticket.Priority.MEDIUM
    response_time_hours = 8
    resolution_time_hours = 24


class LowPrioritySLAFactory(SLAPolicyFactory):
    """Factory for creating low-priority SLA policies."""

    priority = Ticket.Priority.LOW
    response_time_hours = 24
    resolution_time_hours = 72


__all__ = [
    'TicketFactory',
    'NewTicketFactory',
    'HighPriorityTicketFactory',
    'ResolvedTicketFactory',
    'CancelledTicketFactory',
    'EscalationMatrixFactory',
    'Level1EscalationFactory',
    'Level2EscalationFactory',
    'Level3EscalationFactory',
    'SLAPolicyFactory',
    'HighPrioritySLAFactory',
    'MediumPrioritySLAFactory',
    'LowPrioritySLAFactory',
    'BtFactory',
    'PeopleFactory',
    'PgroupFactory',
    'TypeAssistFactory',
    'LocationFactory',
    'AssetFactory',
    'QuestionSetFactory',
    'JobFactory',
]
