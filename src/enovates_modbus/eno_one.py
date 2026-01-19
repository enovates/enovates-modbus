"""
Implementation of EnoONE register mappings and client class
"""

import dataclasses
import enum
import logging
from typing import Annotated

from .base import MB_BOOL, MB_INT16, MB_INT32, MB_UINT16, EnoClient, ModbusRegisterEnumType, ModbusRegisterStrType, RegisterMap

LOGGER = logging.getLogger(__name__)


@enum.verify(enum.UNIQUE, enum.CONTINUOUS)
class LockState(enum.IntEnum):
    UNLOCKED = 0
    LOCKED = 1
    NO_LOCK_PRESENT = 2


MB_LOCK_STATE = Annotated[LockState, ModbusRegisterEnumType[LockState](LockState)]


@enum.verify(enum.UNIQUE, enum.CONTINUOUS)
class LEDColor(enum.IntEnum):
    OFF = 0
    RED = 1
    GREEN = 2
    BLUE = 3
    CYAN = 4
    YELLOW = 5
    PINK = 6
    WHITE = 7
    ORANGE = 8
    PURPLE = 9


MB_LED_COLOR = Annotated[LEDColor, ModbusRegisterEnumType[LEDColor](LEDColor)]


@enum.verify(enum.UNIQUE, enum.CONTINUOUS)
class Mode3State(enum.IntEnum):
    A1 = 0
    A2 = 1
    B1 = 2
    B2 = 3
    C1 = 4
    C2 = 5
    D1 = 6
    D2 = 7
    E = 8
    F = 9


MB_MODE3_STATE = Annotated[Mode3State, ModbusRegisterEnumType[Mode3State](Mode3State)]


@dataclasses.dataclass(frozen=True)
class APIVersion(RegisterMap, base_address=0):
    major: MB_UINT16
    minor: MB_UINT16


assert APIVersion.REGISTER_COUNT == 2


@dataclasses.dataclass(frozen=True)
class State(RegisterMap, base_address=50):
    number_of_phases: MB_UINT16
    max_amp_per_phase: MB_UINT16
    ocpp_state: MB_BOOL
    load_shedding_state: MB_BOOL
    lock_state: MB_LOCK_STATE
    contactor_state: MB_BOOL
    led_color: MB_LED_COLOR


assert State.REGISTER_COUNT == 7


@dataclasses.dataclass(frozen=True)
class Measurements(RegisterMap, base_address=200):
    current_l1: MB_UINT16  # mA
    current_l2: MB_UINT16  # mA
    current_l3: MB_UINT16  # mA
    voltage_l1: MB_INT16  # V
    voltage_l2: MB_INT16  # V
    voltage_l3: MB_INT16  # V
    charger_active_power_total: MB_INT16  # W
    charger_active_power_l1: MB_INT16  # W
    charger_active_power_l2: MB_INT16  # W
    charger_active_power_l3: MB_INT16  # W
    installation_current_l1: MB_INT32  # mA
    installation_current_l2: MB_INT32  # mA
    installation_current_l3: MB_INT32  # mA
    active_energy_import_total: MB_INT32  # Wh


assert Measurements.REGISTER_COUNT == 18


@dataclasses.dataclass(frozen=True)
class Mode3Details(RegisterMap, base_address=300):
    state_num: MB_MODE3_STATE
    state_str: Annotated[str, ModbusRegisterStrType(2)]
    pwm_amp: MB_INT16  # mA
    pwm: MB_INT16  # ‰
    pp: MB_INT16  # A
    CP_pos: MB_INT16  # V
    CP_neg: MB_INT16  # V


assert Mode3Details.REGISTER_COUNT == 8


@dataclasses.dataclass(frozen=True)
class EMSLimit(RegisterMap, base_address=400):
    """
    Writable only if EMS-over-modbus is enabled in device settings.
    Always readable.
    """

    ems_limit: MB_INT16  # mA


assert EMSLimit.REGISTER_COUNT == 1


@dataclasses.dataclass(frozen=True)
class TransactionToken(RegisterMap, base_address=401):
    """
    Readable only if EMS-over-modbus is enabled in device settings.
    """

    transaction_token: Annotated[str, ModbusRegisterStrType(16)]


assert TransactionToken.REGISTER_COUNT == 16


@dataclasses.dataclass(frozen=True)
class CurrentOffered(RegisterMap, base_address=417):
    active_current_offered: MB_UINT16  # mA


assert CurrentOffered.REGISTER_COUNT == 1


@dataclasses.dataclass(frozen=True)
class Diagnostics(RegisterMap, base_address=5000):
    manufacturer: Annotated[str, ModbusRegisterStrType(16)]  # Enovates NV
    vendor_id: Annotated[str, ModbusRegisterStrType(16)]
    serial_nr: Annotated[str, ModbusRegisterStrType(16)]
    model_id: Annotated[str, ModbusRegisterStrType(16)]
    firmware_version: Annotated[str, ModbusRegisterStrType(16)]


assert Diagnostics.REGISTER_COUNT == 80


class EnoOneClient(EnoClient):
    REGISTER_MAPS = (
        APIVersion,
        State,
        Measurements,
        Mode3Details,
        EMSLimit,
        TransactionToken,
        CurrentOffered,
        Diagnostics,
    )

    async def check_version(self) -> bool:
        version = await self.get_api_version()
        return version.major == 1 and version.minor >= 2

    async def get_api_version(self) -> APIVersion:
        return await self.fetch(APIVersion)

    async def get_state(self) -> State:
        return await self.fetch(State)

    async def get_measurements(self) -> Measurements:
        return await self.fetch(Measurements)

    async def get_mode3_details(self) -> Mode3Details:
        return await self.fetch(Mode3Details)

    async def get_transaction_token(self) -> TransactionToken:
        return await self.fetch(TransactionToken)

    async def get_diagnostics(self) -> Diagnostics:
        return await self.fetch(Diagnostics)

    # Functions below are
    async def get_ems_limit(self) -> int:
        """
        Get EMS limit in mA.
        """
        value = (await self.read(EMSLimit.BASE_ADDRESS, 1))[0]
        if value > 0x8000:
            value -= 0x10000
        return value

    async def set_ems_limit(self, limit: int):
        """
        Set EMS limit in mA.
        -1 means no limit and is the accepted sensible negative number.
        """
        if limit < -1 or limit > 0x7FFF:
            raise ValueError("EMS limit is out of range.")
        if limit < 0:
            limit += 0x10000
        return await self.write_single(EMSLimit.BASE_ADDRESS, limit)

    async def get_current_offered(self) -> int:
        """
        Get current offered to the car in mA.
        """
        return (await self.fetch(CurrentOffered)).active_current_offered
