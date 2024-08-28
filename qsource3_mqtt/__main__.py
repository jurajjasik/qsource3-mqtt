import logging
import time

from .qsource3_mqtt_client import QSource3MQTTClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    client = QSource3MQTTClient("config.yaml")

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
