"""
Common base set of Modus register based types and the RegisterMap base class.
"""

import inspect
import struct
import typing
from abc import ABCMeta, abstractmethod
from functools import cached_property
from typing import Annotated, ClassVar

from pymodbus import ModbusException
from pymodbus.client import AsyncModbusTcpClient


class ModbusRegisterType[T](metaclass=ABCMeta):
    """
    Abstract base class for Modbus register type.
    Used by the RegistryMap class to do type conversions.
    """

    def __init__(self, count: int):
        self.count = count
        assert self.count > 0, f"Invalid register count {count!r} for {self.__class__.__name__}."

    @abstractmethod
    def from_registers(self, registers: list[int]) -> T:
        """
        Pops all needed registers of the input list and returns the transformed value.
        --> registers is mutated!
        """
        raise NotImplementedError


class ModbusRegisterEnumType[T](ModbusRegisterType[T]):
    """
    Enum based Modbus register type.
    """

    # Unfortunately there is no nice (supported) way to get T at runtime,
    # so we also have to pass the type to the constructor.
    def __init__(self, enum: type[T], count: int = 1):
        super().__init__(count)
        self.enum = enum

    def from_registers(self, registers: list[int]) -> T:
        assert len(registers) >= self.count
        return self.enum(registers.pop(0))


class ModbusRegisterBoolType(ModbusRegisterType[bool]):
    """
    Boolean based Modbus register type.
    0 = False, anything else = True.
    """

    def from_registers(self, registers: list[int]) -> bool:
        assert len(registers) >= self.count
        return registers.pop(0) != 0


class ModbusRegisterStrType(ModbusRegisterType[str]):
    """
    String based Modbus register type.
    The register count is double the nr of 8 bytes ASCII chars.
    """

    def from_registers(self, registers: list[int]) -> str:
        assert len(registers) >= self.count
        data = b"".join(struct.pack(">H", registers.pop(0)) for _ in range(self.count))
        return data.decode("ascii", "replace").rstrip("\x00")


class ModbusRegisterIntType(ModbusRegisterType[int]):
    """
    Integer based Modbus register type.
    Big endian support only.
    Signed = Two's compliment
    """

    def __init__(self, count: int, signed: bool):
        super().__init__(count)
        self.signed = signed

    def from_registers(self, registers: list[int]) -> int:
        assert len(registers) >= self.count
        value = registers.pop(0)
        for _ in range(self.count - 1):
            value <<= 16
            value |= registers.pop(0)
        if self.signed and value >= 1 << (16 * self.count - 1):
            value -= 1 << (16 * self.count)
        return value


MB_BOOL = Annotated[bool, ModbusRegisterBoolType(1)]
MB_UINT16 = Annotated[int, ModbusRegisterIntType(1, False)]
MB_INT16 = Annotated[int, ModbusRegisterIntType(1, True)]
MB_UINT32 = Annotated[int, ModbusRegisterIntType(2, False)]
MB_INT32 = Annotated[int, ModbusRegisterIntType(2, True)]


class RegisterMap:
    """
    Represents a continues region of registers available via modbus.

    Implement by extending, as a (frozen) dataclass.
    Every field that is a ModbusRegisterType gets added to the kwargs in the constructor when using from_registers.
    """

    BASE_ADDRESS: ClassVar[int]
    REGISTER_COUNT: ClassVar[int]
    _REGISTER_MAP: ClassVar[dict[str, ModbusRegisterType]]

    def __init_subclass__(cls, base_address: int, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.BASE_ADDRESS = base_address
        cls.REGISTER_COUNT = 0
        cls._REGISTER_MAP = {}
        for field, annotation in inspect.get_annotations(cls).items():
            for a in typing.get_args(annotation):
                if not isinstance(a, ModbusRegisterType):
                    continue
                cls.REGISTER_COUNT += a.count
                cls._REGISTER_MAP[field] = a

    @classmethod
    def from_registers(cls, registers: list[int], /, *args, **kwargs) -> typing.Self:
        assert len(registers) >= cls.REGISTER_COUNT, (
            f"Not enough registers for {cls.__name__}. Expected {cls.REGISTER_COUNT} but got {len(registers)}."
        )
        assert cls._REGISTER_MAP.keys().isdisjoint(kwargs.keys()), "kwargs overlaps with register mapping."
        for field, register_type in cls._REGISTER_MAP.items():
            kwargs[field] = register_type.from_registers(registers)
        return cls(*args, **kwargs)


class EnoClient:
    """
    Base class for Modbus connection to Enovates EVSE over Modbus TCP

    Implementation classes should extend, fill REGISTER_MAPS and provide fetch functions for every RegisterMap.
    """

    REGISTER_MAPS: ClassVar[tuple[type[RegisterMap], ...]]

    def __init__(self, host: str, port: int = 502, device_id: int = 1, mb_retries: int = 3, mb_timeout: int = 3):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.mb_retries = mb_retries
        self.mb_timeout = mb_timeout

    @cached_property
    def client(self) -> AsyncModbusTcpClient:
        return AsyncModbusTcpClient(
            self.host, port=self.port, name=self.__class__.__qualname__, timeout=self.mb_timeout, retries=self.mb_retries
        )

    def __str__(self):
        return f"{self.__class__.__name__}(host={self.host!r}, port={self.port!r}, device_id={self.device_id!r})"

    async def __aenter__(self) -> typing.Self:
        await self.ensure_connected()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.client.close()

    async def ensure_connected(self):
        if not self.client.connected:
            try:
                r = await self.client.connect()
            except Exception as e:
                raise ConnectionError(f"Failed to connect to {self.host}:{self.port}: {e}") from e
            else:
                if not r:
                    raise ConnectionError(f"Failed to connect to {self.host}:{self.port}.")

    async def read(self, address: int, count: int = 1) -> list[int]:
        """
        Read one or more (holding) registers.
        """
        await self.ensure_connected()
        reply = await self.client.read_holding_registers(address=address, count=count, device_id=self.device_id)
        if reply.isError():
            raise ModbusException(f"Failed to read modbus registers. Got: {reply!r}")
        return reply.registers

    async def write(self, address: int, registers: list[int]):
        """
        Write one or more (holding) registers.
        """
        await self.ensure_connected()
        reply = await self.client.write_registers(address=address, values=registers, device_id=self.device_id)
        if reply.isError():
            raise ModbusException(f"Failed to write modbus registers. Got: {reply!r}")
        return reply.registers

    async def write_single(self, address: int, data: int):
        """
        Write single (holding) register.
        """
        await self.ensure_connected()
        reply = await self.client.write_register(address=address, value=data, device_id=self.device_id)
        if reply.isError():
            raise ModbusException(f"Failed to write modbus registers. Got: {reply!r}")
        return reply.registers

    async def fetch[T: RegisterMap](self, register_map: type[T]) -> T:
        """
        Get an entire register map in bulk.
        """
        registers = await self.read(register_map.BASE_ADDRESS, register_map.REGISTER_COUNT)
        return register_map.from_registers(registers)

    async def dump_all(self, file=None):
        """
        Dump all register maps to a file, or stdout if file is None.
        Exceptions are logged but otherwise ignored.
        """
        print("Register map dump for ", self, ":", file=file, sep="")
        for register_map in self.REGISTER_MAPS:
            try:
                rm = await self.fetch(register_map)
            except KeyboardInterrupt:
                raise
            except (ModbusException, ConnectionError) as e:
                print("\t", "ERROR\t", register_map.__name__, ": ", repr(e), file=file, sep="")
            else:
                print("\t", repr(rm), file=file, sep="")
