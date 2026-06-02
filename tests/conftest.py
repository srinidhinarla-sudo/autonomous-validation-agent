"""
Shared pytest fixtures.
"""

import pytest

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False

SM_SKIP = pytest.mark.skipif(not _SM_AVAILABLE,
    reason="infotainment_sm C++ module not built — run cmake --build first")


def _permissive_ctx():
    ctx = sm.VehicleContext()
    ctx.engine_running        = True
    ctx.phone_connected       = True
    ctx.carplay_connected     = True
    ctx.android_auto_connected = True
    ctx.usb_connected         = True
    ctx.aux_connected         = True
    ctx.dab_available         = True
    ctx.streaming_connected   = True
    ctx.ev_plugged_in         = True
    ctx.speed_kmh             = 0.0
    ctx.in_reverse            = False
    return ctx


@pytest.fixture
def machine():
    """Fresh state machine, booted to HOME with permissive context."""
    if not _SM_AVAILABLE:
        pytest.skip("infotainment_sm not available")
    m = sm.InfotainmentStateMachine()
    ctx = _permissive_ctx()
    m.set_context(ctx)
    m.transition(sm.Event.POWER_ON)
    return m


@pytest.fixture
def raw_machine():
    """Fresh machine still in BOOT state (no power-on)."""
    if not _SM_AVAILABLE:
        pytest.skip("infotainment_sm not available")
    return sm.InfotainmentStateMachine()


@pytest.fixture
def permissive_ctx():
    if not _SM_AVAILABLE:
        pytest.skip("infotainment_sm not available")
    return _permissive_ctx()


@pytest.fixture
def checker():
    from python.invariant_checker import InvariantChecker
    return InvariantChecker()
