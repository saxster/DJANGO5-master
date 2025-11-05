"""
Transaction and State Management Utilities

Handles database transactions, ticket history tracking, and state management
for complex business operations like ticket updates.
"""

import logging
from datetime import datetime, timezone as dt_timezone
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger("django")
error_logger = logging.getLogger("error_logger")


def save_common_stuff(request, instance, is_superuser=False, ctzoffset=-1):
    """
    Update common audit fields on a model instance.

    Sets creator/modifier user IDs and timestamps based on request context.
    """
    from django.utils import timezone

    if request and hasattr(request, 'user'):
        logger.debug("Request User ID: %s and %s", request.user.id, request)
    userid = (
        1 if is_superuser else request.user.id if request else 1
    )
    if instance.cuser is not None:
        instance.muser_id = userid
        instance.mdtz = timezone.now().replace(microsecond=0)
        instance.ctzoffset = ctzoffset
    else:
        instance.cuser_id = instance.muser_id = userid

    if request and hasattr(request, "session"):
        instance.ctzoffset = int(request.session.get("ctzoffset", 330))
    else:
        instance.ctzoffset = 330

    return instance


def get_action_on_ticket_states(prev_tkt, current_state):
    """
    Compare ticket states and generate human-readable action descriptions.

    Args:
        prev_tkt: List of previous ticket states
        current_state: Current state dictionary

    Returns:
        List of action description strings
    """
    actions = []
    if prev_tkt and prev_tkt[-1]["previous_state"] and current_state:
        prev_state = prev_tkt[-1]["previous_state"]
        if prev_state["status"] != current_state["status"]:
            actions.append(
                f'''Status Changed From "{prev_state['status']}" To "{current_state['status']}"'''
            )

        if prev_state["priority"] != current_state["priority"]:
            actions.append(
                f'''Priority Changed from "{prev_state['priority']}" To "{current_state['priority']}"'''
            )

        if prev_state["location"] != current_state["location"]:
            actions.append(
                f'''Location Changed from "{prev_state['location']}" To "{current_state['location']}"'''
            )

        if prev_state["ticketdesc"] != current_state["ticketdesc"]:
            actions.append(
                f'''Ticket Description Changed From "{prev_state['ticketdesc']}" To "{current_state['ticketdesc']}"'''
            )

        if prev_state["assignedtopeople"] != current_state["assignedtopeople"]:
            actions.append(
                f'''Ticket Is Reassigned From "{prev_state['assignedtopeople']}" To "{current_state['assignedtopeople']}"'''
            )

        if prev_state["assignedtogroup"] != current_state["assignedtogroup"]:
            actions.append(
                f'''Ticket Is Reassigned From "{prev_state['assignedtogroup']}" To "{current_state['assignedtogroup']}"'''
            )

        if prev_state["comments"] != current_state["comments"] and current_state[
            "comments"
        ] not in ["None", None]:
            actions.append(
                f'''New Comments "{current_state['comments']}" are added after "{prev_state['comments']}"'''
            )
        if prev_state["level"] != current_state["level"]:
            actions.append(
                f"""Ticket level is changed from {prev_state['level']} to {current_state["level"]}"""
            )
        return actions
    return ["Ticket Created"]


def store_ticket_history(instance, request=None, user=None):
    """
    Store ticket state changes in ticket history JSONField.

    Tracks all modifications to ticket fields and maintains audit trail.
    """
    from background_tasks.tasks import send_ticket_email

    now = datetime.now(dt_timezone.utc).replace(microsecond=0, second=0)
    peopleid = request.user.id if request else user.id
    peoplename = request.user.peoplename if request else user.peoplename

    current_state = {
        "ticketdesc": instance.ticketdesc,
        "assignedtopeople": instance.assignedtopeople.peoplename if instance.assignedtopeople else "Unassigned",
        "assignedtogroup": instance.assignedtogroup.groupname if instance.assignedtogroup else "Unassigned",
        "comments": instance.comments,
        "status": instance.status,
        "priority": instance.priority,
        "location": instance.location.locname if instance.location else "No Location",
        "level": instance.level,
        "isescalated": instance.isescalated,
    }

    ticketstate = instance.ticketlog["ticket_history"]
    details = get_action_on_ticket_states(ticketstate, current_state)

    history_item = {
        "people_id": peopleid,
        "when": str(now),
        "who": peoplename,
        "assignto": (instance.assignedtogroup.groupname if instance.assignedtogroup else "Unassigned")
        if instance.assignedtopeople_id in [1, None]
        else (instance.assignedtopeople.peoplename if instance.assignedtopeople else "Unassigned"),
        "action": "created",
        "details": details,
        "previous_state": current_state,
    }

    logger.debug(f"{instance.mdtz=} {instance.cdtz=} {ticketstate=} {details=}")

    if (
        instance.mdtz > instance.cdtz
        and ticketstate
        and ticketstate[-1]["previous_state"] != current_state
    ):
        history_item["action"] = "updated"
        ticket_history = instance.ticketlog["ticket_history"]
        ticket_history.append(history_item)
        instance.ticketlog = {"ticket_history": ticket_history}
        logger.info("changes have been made to ticket")
    elif instance.mdtz > instance.cdtz:
        history_item["details"] = "No changes detected"
        history_item["action"] = "updated"
        instance.ticketlog["ticket_history"].append(history_item)
        logger.info("no changed detected")
    else:
        instance.ticketlog["ticket_history"] = [history_item]
        send_ticket_email.delay(id=instance.id)
        logger.info("new ticket is created..")
    instance.save()
    logger.info("saving ticket history ended...")


__all__ = [
    'save_common_stuff',
    'get_action_on_ticket_states',
    'store_ticket_history',
]
