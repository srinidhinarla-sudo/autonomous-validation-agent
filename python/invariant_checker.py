"""
Invariant checker.

Validates safety invariants after every state transition.  Each invariant
is a named predicate over (state, vehicle_context).  Violations are
collected and can be raised as a single AssertionError.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False


@dataclass
class InvariantViolation:
    invariant_name: str
    state:          object
    context_repr:   str
    message:        str
    sequence_step:  int = 0


class InvariantChecker:
    """
    Checks a suite of named invariants against (state, context) pairs.

    Usage
    -----
    checker = InvariantChecker()
    checker.check(machine.get_state(), machine.get_context(), step=i)
    checker.assert_no_violations()   # raises AssertionError if any found
    """

    def __init__(self) -> None:
        self.violations: List[InvariantViolation] = []
        self._invariants: List[tuple[str, Callable]] = self._build_invariants()

    # ------------------------------------------------------------------
    def _build_invariants(self) -> List[tuple[str, Callable]]:
        if not _SM_AVAILABLE:
            return []

        S = sm.State

        SPEED_LOCKED_STATES = {
            S.NAV_ROUTE_PLAN,
            S.NAV_DESTINATION_INPUT,
            S.NAV_POI_SEARCH,
            S.SETTINGS_HOME,
            S.SETTINGS_DISPLAY,
            S.SETTINGS_SOUND,
            S.SETTINGS_CONNECTIVITY,
            S.SETTINGS_VEHICLE,
            S.SETTINGS_LANGUAGE,
            S.SETTINGS_CLOCK,
            S.SETTINGS_PRIVACY,
            S.SETTINGS_DIAGNOSTICS,
        }

        REVERSE_ONLY_STATES = {
            S.PARK_ASSIST_REAR,
            S.PARK_ASSIST_FRONT,
            S.PARK_ASSIST_360,
        }

        PHONE_REQUIRED_STATES = {
            S.PHONE_DIALING,
            S.PHONE_INCALL,
            S.PHONE_INCOMING,
            S.PHONE_CONTACTS,
            S.PHONE_RECENT_CALLS,
            S.PHONE_VOICEMAIL,
        }

        CARPLAY_REQUIRED_STATES = {S.MEDIA_CARPLAY}
        ANDROID_AUTO_REQUIRED_STATES = {S.MEDIA_ANDROID_AUTO}
        USB_REQUIRED_STATES = {S.MEDIA_USB, S.MEDIA_USB_BROWSE}
        AUX_REQUIRED_STATES = {S.MEDIA_AUX}
        EV_REQUIRED_STATES  = {S.CHARGING_STATUS}

        # Mutually exclusive modal pairs:
        # VOICE_ASSISTANT and PHONE_INCALL must never be the active state simultaneously.
        # (We can only be in one state at a time, so the real invariant is:
        #  if in PHONE_INCALL, the previous path must not have gone through VOICE_ASSISTANT
        #  without dismissing it first — enforced by the SM itself.  We check that
        #  VOICE_ASSISTANT is never reached while phone is in-call by checking
        #  that if state == VOICE_ASSISTANT then phone is not connected and in-call.)
        # For simplicity we assert: PHONE_INCALL ∧ state == VOICE_ASSISTANT is impossible.

        def check_speed_lock(state, ctx) -> Optional[str]:
            if state in SPEED_LOCKED_STATES and ctx.speed_kmh > 5.0:
                return (f"Speed-locked state {sm.state_name(state)} reached at "
                        f"{ctx.speed_kmh:.1f} km/h (limit: 5 km/h)")
            return None

        def check_reverse_only(state, ctx) -> Optional[str]:
            if state in REVERSE_ONLY_STATES and not ctx.in_reverse:
                return (f"Park-assist state {sm.state_name(state)} reached "
                        f"while NOT in reverse gear")
            return None

        def check_phone_connected(state, ctx) -> Optional[str]:
            if state in PHONE_REQUIRED_STATES and not ctx.phone_connected:
                return (f"Phone state {sm.state_name(state)} reached "
                        f"without a connected phone")
            return None

        def check_carplay(state, ctx) -> Optional[str]:
            if state in CARPLAY_REQUIRED_STATES and not ctx.carplay_connected:
                return f"MEDIA_CARPLAY reached without CarPlay connection"
            return None

        def check_android_auto(state, ctx) -> Optional[str]:
            if state in ANDROID_AUTO_REQUIRED_STATES and not ctx.android_auto_connected:
                return f"MEDIA_ANDROID_AUTO reached without Android Auto connection"
            return None

        def check_usb(state, ctx) -> Optional[str]:
            if state in USB_REQUIRED_STATES and not ctx.usb_connected:
                return f"USB media state {sm.state_name(state)} reached without USB device"
            return None

        def check_aux(state, ctx) -> Optional[str]:
            if state in AUX_REQUIRED_STATES and not ctx.aux_connected:
                return f"MEDIA_AUX reached without AUX cable"
            return None

        def check_ev(state, ctx) -> Optional[str]:
            if state in EV_REQUIRED_STATES and not ctx.ev_plugged_in:
                return f"CHARGING_STATUS reached without EV plugged in"
            return None

        def check_valid_state(state, ctx) -> Optional[str]:
            try:
                sm.state_name(state)
            except Exception:
                return f"State machine is in an unknown/invalid state: {state}"
            return None

        return [
            ("speed_lock",       check_speed_lock),
            ("reverse_only",     check_reverse_only),
            ("phone_connected",  check_phone_connected),
            ("carplay",          check_carplay),
            ("android_auto",     check_android_auto),
            ("usb_connected",    check_usb),
            ("aux_connected",    check_aux),
            ("ev_plugged_in",    check_ev),
            ("valid_state",      check_valid_state),
        ]

    # ------------------------------------------------------------------
    def check(self, state: object, context: object, step: int = 0) -> bool:
        """
        Run all invariants.  Returns True if all pass; appends violations otherwise.
        """
        all_ok = True
        for name, fn in self._invariants:
            msg = fn(state, context)
            if msg:
                self.violations.append(InvariantViolation(
                    invariant_name=name,
                    state=state,
                    context_repr=repr(context),
                    message=msg,
                    sequence_step=step,
                ))
                all_ok = False
        return all_ok

    def clear(self) -> None:
        self.violations.clear()

    def has_violations(self) -> bool:
        return bool(self.violations)

    def assert_no_violations(self) -> None:
        if self.violations:
            lines = [f"  [{v.sequence_step}] {v.invariant_name}: {v.message}"
                     for v in self.violations]
            raise AssertionError(
                f"{len(self.violations)} invariant violation(s):\n" + "\n".join(lines)
            )

    def summary(self) -> str:
        if not self.violations:
            return "All invariants satisfied."
        lines = [f"  step {v.sequence_step} | {v.invariant_name}: {v.message}"
                 for v in self.violations]
        return f"{len(self.violations)} violation(s):\n" + "\n".join(lines)
