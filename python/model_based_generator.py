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
    def generate_sequences(self) -> List[TestSequence]:
        """
        Return a list of TestSequence objects whose union achieves
        ≥ target_coverage over all transitions.
        """
        self.graph.reset_coverage()
        sequences: List[TestSequence] = []
        reachable = self._reachable_from_boot()

        # Boot sequence — always the first sequence
        boot_seq = self._boot_sequence()
        sequences.append(boot_seq)

        current_state = sm.State.HOME  # after boot
        iterations = 0
        max_iter = self.total_transitions * 3

        while self.graph.coverage < self.target_coverage and iterations < max_iter:
            iterations += 1
            uncovered = [e for e in self.graph.uncovered_edges()
                         if e.from_state in reachable]
            if not uncovered:
                break

            # Pick the edge with the most uncovered outgoing edges from its source
            target_edge = self._pick_best_edge(uncovered, current_state)

            # BFS path to the source of the target edge
            path_to_src = self._bfs_path(current_state, target_edge.from_state)
            if path_to_src is None:
                # Unreachable — start fresh from HOME
                reset_path = self._reset_to_home(current_state)
                path_to_src = (reset_path or []) + \
                              (self._bfs_path(sm.State.HOME, target_edge.from_state) or [])
                if path_to_src is None:
                    continue

            events = path_to_src + [target_edge.event]

            # Simulate to track which transitions are covered
            sim_state = current_state
            covered_pairs: List[Tuple[object, object]] = []
            for ev in events:
                for edge in self.graph.adj.get(sim_state, []):
                    if edge.event == ev:
                        self.graph.mark_covered(sim_state, edge.to_state, ev)
                        covered_pairs.append((sim_state, edge.to_state))
                        sim_state = edge.to_state
                        break

            seq = TestSequence(
                events=events,
                start_state=current_state,
                description=f"Cover {sm.InfotainmentStateMachine.state_name(target_edge.from_state)}"
                            f" --[{sm.InfotainmentStateMachine.event_name(target_edge.event)}]--> "
                            f"{sm.InfotainmentStateMachine.state_name(target_edge.to_state)}",
                covers=covered_pairs,
            )
            sequences.append(seq)
            current_state = sim_state

        return sequences

    def _boot_sequence(self) -> TestSequence:
        """Standard boot-up sequence."""
        ctx_event = sm.Event.POWER_ON
        seq = TestSequence(
            events=[ctx_event],
            start_state=sm.State.BOOT,
            description="Boot sequence",
        )
        self.graph.mark_covered(sm.State.BOOT, sm.State.HOME, ctx_event)
        seq.covers.append((sm.State.BOOT, sm.State.HOME))
        return seq

    def _reset_to_home(self, state: object) -> Optional[List[object]]:
        return self._bfs_path(state, sm.State.HOME)

    def _pick_best_edge(self, uncovered: List[TransitionEdge],
                        current_state: object) -> TransitionEdge:
        """Prefer edges whose source has many uncovered outgoing transitions."""
        def score(e: TransitionEdge) -> int:
            src_uncovered = sum(1 for oe in self.graph.adj.get(e.from_state, [])
                                if not oe.covered)
            # Prefer edges closest to current state (0 = already there)
            path = self._bfs_path(current_state, e.from_state)
            dist = len(path) if path is not None else 9999
            return src_uncovered * 100 - dist

        return max(uncovered, key=score)

    @property
    def total_transitions(self) -> int:
        return self.graph.total_edges

    @property
    def current_coverage(self) -> float:
        return self.graph.coverage

    def coverage_report(self) -> str:
        covered = self.graph.covered_edges
        total = self.graph.total_edges
        pct = 100.0 * covered / total if total else 100.0
        return (f"Transition coverage: {covered}/{total} ({pct:.1f}%) "
                f"[target: {self.target_coverage*100:.0f}%]")
