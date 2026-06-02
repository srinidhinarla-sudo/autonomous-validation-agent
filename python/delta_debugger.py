"""
Delta debugger (ddmin algorithm — Zeller 1999).

Reduces a failing N-step event sequence to a minimal 1-minimal sub-sequence
that still triggers the same invariant violation.

Reference: A. Zeller, "Yesterday, My Program Worked. Today, It Does Not. Why?"
           ESEC/FSE 1999.
"""

from __future__ import annotations

import math
from typing import Callable, List, Optional, Tuple

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False


# A predicate that receives an event list and returns True if the sequence
# still triggers the failure of interest.
Predicate = Callable[[List[object]], bool]


def build_predicate(
    violation_invariant: Optional[str] = None,
    context_factory: Optional[Callable[[], "sm.VehicleContext"]] = None,
) -> Predicate:
    """
    Build a standard predicate: replay the sequence on a fresh machine
    and check for any invariant violation (or a specific named one).
    """
    from .invariant_checker import InvariantChecker

    def _pred(events: List[object]) -> bool:
        if not _SM_AVAILABLE or not events:
            return False
        machine = sm.InfotainmentStateMachine()
        if context_factory:
            machine.set_context(context_factory())
        else:
            ctx = sm.VehicleContext()
            ctx.engine_running = True
            machine.set_context(ctx)

        checker = InvariantChecker()
        for step, ev in enumerate(events):
            machine.transition(ev)
            checker.check(machine.get_state(), machine.get_context(), step=step)

        if violation_invariant:
            return any(v.invariant_name == violation_invariant
                       for v in checker.violations)
        return checker.has_violations()

    return _pred


def ddmin(events: List[object], predicate: Predicate) -> List[object]:
    """
    Classic ddmin: reduces *events* to a 1-minimal subsequence that
    still satisfies *predicate*.

    Returns the minimal failing subsequence.
    Raises ValueError if the full sequence does not satisfy the predicate.
    """
    if not predicate(events):
        raise ValueError("Original sequence does not trigger the failure. "
                         "Check your predicate.")

    n = len(events)
    granularity = 2

    while n > 1:
        subsets = _partition(events, granularity)
        complement_found = False

        for subset in subsets:
            complement = [e for e in events if e not in subset]  # type: ignore[comparison-overlap]
            # (identity comparison is fine because these are enum values)
            complement = _ordered_complement(events, subset)
            if predicate(complement):
                events = complement
                n = len(events)
                granularity = max(granularity - 1, 2)
                complement_found = True
                break

        if not complement_found:
            if granularity >= n:
                break
            granularity = min(granularity * 2, n)

    return events


def _partition(events: List[object], n: int) -> List[List[object]]:
    """Split *events* into *n* roughly-equal chunks."""
    size = math.ceil(len(events) / n)
    return [events[i:i+size] for i in range(0, len(events), size)]


def _ordered_complement(full: List[object], subset: List[object]) -> List[object]:
    """Return full minus subset, preserving order.  Uses index-based exclusion."""
    subset_indices: set[int] = set()
    used: List[bool] = [False] * len(full)
    for item in subset:
        for i, e in enumerate(full):
            if not used[i] and e == item:
                subset_indices.add(i)
                used[i] = True
                break
    return [e for i, e in enumerate(full) if i not in subset_indices]


class DeltaDebugger:
    """
    High-level wrapper around ddmin.

    Example
    -------
    dbg = DeltaDebugger()
    minimal = dbg.minimize(long_failing_sequence, predicate)
    print(dbg.report(long_failing_sequence, minimal))
    """

    def minimize(
        self,
        events:    List[object],
        predicate: Predicate,
    ) -> List[object]:
        return ddmin(events, predicate)

    def report(
        self,
        original:  List[object],
        minimal:   List[object],
        predicate: Optional[Predicate] = None,
    ) -> str:
        lines = [
            f"Delta-debugging report",
            f"  Original length : {len(original)} steps",
            f"  Minimal length  : {len(minimal)} steps",
            f"  Reduction       : {100*(1 - len(minimal)/len(original)):.1f}%",
        ]
        if _SM_AVAILABLE:
            lines.append("  Minimal sequence:")
            for i, ev in enumerate(minimal):
                lines.append(f"    [{i}] {sm.event_name(ev)}")
        if predicate is not None:
            still_fails = predicate(minimal)
            lines.append(f"  Still fails: {still_fails}")
        return "\n".join(lines)

    def minimize_and_report(
        self,
        events:    List[object],
        predicate: Predicate,
    ) -> Tuple[List[object], str]:
        minimal = self.minimize(events, predicate)
        return minimal, self.report(events, minimal, predicate)
