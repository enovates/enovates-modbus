# enovates-modbus

A library to communicate with [Enovates](https://www.enovates.com/) EVSEs over Moodbus TCP.

This library is designed for use with [the Enovates Home Assistant integration](https://github.com/enovates/home-assistant-enovates).

Other EVSE models than listed below may work or be added in the future.
The minimum Modbus API version is 1.2, update your EVSE's firmware to 2.13 or later if needed.

Beware: The EVSE's Modbus communication must be enabled, this cannot be done via this library.
The relevant setting may be called "EMS mode", and should be switchable between "Off", "Monitoring Only" and "Full Control".
It must be enabled by the Installer or via OCPP. There is currently no switch for it in the end user app.

## ENO one

Device: https://www.enovates.com/products/singlewallbox

Always available, if EMS Mode/Modbus is enabled:

- Modbus API version
  - major (int)
  - minor (int)
- State
  - nr of phases (int)
  - max amp per phase (A)
  - ocpp state (bool)
  - load shedding state (bool)
  - lock state (enum)
  - contactor state (bool)
  - led color (enum)
- Measurements
  - current on L1, L2, L3 (mA)
  - voltage on L1, L2, L3 (V)
  - charge active power total, L1, L2, L3 (W)
  - installation current L1, L2, L3 (mA)
  - active energy import total (Wh)
- Current Offered (mA)
- Mode 3 Details
  - state (enum and str)
  - pwm (in promille and mA)
  - pp (max cable current, if socketed)
  - cp + and - (volts)
- Diagnostics
  - manufacturer (str)
  - vendor id (str)
  - serial nr (str)
  - model id (str)
  - firmware version (str)

If EMS/Modbus TCP mode is "Monitoring only":

- EMS current limit (mA) Read only. Writes may be accepted but are ignored
- Transaction token (str) NOT available. Reading will error.

If EMS/Modbus TCP mode is "Full control":

- EMS current limit (mA) Read / Write.
- Transaction token (str)

The recommended registers for active power management are the "Current Offered", "EMS Current Limit" and the registers under Measurements. For cars that support digital communication (ISO 15118), the values under Mode 3 Details could give a false impression of the EVSE/car behaviour.

## Development

Contributions may be accepted under the terms of the [Apache License, Version 2.0](./LICENSE.md).

This project uses [uv](https://docs.astral.sh/uv) for project management. If you are not familiar, read its [Getting Started](https://docs.astral.sh/uv/getting-started/installation/) and [Project structure](https://docs.astral.sh/uv/guides/projects/#project-structure) guide in particular.

After cloning the repo and setting up your working environment with uv, make sure to install [pre-commit](http://pre-commit.com/)'s hooks if your global git configuration lacks them:

```shell
pre-commit install
```

All checks should pass before you push your code.
Merge requests with violations are likely to be ignored until they are fully compliant.
