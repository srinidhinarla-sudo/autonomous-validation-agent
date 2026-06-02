# Autonomous Validation Agent — Infotainment UI Test Platform

> Python · C++ · pybind11 · pytest | December 2025 – February 2026

An autonomous test platform for a **60-state C++ vehicle-infotainment state machine** exposed to Python via pybind11, enforcing safety guards like speed-locked controls and mutually exclusive modal states.

---

## Architecture

```
.
├── cpp/
│   ├── include/infotainment_sm.h      # State/Event enums, VehicleContext, SM class
│   └── src/
│       ├── infotainment_sm.cpp        # 160+ transitions, guard implementations
│       └── bindings.cpp               # pybind11 module definition
├── python/
│   ├── model_based_generator.py       # BFS-based generator → ≥90 % transition coverage
│   ├── invariant_checker.py           # Safety invariant suite (9 named invariants)
│   ├── fuzzer.py                      # Random-walk fuzzer, 3 context modes
│   ├── delta_debugger.py              # ddmin — reduces N-step failures to minimal repro
│   └── state_renderer.py              # PIL-based PNG mockup renderer for visual regression
├── tests/
│   ├── conftest.py                    # Shared fixtures (machine, permissive_ctx, checker)
│   ├── test_unit.py                   # 50+ unit tests for individual transitions & guards
│   ├── test_integration.py            # Model-based generated sequences + completeness
│   ├── test_fuzz.py                   # Fuzz campaigns + delta debugger tests
│   └── test_visual_regression.py      # Screenshot diffing, pixel-threshold gating
├── .github/workflows/ci.yml           # 5-job pipeline: build → test → flaky → mutmut → coverage
├── CMakeLists.txt                     # cmake build for C++ lib + pybind11 extension
├── requirements.txt
└── README.md
```

### State machine subsystems (60 states total)

| Subsystem     | States                                                       | Guards                        |
|---------------|--------------------------------------------------------------|-------------------------------|
| Boot/Home     | BOOT, HOME                                                   | `engine_running`              |
| Radio         | RADIO_HOME, FM, AM, DAB, PRESETS, SCAN, INFO                 | `dab_available`               |
| Navigation    | NAV_HOME, MAP, ROUTE_PLAN, DEST_INPUT, TURN_BY_TURN, POI, FAV | **`speed ≤ 5 km/h`**        |
| Phone         | PHONE_HOME, DIALING, INCALL, INCOMING, CONTACTS, RECENT, VM  | `phone_connected`             |
| Media         | MEDIA_HOME, USB, USB_BROWSE, BT_AUDIO, STREAMING, AUX, CARPLAY, AA | device-specific guards  |
| Settings      | SETTINGS_HOME + 8 sub-pages                                  | **`speed ≤ 5 km/h`**        |
| Climate       | CLIMATE_HOME, ZONES, SEAT_HEAT, STEERING_HEAT, VENTILATION   | none                          |
| Park Assist   | PARK_REAR, PARK_FRONT, PARK_360                              | **`in_reverse`**             |
| Vehicle Info  | VEHICLE_HOME, FUEL, TRIP, TIRES                              | none                          |
| Apps          | APPS_HOME, SPOTIFY, GOOGLE_MAPS                              | `streaming_connected`         |
| Modal overlays| NOTIFICATION_CENTER, VOICE_ASSISTANT, CHARGING, DRIVER_PROFILE, AMBIENT, ERROR | `ev_plugged_in` |

---

## Building

### Prerequisites

| Tool          | Version  |
|---------------|----------|
| CMake         | ≥ 3.15   |
| C++ compiler  | C++17    |
| Python        | ≥ 3.9    |
| pybind11      | ≥ 2.11   |

### Build steps

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure and build the C++ extension
cmake -S . -B build -DPython3_EXECUTABLE=$(which python3)
cmake --build build --parallel

# 3. Verify
python3 -c "import infotainment_sm as sm; print(int(sm.State.STATE_COUNT), 'states')"
```

The `infotainment_sm.cpython-*.so` module is placed in the project root so
`import infotainment_sm` works from any test or script without installation.

---

## Running Tests

```bash
# Full suite
pytest tests/ -v

# Unit tests only
pytest tests/test_unit.py -v

# Integration (model-based + completeness)
pytest tests/test_integration.py -v

# Fuzz + delta debugger
pytest tests/test_fuzz.py -v

# Visual regression — generate baselines first
pytest tests/test_visual_regression.py --generate-baseline
pytest tests/test_visual_regression.py -v

# Flaky-test detection (3× repetition)
pip install pytest-repeat
pytest tests/test_unit.py --count=3 -v
```

---

## Model-Based Generator

```python
from python.model_based_generator import ModelBasedGenerator

gen = ModelBasedGenerator(target_coverage=0.90)
sequences = gen.generate_sequences()
print(gen.coverage_report())
# Transition coverage: 148/160 (92.5%) [target: 90%]
```

The generator builds a directed graph from `get_all_transitions()` and uses
a greedy BFS heuristic (prioritises source states with the most uncovered
outgoing edges) to produce a minimal set of sequences reaching the target.

---

## Fuzzer + Delta Debugger

```python
from python.fuzzer import Fuzzer
from python.delta_debugger import DeltaDebugger, build_predicate

fuzzer  = Fuzzer(max_steps=250, context_mode="adversarial")
_, failing = fuzzer.run_campaign(num_runs=1000)

if failing:
    dbg      = DeltaDebugger()
    pred     = build_predicate()
    minimal, report = dbg.minimize_and_report(failing[0].sequence, pred)
    print(report)
    # Reduced a 250-step sequence to 4 steps
```

The delta debugger implements Zeller's **ddmin** algorithm (1999): it
bisects the failing sequence, tests each half, and recurses on whichever
half still satisfies the predicate — achieving ≥50 % reduction per pass.

---

## Invariant Checker

Nine named safety invariants are checked after every state transition:

| Invariant         | Description                                                   |
|-------------------|---------------------------------------------------------------|
| `speed_lock`      | Speed-locked states unreachable above 5 km/h                  |
| `reverse_only`    | Park-assist states only reachable in reverse gear             |
| `phone_connected` | Phone states require a connected device                       |
| `carplay`         | CarPlay state requires active CarPlay session                 |
| `android_auto`    | Android Auto state requires connection                        |
| `usb_connected`   | USB media states require USB device                           |
| `aux_connected`   | AUX state requires cable                                      |
| `ev_plugged_in`   | Charging status screen requires EV plugged in                 |
| `valid_state`     | Machine is in a known, named state                            |

---

## CI/CD Pipeline

Five jobs run on every push and PR:

```
build → test ──────────────────────────────┐
            → flaky-detection              │ all run in parallel after build
            → mutation-testing             │
            → coverage-gate ───────────────┘
```

| Job                 | Gate                               |
|---------------------|------------------------------------|
| **build**           | C++ compiles + module loads        |
| **test**            | All pytest suites pass             |
| **flaky-detection** | No test shows mixed pass/fail      |
| **mutation-testing**| mutmut kill rate ≥ 88 %            |
| **coverage-gate**   | Transition coverage ≥ 90 %         |

Visual regression diffs are uploaded as artifacts on failure.

---

## Results (from portfolio)

- Model-based generator reaches **90 %+ transition coverage** across all subsystems.
- Invariant-checking fuzzer with delta debugging reduced a **250-step failing sequence to a 4-step minimal repro**.
- Surfaced **3 defects**, including one reported upstream in an open-source project.
- Mutation testing gate kills **~88 % of mutants** across the Python test layer.

---

## License

MIT
