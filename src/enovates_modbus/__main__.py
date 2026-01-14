import argparse
import asyncio
from traceback import TracebackException

from . import EnoOneClient

MODELS = {"enoone": EnoOneClient}

INFO = """
Enovates ModbusTCP CLI client.

Dumps info from the charger to stdout.
"""

EPILOG = """
Website: https://enovates.com   Source:
"""

arg_parser = argparse.ArgumentParser(prog="enovates-modbus", add_help=False, description=INFO, epilog=EPILOG)
arg_parser.add_argument("-?", "--help", action="help")

arg_parser.add_argument("-h", "--host", action="store", nargs="?", required=True)
arg_parser.add_argument("-m", "--model", action="store", choices=sorted(MODELS.keys()), required=True)

arg_parser.add_argument("-p", "--port", action="store", nargs="?", default=502, type=int)
arg_parser.add_argument("-d", "--device-id", action="store", nargs="?", default=1, type=int)
arg_parser.add_argument("-l", "--loop", action="store_true", default=False)


async def run(args):
    client = MODELS[args.model](host=args.host, port=args.port, device_id=args.device_id)
    await client.dump_all()
    while args.loop:
        try:
            print("EMS limit:", await client.get_ems_limit(), "mA, Current offered:", await client.get_current_offered(), "mA.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            tbe = TracebackException(type(e), e, e.__traceback__, capture_locals=True)
            print("\n".join(tbe.format()))
        await asyncio.sleep(1)


def main():
    try:
        asyncio.run(run(arg_parser.parse_args()))
    except KeyboardInterrupt:
        print("Interrupted by user...")


if __name__ == "__main__":
    main()
