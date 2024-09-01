import logging
import time

from qsource3_mqtt.qsource3_mqtt_client import QSource3MQTTClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = "config.yaml"

    client = QSource3MQTTClient(config_file)

    try:
        while True:
            client.main()
            logger.info(
                f"Main loop stopped. Disconnected status: {client.disconnected}"
            )
            logger.info("Attempt to reconnect in 5 seconds ...")
            time.sleep(5)
    except KeyboardInterrupt:
        if client is not None:
            client.stop()
