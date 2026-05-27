"""Graceful shutdown: SIGTERM must set the stop event, not hang until SIGKILL.

Regression for the systemd 'stop-sigterm timed out. Killing.' warning seen
after the 2026-05-27 VPS deploy — the bot ignored SIGTERM and was force-killed
after the 90s stop timeout on every restart/reboot.
"""
import asyncio
import os
import signal

from leads_bot.main import _install_signal_handlers


async def test_sigterm_sets_stop_event():
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    _install_signal_handlers(loop, stop)

    os.kill(os.getpid(), signal.SIGTERM)  # absorbed by the handler, not fatal
    await asyncio.wait_for(stop.wait(), timeout=2)

    assert stop.is_set()


async def test_sigint_sets_stop_event():
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    _install_signal_handlers(loop, stop)

    os.kill(os.getpid(), signal.SIGINT)
    await asyncio.wait_for(stop.wait(), timeout=2)

    assert stop.is_set()
