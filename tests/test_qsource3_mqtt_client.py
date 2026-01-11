"""
Unit tests for QSource3MQTTClient class.
"""

import json
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch

import paho.mqtt.client as mqtt
import yaml

from qsource3_mqtt.qsource3_logic import QSource3NotConnectedException
from qsource3_mqtt.qsource3_mqtt_client import (
    QSource3MQTTClient, QSource3MQTTClientNotConnectedException,
    handle_connection_error)


class TestHandleConnectionErrorDecorator(unittest.TestCase):
    """Test cases for handle_connection_error decorator."""

    def test_handle_connection_error_success(self):
        """Test decorator when method executes successfully."""

        class TestClass:
            def __init__(self):
                self.publish_error = Mock()

            @handle_connection_error
            def test_method_range(self):
                return "success"

        test_instance = TestClass()
        result = test_instance.test_method_range()

        self.assertEqual(result, "success")
        test_instance.publish_error.assert_not_called()

    def test_handle_connection_error_exception(self):
        """Test decorator when QSource3NotConnectedException is raised."""

        class TestClass:
            def __init__(self):
                self.publish_error = Mock()

            @handle_connection_error
            def test_method_mz(self):
                raise QSource3NotConnectedException("Device not connected")

        test_instance = TestClass()
        test_instance.test_method_mz()  # Should not raise, but call publish_error

        test_instance.publish_error.assert_called_once_with(
            "mz", "Device not connected"
        )


class TestQSource3MQTTClient(unittest.TestCase):
    """Test cases for QSource3MQTTClient class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config_data = {
            "client_id": "test-client-123",
            "topic_base": "test/qsource3",
            "device_name": "TestDevice",
            "mqtt_broker": "localhost",
            "mqtt_port": 1883,
            "mqtt_connection_timeout": 60,
            "status_interval": 1000,
            "qsource3_com_port": "ASRL/dev/ttyUSB0::INSTR",
            "r0": 4e-3,
            "number_of_ranges": 3,
            "settings_file": "test_settings.json",
        }

        # Create temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        )
        yaml.dump(self.config_data, self.temp_config)
        self.temp_config.close()
        self.config_file = self.temp_config.name

    def tearDown(self):
        """Clean up after each test."""
        import os

        if os.path.exists(self.config_file):
            os.unlink(self.config_file)

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_init_success(self, mock_mqtt_client, mock_qsource3_logic):
        """Test successful initialization of QSource3MQTTClient."""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        mock_logic_instance = Mock()
        mock_qsource3_logic.return_value = mock_logic_instance

        client = QSource3MQTTClient(self.config_file)

        # Verify configuration loaded
        self.assertEqual(client.config, self.config_data)
        self.assertEqual(client.topic_base, "test/qsource3")
        self.assertEqual(client.device_name, "TestDevice")
        self.assertEqual(client.status_interval, 1000)

        # Verify MQTT client setup
        mock_mqtt_client.assert_called_once_with(
            client_id="test-client-123",
            clean_session=False,
        )
        self.assertEqual(client.client, mock_client_instance)

        # Verify callbacks set
        self.assertEqual(mock_client_instance.on_connect, client.on_connect)
        self.assertEqual(mock_client_instance.on_message, client.on_message)
        self.assertEqual(mock_client_instance.on_disconnect, client.on_disconnect)

        # Verify will message set
        expected_will_topic = "test/qsource3/status/TestDevice/broker_connected"
        mock_client_instance.will_set.assert_called_once_with(
            expected_will_topic,
            '{"value": "OFFLINE"}',
            retain=True,
        )

        # Verify QSource3Logic setup
        mock_qsource3_logic.assert_called_once_with(
            comport="ASRL/dev/ttyUSB0::INSTR",
            r0=4e-3,
            on_connected=client.on_qsource3_connected,
            number_of_ranges=3,
            settings_file="test_settings.json",
        )

    def test_load_config_file_not_found(self):
        """Test load_config with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            QSource3MQTTClient("nonexistent.yaml")

    def test_load_config_invalid_yaml(self):
        """Test load_config with invalid YAML."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid: yaml: content: [")
            invalid_config_file = f.name

        try:
            with self.assertRaises(yaml.YAMLError):
                QSource3MQTTClient(invalid_config_file)
        finally:
            import os

            os.unlink(invalid_config_file)

    def test_load_config_missing_required_keys(self):
        """Test load_config with missing required keys."""
        incomplete_config = {"client_id": "test"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(incomplete_config, f)
            incomplete_config_file = f.name

        try:
            with self.assertRaises(ValueError) as context:
                QSource3MQTTClient(incomplete_config_file)
            self.assertIn("Missing required configuration keys", str(context.exception))
        finally:
            import os

            os.unlink(incomplete_config_file)

    def test_validate_payload_structure_valid(self):
        """Test _validate_payload_structure with valid payload."""
        client = self._create_test_client()
        # Should not raise any exception
        client._validate_payload_structure({"value": True}, "test_command")

    def test_validate_payload_structure_invalid(self):
        """Test _validate_payload_structure with invalid payload."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_payload_structure("invalid", "test_command")
        self.assertIn(
            "test_command payload must be a dictionary", str(context.exception)
        )

    def test_validate_numeric_value_valid(self):
        """Test _validate_numeric_value with valid values."""
        client = self._create_test_client()
        client._validate_numeric_value(5, "test_param")
        client._validate_numeric_value(5.5, "test_param")
        client._validate_numeric_value(-3, "test_param", allow_negative=True)

    def test_validate_numeric_value_invalid_type(self):
        """Test _validate_numeric_value with invalid type."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_numeric_value("invalid", "test_param")
        self.assertIn("test_param must be a number", str(context.exception))

    def test_validate_numeric_value_negative_not_allowed(self):
        """Test _validate_numeric_value with negative value when not allowed."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_numeric_value(-5, "test_param", allow_negative=False)
        self.assertIn("test_param must be non-negative", str(context.exception))

    def test_validate_boolean_value_valid(self):
        """Test _validate_boolean_value with valid values."""
        client = self._create_test_client()
        client._validate_boolean_value(True, "test_param")
        client._validate_boolean_value(False, "test_param")

    def test_validate_boolean_value_invalid(self):
        """Test _validate_boolean_value with invalid values."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_boolean_value("invalid", "test_param")
        self.assertIn("test_param must be a boolean", str(context.exception))

    def test_validate_calibration_points_valid(self):
        """Test _validate_calibration_points with valid data."""
        client = self._create_test_client()
        valid_points = [[1.0, 2.0], [3.0, 4.0]]
        client._validate_calibration_points(valid_points, "test_param")

    def test_validate_calibration_points_invalid_type(self):
        """Test _validate_calibration_points with invalid type."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_calibration_points("invalid", "test_param")
        self.assertIn("test_param must be a list", str(context.exception))

    def test_validate_calibration_points_invalid_point_format(self):
        """Test _validate_calibration_points with invalid point format."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_calibration_points([[1.0]], "test_param")
        self.assertIn(
            "test_param[0] must be a list of 2 numbers", str(context.exception)
        )

    def test_validate_calibration_points_invalid_coordinates(self):
        """Test _validate_calibration_points with invalid coordinates."""
        client = self._create_test_client()
        with self.assertRaises(ValueError) as context:
            client._validate_calibration_points([["a", "b"]], "test_param")
        self.assertIn(
            "test_param[0] coordinates must be numbers", str(context.exception)
        )

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_connect_to_broker_success(self, mock_mqtt_client, mock_qsource3_logic):
        """Test successful broker connection."""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        client = QSource3MQTTClient(self.config_file)
        client.connect_to_broker()

        mock_client_instance.connect.assert_called_once_with("localhost", 1883, 60)

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_connect_to_broker_exception(self, mock_mqtt_client, mock_qsource3_logic):
        """Test broker connection with exception."""
        mock_client_instance = Mock()
        mock_client_instance.connect.side_effect = Exception("Connection failed")
        mock_mqtt_client.return_value = mock_client_instance

        client = QSource3MQTTClient(self.config_file)
        client.connect_to_broker()

        # Should set disconnected status
        self.assertEqual(client.disconnected, (True, -1))

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_on_connect_success(self, mock_mqtt_client, mock_qsource3_logic):
        """Test successful MQTT on_connect callback."""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        client = QSource3MQTTClient(self.config_file)

        # Mock publish_connected method
        with patch.object(client, "publish_connected") as mock_publish:
            client.on_connect(mock_client_instance, None, None, 0)

            # Verify subscription and connection publication
            expected_topic = "test/qsource3/cmnd/TestDevice/#"
            mock_client_instance.subscribe.assert_called_once_with(expected_topic)
            mock_publish.assert_called_once_with(True)

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_on_connect_failure(self, mock_mqtt_client, mock_qsource3_logic):
        """Test MQTT on_connect callback with failure."""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        client = QSource3MQTTClient(self.config_file)

        with self.assertRaises(QSource3MQTTClientNotConnectedException):
            client.on_connect(mock_client_instance, None, None, 1)

        self.assertEqual(client.disconnected, (True, 1))

    @patch("qsource3_mqtt.qsource3_mqtt_client.QSource3Logic")
    @patch("paho.mqtt.client.Client")
    def test_on_disconnect(self, mock_mqtt_client, mock_qsource3_logic):
        """Test MQTT on_disconnect callback."""
        mock_client_instance = Mock()
        mock_mqtt_client.return_value = mock_client_instance

        client = QSource3MQTTClient(self.config_file)
        client.on_disconnect(mock_client_instance, None, None, 2)

        self.assertEqual(client.disconnected, (True, 2))

    def test_on_message_valid_json(self):
        """Test on_message with valid JSON payload."""
        client = self._create_test_client()

        # Mock message
        mock_msg = Mock()
        mock_msg.topic = "test/qsource3/cmnd/TestDevice/is_dc_on"
        mock_msg.payload = '{"value": true}'

        with patch.object(client, "handle_is_dc_on") as mock_handle:
            client.on_message(None, None, mock_msg)
            mock_handle.assert_called_once_with({"value": True})

    def test_on_message_invalid_json(self):
        """Test on_message with invalid JSON payload."""
        client = self._create_test_client()

        # Mock message with invalid JSON
        mock_msg = Mock()
        mock_msg.topic = "test/qsource3/cmnd/TestDevice/is_dc_on"
        mock_msg.payload = "invalid json"

        with patch.object(client, "handle_is_dc_on") as mock_handle:
            client.on_message(None, None, mock_msg)
            mock_handle.assert_not_called()

    def test_on_message_unknown_topic(self):
        """Test on_message with unknown topic."""
        client = self._create_test_client()

        # Mock message with unknown topic
        mock_msg = Mock()
        mock_msg.topic = "test/qsource3/cmnd/TestDevice/unknown_command"
        mock_msg.payload = '{"value": true}'

        # Should not raise exception, just log warning
        client.on_message(None, None, mock_msg)

    def test_handle_is_dc_on_getter(self):
        """Test handle_is_dc_on as getter."""
        client = self._create_test_client()

        # Mock qsource3 property
        client.qsource3.is_dc_on = True

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_is_dc_on({})
            mock_publish.assert_called_once_with("is_dc_on", True, {})

    def test_handle_is_dc_on_setter(self):
        """Test handle_is_dc_on as setter."""
        client = self._create_test_client()

        payload = {"value": False}

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_is_dc_on(payload)

            # Verify value was set
            self.assertEqual(client.qsource3.is_dc_on, False)
            mock_publish.assert_called_once_with("is_dc_on", False, payload)

    def test_handle_is_dc_on_invalid_payload(self):
        """Test handle_is_dc_on with invalid payload."""
        client = self._create_test_client()

        with self.assertRaises(ValueError):
            client.handle_is_dc_on("invalid")

    def test_handle_is_dc_on_invalid_value_type(self):
        """Test handle_is_dc_on with invalid value type."""
        client = self._create_test_client()

        with self.assertRaises(ValueError):
            client.handle_is_dc_on({"value": "not_boolean"})

    def test_handle_range_setter(self):
        """Test handle_range as setter."""
        client = self._create_test_client()

        payload = {"value": 2}

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_range(payload)

            # Verify set_range was called and get_range returns value
            client.qsource3.set_range.assert_called_once_with(2)
            mock_publish.assert_called_once_with(
                "range", 1, payload
            )  # get_range returns 1

    def test_handle_range_invalid_type(self):
        """Test handle_range with non-integer value."""
        client = self._create_test_client()

        with self.assertRaises(ValueError) as context:
            client.handle_range({"value": 2.5})
        self.assertIn("range value must be an integer", str(context.exception))

    def test_handle_mz_setter(self):
        """Test handle_mz as setter."""
        client = self._create_test_client()

        payload = {"value": 50.5}
        client.qsource3.mz = 50.5  # Mock the return value

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_mz(payload)

            # Verify mz was set
            self.assertEqual(client.qsource3.mz, 50.5)
            mock_publish.assert_called_once_with("mz", 50.5, payload)

    def test_handle_mz_negative_value(self):
        """Test handle_mz with negative value."""
        client = self._create_test_client()

        with self.assertRaises(ValueError) as context:
            client.handle_mz({"value": -10})
        self.assertIn("mz must be non-negative", str(context.exception))

    def test_handle_max_mz_readonly(self):
        """Test handle_max_mz as read-only property."""
        client = self._create_test_client()

        client.qsource3.max_mz = 1000.0
        payload = {"value": 500}  # Should be ignored

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_max_mz(payload)
            mock_publish.assert_called_once_with("max_mz", 1000.0, payload)

    def test_handle_calib_pnts_dc_setter(self):
        """Test handle_calib_pnts_dc as setter."""
        client = self._create_test_client()

        calibration_points = [[10, 0.1], [20, 0.2]]
        payload = {"value": calibration_points}
        client.qsource3.calib_pnts_dc = calibration_points

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_calib_pnts_dc(payload)

            # Verify calibration points were set
            self.assertEqual(client.qsource3.calib_pnts_dc, calibration_points)
            mock_publish.assert_called_once_with(
                "calib_pnts_dc", calibration_points, payload
            )

    def test_handle_dc_offst_setter(self):
        """Test handle_dc_offst as setter."""
        client = self._create_test_client()

        payload = {"value": -5.5}
        client.qsource3.dc_offst = -5.5

        with patch.object(client, "publish_response") as mock_publish:
            client.handle_dc_offst(payload)

            # Verify dc_offst was set
            self.assertEqual(client.qsource3.dc_offst, -5.5)
            mock_publish.assert_called_once_with("dc_offst", -5.5, payload)

    def test_publish_status_connected(self):
        """Test publish_status when client is connected."""
        client = self._create_test_client()

        # Mock client as connected
        client.client.is_connected.return_value = True

        # Mock status data
        status_data = {"range": 1, "mz": 50.0}
        client.qsource3.get_status.return_value = status_data

        client.publish_status()

        expected_topic = "test/qsource3/status/TestDevice/state"
        client.client.publish.assert_called_once_with(
            expected_topic, json.dumps(status_data)
        )

    def test_publish_status_not_connected(self):
        """Test publish_status when client is not connected."""
        client = self._create_test_client()

        # Mock client as not connected
        client.client.is_connected.return_value = False

        client.publish_status()

        # Should not call publish
        client.client.publish.assert_not_called()

    def test_publish_status_no_status_data(self):
        """Test publish_status when qsource3 returns None."""
        client = self._create_test_client()

        client.client.is_connected.return_value = True
        client.qsource3.get_status.return_value = None

        client.publish_status()

        # Should not call publish
        client.client.publish.assert_not_called()

    def test_publish_connected(self):
        """Test publish_connected method."""
        client = self._create_test_client()

        # Test connected = True
        client.publish_connected(True)
        expected_topic = "test/qsource3/status/TestDevice/broker_connected"
        client.client.publish.assert_called_with(
            expected_topic, '{"value": "ONLINE"}', retain=True
        )

        # Test connected = False
        client.publish_connected(False)
        client.client.publish.assert_called_with(
            expected_topic, '{"value": "OFFLINE"}', retain=True
        )

    def test_publish_qsource3_connected(self):
        """Test publish_qsource3_connected method."""
        client = self._create_test_client()

        # Test connected = True
        client.publish_qsource3_connected(True)
        expected_topic = "test/qsource3/status/TestDevice/qsource3_connected"
        client.client.publish.assert_called_with(
            expected_topic, '{"value": "True"}', retain=True
        )

    def test_on_qsource3_connected(self):
        """Test on_qsource3_connected callback."""
        client = self._create_test_client()

        with patch.object(client, "publish_qsource3_connected") as mock_publish:
            client.on_qsource3_connected()
            mock_publish.assert_called_once_with(True)

    def test_publish_response(self):
        """Test publish_response method."""
        client = self._create_test_client()

        # Mock client as connected
        client.client.is_connected.return_value = True

        command = "is_dc_on"
        value = True
        sender_payload = {"value": True}

        client.publish_response(command, value, sender_payload)

        expected_topic = "test/qsource3/response/TestDevice/is_dc_on"
        expected_payload = {"value": True, "sender_payload": {"value": True}}

        client.client.publish.assert_called_once_with(
            expected_topic, json.dumps(expected_payload)
        )

    def test_publish_error(self):
        """Test publish_error method."""
        client = self._create_test_client()

        # Mock client as connected
        client.client.is_connected.return_value = True

        client.publish_error("test_command", "Test error message")

        expected_topic = "test/qsource3/error/TestDevice/disconnected"
        expected_payload = {"error": "Test error message", "command": "test_command"}

        client.client.publish.assert_called_once_with(
            expected_topic, json.dumps(expected_payload)
        )

    def test_stop(self):
        """Test stop method."""
        client = self._create_test_client()

        self.assertFalse(client.user_stop_event.is_set())
        client.stop()
        self.assertTrue(client.user_stop_event.is_set())

    @patch("qsource3_mqtt.qsource3_mqtt_client.select")
    def test_do_select_normal_operation(self, mock_select):
        """Test do_select with normal operation."""
        client = self._create_test_client()

        # Mock socket operations
        mock_socket = Mock()
        client.client.socket.return_value = mock_socket
        client.client.want_write.return_value = False

        # Mock select to return socket ready for reading
        mock_select.return_value = ([mock_socket], [], [])

        # Mock time for status interval
        with patch("time.time", return_value=1000):
            client.last_time = 999  # Force status publish
            client.status_interval = 500  # 0.5 seconds
            client.client.is_connected.return_value = True

            with patch.object(client, "publish_status") as mock_publish_status:
                client.do_select()

                # Verify socket operations
                client.client.loop_read.assert_called_once()
                client.client.loop_misc.assert_called_once()
                mock_publish_status.assert_called_once()

    @patch("qsource3_mqtt.qsource3_mqtt_client.select")
    def test_do_select_socket_gone(self, mock_select):
        """Test do_select when socket is gone."""
        client = self._create_test_client()

        # Mock socket as None/False
        client.client.socket.return_value = None

        with self.assertRaises(Exception) as context:
            client.do_select()

        self.assertIn("Socket is gone", str(context.exception))

    def test_main_loop_with_stop_event(self):
        """Test main method loop with user stop event."""
        client = self._create_test_client()

        with patch.object(client, "connect_to_broker") as mock_connect, patch.object(
            client, "do_select"
        ) as mock_do_select:

            # Set user stop event
            client.user_stop_event.set()

            client.main()

            mock_connect.assert_called_once()
            # do_select should not be called due to stop event
            mock_do_select.assert_not_called()

    def _create_test_client(self):
        """Helper method to create a test client with mocked dependencies."""
        with patch(
            "qsource3_mqtt.qsource3_mqtt_client.QSource3Logic"
        ) as mock_qsource3_logic, patch("paho.mqtt.client.Client") as mock_mqtt_client:

            # Setup mocks
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance

            mock_logic_instance = Mock()
            mock_logic_instance.is_dc_on = True
            mock_logic_instance.is_rod_polarity_positive = True
            mock_logic_instance.max_mz = 1000.0
            mock_logic_instance.calib_pnts_dc = [[10, 0.1], [20, 0.2]]
            mock_logic_instance.calib_pnts_rf = [[30, 0.3], [40, 0.4]]
            mock_logic_instance.dc_offst = 5.0
            mock_logic_instance.mz = 50.0
            mock_logic_instance.get_range.return_value = 1
            mock_logic_instance.get_status.return_value = {"range": 1}
            mock_qsource3_logic.return_value = mock_logic_instance

            client = QSource3MQTTClient(self.config_file)
            return client


if __name__ == "__main__":
    unittest.main()
