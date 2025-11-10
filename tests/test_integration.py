"""
Integration tests for qsource3-mqtt application.
"""

import json
import os
import tempfile
import time
import unittest
from threading import Thread
from unittest.mock import Mock, patch

import yaml

from qsource3_mqtt.qsource3_mqtt_client import QSource3MQTTClient


class TestQSource3MQTTIntegration(unittest.TestCase):
    """Integration tests for the complete MQTT client system."""

    def setUp(self):
        """Set up test fixtures for integration tests."""
        self.config_data = {
            "client_id": "test-integration-client",
            "topic_base": "test/integration/qsource3",
            "device_name": "IntegrationTestDevice",
            "mqtt_broker": "localhost",
            "mqtt_port": 1883,
            "mqtt_connection_timeout": 60,
            "status_interval": 100,  # Fast for testing
            "qsource3_com_port": "ASRL/dev/ttyUSB0::INSTR",
            "r0": 4e-3,
            "number_of_ranges": 2,  # Smaller for faster tests
            "settings_file": "integration_test_settings.json",
        }

        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        )
        yaml.dump(self.config_data, self.temp_config)
        self.temp_config.close()
        self.config_file = self.temp_config.name

        # Create temporary settings file
        self.temp_settings = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        )
        self.settings_file = self.temp_settings.name
        self.temp_settings.close()

        # Update config to use temp settings file
        self.config_data["settings_file"] = self.settings_file

        # Rewrite config file with updated settings path
        with open(self.config_file, "w") as f:
            yaml.dump(self.config_data, f)

    def tearDown(self):
        """Clean up after integration tests."""
        for file_path in [self.config_file, self.settings_file]:
            if os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except OSError:
                    pass

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_full_client_lifecycle(self, mock_mqtt_client, mock_qsource3_logic):
        """Test the complete client lifecycle from initialization to shutdown."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_client_instance.is_connected.return_value = True
        mock_client_instance.socket.return_value = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        mock_logic_instance = Mock()
        mock_logic_instance.get_status.return_value = {
            "range": 0,
            "frequency": 1000000.0,
            "mz": 50.0,
            "is_dc_on": True,
        }
        mock_qsource3_logic.return_value = mock_logic_instance

        # Create client
        client = QSource3MQTTClient(self.config_file)

        # Test initialization
        self.assertIsNotNone(client.client)
        self.assertIsNotNone(client.qsource3)
        self.assertEqual(client.topic_base, "test/integration/qsource3")
        self.assertEqual(client.device_name, "IntegrationTestDevice")

        # Test connection setup
        with patch("qsource3_mqtt.qsource3_mqtt_client.select") as mock_select:
            mock_select.return_value = ([], [], [])  # No socket activity

            # Set up to exit main loop quickly
            client.disconnected = (False, None)

            # Start main loop in thread for short duration
            def run_client():
                client.connect_to_broker()
                # Run one iteration
                try:
                    client.do_select()
                except:
                    pass  # Expected due to mocking
                client.disconnected = (True, None)  # Force exit

            thread = Thread(target=run_client)
            thread.start()
            thread.join(timeout=1.0)  # 1 second timeout

        # Verify MQTT client was configured correctly
        mock_mqtt_client.assert_called_once_with(
            client_id="test-integration-client",
            clean_session=False,
        )

        # Test stop functionality
        client.stop()
        self.assertTrue(client.user_stop_event.is_set())

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_settings_persistence_integration(
        self, mock_mqtt_client, mock_qsource3_logic
    ):
        """Test that settings are properly saved and loaded across client restarts."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        # First client instance - create settings
        initial_settings = {
            "range": 1,
            "calib_pnts_dc": {0: [[10, 0.1]], 1: [[20, 0.2]]},
            "calib_pnts_rf": {0: [[30, 0.3]], 1: [[40, 0.4]]},
            "dc_offst": {0: 1.5, 1: 2.0},
            "is_dc_on": {0: True, 1: False},
            "is_rod_polarity_positive": {0: True, 1: False},
        }

        # Write initial settings to file
        with open(self.settings_file, "w") as f:
            json.dump(initial_settings, f)

        # Mock logic for first client
        mock_logic_instance1 = Mock()
        mock_qsource3_logic.return_value = mock_logic_instance1

        # Create first client
        client1 = QSource3MQTTClient(self.config_file)

        # Verify QSource3Logic was initialized with correct parameters
        mock_qsource3_logic.assert_called_with(
            comport="ASRL/dev/ttyUSB0::INSTR",
            r0=4e-3,
            on_connected=client1.on_qsource3_connected,
            number_of_ranges=2,
            settings_file=self.settings_file,
        )

        # Reset mock for second client
        mock_qsource3_logic.reset_mock()

        # Create second client (simulating restart)
        mock_logic_instance2 = Mock()
        mock_qsource3_logic.return_value = mock_logic_instance2

        client2 = QSource3MQTTClient(self.config_file)

        # Verify settings file is still passed correctly
        mock_qsource3_logic.assert_called_with(
            comport="ASRL/dev/ttyUSB0::INSTR",
            r0=4e-3,
            on_connected=client2.on_qsource3_connected,
            number_of_ranges=2,
            settings_file=self.settings_file,
        )

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_command_message_flow_integration(
        self, mock_mqtt_client, mock_qsource3_logic
    ):
        """Test the complete flow of receiving and processing command messages."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_client_instance.is_connected.return_value = True
        mock_mqtt_client.return_value = mock_client_instance

        mock_logic_instance = Mock()
        mock_logic_instance.is_dc_on = True
        mock_logic_instance.mz = 75.0
        mock_logic_instance.get_range.return_value = 1
        mock_qsource3_logic.return_value = mock_logic_instance

        # Create client
        client = QSource3MQTTClient(self.config_file)

        # Test is_dc_on command flow
        mock_msg = Mock()
        mock_msg.topic = "test/integration/qsource3/cmnd/IntegrationTestDevice/is_dc_on"
        mock_msg.payload = '{"value": false}'

        client.on_message(None, None, mock_msg)

        # Verify logic was updated
        self.assertEqual(mock_logic_instance.is_dc_on, False)

        # Verify response was published
        expected_response_topic = (
            "test/integration/qsource3/response/IntegrationTestDevice/is_dc_on"
        )
        expected_response_payload = json.dumps(
            {"value": False, "sender_payload": {"value": False}}
        )

        # Check that publish was called with correct parameters
        publish_calls = mock_client_instance.publish.call_args_list
        self.assertTrue(
            any(
                call[0][0] == expected_response_topic
                and call[0][1] == expected_response_payload
                for call in publish_calls
            )
        )

        # Test mz command flow
        mock_msg2 = Mock()
        mock_msg2.topic = "test/integration/qsource3/cmnd/IntegrationTestDevice/mz"
        mock_msg2.payload = '{"value": 85.5}'

        client.on_message(None, None, mock_msg2)

        # Verify mz was set
        self.assertEqual(mock_logic_instance.mz, 85.5)

        # Test range command flow
        mock_msg3 = Mock()
        mock_msg3.topic = "test/integration/qsource3/cmnd/IntegrationTestDevice/range"
        mock_msg3.payload = '{"value": 1}'

        client.on_message(None, None, mock_msg3)

        # Verify set_range was called
        mock_logic_instance.set_range.assert_called_with(1)

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_error_handling_integration(self, mock_mqtt_client, mock_qsource3_logic):
        """Test error handling across the system integration points."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_client_instance.is_connected.return_value = True
        mock_mqtt_client.return_value = mock_client_instance

        mock_logic_instance = Mock()
        mock_qsource3_logic.return_value = mock_logic_instance

        # Create client
        client = QSource3MQTTClient(self.config_file)

        # Test invalid JSON payload
        mock_msg = Mock()
        mock_msg.topic = "test/integration/qsource3/cmnd/IntegrationTestDevice/is_dc_on"
        mock_msg.payload = "invalid json {"

        # Should not raise exception
        client.on_message(None, None, mock_msg)

        # Test invalid payload structure
        mock_msg2 = Mock()
        mock_msg2.topic = (
            "test/integration/qsource3/cmnd/IntegrationTestDevice/is_dc_on"
        )
        mock_msg2.payload = '"just a string"'

        # Should not raise exception, but should publish error
        client.on_message(None, None, mock_msg2)

        # Verify error was published
        error_calls = [
            call
            for call in mock_client_instance.publish.call_args_list
            if "error" in call[0][0]
        ]
        self.assertTrue(len(error_calls) > 0)

        # Test connection error handling
        from qsource3_mqtt.qsource3_logic import QSource3NotConnectedException

        mock_logic_instance.is_dc_on = Mock(
            side_effect=QSource3NotConnectedException("Device disconnected")
        )

        mock_msg3 = Mock()
        mock_msg3.topic = (
            "test/integration/qsource3/cmnd/IntegrationTestDevice/is_dc_on"
        )
        mock_msg3.payload = '{"value": true}'

        client.on_message(None, None, mock_msg3)

        # Should have published error message
        error_calls = [
            call
            for call in mock_client_instance.publish.call_args_list
            if "error" in call[0][0]
        ]
        self.assertTrue(len(error_calls) > 0)

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_status_publishing_integration(self, mock_mqtt_client, mock_qsource3_logic):
        """Test the status publishing functionality integration."""
        # Setup mocks
        mock_client_instance = Mock()
        mock_client_instance.is_connected.return_value = True
        mock_mqtt_client.return_value = mock_client_instance

        mock_logic_instance = Mock()
        test_status = {
            "range": 1,
            "frequency": 480000.0,
            "rf_amp": 500.0,
            "dc1": 10.0,
            "dc2": -10.0,
            "current": 150.0,
            "mz": 75.5,
            "is_dc_on": True,
            "is_rod_polarity_positive": False,
            "max_mz": 1000.0,
        }
        mock_logic_instance.get_status.return_value = test_status
        mock_qsource3_logic.return_value = mock_logic_instance

        # Create client
        client = QSource3MQTTClient(self.config_file)

        # Test status publishing
        client.publish_status()

        # Verify status was published to correct topic
        expected_topic = "test/integration/qsource3/status/IntegrationTestDevice/state"
        expected_payload = json.dumps(test_status)

        mock_client_instance.publish.assert_called_with(
            expected_topic, expected_payload
        )

        # Test connection status publishing
        client.publish_connected(True)
        expected_conn_topic = (
            "test/integration/qsource3/status/IntegrationTestDevice/broker_connected"
        )

        # Find the call with the connection topic
        conn_calls = [
            call
            for call in mock_client_instance.publish.call_args_list
            if call[0][0] == expected_conn_topic
        ]
        self.assertTrue(len(conn_calls) > 0)

        # Test QSource3 connection status
        client.publish_qsource3_connected(True)
        expected_qsource3_topic = (
            "test/integration/qsource3/status/IntegrationTestDevice/qsource3_connected"
        )

        qsource3_calls = [
            call
            for call in mock_client_instance.publish.call_args_list
            if call[0][0] == expected_qsource3_topic
        ]
        self.assertTrue(len(qsource3_calls) > 0)

    def test_config_validation_integration(self):
        """Test configuration validation across system components."""
        # Test missing required keys
        incomplete_config = {
            "client_id": "test-client",
            "topic_base": "test/qsource3",
            # Missing other required keys
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(incomplete_config, f)
            incomplete_config_file = f.name

        try:
            with self.assertRaises(ValueError) as context:
                QSource3MQTTClient(incomplete_config_file)
            self.assertIn("Missing required configuration keys", str(context.exception))
        finally:
            os.unlink(incomplete_config_file)

        # Test invalid YAML syntax
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: [unclosed")
            invalid_yaml_file = f.name

        try:
            with self.assertRaises(yaml.YAMLError):
                QSource3MQTTClient(invalid_yaml_file)
        finally:
            os.unlink(invalid_yaml_file)


if __name__ == "__main__":
    unittest.main()
