from django.shortcuts import render
from django.db.utils import IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import permission_required
from django.utils.decorators import method_decorator
from apps.core_onboarding.models import TypeAssist
from .models import EscalationMatrix, Ticket
from .forms import TicketForm, EscalationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.http import response as rp
from apps.core import utils
from apps.api.pagination import StandardPageNumberPagination
from django.db import transaction, DatabaseError
from apps.peoples import utils as putils
from apps.peoples import models as pm
from apps.core.utils_new.db_utils import get_current_db_name
from apps.activity.models.job_model import Job

# Import unified serializer for consistent API responses
from .serializers.unified_ticket_serializer import (
    serialize_for_web_api,
    serialize_for_dashboard,
    SerializationContext
)


# Create your views here.
@method_decorator(permission_required('y_helpdesk.view_escalationmatrix', raise_exception=True), name='dispatch')
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
            # Performance: Apply pagination to prevent loading all users at once
            qset = pm.People.objects.getPeoplesForEscForm(request)

            # Get pagination parameters from request
            page_number = int(R.get('page', 1))
            page_size = int(R.get('page_size', 25))  # Default from StandardPageNumberPagination

            # Apply pagination
            paginator = Paginator(qset, page_size)
            try:
                page_obj = paginator.page(page_number)
                items = list(page_obj)
            except (EmptyPage, PageNotAnInteger):
                # Return empty results for invalid page numbers
                items = []
                page_obj = None

            return rp.JsonResponse({
                "items": items,
                "total_count": paginator.count if paginator else 0,
                "page_size": page_size,
                "current_page": page_number,
                "total_pages": paginator.num_pages if paginator else 0,
                "has_next": page_obj.has_next() if page_obj else False,
                "has_previous": page_obj.has_previous() if page_obj else False
            }, status=200)

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


@method_decorator(permission_required('y_helpdesk.view_ticket', raise_exception=True), name='dispatch')
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
            # Query optimization note: select_related() covers all foreign keys accessed by serializer
            # (assignedtopeople.peoplename, bu.buname, etc.). No nested relationships like
            # assignedtopeople.profile are accessed, so current optimization is sufficient.

            # Security fix: Validate session data against user's actual organizational context
            # to prevent cross-tenant access via session manipulation
            if not hasattr(request.user, 'peopleorganizational'):
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied("User lacks organizational context")

            user_org = request.user.peopleorganizational

            # Superusers can access all tickets; regular users limited to their scope
            if request.user.is_superuser:
                allowed_bu_ids = request.session.get("assignedsites", [])
                allowed_client_id = request.session.get("client_id")
            else:
                # Validate session data matches user's actual organizational context
                allowed_bu_ids = [user_org.bu_id] if user_org.bu_id else []
                allowed_client_id = user_org.client_id

            tickets = P["model"].objects.filter(
                cdtz__date__gte=request.GET.get('from'),
                cdtz__date__lte=request.GET.get('to'),
                bu_id__in=allowed_bu_ids,
                client_id=allowed_client_id,
            ).select_related(
                'assignedtopeople', 'assignedtogroup', 'bu', 'ticketcategory', 'cuser'
            ).prefetch_related('workflow')

            # Apply status filtering
            status = request.GET.get("status")
            if status == "SYSTEMGENERATED":
                tickets = tickets.filter(ticketsource="SYSTEMGENERATED")
            elif status:
                tickets = tickets.filter(status=status, ticketsource="USERDEFINED")

            # Apply sentiment filtering (Feature 2: NL/AI Platform Quick Win)
            sentiment_label = request.GET.get("sentiment_label")
            if sentiment_label:
                tickets = tickets.filter(sentiment_label=sentiment_label)

            # Filter by sentiment score range
            min_sentiment = request.GET.get("min_sentiment")
            max_sentiment = request.GET.get("max_sentiment")
            if min_sentiment:
                tickets = tickets.filter(sentiment_score__gte=float(min_sentiment))
            if max_sentiment:
                tickets = tickets.filter(sentiment_score__lte=float(max_sentiment))

            # Sort by sentiment (negative first for priority)
            sentiment_sort = request.GET.get("sort_by_sentiment")
            if sentiment_sort == "negative_first":
                tickets = tickets.order_by('sentiment_score', '-cdtz')
            elif sentiment_sort == "positive_first":
                tickets = tickets.order_by('-sentiment_score', '-cdtz')

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
        Handle valid ticket form submission with non-blocking retry logic.

        Uses cache-based retry coordination to eliminate blocking time.sleep().
        Returns 429 status with Retry-After header if operation needs retry.

        Fixed: Eliminated blocking time.sleep() per .claude/rules.md Rule #14
        """
        from apps.core.utils_new.async_retry_mechanism import AsyncRetryCoordinator
        import logging

        logger = logging.getLogger(__name__)
        max_retries = 3

        # Generate retry coordination key
        operation_id = f"ticket_create:{request.user.id}"
        context = {'path': request.path, 'user_id': request.user.id}
        retry_key = AsyncRetryCoordinator.generate_retry_key(operation_id, context)

        # Check if we should retry (non-blocking)
        should_retry, attempt = AsyncRetryCoordinator.should_retry(
            retry_key,
            max_retries,
            backoff_seconds=0.05  # 50ms base backoff
        )

        if not should_retry and attempt > 1:
            # Backoff period not elapsed - return 429
            backoff_time = AsyncRetryCoordinator._calculate_backoff(attempt, 0.05)
            return rp.JsonResponse(
                {
                    'error': 'Ticket number conflict - please retry',
                    'retry_after_ms': int(backoff_time * 1000),
                    'attempt': attempt
                },
                status=429,
                headers={'Retry-After': str(int(backoff_time))}
            )

        try:
            with transaction.atomic(using=get_current_db_name()):
                ticket = form.save(commit=False)
                ticket.uuid = request.POST.get("uuid")
                bu = ticket.bu_id if request.POST.get("pk") else None
                ticket = putils.save_userinfo(ticket, request.user, request.session, bu=bu)
                utils.store_ticket_history(ticket, request)

                # Success - clear retry state
                AsyncRetryCoordinator.clear_retry_state(retry_key)
                return rp.JsonResponse({"pk": ticket.id}, status=200)

        except IntegrityError as e:
            if "ticketno" in str(e):
                logger.warning(
                    f"IntegrityError on ticketno, attempt {attempt}/{max_retries}",
                    extra={
                        'attempt': attempt,
                        'user': request.user.loginid if hasattr(request.user, 'loginid') else 'unknown'
                    }
                )

                if attempt >= max_retries:
                    # Max retries exhausted
                    AsyncRetryCoordinator.clear_retry_state(retry_key)
                    logger.error(
                        f"Failed to create ticket after {max_retries} attempts",
                        extra={'error': str(e)},
                        exc_info=True
                    )
                    return utils.handle_intergrity_error("Ticket")

                # Return 429 - client should retry after backoff
                backoff_time = AsyncRetryCoordinator._calculate_backoff(attempt + 1, 0.05)
                return rp.JsonResponse(
                    {
                        'error': 'Ticket number conflict - please retry',
                        'retry_after_ms': int(backoff_time * 1000),
                        'attempt': attempt,
                        'max_retries': max_retries
                    },
                    status=429,
                    headers={'Retry-After': str(int(backoff_time))}
                )
            else:
                # Different IntegrityError - don't retry
                logger.error(f"IntegrityError (not ticketno): {e}", exc_info=True)
                return utils.handle_intergrity_error("Ticket")


@method_decorator(permission_required('activity.view_job', raise_exception=True), name='dispatch')
class PostingOrderView(LoginRequiredMixin, View):

    params = {
        "template_list": "y_helpdesk/posting_order_list.html",
        "model": Job,  # Fixed: Was Jobneed (legacy name)
    }

    def get(self, request, *args, **kwargs):
        R, P = request.GET, self.params
        if R.get("template") == "true":
            return render(request, P["template_list"])

        if R.get("action") == "list":
            # Optimized: Manager method already returns a list with pagination
            objs = P["model"].objects.get_posting_order_listview(request)
            return rp.JsonResponse({"data": objs}, status=200)


@method_decorator(permission_required('y_helpdesk.view_uniform', raise_exception=True), name='dispatch')
class UniformView(LoginRequiredMixin, View):
    params = {
        "template_list": "y_helpdesk/uniform_list.html",
    }

    def get(self, request, *args, **kwargs):
        return render(request, self.params["template_list"])
