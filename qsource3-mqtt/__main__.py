import time

from .qsource3_mqtt_client import QSource3MQTTClient

if __name__ == "__main__":
    client = QSource3MQTTClient("config.yaml")
    client.start_status_thread()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.stop()
