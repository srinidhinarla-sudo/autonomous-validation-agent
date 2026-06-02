#!/usr/bin/env python3
"""
Standalone demo — no server required.

Fires a representative sequence through the state machine, showing:
- Normal navigation across subsystems
- Safety guard blocking (speed-lock, park assist)
- Mutual-exclusion guard: VOICE_ASSISTANT blocked while call is active,
  then allowed after the call ends

Run from the project root:
    python demo.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import infotainment_sm as sm
from python.invariant_checker import InvariantChecker

machine = sm.InfotainmentStateMachine()
checker = InvariantChecker()

# Start with engine running (required for POWER_ON guard)
_ctx = machine.get_context()
_ctx.engine_running = True
machine.set_context(_ctx)

# (event_name, context_patch, note)
SEQUENCE = [
    ("POWER_ON",              {},                          "Boot → Home"),
    ("SELECT_RADIO",          {},                          "Open Radio"),
    ("TUNE_FM",               {},                          "FM tuner"),
    ("HOME_BUTTON",           {},                          "Back to Home"),
    ("SELECT_NAV",            {},                          "Open Nav"),
    ("OPEN_MAP",              {},                          "Map view"),
    ("PLAN_ROUTE",            {},                          "Route planner"),
    ("ENTER_DESTINATION",     {},                          "Destination input"),
    ("CONFIRM_DESTINATION",   {},                          "Confirm → Route plan"),
    ("CONFIRM_DESTINATION",   {},                          "Start nav"),
    ("HOME_BUTTON",           {},                          "Back to Home"),
    # Speed-lock guard: Settings blocked above 5 km/h
    ("SELECT_SETTINGS",       {"speed_kmh": 60.0},        "Settings @ 60 km/h → BLOCKED (speed guard)"),
    ("SELECT_SETTINGS",       {"speed_kmh": 0.0},         "Settings @ 0 km/h   → OK"),
    ("HOME_BUTTON",           {},                          "Back to Home"),
    # Phone + mutual-exclusion guard
    ("SELECT_PHONE",          {"phone_connected": True},   "Phone hub (device connected)"),
    ("CALL_INITIATE",         {},                          "Dial out → DIALING"),
    ("CALL_ANSWER",           {},                          "Answer → INCALL (call_active=True)"),
    ("ACTIVATE_VOICE",        {},                          "Voice while call active → BLOCKED (mutual-exclusion guard)"),
    ("CALL_END",              {},                          "Hang up → call_active cleared"),
    ("HOME_BUTTON",           {},                          "Back to Home"),
    ("ACTIVATE_VOICE",        {},                          "Voice after call ends  → OK"),
    ("DEACTIVATE_VOICE",      {},                          "Close voice assistant"),
    # Park-assist guard: requires reverse gear
    ("SELECT_PARK_ASSIST",    {"in_reverse": False},       "Park assist, not in reverse → BLOCKED (reverse guard)"),
    ("SELECT_PARK_ASSIST",    {"in_reverse": True},        "Park assist, in reverse     → OK"),
]

HDR = f"{'#':<3}  {'Event':<25}  {'From':<24}  {'To':<24}  {'Result'}"
SEP = "─" * len(HDR)

print()
print("  Autonomous Validation Agent — Infotainment SM Demo")
print(SEP)
print(HDR)
print(SEP)

for i, (event_name, patch, note) in enumerate(SEQUENCE):
    if patch:
        ctx = machine.get_context()
        for k, v in patch.items():
            setattr(ctx, k, v)
        machine.set_context(ctx)

    from_state = sm.state_name(machine.get_state())
    event      = getattr(sm.Event, event_name)
    success    = machine.transition(event)
    to_state   = sm.state_name(machine.get_state())

    checker.check(machine.get_state(), machine.get_context(), step=i)

    tag = "✓  OK     " if success else "✗  BLOCKED"
    print(f"  {i:<3}  {event_name:<25}  {from_state:<24}  {to_state:<24}  {tag}  # {note}")

print(SEP)
print()

if checker.has_violations():
    print("INVARIANT VIOLATIONS DETECTED:")
    print(checker.summary())
    sys.exit(1)
else:
    print("  All 10 safety invariants satisfied across every step.")
    print()
