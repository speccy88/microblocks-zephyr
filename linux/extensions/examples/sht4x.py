"""Lazy official Blinka/SHT4x APIs; no forced Radxa/MicroDuck pin mapping."""
# SPDX-License-Identifier: MIT
from ..api import ExtensionError,arguments


class Extension:
    def __init__(self,settings,context):
        self.settings,self.context=settings,context;self.bus=None;self.device=None
        self.operations={'read':self.read}

    def read(self,args):
        arguments(args,())
        if self.context.board=='microduck' and self.settings.get('pin_map_validated') is not True:raise ExtensionError('pin_map_unverified','MicroDuck I2C pin mapping is unverified; sharing the RK3566 with Radxa does not establish compatible pins')
        if not self.device:
            try:
                from adafruit_platformdetect import Detector
                import board
                import adafruit_sht4x
            except ImportError:raise ExtensionError('dependency_missing','Install official Adafruit-Blinka and adafruit-circuitpython-sht4x in the configured Python environment') from None
            expected=self.settings.get('expected_board')
            if not expected or Detector().board.id!=expected:raise ExtensionError('board_mismatch','Blinka board detection does not match the configured and validated board')
            try:
                self.bus=board.I2C();self.device=adafruit_sht4x.SHT4x(self.bus,address=self.settings.get('address',0x44))
            except (OSError,ValueError):raise ExtensionError('device_unavailable','SHT4x is unavailable; verify the configured I2C bus, device and permissions') from None
        try:temperature,humidity=self.device.measurements
        except OSError:raise ExtensionError('device_unavailable','SHT4x read failed; verify the connected device and I2C bus') from None
        return {'temperature_mc':round(temperature*1000),'humidity_millipercent':round(humidity*1000),'source':'blinka_sht4x','physical_validated':False}

    def close(self):
        if self.bus:self.bus.deinit()
