"""
Unit tests for QSource3Logic class.
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, mock_open, patch

from pyvisa import VisaIOError

from qsource3_mqtt.qsource3_logic import (QSource3Logic,
                                          QSource3NotConnectedException)


class TestQSource3Logic(unittest.TestCase):
    """Test cases for QSource3Logic class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.comport = "ASRL/dev/ttyUSB0::INSTR"
        self.r0 = 4e-3
        self.on_connected = Mock()
        self.number_of_ranges = 3
        self.temp_settings_file = tempfile.NamedTemporaryFile(delete=False)
        self.settings_file = self.temp_settings_file.name
        self.temp_settings_file.close()

        # Create QSource3Logic instance
        self.logic = QSource3Logic(
            comport=self.comport,
            r0=self.r0,
            on_connected=self.on_connected,
            number_of_ranges=self.number_of_ranges,
            settings_file=self.settings_file,
        )

    def tearDown(self):
        """Clean up after each test."""
        if os.path.exists(self.settings_file):
            os.unlink(self.settings_file)

    def test_init(self):
        """Test QSource3Logic initialization."""
        self.assertEqual(self.logic.comport, self.comport)
        self.assertEqual(self.logic.r0, self.r0)
        self.assertEqual(self.logic.on_connected, self.on_connected)
        self.assertEqual(self.logic.number_of_ranges, self.number_of_ranges)
        self.assertEqual(self.logic.settings_file, self.settings_file)
        self.assertIsNone(self.logic.driver)
        self.assertEqual(self.logic.quads, [])
        self.assertEqual(self.logic.current_range, 0)
        self.assertFalse(self.logic._is_connected)

    def test_is_connected(self):
        """Test is_connected method."""
        # Initially not connected
        self.assertFalse(self.logic.is_connected())

        # Set connected
        self.logic._is_connected = True
        self.assertTrue(self.logic.is_connected())

    @patch("qsource3_mqtt.qsource3_logic.QSource3Driver")
    @patch("qsource3_mqtt.qsource3_logic.Quadrupole")
    def test_try_connect_success_no_settings(self, mock_quadrupole, mock_driver):
        """Test successful connection without existing settings file."""
        # Setup mocks
        mock_driver_instance = Mock()
        mock_driver_instance.frequency = 1000000.0
        mock_driver.return_value = mock_driver_instance

        mock_quad_instances = []
        for i in range(self.number_of_ranges):
            mock_quad = Mock()
            mock_quad.mz = 0
            mock_quad.calib_pnts_dc.tolist.return_value = [[0, 0]]
            mock_quad.calib_pnts_rf.tolist.return_value = [[0, 0]]
            mock_quad.dc_offst = 0
            mock_quad.is_dc_on = True
            mock_quad.is_rod_polarity_positive = True
            mock_quad_instances.append(mock_quad)

        mock_quadrupole.side_effect = mock_quad_instances

        # Test connection
        self.logic.try_connect()

        # Verify driver setup
        mock_driver.assert_called_once_with(self.comport)
        self.assertEqual(self.logic.driver, mock_driver_instance)

        # Verify quadrupoles setup
        self.assertEqual(len(self.logic.quads), self.number_of_ranges)
        self.assertEqual(mock_driver_instance.set_range.call_count, self.number_of_ranges + 1)

        # Verify connection status
        self.assertTrue(self.logic.is_connected())
        self.on_connected.assert_called_once()

        # Verify default settings
        expected_settings = {
            "range": 0,
            "calib_pnts_dc": [[[0, 0]] for _ in range(self.number_of_ranges)],
            "calib_pnts_rf": [[[0, 0]] for _ in range(self.number_of_ranges)],
            "dc_offst": [0 for _ in range(self.number_of_ranges)],
            "is_dc_on": [True for _ in range(self.number_of_ranges)],
            "is_rod_polarity_positive": [True for _ in range(self.number_of_ranges)],
        }
        self.assertEqual(self.logic.settings, expected_settings)

    @patch("qsource3_mqtt.qsource3_logic.QSource3Driver")
    @patch("qsource3_mqtt.qsource3_logic.Quadrupole")
    def test_try_connect_with_existing_settings(self, mock_quadrupole, mock_driver):
        """Test connection with existing settings file."""
        # Create settings file
        test_settings = {
            "range": 1,
            "calib_pnts_dc": [[[10, 0.1], [20, 0.2]], [[15, 0.15]], [[25, 0.25]]],
            "calib_pnts_rf": [[[30, 0.3]], [[35, 0.35]], [[40, 0.4]]],
            "dc_offst": [1.5, 2.0, 2.5],
            "is_dc_on": [False, True, False],
            "is_rod_polarity_positive": [False, True, False],
        }

        with open(self.settings_file, "w") as f:
            json.dump(test_settings, f)

        # Setup mocks
        mock_driver_instance = Mock()
        mock_driver_instance.frequency = 1000000.0
        mock_driver.return_value = mock_driver_instance

        mock_quad_instances = []
        for i in range(self.number_of_ranges):
            mock_quad = Mock()
            mock_quad.mz = 0
            mock_quad.calib_pnts_dc.tolist.return_value = test_settings["calib_pnts_dc"][i]
            mock_quad.calib_pnts_rf.tolist.return_value = test_settings["calib_pnts_rf"][i]
            mock_quad_instances.append(mock_quad)

        mock_quadrupole.side_effect = mock_quad_instances

        # Test connection
        self.logic.try_connect()

        # Verify settings were applied
        self.assertEqual(self.logic.current_range, 1)
        self.assertTrue(self.logic.is_connected())

    @patch("qsource3_mqtt.qsource3_logic.QSource3Driver")
    def test_try_connect_visa_error(self, mock_driver):
        """Test connection failure due to VisaIOError."""
        mock_driver.side_effect = VisaIOError(-1)

        with self.assertRaises(QSource3NotConnectedException):
            self.logic.try_connect()

        self.assertFalse(self.logic.is_connected())
        self.on_connected.assert_not_called()

    def test_check_connection_not_connected(self):
        """Test check_connection when not connected."""
        with patch.object(self.logic, "try_connect") as mock_try_connect:
            self.logic.check_connection()
            mock_try_connect.assert_called_once()

    def test_check_connection_already_connected(self):
        """Test check_connection when already connected."""
        self.logic._is_connected = True
        with patch.object(self.logic, "try_connect") as mock_try_connect:
            self.logic.check_connection()
            mock_try_connect.assert_not_called()

    def test_load_settings_file_not_found(self):
        """Test loading settings when file doesn't exist."""
        # Remove the temp file
        os.unlink(self.settings_file)

        result = self.logic.load_settings()
        self.assertIsNone(result)

    def test_load_settings_success(self):
        """Test successful settings loading."""
        test_settings = {"range": 1, "test": "value"}
        with open(self.settings_file, "w") as f:
            json.dump(test_settings, f)

        result = self.logic.load_settings()
        self.assertEqual(result, test_settings)

    def test_save_settings_success(self):
        """Test successful settings saving."""
        self.logic.settings = {"range": 2, "test": "save"}
        self.logic.save_settings()

        with open(self.settings_file, "r") as f:
            saved_settings = json.load(f)

        self.assertEqual(saved_settings, self.logic.settings)

    def test_save_settings_permission_error(self):
        """Test save_settings with permission error."""
        # Use invalid path to trigger permission error
        self.logic.settings_file = "/root/invalid_path/settings.json"
        self.logic.settings = {"test": "value"}

        with self.assertRaises(Exception):
            self.logic.save_settings()

    def test_check_mass_range_valid(self):
        """Test check_mass_range with valid values."""
        self.assertEqual(self.logic.check_mass_range(0), 0)
        self.assertEqual(self.logic.check_mass_range(2), 2)

    def test_check_mass_range_invalid(self):
        """Test check_mass_range with invalid values."""
        self.assertEqual(self.logic.check_mass_range(-1), 0)
        self.assertEqual(self.logic.check_mass_range(5), 0)

    def test_check_calibration_points_valid(self):
        """Test check_calibration_points with valid data."""
        valid_points = [[1.0, 2.0], [3.0, 4.0]]
        result = self.logic.check_calibration_points(valid_points)
        self.assertEqual(result, valid_points)

    def test_check_calibration_points_invalid(self):
        """Test check_calibration_points with invalid data."""
        # Test with non-list
        result = self.logic.check_calibration_points(None)
        self.assertEqual(result, [[[0, 0]] for _ in range(self.number_of_ranges)])

        # Test with invalid pair format
        result = self.logic.check_calibration_points([[1.0]])
        self.assertEqual(result, [[[0, 0]] for _ in range(self.number_of_ranges)])
        # Test with non-numeric values
        result = self.logic.check_calibration_points([["a", "b"]])
        self.assertEqual(result, [[[0, 0]] for _ in range(self.number_of_ranges)])

    def test_check_number_valid(self):
        """Test check_number with valid values."""
        self.assertEqual(self.logic.check_number(5), 5)
        self.assertEqual(self.logic.check_number(5.5), 5.5)
        self.assertEqual(self.logic.check_number(-3), -3)

    def test_check_number_invalid(self):
        """Test check_number with invalid values."""
        self.assertEqual(self.logic.check_number("invalid"), 0)
        self.assertEqual(self.logic.check_number(None), 0)

    def test_check_boolean_valid(self):
        """Test check_boolean with valid values."""
        self.assertTrue(self.logic.check_boolean(True))
        self.assertFalse(self.logic.check_boolean(False))

    def test_check_boolean_invalid(self):
        """Test check_boolean with invalid values."""
        self.assertTrue(self.logic.check_boolean("invalid"))
        self.assertTrue(self.logic.check_boolean(1))
        self.assertTrue(self.logic.check_boolean(None))

    def setup_connected_logic(self):
        """Helper method to setup a connected logic instance."""
        self.logic._is_connected = True
        self.logic.driver = Mock()
        
        # Create mock quadrupoles
        mock_quads = []
        for i in range(self.number_of_ranges):
            mock_quad = Mock()
            mock_quad.mz = 50.0
            mock_quad.is_dc_on = True
            mock_quad.is_rod_polarity_positive = True
            mock_quad.max_mz = 1000.0
            mock_quad.calib_pnts_dc.tolist.return_value = [[10, 0.1], [20, 0.2]]
            mock_quad.calib_pnts_rf.tolist.return_value = [[30, 0.3], [40, 0.4]]
            mock_quad.dc_offst = 5.0
            mock_quad.rf = 100.0
            mock_quad.dc1 = 10.0
            mock_quad.dc2 = -10.0
            mock_quads.append(mock_quad)
        
        self.logic.quads = mock_quads
        self.logic.driver.frequency = 1000000.0
        self.logic.driver.current = 150.0
        self.logic.settings = {
            "range": 0,
            "calib_pnts_dc": [[[10, 0.1], [20, 0.2]] for _ in range(self.number_of_ranges)],
            "calib_pnts_rf": [[[30, 0.3], [40, 0.4]] for _ in range(self.number_of_ranges)],
            "dc_offst": [5.0 for _ in range(self.number_of_ranges)],
            "is_dc_on": [True for _ in range(self.number_of_ranges)],
            "is_rod_polarity_positive": [True for _ in range(self.number_of_ranges)],
        }

    def test_is_dc_on_property_getter(self):
        """Test is_dc_on property getter."""
        self.setup_connected_logic()
        result = self.logic.is_dc_on
        self.assertTrue(result)

    def test_is_dc_on_property_setter(self):
        """Test is_dc_on property setter."""
        self.setup_connected_logic()
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.is_dc_on = False
            self.logic.quads[0].is_dc_on = False
            self.assertEqual(self.logic.settings["is_dc_on"][0], False)
            mock_save.assert_called_once()

    def test_is_dc_on_not_connected(self):
        """Test is_dc_on when not connected."""
        with self.assertRaises(QSource3NotConnectedException):
            _ = self.logic.is_dc_on

    def test_is_rod_polarity_positive_property(self):
        """Test is_rod_polarity_positive property."""
        self.setup_connected_logic()
        result = self.logic.is_rod_polarity_positive
        self.assertTrue(result)

        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.is_rod_polarity_positive = False
            mock_save.assert_called_once()

    def test_max_mz_property(self):
        """Test max_mz property getter."""
        self.setup_connected_logic()
        result = self.logic.max_mz
        self.assertEqual(result, 1000.0)

    def test_calib_pnts_dc_property(self):
        """Test calib_pnts_dc property."""
        self.setup_connected_logic()
        result = self.logic.calib_pnts_dc
        self.assertEqual(result, [[10, 0.1], [20, 0.2]])

        # Test setter
        new_points = [[15, 0.15], [25, 0.25]]
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.calib_pnts_dc = new_points
            mock_save.assert_called_once()
            self.assertEqual(self.logic.settings["calib_pnts_dc"][0], new_points)

    def test_calib_pnts_rf_property(self):
        """Test calib_pnts_rf property."""
        self.setup_connected_logic()
        result = self.logic.calib_pnts_rf
        self.assertEqual(result, [[30, 0.3], [40, 0.4]])

        # Test setter
        new_points = [[35, 0.35], [45, 0.45]]
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.calib_pnts_rf = new_points
            mock_save.assert_called_once()
            self.assertEqual(self.logic.settings["calib_pnts_rf"][0], new_points)

    def test_dc_offst_property(self):
        """Test dc_offst property."""
        self.setup_connected_logic()
        result = self.logic.dc_offst
        self.assertEqual(result, 5.0)

        # Test setter
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.dc_offst = 7.5
            mock_save.assert_called_once()
            self.assertEqual(self.logic.settings["dc_offst"][0], 7.5)

    def test_set_range_valid(self):
        """Test set_range with valid range."""
        self.setup_connected_logic()
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.set_range(1)
            self.logic.driver.set_range.assert_called_with(1)
            self.assertEqual(self.logic.current_range, 1)
            self.assertEqual(self.logic.settings["range"], 1)
            mock_save.assert_called_once()

    def test_set_range_invalid(self):
        """Test set_range with invalid range."""
        self.setup_connected_logic()
        with patch.object(self.logic, "save_settings") as mock_save:
            self.logic.set_range(-1)
            self.logic.driver.set_range.assert_not_called()
            mock_save.assert_not_called()

            self.logic.set_range(5)
            self.logic.driver.set_range.assert_not_called()
            mock_save.assert_not_called()

    def test_get_range(self):
        """Test get_range method."""
        self.setup_connected_logic()
        self.logic.current_range = 2
        result = self.logic.get_range()
        self.assertEqual(result, 2)

    def test_mz_property(self):
        """Test mz property."""
        self.setup_connected_logic()
        result = self.logic.mz
        self.assertEqual(result, 50.0)

        # Test setter
        self.logic.mz = 75.0
        self.logic.quads[0].mz = 75.0

    def test_get_status(self):
        """Test get_status method."""
        self.setup_connected_logic()
        result = self.logic.get_status()

        expected_status = {
            "range": 0,
            "frequency": 1000000.0,
            "rf_amp": 100.0,
            "dc1": 10.0,
            "dc2": -10.0,
            "current": 150.0,
            "mz": 50.0,
            "is_dc_on": True,
            "is_rod_polarity_positive": True,
            "max_mz": 1000.0,
        }
        self.assertEqual(result, expected_status)

    def test_get_status_no_driver(self):
        """Test get_status when driver is None."""
        result = self.logic.get_status()
        self.assertIsNone(result)

    @patch("qsource3_mqtt.qsource3_logic.QSource3Driver")
    def test_connection_error_handling(self, mock_driver):
        """Test connection error handling in decorated methods."""
        self.setup_connected_logic()
        
        # Simulate connection loss
        self.logic.quads[0].mz = Mock(side_effect=VisaIOError(-1))
        
        with self.assertRaises(QSource3NotConnectedException):
            _ = self.logic.mz
        
        # Verify connection status reset
        self.assertFalse(self.logic._is_connected)
        self.assertIsNone(self.logic.driver)
        self.assertEqual(self.logic.quads, [None] * self.number_of_ranges)


if __name__ == "__main__":
    unittest.main()