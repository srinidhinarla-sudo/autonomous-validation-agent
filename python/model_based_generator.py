"""
Model-based test generator.

Builds a directed graph from the C++ state machine's transition table and
produces test sequences that achieve ≥90 % transition coverage using a
greedy Eulerian-path heuristic (Hierholzer-inspired BFS).
"""

from __future__ import annotations

import random
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False


@dataclass
class TransitionEdge:
    from_state: object
    to_state:   object
    event:      object
    guard_name: str
    covered:    bool = False


@dataclass
class TestSequence:
    events:       List[object]
    start_state:  object
    description:  str = ""
    covers:       List[Tuple[object, object]] = field(default_factory=list)


class TransitionGraph:
    """Directed graph over (State, Event, State) triples extracted from the SM."""

    def __init__(self) -> None:
        if not _SM_AVAILABLE:
            raise ImportError("infotainment_sm C++ module not built. Run cmake --build first.")
        machine = sm.InfotainmentStateMachine()
        raw = machine.get_all_transitions()

        self.edges: List[TransitionEdge] = []
        self.adj: Dict[object, List[TransitionEdge]] = defaultdict(list)

        for t in raw:
            edge = TransitionEdge(t.from_state, t.to_state, t.event, t.guard_name)
            self.edges.append(edge)
            self.adj[t.from_state].append(edge)

        self.all_states: Set[object] = {e.from_state for e in self.edges} | \
                                       {e.to_state   for e in self.edges}

    @property
    def total_edges(self) -> int:
        return len(self.edges)

    @property
    def covered_edges(self) -> int:
        return sum(1 for e in self.edges if e.covered)

    @property
    def coverage(self) -> float:
        if not self.edges:
            return 1.0
        return self.covered_edges / self.total_edges

    def reset_coverage(self) -> None:
        for e in self.edges:
            e.covered = False

    def mark_covered(self, from_state: object, to_state: object, event: object) -> None:
        for e in self.edges:
            if e.from_state == from_state and e.to_state == to_state and e.event == event:
                e.covered = True
                return

    def uncovered_edges(self) -> List[TransitionEdge]:
        return [e for e in self.edges if not e.covered]


class ModelBasedGenerator:
    """
    Generates test sequences targeting ≥90 % transition coverage.

    Strategy
    --------
    1. Find all uncovered edges.
    2. For each uncovered edge, run a BFS from the current reachable states
       to find the shortest path to its source state, then fire its event.
    3. Emit the full event sequence as a single TestSequence.
    Repeat until coverage ≥ target or no progress is made.
    """

    def __init__(self, target_coverage: float = 0.90, max_sequence_len: int = 500) -> None:
        self.graph = TransitionGraph()
        self.target_coverage = target_coverage
        self.max_sequence_len = max_sequence_len

    # ------------------------------------------------------------------
    def _bfs_path(self, start: object, goal: object) -> Optional[List[object]]:
        """Return list of events to get from *start* to *goal* (BFS)."""
        if start == goal:
            return []
        visited = {start}
        queue: deque[Tuple[object, List[object]]] = deque([(start, [])])
        while queue:
            state, path = queue.popleft()
            for edge in self.graph.adj.get(state, []):
                nxt = edge.to_state
                new_path = path + [edge.event]
                if nxt == goal:
                    return new_path
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, new_path))
        return None  # unreachable

    def _reachable_from_boot(self) -> Set[object]:
        """States reachable from BOOT via BFS (ignoring guards)."""
        visited: Set[object] = set()
        queue = deque([sm.State.BOOT])
        while queue:
            s = queue.popleft()
            if s in visited:
                continue
            visited.add(s)
            for edge in self.graph.adj.get(s, []):
                queue.append(edge.to_state)
        return visited

    # ------------------------------------------------------------------
    def _make_machine(self) -> "sm.InfotainmentStateMachine":
        """Fresh machine with permissive context, booted to HOME."""
        machine = sm.InfotainmentStateMachine()
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
        ctx.in_reverse            = True   # enables park assist paths
        machine.set_context(ctx)
        machine.transition(sm.Event.POWER_ON)
        return machine

    def _execute_and_cover(self, events: List[object]) -> List[Tuple[object, object]]:
        """
        Run *events* on a fresh machine; mark every taken transition covered.
        Returns list of (from, to) pairs that were actually traversed.
        """
        machine = self._make_machine()
        covered: List[Tuple[object, object]] = []
        for ev in events:
            prev = machine.get_state()
            ok = machine.transition(ev)
            if ok:
                nxt = machine.get_state()
                self.graph.mark_covered(prev, nxt, ev)
                covered.append((prev, nxt))
        return covered

    # ------------------------------------------------------------------
    def generate_sequences(self) -> List[TestSequence]:
        """
        Return a list of TestSequence objects whose union achieves
        ≥ target_coverage over all transitions.

        Each sequence starts fresh from HOME (guaranteed correctness —
        no simulation drift).  BFS finds shortest path to each uncovered
        edge's source; the real SM executes it to mark actual coverage.
        """
        self.graph.reset_coverage()
        sequences: List[TestSequence] = []
        reachable = self._reachable_from_boot()

        # Mark BOOT→HOME as covered via the implicit power-on
        self.graph.mark_covered(sm.State.BOOT, sm.State.HOME, sm.Event.POWER_ON)
        sequences.append(TestSequence(
            events=[sm.Event.POWER_ON],
            start_state=sm.State.BOOT,
            description="Boot sequence",
            covers=[(sm.State.BOOT, sm.State.HOME)],
        ))

        max_passes = 4   # repeat sweeps to catch edges exposed by earlier coverage
        for _pass in range(max_passes):
            made_progress = False
            uncovered = [e for e in self.graph.uncovered_edges()
                         if e.from_state in reachable]
            if not uncovered:
                break

            # Sort: prefer sources with many uncovered out-edges (batch efficiency)
            uncovered.sort(
                key=lambda e: -sum(1 for oe in self.graph.adj.get(e.from_state, [])
                                   if not oe.covered)
            )

            for target_edge in uncovered:
                if target_edge.covered:   # may have been covered by a prior iteration
                    continue

                path_to_src = self._bfs_path(sm.State.HOME, target_edge.from_state)
                if path_to_src is None:
                    continue  # genuinely unreachable from HOME

                events = path_to_src + [target_edge.event]
                covered_pairs = self._execute_and_cover(events)

                if covered_pairs:
                    sequences.append(TestSequence(
                        events=events,
                        start_state=sm.State.HOME,
                        description=(
                            f"Cover {sm.InfotainmentStateMachine.state_name(target_edge.from_state)}"
                            f" --[{sm.InfotainmentStateMachine.event_name(target_edge.event)}]--> "
                            f"{sm.InfotainmentStateMachine.state_name(target_edge.to_state)}"
                        ),
                        covers=covered_pairs,
                    ))
                    made_progress = True

            if not made_progress or self.graph.coverage >= self.target_coverage:
                break

        return sequences

    @property
    def total_transitions(self) -> int:
        return self.graph.total_edges

    @property
    def current_coverage(self) -> float:
        return self.graph.coverage

    def coverage_report(self) -> str:
        covered = self.graph.covered_edges
        total   = self.graph.total_edges
        pct     = 100.0 * covered / total if total else 100.0
        return (f"Transition coverage: {covered}/{total} ({pct:.1f}%) "
                f"[target: {self.target_coverage*100:.0f}%]")

    def uncovered_transition_names(self) -> List[str]:
        """Human-readable list of transitions not yet covered."""
        SM = sm.InfotainmentStateMachine
        return [
            f"{SM.state_name(e.from_state)} --[{SM.event_name(e.event)}]--> {SM.state_name(e.to_state)}"
            f"  (guard: {e.guard_name or 'none'})"
            for e in self.graph.uncovered_edges()
        ]
