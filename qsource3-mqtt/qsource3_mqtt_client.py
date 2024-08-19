import json
import logging
import time
from functools import wraps
from threading import Event, Thread

import paho.mqtt.client as mqtt
import yaml
from paho.mqtt.enums import CallbackAPIVersion

from .qsource3_logic import QSource3Logic, QSource3NotConnectedException

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
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


class QSource3MQTTClient:
    def __init__(self, config_file):
        self.load_config(config_file)

        self.qsource3 = QSource3Logic(
            comport=self.config["qsource3_com_port"], r0=self.config["r0"]
        )
        self.client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.connect_to_broker()
        self.status_event = Event()

    def load_config(self, config_file):
        with open(config_file, "r") as file:
            self.config = yaml.safe_load(file)
        self.topic_base = self.config["topic_base"]
        self.device_name = self.config["device_name"]
        self.status_interval = self.config["status_interval"]

    def connect_to_broker(self):
        logger.debug(
            f'Connecting to brooker {self.config["mqtt_broker"]}:{self.config["mqtt_port"]}...'
        )
        self.client.connect(
            self.config["mqtt_broker"],
            self.config["mqtt_port"],
            self.config["mqtt_connection_timeout"],
        )
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc, properties):
        logger.debug(f"Connected with result code {rc}")
        # Subscribe to command topics
        self.client.subscribe(f"{self.topic_base}/cmnd/{self.device_name}/#")
        self.publish_status_loop()

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = json.loads(msg.payload)

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

    # Define handlers for each command topic
    @handle_connection_error
    def handle_is_dc_on(self, payload):
        if "value" in payload:
            self.qsource3.is_dc_on = payload["value"]
        self.publish_response("is_dc_on", self.qsource3.is_dc_on, payload)

    @handle_connection_error
    def handle_is_rod_polarity_positive(self, payload):
        if "value" in payload:
            self.qsource3.is_rod_polarity_positive = payload["value"]
        self.publish_response(
            "is_rod_polarity_positive", self.qsource3.is_rod_polarity_positive, payload
        )

    @handle_connection_error
    def handle_max_mz(self, payload):
        self.publish_response("max_mz", self.qsource3.max_mz, payload)

    @handle_connection_error
    def handle_calib_pnts_dc(self, payload):
        if "value" in payload:
            self.qsource3.calib_pnts_dc = payload["value"]
        self.publish_response("calib_pnts_dc", self.qsource3.calib_pnts_dc, payload)

    @handle_connection_error
    def handle_calib_pnts_rf(self, payload):
        if "value" in payload:
            self.qsource3.calib_pnts_rf = payload["value"]
        self.publish_response("calib_pnts_rf", self.qsource3.calib_pnts_rf, payload)

    @handle_connection_error
    def handle_dc_offst(self, payload):
        if "value" in payload:
            self.qsource3.dc_offst = payload["value"]
        self.publish_response("dc_offst", self.qsource3.dc_offst, payload)

    @handle_connection_error
    def handle_range(self, payload):
        if "value" in payload:
            self.qsource3.set_range(payload["value"])
        self.publish_response("range", self.qsource3.get_range(), payload)

    # Example implementation of status publishing
    def publish_status_loop(self):
        while not self.status_event.is_set():
            self.publish_status()
            time.sleep(self.status_interval / 1000)

    @handle_connection_error
    def publish_status(self):
        status_payload = self.qsource3.get_status()
        self.client.publish(
            f"{self.topic_base}/status/{self.device_name}/state",
            json.dumps(status_payload),
        )

    def publish_response(self, command, value, sender_payload):
        response_payload = {"value": value, "sender_payload": sender_payload}
        self.client.publish(
            f"{self.topic_base}/response/{self.device_name}/{command}",
            json.dumps(response_payload),
        )

    def publish_error(self, command, error_message):
        error_payload = {"error": error_message}
        self.client.publish(
            f"{self.topic_base}/error/disconnected/{self.device_name}/{command}",
            json.dumps(error_payload),
        )
        logger.debug(f"Publish error: {error_message}")

    def start_status_thread(self):
        status_thread = Thread(target=self.publish_status_loop)
        status_thread.start()

    def stop(self):
        self.status_event.set()
        self.client.loop_stop()


if __name__ == "__main__":
    client = QSource3MQTTClient("config.yaml")
    client.start_status_thread()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.stop()
