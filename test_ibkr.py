import asyncio

# Python 3.14 compatibility for eventkit/ib_insync import-time loop access.
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import *

ib = IB()

ib.connect(
    '127.0.0.1',
    7497,
    clientId=1
)

print("CONNECTED")
ib.disconnect()
