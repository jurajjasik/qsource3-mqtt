import json
import logging
import time
from ctypes import Array
from functools import wraps

from pyvisa import VisaIOError
from qsource3.massfilter import Quadrupole
from qsource3.qsource3driver import QSource3Driver

logger = logging.getLogger(__name__)
# logger.setLevel(logging.DEBUG)


class QSource3NotConnectedException(Exception):
    """Exception raised when the QSource3 peripheral is not connected."""

    pass


def check_connection_decorator(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self.check_connection()
        try:
            return method(self, *args, **kwargs)
        except (VisaIOError, ConnectionError) as e:
            logger.error(f"Connection lost during {method.__name__}: {e}")
            self._is_connected = False
            self.driver = None
            self.quads = [None] * self.number_of_ranges  # Reset all ranges properly
            raise QSource3NotConnectedException(
                f"QSource3 peripheral is not connected. Error: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error in {method.__name__}: {e}")
            raise

    return wrapper


class QSource3Logic:
    def __init__(self, comport, r0, on_connected, number_of_ranges, settings_file):
        self.settings_file = settings_file
        self.number_of_ranges = number_of_ranges
        self.on_connected = on_connected
        self.r0 = r0
        self.comport = comport
        self.driver = None
        self.quads: list[Quadrupole] = []
        self.current_range = 0

        self._is_connected = False

    def check_connection(self):
        if not self.is_connected():
            self.try_connect()

    def _delay(self):
        time.sleep(0.1)

    def _default_calibration_points(self):
        return [[[0, 0]] for _ in range(self.number_of_ranges)]

    def _default_zeros_list(self):
        return [0 for _ in range(self.number_of_ranges)]

    def _default_booleans_list(self):
        return [True for _ in range(self.number_of_ranges)]

    def try_connect(self):
        try:
            self.driver = QSource3Driver(self.comport)
            for idx in range(self.number_of_ranges):
                self._delay()
                self.driver.set_range(idx)
                self._delay()
                freq = self.driver.frequency
                self.quads.append(
                    Quadrupole(
                        frequency=freq,
                        r0=self.r0,
                        driver=self.driver,
                        name=f"Q{idx}",
                    )
                )
                self.quads[idx].mz = 0
            self._delay()

            self.settings = {
                "range": 0,
                "calib_pnts_dc": self._default_calibration_points(),
                "calib_pnts_rf": self._default_calibration_points(),
                "dc_offst": self._default_zeros_list(),
                "is_dc_on": self._default_booleans_list(),
                "is_rod_polarity_positive": self._default_booleans_list(),
            }

            settings = self.load_settings()
            if settings is None:
                self.driver.set_range(self.current_range)

            else:
                # Validate and ensure all required keys exist
                if not isinstance(settings, dict):
                    logger.warning(
                        "Loaded settings is not a dictionary. Using defaults."
                    )
                    settings = {}

                # Extract settings with defaults for missing keys
                calib_pnts_dc = settings.get("calib_pnts_dc", [])
                calib_pnts_rf = settings.get("calib_pnts_rf", [])
                dc_offst = settings.get("dc_offst", [])
                is_dc_on = settings.get("is_dc_on", [])
                is_rod_polarity_positive = settings.get("is_rod_polarity_positive", [])

                # Ensure they are lists
                if not isinstance(calib_pnts_dc, list):
                    calib_pnts_dc = []
                if not isinstance(calib_pnts_rf, list):
                    calib_pnts_rf = []
                if not isinstance(dc_offst, list):
                    dc_offst = []
                if not isinstance(is_dc_on, list):
                    is_dc_on = []
                if not isinstance(is_rod_polarity_positive, list):
                    is_rod_polarity_positive = []

                for idx in range(self.number_of_ranges):
                    # Get calibration points DC with safe indexing
                    if idx < len(calib_pnts_dc):
                        calib_dc_value = calib_pnts_dc[idx]
                    else:
                        calib_dc_value = [[0, 0]]

                    self.quads[idx].calib_pnts_dc = self.check_calibration_points(
                        calib_dc_value
                    )
                    # Store as list - call tolist() if it's a numpy array, otherwise use as-is
                    if hasattr(self.quads[idx].calib_pnts_dc, "tolist"):
                        self.settings["calib_pnts_dc"][idx] = self.quads[
                            idx
                        ].calib_pnts_dc.tolist()
                    else:
                        self.settings["calib_pnts_dc"][idx] = self.quads[
                            idx
                        ].calib_pnts_dc
                    logger.debug(
                        f"Calibration points DC for range {idx}: {self.quads[idx].calib_pnts_dc}"
                    )
                    self._delay()

                    # Get calibration points RF with safe indexing
                    if idx < len(calib_pnts_rf):
                        calib_rf_value = calib_pnts_rf[idx]
                    else:
                        calib_rf_value = [[0, 0]]

                    self.quads[idx].calib_pnts_rf = self.check_calibration_points(
                        calib_rf_value
                    )
                    # Store as list - call tolist() if it's a numpy array, otherwise use as-is
                    if hasattr(self.quads[idx].calib_pnts_rf, "tolist"):
                        self.settings["calib_pnts_rf"][idx] = self.quads[
                            idx
                        ].calib_pnts_rf.tolist()
                    else:
                        self.settings["calib_pnts_rf"][idx] = self.quads[
                            idx
                        ].calib_pnts_rf
                    logger.debug(
                        f"Calibration points RF for range {idx}: {self.quads[idx].calib_pnts_rf}"
                    )
                    self._delay()

                    # Get DC offset with safe indexing
                    if idx < len(dc_offst):
                        dc_offst_value = dc_offst[idx]
                    else:
                        dc_offst_value = 0

                    self.quads[idx].dc_offst = self.check_number(dc_offst_value)
                    self.settings["dc_offst"][idx] = self.quads[idx].dc_offst
                    logger.debug(
                        f"DC offset for range {idx}: {self.quads[idx].dc_offst}"
                    )
                    self._delay()

                    # Get is_dc_on with safe indexing
                    if idx < len(is_dc_on):
                        is_dc_on_value = is_dc_on[idx]
                    else:
                        is_dc_on_value = True

                    self.quads[idx].is_dc_on = self.check_boolean(is_dc_on_value)
                    self.settings["is_dc_on"][idx] = self.quads[idx].is_dc_on
                    logger.debug(
                        f"Is DC on for range {idx}: {self.quads[idx].is_dc_on}"
                    )
                    self._delay()

                    # Get is_rod_polarity_positive with safe indexing
                    if idx < len(is_rod_polarity_positive):
                        is_rod_polarity_positive_value = is_rod_polarity_positive[idx]
                    else:
                        is_rod_polarity_positive_value = True

                    self.quads[idx].is_rod_polarity_positive = self.check_boolean(
                        is_rod_polarity_positive_value
                    )
                    self.settings["is_rod_polarity_positive"][idx] = self.quads[
                        idx
                    ].is_rod_polarity_positive
                    logger.debug(
                        f"Is rod polarity positive for range {idx}: {self.quads[idx].is_rod_polarity_positive}"
                    )
                    self._delay()

                # Set the current range
                self.current_range = self.check_mass_range(settings.get("range", 0))
                self.driver.set_range(self.current_range)
                self.settings["range"] = self.current_range
                logger.debug(f"Current range: {self.current_range}")
                self._delay()

            self._is_connected = True
            if self.on_connected is not None:
                self.on_connected()

        except VisaIOError:
            self._is_connected = False
            raise QSource3NotConnectedException("QSource3 peripheral is not connected.")

    def is_connected(self):
        return self._is_connected

    @property
    @check_connection_decorator
    def is_dc_on(self) -> bool:
        if (
            self.current_range >= len(self.quads)
            or self.quads[self.current_range] is None
        ):
            raise QSource3NotConnectedException(
                "Invalid range or quadrupole not initialized"
            )
        return self.quads[self.current_range].is_dc_on

    @is_dc_on.setter
    @check_connection_decorator
    def is_dc_on(self, value):
        self.quads[self.current_range].is_dc_on = value
        self.settings["is_dc_on"][self.current_range] = value
        self.save_settings()

    @property
    @check_connection_decorator
    def is_rod_polarity_positive(self) -> bool:
        return self.quads[self.current_range].is_rod_polarity_positive

    @is_rod_polarity_positive.setter
    @check_connection_decorator
    def is_rod_polarity_positive(self, value):
        self.quads[self.current_range].is_rod_polarity_positive = value
        self.settings["is_rod_polarity_positive"][self.current_range] = value
        self.save_settings()

    @property
    @check_connection_decorator
    def max_mz(self) -> float:
        return self.quads[self.current_range].max_mz

    @property
    @check_connection_decorator
    def calib_pnts_dc(self) -> Array:
        return self.quads[self.current_range].calib_pnts_dc.tolist()

    @calib_pnts_dc.setter
    @check_connection_decorator
    def calib_pnts_dc(self, value: Array):
        logger.debug(f"Setting calib_pnts_dc: {value}")
        self.quads[self.current_range].calib_pnts_dc = value
        self.mz = self.quads[self.current_range].mz  # set mz to the last value
        self.settings["calib_pnts_dc"][self.current_range] = value
        self.save_settings()

    @property
    @check_connection_decorator
    def calib_pnts_rf(self) -> Array:
        return self.quads[self.current_range].calib_pnts_rf.tolist()

    @calib_pnts_rf.setter
    @check_connection_decorator
    def calib_pnts_rf(self, value: Array):
        logger.debug(f"Setting calib_pnts_rf: {value}")
        self.quads[self.current_range].calib_pnts_rf = value
        self.mz = self.quads[self.current_range].mz  # set mz to the last value
        self.settings["calib_pnts_rf"][self.current_range] = value
        self.save_settings()

    @property
    @check_connection_decorator
    def dc_offst(self) -> float:
        return self.quads[self.current_range].dc_offst

    @dc_offst.setter
    @check_connection_decorator
    def dc_offst(self, value: float):
        self.quads[self.current_range].dc_offst = value
        self.settings["dc_offst"][self.current_range] = value
        self.save_settings()

    @check_connection_decorator
    def set_range(self, value: int):
        if value < 0 or value >= self.number_of_ranges:
            logger.error(f"Invalid range value: {value}")
            return

        if self.driver is not None:
            self.driver.set_range(value)
            self.current_range = value

            self.mz = self.quads[self.current_range].mz  # set mz to the last value

            self.settings["range"] = value
            self.save_settings()

    @check_connection_decorator
    def get_range(self) -> int:
        return self.current_range

    @property
    @check_connection_decorator
    def mz(self) -> float:
        return self.quads[self.current_range].mz

    @mz.setter
    @check_connection_decorator
    def mz(self, value: float):
        self.quads[self.current_range].mz = value
        # mz element is not in settings => not saved

    @check_connection_decorator
    def get_status(self):
        if self.driver is None:
            return None
        return {
            "range": self.current_range,
            "frequency": self.driver.frequency,
            "rf_amp": self.quads[self.current_range].rf,
            "dc1": self.quads[self.current_range].dc1,
            "dc2": self.quads[self.current_range].dc2,
            "current": self.driver.current,
            "mz": self.quads[self.current_range].mz,
            "is_dc_on": self.quads[self.current_range].is_dc_on,
            "is_rod_polarity_positive": self.quads[
                self.current_range
            ].is_rod_polarity_positive,
            "max_mz": self.quads[self.current_range].max_mz,
        }

    def load_settings(self):
        # return None if settings file does not exist
        try:
            with open(self.settings_file, "r") as f:
                logger.info(f"Loading settings from {self.settings_file}")
                return json.load(f)
        except FileNotFoundError:
            logger.info(
                f"Settings file {self.settings_file} not found. Using default settings."
            )
            return None
        except Exception as e:
            logger.error(f"Failed to load settings from {self.settings_file}: {e}")
            logger.info("Using default settings.")
            return None

    def save_settings(self):
        try:
            with open(self.settings_file, "w") as f:
                json.dump(self.settings, f, indent=4)
            logger.debug(f"Settings saved to {self.settings_file}")
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to save settings to {self.settings_file}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving settings: {e}")
            raise

    def check_mass_range(self, value):
        if value < 0 or value >= self.number_of_ranges:
            logger.error(f"Invalid range value: {value}")
            return 0
        return value

    def check_calibration_points(self, value: list | None = None):
        # check if value is a list of number pairs in the format [[x1, y1], [x2, y2], ...]
        if value is None:
            return self._default_calibration_points()

        if not isinstance(value, list):
            return self._default_calibration_points()

        for pair in value:
            if not isinstance(pair, list) or len(pair) != 2:
                return self._default_calibration_points()
            for number in pair:
                if not isinstance(number, (int, float)):
                    return self._default_calibration_points()

        return value

    def check_number(self, value):
        if not isinstance(value, (int, float)):
            return 0
        return value

    def check_boolean(self, value):
        if not isinstance(value, bool):
            return True
        return value
