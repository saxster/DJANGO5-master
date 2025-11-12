"""
MQTT health checks: MQTT broker connectivity for IoT device communication.
Follows Rule 11: Specific exception handling only.
"""

import time
import logging
from typing import Dict, Any
from .utils import timeout_check, format_check_result, CircuitBreaker

logger = logging.getLogger(__name__)

__all__ = [
    'check_mqtt_broker',
]

mqtt_circuit_breaker = CircuitBreaker(failure_threshold=3, timeout_seconds=30)


@timeout_check(timeout_seconds=3)
def check_mqtt_broker() -> Dict[str, Any]:
    """
    Check MQTT broker connectivity without publishing messages.
    Uses circuit breaker to prevent cascading failures.

    Returns:
        Health check result with MQTT broker status.
    """
    start_time = time.time()

    def _mqtt_connectivity_test() -> Dict[str, Any]:
        try:
            from paho.mqtt import client as mqtt
            from paho.mqtt.enums import CallbackAPIVersion
            from django.conf import settings

            mqtt_config = getattr(settings, "MQTT_CONFIG", {})

            broker_address = mqtt_config.get("BROKER_ADDRESS")
            broker_port = mqtt_config.get("BROKER_PORT", 1883)

            if not broker_address:
                return format_check_result(
                    status="degraded",
                    message="MQTT broker not configured",
                    details={"note": "IoT features unavailable"},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            test_client = mqtt.Client(CallbackAPIVersion.VERSION2)

            connection_result = {"connected": False}

            def on_connect(client, userdata, flags, rc, props):
                if rc == 0:
                    connection_result["connected"] = True
                    client.disconnect()
                else:
                    connection_result["rc"] = rc

            test_client.on_connect = on_connect

            try:
                test_client.connect(broker_address, broker_port, keepalive=3)
                test_client.loop_start()
                # SAFE: time.sleep() acceptable in health check (not in request path)
                # - Called from management command or monitoring task
                # - Brief delay required for MQTT connection handshake
                time.sleep(1)
                test_client.loop_stop()
            except ConnectionRefusedError as e:
                raise ConnectionError(f"MQTT broker refused connection: {str(e)}")
            except OSError as e:
                raise ConnectionError(f"MQTT broker unreachable: {str(e)}")
            finally:
                try:
                    test_client.disconnect()
                except (ValueError, TypeError, AttributeError) as e:
                    pass

            if not connection_result.get("connected"):
                rc = connection_result.get("rc", "unknown")
                return format_check_result(
                    status="error",
                    message=f"MQTT broker connection failed with code: {rc}",
                    details={"broker": broker_address, "port": broker_port, "return_code": rc},
                    duration_ms=(time.time() - start_time) * 1000,
                )

            duration = (time.time() - start_time) * 1000

            return format_check_result(
                status="healthy",
                message="MQTT broker reachable",
                details={
                    "broker": broker_address,
                    "port": broker_port,
                    "connection_test": "passed",
                },
                duration_ms=duration,
            )

        except ImportError as e:
            logger.warning("paho-mqtt not installed")
            return format_check_result(
                status="degraded",
                message="paho-mqtt not installed",
                details={"note": "IoT features unavailable"},
                duration_ms=(time.time() - start_time) * 1000,
            )

    return mqtt_circuit_breaker.call(_mqtt_connectivity_test)
