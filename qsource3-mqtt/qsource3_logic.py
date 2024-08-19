from ctypes import Array
from functools import wraps

from pyvisa import VisaIOError
from qsource3.massfilter import Quadrupole  # type: ignore
from qsource3.qsource3driver import QSource3Driver  # type: ignore


class QSource3NotConnectedException(Exception):
    """Exception raised when the QSource3 peripheral is not connected."""

    pass


def check_connection_decorator(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        self.check_connection()
        try:
            return method(self, *args, **kwargs)
        except VisaIOError:
            self.is_connected = False
            raise QSource3NotConnectedException("QSource3 peripheral is not connected.")

    return wrapper


class QSource3Logic:
    def __init__(self, comport, r0):
        self.r0 = r0
        self.comport = comport
        self.driver = None
        self.quads = [None, None, None]
        self.current_range = 0

        self._is_connected = False

    def check_connection(self):
        if not self.is_connected():
            self.try_connect()

    def _delay(self):
        # TODO
        pass

    def try_connect(self):
        try:
            self.driver = QSource3Driver(self.comport)
            for idx in range(3):
                self._delay()
                self.driver.set_range(0)
                freq = self.driver.frequency
                self.quads[idx] = Quadrupole(
                    frequency=freq,
                    r0=self.r0,
                    driver=self.driver,
                    name=f"Q{idx}",
                )
            self.driver.set_range(self.current_range)
            self._is_connected = True
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

    @property
    @check_connection_decorator
    def is_rod_polarity_positive(self) -> bool:
        return self.quads[self.current_range].is_rod_polarity_positive

    @is_rod_polarity_positive.setter
    @check_connection_decorator
    def is_rod_polarity_positive(self, value):
        self.quads[self.current_range].is_rod_polarity_positive = value

    @property
    @check_connection_decorator
    def max_mz(self) -> float:
        return self.quads[self.current_range].max_mz

    @property
    @check_connection_decorator
    def calib_pnts_dc(self) -> Array:
        return self.quads[self.current_range].calib_pnts_dc

    @calib_pnts_dc.setter
    @check_connection_decorator
    def calib_pnts_dc(self, value: Array):
        self.quads[self.current_range].calib_pnts_dc = value

    @property
    @check_connection_decorator
    def calib_pnts_rf(self) -> Array:
        return self.quads[self.current_range].calib_pnts_rf

    @calib_pnts_rf.setter
    @check_connection_decorator
    def calib_pnts_rf(self, value: Array):
        self.quads[self.current_range].calib_pnts_rf = value

    @property
    @check_connection_decorator
    def dc_offst(self) -> float:
        return self.quads[self.current_range].dc_offst

    @dc_offst.setter
    @check_connection_decorator
    def dc_offst(self, value: float):
        self.quads[self.current_range].dc_offst = value

    @check_connection_decorator
    def set_range(self, value: int):
        self.driver.set_range(value)
        self.current_range = value

    @check_connection_decorator
    def get_range(self) -> int:
        return self.current_range

    @check_connection_decorator
    def get_status(self):
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
