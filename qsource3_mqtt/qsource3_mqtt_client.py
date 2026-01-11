import json
import logging
import socket
from functools import wraps
from select import select
from threading import Event, Thread
from time import time

import paho.mqtt.client as mqtt
import yaml

from .qsource3_logic import QSource3Logic, QSource3NotConnectedException

logger = logging.getLogger(__name__)


def handle_connection_error(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        logger.debug(
            f"Calling method: {method.__name__} with args: {args} and kwargs: {kwargs}"
        )
        try:
            result = method(self, *args, **kwargs)
            logger.debug(f"Method {method.__name__} returned: {result}")
            return result
        except QSource3NotConnectedException as e:
            command = method.__name__.split("_")[1]  # Extract command from method name
            logger.error(f"Connection error in method {method.__name__}: {e}")
            self.publish_error(command, str(e))

    return wrapper


class QSource3MQTTClientNotConnectedException(Exception):
    """Exception raised when the QSource3MQTTClient could not connect to the broker."""

    def __init__(
        self,
        additional_massage="",
        message="QSource3MQTTClient could not connect to the broker.",
    ):
        super().__init__(message + " " + additional_massage)


class QSource3MQTTClient:
    def __init__(self, config_file):
        self.user_stop_event = Event()

        self.load_config(config_file)

        self.client = mqtt.Client(
            client_id=self.config["client_id"],
            clean_session=False,
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.will_set(
            f"{self.topic_base}/status/{self.device_name}/broker_connected",
            '{"value": "OFFLINE"}',
            retain=True,
        )

        self.qsource3 = QSource3Logic(
            comport=self.config["qsource3_com_port"],
            r0=float(self.config["r0"]),
            on_connected=self.on_qsource3_connected,
            number_of_ranges=self.config["number_of_ranges"],
            settings_file=self.config["settings_file"],
        )

    def load_config(self, config_file):
        try:
            with open(config_file, "r") as file:
                self.config = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML configuration: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise

        # Validate required configuration keys
        required_keys = [
            "client_id",
            "topic_base",
            "device_name",
            "mqtt_broker",
            "mqtt_port",
            "status_interval",
            "qsource3_com_port",
            "r0",
            "number_of_ranges",
            "settings_file",
        ]

        missing_keys = [key for key in required_keys if key not in self.config]
        if missing_keys:
            raise ValueError(f"Missing required configuration keys: {missing_keys}")

        self.topic_base = self.config["topic_base"]
        self.device_name = self.config["device_name"]
        self.status_interval = self.config["status_interval"]

    def _validate_payload_structure(self, payload, command_name):
        """Validate basic payload structure."""
        if not isinstance(payload, dict):
            raise ValueError(
                f"{command_name} payload must be a dictionary, got {type(payload)}"
            )

    def _validate_numeric_value(self, value, param_name, allow_negative=True):
        """Validate that a value is numeric."""
        if not isinstance(value, (int, float)):
            raise ValueError(f"{param_name} must be a number, got {type(value)}")
        if not allow_negative and value < 0:
            raise ValueError(f"{param_name} must be non-negative, got {value}")

    def _validate_boolean_value(self, value, param_name):
        """Validate that a value is boolean."""
        if not isinstance(value, bool):
            raise ValueError(f"{param_name} must be a boolean, got {type(value)}")

    def _validate_calibration_points(self, points, param_name):
        """Validate calibration points structure."""
        if not isinstance(points, list):
            raise ValueError(f"{param_name} must be a list, got {type(points)}")
        for i, point in enumerate(points):
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError(
                    f"{param_name}[{i}] must be a list of 2 numbers, got {point}"
                )
            if not all(isinstance(coord, (int, float)) for coord in point):
                raise ValueError(
                    f"{param_name}[{i}] coordinates must be numbers, got {point}"
                )

    def connect_to_broker(self):
        logger.debug(
            f'Connecting client_id {self.config["client_id"]} to brooker {self.config["mqtt_broker"]}:{self.config["mqtt_port"]}...'
        )
        if self.client is not None:
            try:
                self.client.connect(
                    self.config["mqtt_broker"],
                    self.config["mqtt_port"],
                    self.config["mqtt_connection_timeout"],
                )
            except Exception as e:
                logger.error(f"Error connecting to MQTT broker: {e}")
                self.disconnected = True, -1
        else:
            logger.error("MQTT client is None in connect_to_broker")
            raise QSource3MQTTClientNotConnectedException("MQTT client is None")

    def on_connect(self, client, userdata, flags, reason_code):
        logger.debug(f"on_connect with reason code {reason_code}")
        if reason_code != 0:
            self.disconnected = True, reason_code
            raise QSource3MQTTClientNotConnectedException(
                f"reason_code = {reason_code}"
            )

        # Subscribe to command topics
        if self.client is not None:
            self.client.subscribe(f"{self.topic_base}/cmnd/{self.device_name}/#")
            self.publish_connected(True)
        else:
            logger.error("MQTT client is None in on_connect")

    def on_disconnect(self, client, userdata, flags, reason_code=None):
        logger.debug(f"on_disconnect with reason code {reason_code}")
        self.disconnected = True, reason_code

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in message on topic {topic}: {e}")
            return
        except Exception as e:
            logger.error(f"Error processing message on topic {topic}: {e}")
            return

        try:
            if topic.endswith("/is_dc_on"):
                self.handle_is_dc_on(payload)
            elif topic.endswith("/is_rod_polarity_positive"):
                self.handle_is_rod_polarity_positive(payload)
            elif topic.endswith("/max_mz"):
                self.handle_max_mz(payload)
            elif topic.endswith("/calib_pnts_dc"):
                self.handle_calib_pnts_dc(payload)
            elif topic.endswith("/calib_pnts_rf"):
                self.handle_calib_pnts_rf(payload)
            elif topic.endswith("/dc_offst"):
                self.handle_dc_offst(payload)
            elif topic.endswith("/range"):
                self.handle_range(payload)
            elif topic.endswith("/mz"):
                self.handle_mz(payload)
            else:
                logger.warning(f"Unknown command topic: {topic}")
        except Exception as e:
            logger.error(f"Error handling message on topic {topic}: {e}")
            # Extract command from topic for error reporting
            command = topic.split("/")[-1] if "/" in topic else "unknown"
            self.publish_error(command, f"Message handling error: {str(e)}")

    # Define handlers for each command topic
    @handle_connection_error
    def handle_is_dc_on(self, payload):
        self._validate_payload_structure(payload, "is_dc_on")
        if "value" in payload:
            self._validate_boolean_value(payload["value"], "is_dc_on")
            self.qsource3.is_dc_on = payload["value"]
        self.publish_response("is_dc_on", self.qsource3.is_dc_on, payload)

    @handle_connection_error
    def handle_is_rod_polarity_positive(self, payload):
        self._validate_payload_structure(payload, "is_rod_polarity_positive")
        if "value" in payload:
            self._validate_boolean_value(payload["value"], "is_rod_polarity_positive")
            self.qsource3.is_rod_polarity_positive = payload["value"]
        self.publish_response(
            "is_rod_polarity_positive", self.qsource3.is_rod_polarity_positive, payload
        )

    @handle_connection_error
    def handle_max_mz(self, payload):
        self._validate_payload_structure(payload, "max_mz")
        # This is a getter method, so no "value" expected
        if "value" in payload:
            logger.warning("max_mz is a read-only property, ignoring provided value")
        self.publish_response("max_mz", self.qsource3.max_mz, payload)

    @handle_connection_error
    def handle_calib_pnts_dc(self, payload):
        self._validate_payload_structure(payload, "calib_pnts_dc")
        if "value" in payload:
            self._validate_calibration_points(payload["value"], "calib_pnts_dc")
            self.qsource3.calib_pnts_dc = payload["value"]
        self.publish_response("calib_pnts_dc", self.qsource3.calib_pnts_dc, payload)

    @handle_connection_error
    def handle_calib_pnts_rf(self, payload):
        self._validate_payload_structure(payload, "calib_pnts_rf")
        if "value" in payload:
            self._validate_calibration_points(payload["value"], "calib_pnts_rf")
            self.qsource3.calib_pnts_rf = payload["value"]
        self.publish_response("calib_pnts_rf", self.qsource3.calib_pnts_rf, payload)

    @handle_connection_error
    def handle_dc_offst(self, payload):
        self._validate_payload_structure(payload, "dc_offst")
        if "value" in payload:
            self._validate_numeric_value(
                payload["value"], "dc_offst", allow_negative=True
            )
            self.qsource3.dc_offst = payload["value"]
        self.publish_response("dc_offst", self.qsource3.dc_offst, payload)

    @handle_connection_error
    def handle_range(self, payload):
        self._validate_payload_structure(payload, "range")
        if "value" in payload:
            if not isinstance(payload["value"], int):
                raise ValueError(
                    f"range value must be an integer, got {type(payload['value'])}"
                )
            self._validate_numeric_value(
                payload["value"], "range", allow_negative=False
            )
            # Note: Upper bound checking is handled in qsource3_logic.py set_range method
            self.qsource3.set_range(payload["value"])
        self.publish_response("range", self.qsource3.get_range(), payload)

    @handle_connection_error
    def handle_mz(self, payload):
        self._validate_payload_structure(payload, "mz")
        if "value" in payload:
            self._validate_numeric_value(payload["value"], "mz", allow_negative=False)
            self.qsource3.mz = payload["value"]
        self.publish_response("mz", self.qsource3.mz, payload)

    @handle_connection_error
    def publish_status(self):
        if self.client is not None and self.client.is_connected():
            status_payload = self.qsource3.get_status()
            if status_payload is not None:
                self.client.publish(
                    f"{self.topic_base}/status/{self.device_name}/state",
                    json.dumps(status_payload),
                )

    def publish_connected(self, connected: bool):
        """Publishes a retained message indicating the connection status."""
        if self.client is not None:
            topic = f"{self.topic_base}/status/{self.device_name}/broker_connected"
            payload = '{"value": "ONLINE"}' if connected else '{"value": "OFFLINE"}'
            self.client.publish(topic, payload, retain=True)
            logger.debug(f"Published broker connected status to {topic}")

    def publish_qsource3_connected(self, connected: bool):
        """Publishes a retained message indicating the qsource3 connection status."""
        if self.client is not None:
            topic = f"{self.topic_base}/status/{self.device_name}/qsource3_connected"
            payload = '{"value": "True"}' if connected else '{"value": "False"}'
            self.client.publish(topic, payload, retain=True)
            logger.debug(f"Published qsource3 connected status to {topic}")

    def on_qsource3_connected(self):
        """Publishes a retained message indicating the qsource3 is connected."""
        self.publish_qsource3_connected(True)

    def publish_response(self, command, value, sender_payload):
        if self.client is not None and self.client.is_connected():
            response_payload = {"value": value, "sender_payload": sender_payload}
            topic = f"{self.topic_base}/response/{self.device_name}/{command}"
            self.client.publish(
                topic,
                json.dumps(response_payload),
            )
            logger.debug(f"Publish topic: {topic}, payload: {response_payload}")

    def publish_error(self, command, error_message):
        if self.client is not None and self.client.is_connected():
            error_payload = {"error": error_message, "command": command}
            self.client.publish(
                f"{self.topic_base}/error/{self.device_name}/disconnected",
                json.dumps(error_payload),
            )
            logger.debug(f"Publish error: {error_message}")

    def stop(self):
        logger.debug("User stop")
        self.user_stop_event.set()

    def do_select(self):
        if self.client is None:
            return
        sock = self.client.socket()
        if not sock:
            logger.debug("Socket is gone")
            raise Exception("Socket is gone")

        logger.debug(
            "Selecting for reading"
            + (" and writing" if self.client.want_write() else "")
        )
        r, w, e = select([sock], [sock] if self.client.want_write() else [], [], 1)

        if sock in r:
            logger.debug("Socket is readable, calling loop_read")
            self.client.loop_read()

        if sock in w:
            logger.debug("Socket is writable, calling loop_write")
            self.client.loop_write()

        self.client.loop_misc()

        if time() - self.last_time >= self.status_interval / 1000:
            self.last_time = time()
            if self.client.is_connected():
                self.publish_status()

    def main(self):
        self.disconnected = (False, None)

        self.connect_to_broker()

        self.last_time = time()
        while not self.disconnected[0] and not self.user_stop_event.is_set():
            self.do_select()

        if self.client is not None:
            self.publish_qsource3_connected(False)
