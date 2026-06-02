"""
Invariant-checking fuzzer.

Generates random event sequences, fires them at the state machine, and
checks invariants after every step.  Failing sequences are returned with
their full context so the delta debugger can minimise them.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .invariant_checker import InvariantChecker, InvariantViolation

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False


@dataclass
class FuzzResult:
    """Result of a single fuzz run."""
    seed:       int
    sequence:   List[object]          # list of sm.Event values
    violated:   bool
    violations: List[InvariantViolation] = field(default_factory=list)
    fail_step:  int = -1              # index of first violation
    final_state: Optional[object] = None


def _make_permissive_context() -> "sm.VehicleContext":
    """Context that enables as many transitions as possible."""
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


def _make_random_context(rng: random.Random) -> "sm.VehicleContext":
    """Random context that may violate guards — used to stress-test guards."""
    ctx = sm.VehicleContext()
    ctx.engine_running        = rng.random() > 0.1
    ctx.phone_connected       = rng.random() > 0.3
    ctx.carplay_connected     = rng.random() > 0.5
    ctx.android_auto_connected = rng.random() > 0.5
    ctx.usb_connected         = rng.random() > 0.4
    ctx.aux_connected         = rng.random() > 0.4
    ctx.dab_available         = rng.random() > 0.3
    ctx.streaming_connected   = rng.random() > 0.3
    ctx.ev_plugged_in         = rng.random() > 0.7
    ctx.speed_kmh             = rng.uniform(0, 130)
    ctx.in_reverse            = rng.random() > 0.8
    return ctx


class Fuzzer:
    """
    Random-walk fuzzer over the infotainment state machine.

    Parameters
    ----------
    max_steps:       Maximum events per single fuzz run.
    use_valid_events: If True, only pick from events the SM says are
                      available in the current state (still random context).
    context_mode:    'permissive' | 'random' | 'adversarial'
                     adversarial = random context + random speed spike mid-run
    """

    def __init__(
        self,
        max_steps: int = 250,
        use_valid_events: bool = True,
        context_mode: str = "permissive",
    ) -> None:
        if not _SM_AVAILABLE:
            raise ImportError("infotainment_sm module not built.")
        self.max_steps = max_steps
        self.use_valid_events = use_valid_events
        self.context_mode = context_mode

        # Pre-build the full event list once
        self._all_events = [
            e for e in vars(sm.Event).values()
            if isinstance(e, sm.Event) and e != sm.Event.EVENT_COUNT
        ]

    def _context_for_seed(self, seed: int) -> "sm.VehicleContext":
        rng = random.Random(seed)
        if self.context_mode == "random":
            return _make_random_context(rng)
        return _make_permissive_context()

    def run_once(self, seed: int) -> FuzzResult:
        """Execute one fuzz run with the given seed."""
        rng = random.Random(seed)
        machine = sm.InfotainmentStateMachine()
        ctx = self._context_for_seed(seed)
        machine.set_context(ctx)
        checker = InvariantChecker()

        sequence: List[object] = []
        fail_step = -1

        # Boot first
        machine.transition(sm.Event.POWER_ON)
        sequence.append(sm.Event.POWER_ON)
        ctx.engine_running = True
        machine.set_context(ctx)

        for step in range(self.max_steps):
            # Adversarial: occasionally spike speed
            if self.context_mode == "adversarial" and rng.random() < 0.05:
                ctx.speed_kmh = rng.choice([0.0, 10.0, 80.0, 120.0])
                machine.set_context(ctx)

            if self.use_valid_events:
                candidates = machine.get_available_events()
            else:
                candidates = self._all_events

            if not candidates:
                break

            event = rng.choice(candidates)
            machine.transition(event)
            sequence.append(event)

            ok = checker.check(machine.get_state(), machine.get_context(), step=step)
            if not ok and fail_step == -1:
                fail_step = step

        return FuzzResult(
            seed=seed,
            sequence=sequence,
            violated=checker.has_violations(),
            violations=list(checker.violations),
            fail_step=fail_step,
            final_state=machine.get_state(),
        )

    def run_campaign(
        self,
        num_runs: int = 1000,
        base_seed: int = 42,
    ) -> Tuple[List[FuzzResult], List[FuzzResult]]:
        """
        Run *num_runs* fuzz campaigns.

        Returns (all_results, failing_results).
        """
        all_results: List[FuzzResult] = []
        failing:     List[FuzzResult] = []

        for i in range(num_runs):
            result = self.run_once(base_seed + i)
            all_results.append(result)
            if result.violated:
                failing.append(result)

        return all_results, failing

    def coverage_stats(self, results: List[FuzzResult]) -> str:
        total   = len(results)
        failing = sum(1 for r in results if r.violated)
        return (f"Fuzz campaign: {total} runs, "
                f"{failing} violations ({100*failing/total:.1f}%)")
