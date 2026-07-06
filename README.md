# pynadtcp

Async Python client for NAD amplifiers that expose a TCP/IP control protocol on
port 30001 — most notably the **NAD C338**. It is a modern, typed rewrite of the
abandoned [`nadtcp`](https://gitlab.com/mindig.marton/nadtcp) library and is
designed to back the Home Assistant `nad_tcp` integration, but has no Home
Assistant dependency and can be used standalone.

## Install

```bash
pip install pynadtcp
```

## Usage

```python
import asyncio
from pynadtcp import NadClient


async def main() -> None:
    async with NadClient("192.168.1.50") as client:
        print(client.state.model, client.state.version)

        await client.power_on()
        await client.set_volume(-40)        # dB, clamped to [-80, 0]
        await client.select_source("Stream")

        def on_update(c: NadClient) -> None:
            print("state:", c.state)

        unsubscribe = client.register_state_update_callback(on_update)
        await asyncio.sleep(30)
        unsubscribe()


asyncio.run(main())
```

## API

- `NadClient(host, *, port=30001, connect_timeout=5.0, reconnect_interval=15.0)`
- `await client.connect()` / `await client.disconnect()` (or use as an async context manager)
- `client.is_connected()` → `bool`
- `client.state` → `NadState(power, volume_db, muted, source, model, version)`
- `client.sources` → list of selectable input source names
- `await client.power_on()` / `power_off()`
- `await client.set_volume(db)` / `volume_up()` / `volume_down()`
- `await client.set_mute(bool)`
- `await client.select_source(name)`
- `client.register_state_update_callback(cb)` → unsubscribe callable

After a successful `connect()`, the client keeps the connection alive and
transparently reconnects if it drops. Callbacks fire on every state change and
whenever the connection is established or lost.

## Supported devices

Developed and tested against the **NAD C338**. Other NAD models that speak the
same port-30001 text protocol (potentially the C368 / C388 / M10) are likely to
work, but are currently untested — reports welcome.

## License

MIT
