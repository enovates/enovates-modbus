import pytest
import pytest_asyncio
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.datastore import ModbusServerContext, ModbusSimulatorContext
from pymodbus.server import ModbusTcpServer


@pytest_asyncio.fixture
async def eno_one_v1_2_simulator(unused_tcp_port):
    def padded_string(start: int, text: str, size: int) -> dict:
        return {"addr": [start, start + size - 1], "value": text.ljust(size * 2, "\x00")}

    # https://pymodbus.readthedocs.io/en/latest/source/library/simulator/config.html
    store = ModbusSimulatorContext(
        {
            "setup": {
                "di size": 0,
                "co size": 0,
                "ir size": 0,
                "hr size": 6000,
                "shared blocks": False,
                "type exception": False,
                "defaults": {
                    "value": {
                        "bits": 0,
                        "uint16": 42,
                        "uint32": 742,
                        "float32": 3.14,
                        "string": "K",
                    },
                    "action": {
                        "bits": None,
                        "uint16": None,
                        "uint32": None,
                        "float32": None,
                        "string": None,
                    },
                },
            },
            "write": [
                400,
            ],
            "repeat": [],
            "invalid": [
                [0, 6000 - 1],  # Only allow reading of explicitly defined values below.
            ],
            "bits": [],
            "float32": [],
            "uint16": [
                {"addr": 0, "value": 1},  # API version major
                {"addr": 1, "value": 2},  # API version minor
                {"addr": 50, "value": 3},  # Nr of phases
                {"addr": 51, "value": 16},  # Max amp per phase
                {"addr": 52, "value": 0},  # ocpp connected state
                {"addr": 53, "value": 1},  # load shedding state
                {"addr": 54, "value": 2},  # lock state (no lock present)
                {"addr": 55, "value": 0},  # contactor state
                {"addr": 56, "value": 6},  # led color (pink)
                {"addr": 200, "value": 4234},  # L1 current
                {"addr": 201, "value": 4645},  # L2 current
                {"addr": 202, "value": 4589},  # L3 current
                {"addr": 203, "value": 235},  # L1 voltage
                {"addr": 204, "value": 222},  # L2 voltage
                {"addr": 205, "value": 250},  # L3 voltage
                {"addr": 206, "value": 11000},  # Power total
                {"addr": 207, "value": 3000},  # Power L1
                {"addr": 208, "value": 3400},  # Power L2
                {"addr": 209, "value": 4600},  # Power L3
                # 4 x int32
                {"addr": 300, "value": 8},  # mode 3 int (E)
                # 1x str
                {"addr": 303, "value": 8000},  # pwm mA
                {"addr": 304, "value": 750},  # pwm promille
                {"addr": 305, "value": 16},  # PP A
                {"addr": 306, "value": 12},  # CP pos V
                {"addr": 307, "value": 0},  # CP neg V
                {"addr": 400, "value": 7000},  # EMS limit mA
                # 16x str
                {"addr": 417, "value": 9001},  # Current offered mA
            ],
            "uint32": [
                {"addr": 210, "value": 0xFFFFE4A8},  # Installation current L1 (-7000)
                {"addr": 212, "value": 8000},  # Installation current L2
                {"addr": 214, "value": 0},  # Installation current L3
                {"addr": 216, "value": 0x300FCAFE},  # total energy (806341374)
            ],
            "string": [
                padded_string(301, "Q5", 2),  # Mode 3
                padded_string(401, "AtEsTtOkEn 007", 16),  # Session token
                padded_string(5000, "Enovates TEST", 16),
                padded_string(5016, "Pytest Mock Vendor", 16),
                padded_string(5032, "7" * 32, 16),
                padded_string(5048, "ENO one 479", 16),
                padded_string(5064, "2.15.1.0@3.3.0.1.3", 16),
            ],
        },
        None,
    )
    ctx = ModbusServerContext(devices=store, single=True)
    server = ModbusTcpServer(context=ctx, address=("localhost", unused_tcp_port))
    await server.serve_forever(background=True)
    yield unused_tcp_port
    await server.shutdown()


@pytest_asyncio.fixture
async def eno_one_client(eno_one_v1_2_simulator):
    from enovates_modbus import EnoOneClient

    async with EnoOneClient("localhost", eno_one_v1_2_simulator) as client:
        yield client


@pytest.mark.asyncio
async def test_eno_one(eno_one_client):
    from enovates_modbus.eno_one import LEDColor, LockState, Mode3State

    mb_client = eno_one_client.client
    assert isinstance(mb_client, AsyncModbusTcpClient)
    assert id(mb_client) == id(eno_one_client.client), "client property must be cached"

    assert await eno_one_client.check_version()

    api_version = await eno_one_client.get_api_version()
    assert api_version.major == 1
    assert api_version.minor == 2

    state = await eno_one_client.get_state()
    assert state.number_of_phases == 3
    assert state.max_amp_per_phase == 16
    assert state.ocpp_state is False
    assert state.load_shedding_state is True
    assert state.lock_state == LockState.NO_LOCK_PRESENT
    assert state.contactor_state is False
    assert state.led_color == LEDColor.PINK

    measurements = await eno_one_client.get_measurements()
    assert measurements.current_l1 == 4234
    assert measurements.current_l2 == 4645
    assert measurements.current_l3 == 4589
    assert measurements.voltage_l1 == 235
    assert measurements.voltage_l2 == 222
    assert measurements.voltage_l3 == 250
    assert measurements.charger_active_power_total == 11000
    assert measurements.charger_active_power_l1 == 3000
    assert measurements.charger_active_power_l2 == 3400
    assert measurements.charger_active_power_l3 == 4600
    assert measurements.installation_current_l1 == -7000
    assert measurements.installation_current_l2 == 8000
    assert measurements.installation_current_l3 == 0
    assert measurements.active_energy_import_total == 806341374

    mode3 = await eno_one_client.get_mode3_details()
    assert mode3.state_num == Mode3State.E
    assert mode3.state_str == "Q5"
    assert mode3.pwm_amp == 8000
    assert mode3.pwm == 750
    assert mode3.pp == 16
    assert mode3.CP_pos == 12
    assert mode3.CP_neg == 0

    assert await eno_one_client.get_ems_limit() == 7000

    assert (await eno_one_client.get_transaction_token()).transaction_token == "AtEsTtOkEn 007"

    assert await eno_one_client.get_current_offered() == 9001

    diag = await eno_one_client.get_diagnostics()
    assert diag.manufacturer == "Enovates TEST"
    assert diag.vendor_id == "Pytest Mock Vendor"
    assert diag.serial_nr == "7" * 32
    assert diag.model_id == "ENO one 479"
    assert diag.firmware_version == "2.15.1.0@3.3.0.1.3"

    await eno_one_client.set_ems_limit(4000)
    assert await eno_one_client.get_ems_limit() == 4000
