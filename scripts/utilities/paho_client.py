import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django

django.setup()
from paho.mqtt import client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from django.conf import settings
from background_tasks.tasks import process_graphql_mutation_async
from celery.result import AsyncResult
import json
import logging
from base64 import b64decode
from zlib import decompress

MQTT_CONFIG = settings.MQTT_CONFIG
log = logging.getLogger("message_q")

# MQTT broker settings
BROKER_ADDRESS = MQTT_CONFIG["BROKER_ADDRESS"]
BROKER_PORT = MQTT_CONFIG["broker_port"]

GRAPHQL_MUTATION = "graphql/django5mutation"
GRAPHQL_ATTACHMENT = "graphql/django5attachment"
MUTATION_STATUS = "graphql/mutation/django5status"
# GRAPHQL_DOWNLOAD = "graphql/download"


RESPONSE_TOPIC = "response"
# RESPONSE_DOWNLOAD = "response/download"
STATUS_TOPIC = "response/status"

TESTMQ = "django5post"
TESTPUBMQ = "django5received"

REDMINE_TO_NOC = "redmine_to_noc"


def get_task_status(item):
    """
    Get status of a task
    """
    status = AsyncResult(item.get("taskId")).status
    item.update({"status": status})
    return item


def unzip_string(encoded_input):
    # Ensure input is a string
    if isinstance(encoded_input, bytes):
        encoded_input = encoded_input.decode('utf-8')

    # First, check if the input looks like valid JSON already (not compressed)
    try:
        json.loads(encoded_input)
        log.info("Input appears to be uncompressed JSON, returning as-is")
        return encoded_input
    except json.JSONDecodeError:
        pass  # Continue with decompression attempt

    # Remove any whitespace, newlines, and common URL-safe substitutions
    encoded_input = encoded_input.strip()

    # Handle URL-safe base64 (convert back to standard base64)
    # URL-safe uses - and _ instead of + and /
    encoded_input = encoded_input.replace('-', '+').replace('_', '/')

    # Remove any existing padding first
    encoded_input = encoded_input.rstrip('=')

    # Calculate and add proper padding
    missing_padding = len(encoded_input) % 4
    if missing_padding:
        encoded_input += '=' * (4 - missing_padding)

    try:
        # Decode the base64 encoded string to get compressed bytes
        compressed_bytes = b64decode(encoded_input)
    except Exception as e:
        log.error(f"Base64 decode failed, trying without padding: {e}")
        try:
            # Try without any padding
            encoded_input = encoded_input.rstrip('=')
            compressed_bytes = b64decode(encoded_input + '==')  # Try with double padding
        except:
            try:
                # Last attempt with single padding
                compressed_bytes = b64decode(encoded_input + '=')
            except Exception as final_e:
                log.error(f"All base64 decode attempts failed: {final_e}")
                log.error(f"Problematic input (first 100 chars): {encoded_input[:100]}")
                raise

    # Decompress the bytes using zlib
    try:
        decompressed_bytes = decompress(compressed_bytes)
        log.info("Successfully decompressed message")
    except Exception as e:
        log.error(f"Decompression failed: {e}")
        # Maybe it's not compressed? Try to use as-is
        decompressed_bytes = compressed_bytes
        log.info("Using base64 decoded bytes without decompression")

    # Convert the bytes back to a UTF-8 string
    try:
        result = decompressed_bytes.decode("utf-8")
        # Validate the result is valid JSON
        json.loads(result)
        return result
    except json.JSONDecodeError as json_err:
        log.error(f"Decompressed result is not valid JSON: {json_err}")
        raise
    except UnicodeDecodeError:
        # Try different encodings
        try:
            result = decompressed_bytes.decode("latin-1")
            json.loads(result)
            return result
        except:
            log.error("Failed to decode bytes to valid JSON string")
            raise


class MqttClient:
    """
    MQTT client class listens for connection, messages,
    dis-connection
    """

    def __init__(self):
        """
        Initializes the MQTT client
        """
        self.client = mqtt.Client(CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        """
        Initializes the MQTT client and sets up the callback functions
        for connect, message, and disconnect events.
        """

    # MQTT client callback functions
    def on_connect(self, client, userdata, flags, rc, props):
        log.info("Hello %s", rc)
        if rc == "Success":
            log.info("Connected to MQTT Broker!")
            # Subscribe to Django5-specific topics only
            client.subscribe(GRAPHQL_MUTATION, qos=1)  # graphql/django5mutation
            client.subscribe(MUTATION_STATUS, qos=1)   # graphql/mutation/django5status
            client.subscribe(TESTMQ)                   # django5post
            client.subscribe(GRAPHQL_ATTACHMENT, qos=1) # graphql/django5attachment
            log.info("Subscribed to Django5 topics only")
        else:
            fail = f"Failed to connect, return code {rc}"

    def on_message(self, client, userdata, msg):
        try:
            log.info(
                "message: {} from MQTT broker on topic {} {}".format(
                    msg.mid,
                    msg.topic,
                    "payload recieved" if msg.payload else "payload not recieved",
                )
            )
            log.info("processing started [+]")

            if msg.topic == TESTMQ:
                response = json.dumps({"name": "Satyam"})
                log.info(f"Response published to {RESPONSE_TOPIC} after accepting")
                client.publish(TESTPUBMQ, response, qos=2)

            # Handle Django5 mutation topic only
            if msg.topic == GRAPHQL_MUTATION:
                # Process the received message
                log.info(f"Received Message on Topic {msg.topic}")
                payload = msg.payload.decode("utf-8")

                # Try to decompress the message
                try:
                    original_message = unzip_string(payload)
                except Exception as decomp_error:
                    log.error(f"Failed to decompress message: {decomp_error}")
                    # If decompression fails, try using payload as-is (might be uncompressed)
                    original_message = payload

                # Validate that we have valid JSON before processing
                try:
                    post_data = json.loads(original_message)
                except json.JSONDecodeError as json_error:
                    log.error(f"Invalid JSON in message: {json_error}")
                    log.error(f"Message content (first 200 chars): {original_message[:200]}")
                    # Send error response
                    response = json.dumps({
                        "error": "Invalid message format",
                        "details": str(json_error)
                    })
                    client.publish(RESPONSE_TOPIC, response, qos=2)
                    return

                # process graphql mutations received on this topic
                result = process_graphql_mutation_async.apply_async(args=[original_message], queue='django5_queue')
                uuids, service_name = post_data.get("uuids", []), post_data.get(
                    "serviceName", ""
                )
                response = json.dumps(
                    {
                        "task_id": result.task_id,
                        "status": result.state,
                        "uuids": uuids,
                        "serviceName": service_name,
                        "payload": payload,
                    }
                )

                log.info(
                    f"Response published to {RESPONSE_TOPIC} after accepting {service_name}"
                )
                client.publish(RESPONSE_TOPIC, response, qos=2)

            if msg.topic == MUTATION_STATUS:
                log.info(f"Received Message on Topic {MUTATION_STATUS}")
                payload = msg.payload.decode()
                # enquire the status of tasks ids received on this topic
                payload = json.loads(payload)
                log.info(f"Received taskIds payload: {payload}")
                taskids = payload.get("taskIds", [])
                taskids_with_status = list(map(get_task_status, taskids))
                response = json.dumps(taskids_with_status)
                log.info(f"Response published to {STATUS_TOPIC}: {response}")
                client.publish(STATUS_TOPIC, response, qos=2)

            # Handle Django5 attachment topic only
            if msg.topic == GRAPHQL_ATTACHMENT:
                log.info(f"Received Message on Topic {msg.topic}")
                payload = msg.payload.decode("utf-8")
                original_message = unzip_string(payload)
                log.info("Inside of the Graphql attachment")
                result = process_graphql_mutation_async.apply_async(args=[original_message], queue='django5_queue')
                post_data = json.loads(original_message)
                uuids, service_name = post_data.get("uuids", []), post_data.get(
                    "serviceName", ""
                )
                response = json.dumps(
                    {
                        "task_id": result.task_id,
                        "status": result.state,
                        "uuids": uuids,
                        "serviceName": service_name,
                        "payload": payload,
                    }
                )
                client.publish(RESPONSE_TOPIC, response, qos=2)
        except Exception as e:
            log.error(f"Error processing message: {e}", exc_info=True)
            # Don't re-raise the exception - just log it and continue
            # This prevents the MQTT client from disconnecting on errors
            
            # Try to send error response if possible
            try:
                error_response = json.dumps({
                    "error": str(e),
                    "status": "ERROR",
                    "topic": msg.topic if msg else "unknown"
                })
                client.publish(RESPONSE_TOPIC, error_response, qos=2)
            except:
                pass  # If we can't send error response, just continue

    def on_disconnect(self, client, userdata, disconnect_flags, rc, props):
        log.info("Disconnected from MQTT broker")

    def loop_forever(self):
        # Connect to MQTT broker
        self.client.connect(BROKER_ADDRESS, BROKER_PORT)
        self.client.loop_forever()

    # def publish_message(self,topic,message):
    #     result_code, mid = self.client.publish(topic, message,qos=0)
    #     if result_code == mqtt.MQTT_ERR_SUCCESS:
    #         log.info("Message sent Successfully")
    #     else:
    #         log.info("Failed to send message to topic ")


if __name__ == "__main__":
    client = MqttClient()
    client.loop_forever()
