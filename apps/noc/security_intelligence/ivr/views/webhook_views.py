"""
IVR Webhook Views.

Handles callbacks from IVR providers (Twilio, Google Voice).
Processes call status updates and DTMF responses.

Follows .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator

logger = logging.getLogger('noc.security_intelligence.ivr')


@csrf_exempt  # TODO: Replace with Twilio signature verification (Rule #3)
@require_POST
def twilio_status_callback(request):
    """
    Handle Twilio call status callbacks.

    Twilio sends status updates as POST requests.

    SECURITY TODO: Implement Twilio request signature validation
    https://www.twilio.com/docs/usage/security#validating-requests
    Required implementation:
    1. Get X-Twilio-Signature header
    2. Validate using AccountSid and AuthToken
    3. Return 403 if validation fails

    Current: @csrf_exempt (acceptable only with signature validation)
    Rule #3 Compliance: Webhook requires alternative authentication mechanism
    """
    from apps.noc.security_intelligence.ivr.services import AIIVRService

    try:
        call_sid = request.POST.get('CallSid')
        status_data = request.POST.dict()

        AIIVRService.process_call_callback(call_sid, status_data)

        return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', content_type='text/xml')

    except (ValueError, AttributeError) as e:
        logger.error(f"Twilio callback error: {e}", exc_info=True)
        return HttpResponse(status=500)


@csrf_exempt  # TODO: Replace with Twilio signature verification (Rule #3)
@require_POST
def twilio_gather_callback(request):
    """
    Handle DTMF input from Twilio.

    Processes user keypresses and validates responses.

    SECURITY TODO: Implement Twilio request signature validation
    See twilio_status_callback() for implementation requirements.

    Current: @csrf_exempt (acceptable only with signature validation)
    Rule #3 Compliance: Webhook requires alternative authentication mechanism
    """
    from apps.noc.security_intelligence.ivr.services import ResponseValidator
    from apps.noc.security_intelligence.ivr.models import IVRCallLog

    try:
        call_sid = request.POST.get('CallSid')
        digits = request.POST.get('Digits', '')

        call_log = IVRCallLog.objects.get(call_sid=call_sid)

        expected_options = {'1': 'confirmed', '2': 'assistance', '3': 'escalate'}

        validation = ResponseValidator.validate_dtmf_response(
            dtmf_input=digits,
            expected_options=expected_options,
            anomaly_type='GENERIC'
        )

        ResponseValidator.process_and_act(
            call_log,
            {'dtmf': digits},
            validation
        )

        return HttpResponse(f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>Thank you. Your response has been recorded.</Say></Response>', content_type='text/xml')

    except IVRCallLog.DoesNotExist:
        logger.error(f"Call log not found for SID: {call_sid}")
        return HttpResponse(status=404)
    except (ValueError, AttributeError) as e:
        logger.error(f"Gather callback error: {e}", exc_info=True)
        return HttpResponse(status=500)