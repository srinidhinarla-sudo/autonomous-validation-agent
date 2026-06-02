# Verified Test Results

All numbers below come from actual runs on this machine (Python 3.9.6, Apple clang 21.0, pybind11 3.0.4).

---

## Build

```
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 4
```

```
States     : 61
Events     : 73
Transitions: 217
Boot→HOME  : OK
```

---

## Test Suite — 216 / 216 passed (1.10 s)

```
tests/test_unit.py                  50 passed
tests/test_integration.py           12 passed
tests/test_fuzz.py                  13 passed
tests/test_visual_regression.py     65 passed  (61 state PNGs)
tests/test_invariants_direct.py     76 passed
─────────────────────────────────────────────
Total                               216 passed   0 failed   0 errors
```

---

## Transition Coverage

```
$ python3 -c "from python.model_based_generator import ModelBasedGenerator; \
              g=ModelBasedGenerator(); g.generate_sequences(); print(g.coverage_report())"

Transition coverage: 217/217 (100.0%) [target: 90%]
Sequences generated: 215
```

---

## Fuzz Campaign

```
Permissive (1 000 runs × 250 steps): 0 violations
Adversarial (500 runs × 250 steps) : 72 context-violation events detected
```

---

## Delta Debugging — 250 steps → 4 steps (98.4% reduction)

```
Delta-debugging report
  Original length : 250 steps
  Minimal length  : 4 steps
  Reduction       : 98.4%
  Minimal sequence:
    [0] POWER_ON
    [1] CALL_INITIATE
    [2] CALL_ANSWER
    [3] CALL_END
  Still fails: True
```

---

## Mutation Testing (invariant_checker.py)

```
Total mutants  : 88
Killed (🎉)    : 81
Survived (🙁)  : 7   ← all genuinely unkillable (import-guard & unused defaults)
Kill rate      : 92.0%   [gate: ≥88%]
```

Surviving mutants are structurally unkillable:
- `_SM_AVAILABLE = False` path (requires breaking the import to test)
- `sequence_step: int = 0` dataclass default (always overridden by `check(step=…)`)
- One unreachable `check_valid_state` error string
