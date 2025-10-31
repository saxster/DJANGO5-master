"""
IVR Webhook Views.

Handles callbacks from IVR providers (Twilio, Google Voice).
Processes call status updates and DTMF responses.

Security:
- Twilio webhooks use @validate_twilio_request for signature validation
- Replaces @csrf_exempt with cryptographic authentication (Rule #3)

Follows .claude/rules.md:
- Rule #3: Alternative authentication mechanism for webhooks
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from .decorators import validate_twilio_request

logger = logging.getLogger('noc.security_intelligence.ivr')


@validate_twilio_request  # ✅ SECURE: Validates X-Twilio-Signature header
@require_POST
def twilio_status_callback(request):
    """
    Handle Twilio call status callbacks.

    Twilio sends status updates as POST requests with cryptographic signatures.

    Security (Rule #3 Compliant):
    - @validate_twilio_request validates X-Twilio-Signature header
    - Uses HMAC-SHA1 with Twilio Auth Token as shared secret
    - Returns 403 Forbidden for invalid/missing signatures
    - See: apps/noc/security_intelligence/ivr/decorators.py

    Reference:
    https://www.twilio.com/docs/usage/security#validating-requests
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


@validate_twilio_request  # ✅ SECURE: Validates X-Twilio-Signature header
@require_POST
def twilio_gather_callback(request):
    """
    Handle DTMF input from Twilio.

    Processes user keypresses and validates responses.

    Security (Rule #3 Compliant):
    - @validate_twilio_request validates X-Twilio-Signature header
    - Uses HMAC-SHA1 with Twilio Auth Token as shared secret
    - Returns 403 Forbidden for invalid/missing signatures
    - See: apps/noc/security_intelligence/ivr/decorators.py
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