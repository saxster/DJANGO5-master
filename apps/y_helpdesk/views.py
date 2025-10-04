from django.shortcuts import render
from django.db.utils import IntegrityError
from apps.onboarding.models import TypeAssist
from .models import EscalationMatrix, Ticket
from .forms import TicketForm, EscalationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.http import response as rp
from apps.core import utils
from django.db import transaction
from apps.peoples import utils as putils
from apps.peoples import models as pm
from apps.core.utils_new.db_utils import get_current_db_name

# Import unified serializer for consistent API responses
from .serializers.unified_ticket_serializer import (
    serialize_for_web_api,
    serialize_for_dashboard,
    SerializationContext
)


# Create your views here.
class EscalationMatrixView(LoginRequiredMixin, View):
    P = {
        "model": EscalationMatrix,
        "fields": ["frequencyvalue", "frequency", "notify", "id"],
        "template_list": "y_helpdesk/escalation_list.html",
        "template_form": "y_helpdesk/escalation_form.html",
        "form": EscalationForm,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.P

        if R.get("action") == "form":
            cxt = {"escform": P["form"](request=request)}
            return render(request, P["template_form"], cxt)

        if R.get("action") == "loadPeoples":
            qset = pm.People.objects.getPeoplesForEscForm(request)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        if R.get("action") == "loadGroups":
            qset = pm.Pgroup.objects.getGroupsForEscForm(request)
            return rp.JsonResponse(
                {"items": list(qset), "total_count": len(qset)}, status=200
            )

        if R.get("template") == "true":
            return render(request, P["template_list"])

        if R.get("action") == "list":
            # Optimized: Manager method already returns a list and uses caching
            objs = P["model"].objects.get_escalation_listview(request)
            return rp.JsonResponse({"data": objs}, status=200)

        if R.get("action") == "get_escalationlevels":
            objs = TypeAssist.objects.get_escalationlevels(request)
            return rp.JsonResponse({"data": objs}, status=200)

        if R.get("id") not in ["None", None]:
            initial = {"escalationtemplate": R["id"]}
            cxt = {"escform": P["form"](request=request, initial=initial)}
            return render(request, P["template_form"], cxt)

        if R.get("action") == "get_reminder_config" and R.get("job_id") not in [
            None,
            "None",
        ]:
            objs = P["model"].objects.get_reminder_config_forppm(
                R["job_id"], P["fields"]
            )
            return rp.JsonResponse(data={"data": list(objs)})
        return rp.JsonResponse(data={"data": []})

    def post(self, request, *args, **kwargs):
        R, P = request.POST, self.P
        if R.get("post") == "postEscalations":
            data = P["model"].objects.handle_esclevel_form_postdata(request)
            return rp.JsonResponse(data, status=200, safe=False)

        if R.get("post") == "postReminder":
            data = P["model"].objects.handle_reminder_config_postdata(request)
            return rp.JsonResponse(data, status=200, safe=False)


class TicketView(LoginRequiredMixin, View):
    params = {
        "model": Ticket,
        "form": TicketForm,
        "template": "y_helpdesk/ticket_form.html",
        "template_list": "y_helpdesk/ticket_list.html",
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params

        if R.get("action") == "form":
            import uuid

            cxt = {"ticketform": P["form"](request=request), "ownerid": uuid.uuid4()}
            return render(request, P["template"], cxt)

        if R.get("template") == "true":
            return render(request, P["template_list"])

        if R.get("action") == "list":
            # Use optimized manager method with unified serialization
            tickets = P["model"].objects.filter(
                cdtz__date__gte=request.GET.get('from'),
                cdtz__date__lte=request.GET.get('to'),
                bu_id__in=request.session["assignedsites"],
                client_id=request.session["client_id"],
            ).select_related(
                'assignedtopeople', 'assignedtogroup', 'bu', 'ticketcategory', 'cuser'
            ).prefetch_related('workflow')

            # Apply status filtering
            status = request.GET.get("status")
            if status == "SYSTEMGENERATED":
                tickets = tickets.filter(ticketsource="SYSTEMGENERATED")
            elif status:
                tickets = tickets.filter(status=status, ticketsource="USERDEFINED")

            # Use unified serializer for consistent API response
            objs = serialize_for_web_api(tickets, request.user)
            return rp.JsonResponse({"data": objs}, status=200)

        if R.get("id"):
            try:
                ticket = Ticket.objects.get(
                    id=R["id"],
                    client_id=request.session["client_id"],
                    bu_id__in=request.session["assignedsites"]
                )
            except Ticket.DoesNotExist:
                return utils.handle_DoesNotExist(request)

            if (
                ticket.status == Ticket.Status.NEW.value
                and ticket.cuser != request.user
            ):
                ticket.status, ticket.muser = Ticket.Status.OPEN.value, request.user
                ticket.save()
                utils.store_ticket_history(ticket, request)
            cxt = {
                "ticketform": P["form"](instance=ticket, request=request),
                "ownerid": ticket.uuid,
            }
            return render(request, P["template"], cxt)

    def post(self, request, *args, **kwargs):
        from apps.core.utils_new.http_utils import get_clean_form_data
        R, P, data = request.POST, self.params, get_clean_form_data(request)
        try:
            if pk := R.get("pk"):
                msg = "ticket_view"
                try:
                    ticket = Ticket.objects.get(
                        id=pk,
                        client_id=request.session["client_id"],
                        bu_id__in=request.session["assignedsites"]
                    )
                except Ticket.DoesNotExist:
                    return utils.handle_DoesNotExist(request)
                form = P["form"](data, request=request, instance=ticket)
            else:
                form = P["form"](data, request=request)
            if form.is_valid():
                return self.handle_valid_form(form, request)
            cxt = {"errors": form.errors}
            return utils.handle_invalid_form(request, P, cxt)
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            return utils.handle_Exception(request)

    def handle_valid_form(self, form, request):
        """
        Handle valid ticket form submission with retry logic for unique constraint violations.

        NOTE: Uses exponential backoff with very short delays (10-200ms) for database
        constraint retries. This is acceptable because:
        1. Delays are minimal (< 200ms total across all retries)
        2. IntegrityErrors on ticketno are rare (only during high concurrency)
        3. Ticket creation requires synchronous feedback to user
        4. Alternative solutions (background tasks) would break user experience

        TODO: Consider moving to database-level sequence generator for ticketno
        to eliminate the need for retries entirely.
        """
        from apps.core.utils_new.retry_mechanism import exponential_backoff
        import logging

        logger = logging.getLogger(__name__)
        max_retries = 3

        for attempt in range(max_retries):
            try:
                with transaction.atomic(using=get_current_db_name()):
                    ticket = form.save(commit=False)
                    ticket.uuid = request.POST.get("uuid")
                    bu = ticket.bu_id if request.POST.get("pk") else None
                    ticket = putils.save_userinfo(ticket, request.user, request.session, bu=bu)
                    utils.store_ticket_history(ticket, request)

                    return rp.JsonResponse({"pk": ticket.id}, status=200)

            except IntegrityError as e:
                if "ticketno" in str(e) and attempt < max_retries - 1:
                    # Calculate exponential backoff delay with jitter
                    delay = exponential_backoff(
                        attempt=attempt,
                        initial_delay=0.01,  # 10ms initial delay
                        backoff_factor=2.0,
                        max_delay=0.2,  # 200ms max delay
                        jitter=True
                    )

                    logger.warning(
                        f"IntegrityError on ticketno, retrying (attempt {attempt + 2}/{max_retries})",
                        extra={
                            'delay_ms': delay * 1000,
                            'user': request.user.loginid if hasattr(request.user, 'loginid') else 'unknown'
                        }
                    )

                    # NOTE: This time.sleep is acceptable here due to:
                    # 1. Very short duration (10-200ms)
                    # 2. Rare occurrence (only on ticket number collision)
                    # 3. Synchronous operation requirement
                    import time
                    time.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Failed to create ticket after {max_retries} attempts",
                        extra={'error': str(e)},
                        exc_info=True
                    )
                    return utils.handle_intergrity_error("Ticket")
    
class PostingOrderView(LoginRequiredMixin, View):

    params = {
        "template_list": "y_helpdesk/posting_order_list.html",
        "model": Jobneed,
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("template") == "true":
            return render(request, P["template_list"])

        if R.get("action") == "list":
            # Optimized: Manager method already returns a list with pagination
            objs = P["model"].objects.get_posting_order_listview(request)
            return rp.JsonResponse({"data": objs}, status=200)


class UniformView(LoginRequiredMixin, View):
    params = {
        "template_list": "y_helpdesk/uniform_list.html",
    }

    def get(self, request, *args, **kwargs):
        return render(request, self.params["template_list"])
