# Autonomous Validation Agent — Infotainment UI Test Platform

> Python · C++ · pybind11 · FastAPI · SQLite · pytest

An autonomous test and validation platform for a **61-state C++ vehicle-infotainment state machine** exposed to Python via pybind11. Enforces safety guards (speed-locked controls, reverse-only park assist, device-presence checks, mutual-exclusion modal states) through a layered approach: formal invariant checking, model-based test generation, adversarial fuzzing with delta debugging, and a live interactive dashboard backed by a SQLite transition log.

---

## Architecture

```
.
├── cpp/
│   ├── include/infotainment_sm.h      # State (61) / Event (73) enums, VehicleContext, SM class
│   └── src/
│       ├── infotainment_sm.cpp        # 217 transitions, 10 named guard functions
│       └── bindings.cpp               # pybind11 module — full SM exposed to Python
├── python/
│   ├── model_based_generator.py       # BFS generator → 100% transition coverage
│   ├── invariant_checker.py           # 10 named safety invariants checked after every step
│   ├── fuzzer.py                      # Random-walk fuzzer: permissive / random / adversarial
│   ├── delta_debugger.py              # ddmin (Zeller 1999) — 250-step → 4-step minimal repro
│   ├── state_renderer.py              # PIL renderer: 480×270 PNG mockups for visual regression
│   ├── server.py                      # FastAPI REST + WebSocket dashboard server
│   └── transition_logger.py          # SQLite-backed transition log (timestamp, state, context)
├── static/
│   └── index.html                     # Live dashboard — automotive dark theme, WebSocket feed
├── tests/
│   ├── conftest.py                    # Shared fixtures (machine, permissive_ctx, checker)
│   ├── test_unit.py                   # 50 unit tests for individual transitions & guards
│   ├── test_integration.py            # Model-based sequences + 100% coverage assertion
│   ├── test_fuzz.py                   # Fuzz campaigns + delta-debugger end-to-end test
│   ├── test_visual_regression.py      # 61 state PNGs — pixel-threshold diffing
│   └── test_invariants_direct.py      # 76 direct invariant tests (boundary, message, API)
├── .github/workflows/ci.yml           # 5-job pipeline: build → test → flaky → mutmut → coverage
├── demo.py                            # Standalone demo — guards & mutual exclusion in action
├── CMakeLists.txt
└── requirements.txt
```

### State machine subsystems (61 states · 73 events · 217 transitions)

| Subsystem      | States                                                        | Guard(s)                           |
|----------------|---------------------------------------------------------------|------------------------------------|
| Boot / Home    | BOOT, HOME                                                    | `engine_running`                   |
| Radio          | RADIO_HOME, FM, AM, DAB, PRESETS, SCAN, INFO                  | `dab_available`                    |
| Navigation     | NAV_HOME, MAP, ROUTE_PLAN, DEST_INPUT, TURN_BY_TURN, POI, FAV | **`speed ≤ 5 km/h`**               |
| Phone          | PHONE_HOME, DIALING, INCALL, INCOMING, CONTACTS, RECENT, VM   | `phone_connected`                  |
| Media          | MEDIA_HOME, USB, USB_BROWSE, BT_AUDIO, STREAMING, AUX, CARPLAY, AA | device-specific              |
| Settings       | SETTINGS_HOME + 8 sub-pages                                   | **`speed ≤ 5 km/h`**               |
| Climate        | CLIMATE_HOME, ZONES, SEAT_HEAT, STEERING_HEAT, VENTILATION    | —                                  |
| Park Assist    | PARK_REAR, PARK_FRONT, PARK_360                               | **`in_reverse`**                   |
| Vehicle Info   | VEHICLE_HOME, FUEL, TRIP, TIRES                               | —                                  |
| Apps           | APPS_HOME, SPOTIFY, GOOGLE_MAPS                               | `streaming_connected`              |
| Modal overlays | NOTIFICATION, **VOICE_ASSISTANT**, CHARGING, DRIVER, AMBIENT, ERROR | `ev_plugged_in`, **`no_active_call`** |

The `no_active_call` guard on every VOICE_ASSISTANT entry transition enforces mutual exclusion with PHONE_INCALL. `call_active` is automatically synced on PHONE_INCALL entry/exit inside `transition()`.

---

## Building

### Prerequisites

| Tool          | Version |
|---------------|---------|
| CMake         | ≥ 3.15  |
| C++ compiler  | C++17   |
| Python        | ≥ 3.9   |
| pybind11      | ≥ 2.11  |

```bash
pip install -r requirements.txt

cmake -S . -B build -DPython3_EXECUTABLE=$(which python3)
cmake --build build --parallel

python3 -c "import infotainment_sm as sm; print(sm.InfotainmentStateMachine.all_state_names()[:3], '...')"
```

---

## Quick Demo

Run the standalone demo — no server required:

```bash
python demo.py
```

Output (abridged):

```
  Autonomous Validation Agent — Infotainment SM Demo
────────────────────────────────────────────────────────────────────────────────────────
#    Event                      From                      To                        Result
────────────────────────────────────────────────────────────────────────────────────────
  0    POWER_ON                   BOOT                      HOME                      ✓  OK
  1    SELECT_RADIO               HOME                      RADIO_HOME                ✓  OK
 ...
 11    SELECT_SETTINGS            HOME                      HOME                      ✗  BLOCKED  # speed guard
 12    SELECT_SETTINGS            HOME                      SETTINGS_HOME             ✓  OK
 ...
 17    ACTIVATE_VOICE             PHONE_INCALL              PHONE_INCALL              ✗  BLOCKED  # mutual-exclusion
 ...
 20    ACTIVATE_VOICE             HOME                      VOICE_ASSISTANT           ✓  OK
 ...
 22    SELECT_PARK_ASSIST         HOME                      HOME                      ✗  BLOCKED  # reverse guard
 23    SELECT_PARK_ASSIST         HOME                      PARK_ASSIST_REAR          ✓  OK

  All 10 safety invariants satisfied across every step.
```

---

## Live Dashboard

A FastAPI server exposes the state machine over REST + WebSocket and serves an interactive dashboard.

```bash
uvicorn python.server:app --reload
# Open http://localhost:8000
```

**Dashboard features:**
- Current state displayed with subsystem colour coding (blue = Radio, green = Nav, teal = Phone …)
- Event buttons — highlighted when the guard passes for the current context, greyed when blocked
- Context controls — speed slider (turns red above 5 km/h), device-presence checkboxes
- Live transition log fed by WebSocket
- Footer stats: total transitions, guard-blocked attempts, unique states reached

**REST API:**

| Method | Path                    | Description                                  |
|--------|-------------------------|----------------------------------------------|
| GET    | `/api/state`            | Current state name + integer value           |
| GET    | `/api/context`          | Full vehicle context as JSON                 |
| POST   | `/api/context`          | Patch one or more context fields             |
| GET    | `/api/valid_events`     | Events whose guards pass right now           |
| POST   | `/api/event/{name}`     | Fire an event; returns from/to/success       |
| POST   | `/api/reset`            | Reset machine to BOOT                        |
| GET    | `/api/history?limit=50` | Recent transitions from SQLite               |
| GET    | `/api/stats`            | Aggregate counts from SQLite                 |
| WS     | `/ws`                   | Real-time transition stream                  |

Every event fired through the API is persisted to `transitions.db` with timestamp, states, event name, success flag, and a context snapshot.

---

## Running Tests

```bash
# Full suite (216 tests)
pytest tests/ -v

# Unit tests
pytest tests/test_unit.py -v

# Integration — model-based sequences + 100% coverage gate
pytest tests/test_integration.py -v

# Fuzz + delta debugger
pytest tests/test_fuzz.py -v

# Visual regression — generate baselines first
pytest tests/test_visual_regression.py --generate-baseline
pytest tests/test_visual_regression.py -v

# Invariant checker — 76 boundary & message tests
pytest tests/test_invariants_direct.py -v

# Flaky-test detection (3× repetition)
pytest tests/test_unit.py --count=3 -v
```

---

## Model-Based Generator

```python
from python.model_based_generator import ModelBasedGenerator

gen = ModelBasedGenerator(target_coverage=0.90)
sequences = gen.generate_sequences()
print(gen.coverage_report())
# Transition coverage: 217/217 (100.0%) [target: 90%]
```

The generator drives a **real SM instance** — not a graph simulation — ensuring guards are evaluated as the machine executes. A greedy BFS heuristic prioritises source states with the most uncovered outgoing edges; four passes over uncovered edges achieve complete coverage.

---

## Fuzzer + Delta Debugger

```python
from python.fuzzer import Fuzzer
from python.delta_debugger import DeltaDebugger, build_predicate

fuzzer = Fuzzer(max_steps=250, context_mode="adversarial")
_, failing = fuzzer.run_campaign(num_runs=500)

if failing:
    dbg = DeltaDebugger()
    minimal, report = dbg.minimize_and_report(failing[0].sequence, build_predicate())
    print(report)
    # Reduced a 250-step sequence to 4 steps (98.4% reduction)
```

The delta debugger implements Zeller's **ddmin** algorithm: bisect the sequence, test each half, recurse on whichever half still satisfies the predicate, repeat until 1-minimal.

---

## Invariant Checker

Ten named safety invariants are checked after every state transition:

| Invariant          | Description                                                    |
|--------------------|----------------------------------------------------------------|
| `speed_lock`       | Speed-locked states unreachable above 5 km/h                   |
| `reverse_only`     | Park-assist states only reachable in reverse gear              |
| `phone_connected`  | Phone states require a connected device                        |
| `carplay`          | CarPlay state requires active CarPlay session                  |
| `android_auto`     | Android Auto state requires connection                         |
| `usb_connected`    | USB media states require USB device                            |
| `aux_connected`    | AUX state requires cable                                       |
| `ev_plugged_in`    | Charging status screen requires EV plugged in                  |
| `mutual_exclusion` | VOICE_ASSISTANT unreachable while call_active=True             |
| `valid_state`      | Machine is in a known, named state                             |

---

## CI/CD Pipeline

Five jobs run on every push and PR:

```
build ──→ test ─────────────────────────────┐
          │→ flaky-detection                │ parallel after build
          │→ mutation-testing (≥88% gate)   │
          └→ coverage-gate (≥90% gate) ─────┘
```

| Job                 | Gate                                         |
|---------------------|----------------------------------------------|
| **build**           | C++ compiles, pybind11 module loads          |
| **test**            | All 216 pytest tests pass                    |
| **flaky-detection** | No test shows mixed pass/fail across 3 runs  |
| **mutation-testing**| mutmut kill rate ≥ 88%                       |
| **coverage-gate**   | Transition coverage ≥ 90%                    |

Visual regression diffs are uploaded as CI artifacts on failure.

---

## Verified Results

All numbers below are from real runs on this machine (Python 3.9.6, Apple clang 21.0, pybind11 3.0.4). See [RESULTS.md](RESULTS.md) for reproduction commands.

| Metric                      | Result                                |
|-----------------------------|---------------------------------------|
| Test suite                  | **216 / 216 passed** in 1.10 s        |
| Transition coverage         | **217 / 217 (100.0%)** [gate: ≥ 90%] |
| Fuzz — permissive           | 1 000 runs × 250 steps → 0 violations |
| Fuzz — adversarial          | 500 runs × 250 steps → 72 context violations detected |
| Delta debug reduction       | **250 steps → 4 steps (98.4%)**       |
| Mutation kill rate          | **81 / 88 (92.0%)** [gate: ≥ 88%]    |

---

## License

MIT
