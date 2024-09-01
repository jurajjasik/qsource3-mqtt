import json
import logging
import time
from ctypes import Array
from functools import wraps

from pyvisa import VisaIOError
from qsource3.massfilter import Quadrupole
from qsource3.qsource3driver import QSource3Driver

logger = logging.getLogger(__name__)


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
            self._is_connected = False
            self.driver = None
            self.quads = [None, None]
            raise QSource3NotConnectedException(
                f"QSource3 peripheral is not connected. Error: {e}"
            )

    return wrapper


class QSource3Logic:
    def __init__(self, comport, r0, on_connected, number_of_ranges, settings_file):
        self.settings_file = settings_file
        self.number_of_ranges = number_of_ranges
        self.on_connected = on_connected
        self.r0 = r0
        self.comport = comport
        self.driver = None
        self.quads = [None, None]
        self.current_range = 0

        self._is_connected = False

    def check_connection(self):
        if not self.is_connected():
            self.try_connect()

    def _delay(self):
        time.sleep(0.1)

    def try_connect(self):
        try:
            self.driver = QSource3Driver(self.comport)
            for idx in range(self.number_of_ranges):
                self._delay()
                self.driver.set_range(idx)
                self._delay()
                freq = self.driver.frequency
                self.quads[idx] = Quadrupole(
                    frequency=freq,
                    r0=self.r0,
                    driver=self.driver,
                    name=f"Q{idx}",
                )
                self.quads[idx].mz = 0
            self._delay()

            self.settings = {
                "range": 0,
                "calib_pnts_dc": [[[0, 0]], [[0, 0]]],
                "calib_pnts_rf": [[[0, 0]], [[0, 0]]],
                "dc_offst": [0, 0],
                "is_dc_on": [True, True],
                "is_rod_polarity_positive": [True, True],
            }

            settings = self.load_settings()
            if settings is None:
                self.driver.set_range(self.current_range)

            else:
                for idx in range(self.number_of_ranges):
                    self.quads[idx].calib_pnts_dc = self.check_calibration_points(
                        settings["calib_pnts_dc"][idx]
                    )
                    self.settings["calib_pnts_dc"][idx] = self.quads[
                        idx
                    ].calib_pnts_dc.tolist()
                    logger.debug(
                        f"Calibration points DC: {self.quads[idx].calib_pnts_dc}"
                    )
                    self._delay()

                    self.quads[idx].calib_pnts_rf = self.check_calibration_points(
                        settings["calib_pnts_rf"][idx]
                    )
                    self.settings["calib_pnts_rf"][idx] = self.quads[
                        idx
                    ].calib_pnts_rf.tolist()
                    logger.debug(
                        f"Calibration points RF: {self.quads[idx].calib_pnts_rf}"
                    )
                    self._delay()

                    self.quads[idx].dc_offst = self.check_number(
                        settings["dc_offst"][idx]
                    )
                    self.settings["dc_offst"][idx] = self.quads[idx].dc_offst
                    logger.debug(f"DC offset: {self.quads[idx].dc_offst}")
                    self._delay()

                    self.quads[idx].is_dc_on = self.check_boolean(
                        settings["is_dc_on"][idx]
                    )
                    self.settings["is_dc_on"][idx] = self.quads[idx].is_dc_on
                    logger.debug(f"Is DC on: {self.quads[idx].is_dc_on}")
                    self._delay()

                    self.quads[idx].is_rod_polarity_positive = self.check_boolean(
                        settings["is_rod_polarity_positive"][idx]
                    )
                    self.settings["is_rod_polarity_positive"][idx] = self.quads[
                        idx
                    ].is_rod_polarity_positive
                    logger.debug(
                        f"Is rod polarity positive: {self.quads[idx].is_rod_polarity_positive}"
                    )
                    self._delay()

                self.current_range = self.check_mass_range(settings["range"])
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
        self.quads[self.current_range].calib_pnts_dc = value
        self.settings["calib_pnts_dc"][self.current_range] = value
        self.save_settings()

    @property
    @check_connection_decorator
    def calib_pnts_rf(self) -> Array:
        return self.quads[self.current_range].calib_pnts_rf.tolist()

    @calib_pnts_rf.setter
    @check_connection_decorator
    def calib_pnts_rf(self, value: Array):
        self.quads[self.current_range].calib_pnts_rf = value
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
            self.settings["range"] = value
            self.save_settings()

    @check_connection_decorator
    def get_range(self) -> int:
        return self.current_range

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
            logger.info(f"Settings file {self.settings_file} not found")
            return None

    def save_settings(self):
        with open(self.settings_file, "w") as f:
            json.dump(self.settings, f, indent=4)

    def check_mass_range(self, value):
        if value < 0 or value >= self.number_of_ranges:
            logger.error(f"Invalid range value: {value}")
            return 0
        return value

    def check_calibration_points(self, value):
        # check if value is a list of number pairs in the format [[x1, y1], [x2, y2], ...]
        if not isinstance(value, list):
            return [[[0, 0]], [[0, 0]]]

        for pair in value:
            if not isinstance(pair, list) or len(pair) != 2:
                return [[[0, 0]], [[0, 0]]]
            for number in pair:
                if not isinstance(number, (int, float)):
                    return [[[0, 0]], [[0, 0]]]

        return value

    def check_number(self, value):
        if not isinstance(value, (int, float)):
            return 0
        return value

    def check_boolean(self, value):
        if not isinstance(value, bool):
            return True
        return value
