"""
Direct unit tests for InvariantChecker — designed for high mutant kill rate.

These tests inject (state, context) pairs that are at exact guard boundaries
and verify the checker's Python-level condition code, not just the C++ SM.
"""

import pytest

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _SM_AVAILABLE,
    reason="infotainment_sm C++ module not built")


def make_ctx(**kwargs):
    ctx = sm.VehicleContext()
    ctx.engine_running = True
    for k, v in kwargs.items():
        setattr(ctx, k, v)
    return ctx


@pytest.fixture
def checker():
    from python.invariant_checker import InvariantChecker
    return InvariantChecker()


# ---- speed_lock invariant ---------------------------------------------------

class TestSpeedLockInvariant:
    @pytest.mark.parametrize("speed,state,expect_violation", [
        (5.0,  sm.State.NAV_ROUTE_PLAN,  False),  # exactly at limit — should pass
        (5.01, sm.State.NAV_ROUTE_PLAN,  True),   # just over limit — violation
        (0.0,  sm.State.NAV_ROUTE_PLAN,  False),
        (5.0,  sm.State.NAV_DESTINATION_INPUT, False),
        (6.0,  sm.State.NAV_DESTINATION_INPUT, True),
        (100.0,sm.State.SETTINGS_HOME,   True),
        (4.9,  sm.State.SETTINGS_DISPLAY,False),
        (5.1,  sm.State.SETTINGS_DISPLAY,True),
        (5.0,  sm.State.SETTINGS_SOUND,  False),
        (5.1,  sm.State.SETTINGS_SOUND,  True),
        (0.0,  sm.State.HOME,            False),  # HOME is not speed-locked
        (200.0,sm.State.HOME,            False),  # HOME at any speed is fine
        (5.1,  sm.State.NAV_POI_SEARCH,  True),
        (5.0,  sm.State.NAV_POI_SEARCH,  False),
    ])
    def test_speed_boundary(self, checker, speed, state, expect_violation):
        ctx = make_ctx(speed_kmh=speed)
        checker.check(state, ctx, step=0)
        violations = [v for v in checker.violations if v.invariant_name == "speed_lock"]
        checker.clear()
        assert bool(violations) == expect_violation, (
            f"speed={speed} state={sm.state_name(state)}: "
            f"expected violation={expect_violation}, got {bool(violations)}"
        )

    def test_all_speed_locked_states_fire_above_5(self, checker):
        from python.invariant_checker import InvariantChecker
        speed_locked = [
            sm.State.NAV_ROUTE_PLAN, sm.State.NAV_DESTINATION_INPUT,
            sm.State.NAV_POI_SEARCH,
            sm.State.SETTINGS_HOME, sm.State.SETTINGS_DISPLAY,
            sm.State.SETTINGS_SOUND, sm.State.SETTINGS_CONNECTIVITY,
            sm.State.SETTINGS_VEHICLE, sm.State.SETTINGS_LANGUAGE,
            sm.State.SETTINGS_CLOCK, sm.State.SETTINGS_PRIVACY,
            sm.State.SETTINGS_DIAGNOSTICS,
        ]
        ctx = make_ctx(speed_kmh=10.0)
        for state in speed_locked:
            c = InvariantChecker()
            c.check(state, ctx)
            assert c.has_violations(), f"{sm.state_name(state)} should fire at 10 km/h"


# ---- reverse_only invariant ------------------------------------------------

class TestReverseOnlyInvariant:
    @pytest.mark.parametrize("in_reverse,state,expect_violation", [
        (False, sm.State.PARK_ASSIST_REAR,  True),
        (True,  sm.State.PARK_ASSIST_REAR,  False),
        (False, sm.State.PARK_ASSIST_FRONT, True),
        (True,  sm.State.PARK_ASSIST_FRONT, False),
        (False, sm.State.PARK_ASSIST_360,   True),
        (True,  sm.State.PARK_ASSIST_360,   False),
        (False, sm.State.HOME,              False),  # HOME not reverse-locked
        (True,  sm.State.HOME,              False),
    ])
    def test_reverse_boundary(self, checker, in_reverse, state, expect_violation):
        ctx = make_ctx(in_reverse=in_reverse)
        checker.check(state, ctx)
        violations = [v for v in checker.violations if v.invariant_name == "reverse_only"]
        checker.clear()
        assert bool(violations) == expect_violation


# ---- phone_connected invariant ---------------------------------------------

class TestPhoneConnectedInvariant:
    PHONE_STATES = [
        sm.State.PHONE_DIALING, sm.State.PHONE_INCALL, sm.State.PHONE_INCOMING,
        sm.State.PHONE_CONTACTS, sm.State.PHONE_RECENT_CALLS, sm.State.PHONE_VOICEMAIL,
    ]

    @pytest.mark.parametrize("state", [
        sm.State.PHONE_DIALING, sm.State.PHONE_INCALL, sm.State.PHONE_INCOMING,
        sm.State.PHONE_CONTACTS, sm.State.PHONE_RECENT_CALLS, sm.State.PHONE_VOICEMAIL,
    ])
    def test_phone_state_without_connection_fires(self, checker, state):
        ctx = make_ctx(phone_connected=False)
        checker.check(state, ctx)
        violations = [v for v in checker.violations if v.invariant_name == "phone_connected"]
        assert violations, f"{sm.state_name(state)} should violate phone_connected"
        checker.clear()

    @pytest.mark.parametrize("state", [
        sm.State.PHONE_DIALING, sm.State.PHONE_INCALL,
    ])
    def test_phone_state_with_connection_passes(self, checker, state):
        ctx = make_ctx(phone_connected=True)
        checker.check(state, ctx)
        violations = [v for v in checker.violations if v.invariant_name == "phone_connected"]
        assert not violations


# ---- carplay / android_auto / usb / aux / ev invariants --------------------

class TestDeviceInvariants:
    def test_carplay_without_connection(self, checker):
        ctx = make_ctx(carplay_connected=False)
        checker.check(sm.State.MEDIA_CARPLAY, ctx)
        assert any(v.invariant_name == "carplay" for v in checker.violations)

    def test_carplay_with_connection(self, checker):
        ctx = make_ctx(carplay_connected=True)
        checker.check(sm.State.MEDIA_CARPLAY, ctx)
        assert not any(v.invariant_name == "carplay" for v in checker.violations)

    def test_android_auto_without_connection(self, checker):
        ctx = make_ctx(android_auto_connected=False)
        checker.check(sm.State.MEDIA_ANDROID_AUTO, ctx)
        assert any(v.invariant_name == "android_auto" for v in checker.violations)

    def test_android_auto_with_connection(self, checker):
        ctx = make_ctx(android_auto_connected=True)
        checker.check(sm.State.MEDIA_ANDROID_AUTO, ctx)
        assert not any(v.invariant_name == "android_auto" for v in checker.violations)

    @pytest.mark.parametrize("state", [sm.State.MEDIA_USB, sm.State.MEDIA_USB_BROWSE])
    def test_usb_states_without_device(self, checker, state):
        ctx = make_ctx(usb_connected=False)
        checker.check(state, ctx)
        assert any(v.invariant_name == "usb_connected" for v in checker.violations)
        checker.clear()

    @pytest.mark.parametrize("state", [sm.State.MEDIA_USB, sm.State.MEDIA_USB_BROWSE])
    def test_usb_states_with_device(self, checker, state):
        ctx = make_ctx(usb_connected=True)
        checker.check(state, ctx)
        assert not any(v.invariant_name == "usb_connected" for v in checker.violations)
        checker.clear()

    def test_aux_without_cable(self, checker):
        ctx = make_ctx(aux_connected=False)
        checker.check(sm.State.MEDIA_AUX, ctx)
        assert any(v.invariant_name == "aux_connected" for v in checker.violations)

    def test_aux_with_cable(self, checker):
        ctx = make_ctx(aux_connected=True)
        checker.check(sm.State.MEDIA_AUX, ctx)
        assert not any(v.invariant_name == "aux_connected" for v in checker.violations)

    def test_charging_without_ev(self, checker):
        ctx = make_ctx(ev_plugged_in=False)
        checker.check(sm.State.CHARGING_STATUS, ctx)
        assert any(v.invariant_name == "ev_plugged_in" for v in checker.violations)

    def test_charging_with_ev(self, checker):
        ctx = make_ctx(ev_plugged_in=True)
        checker.check(sm.State.CHARGING_STATUS, ctx)
        assert not any(v.invariant_name == "ev_plugged_in" for v in checker.violations)


# ---- mutual_exclusion invariant --------------------------------------------

class TestMutualExclusionInvariant:
    def test_voice_during_call_fires(self, checker):
        ctx = make_ctx(call_active=True)
        checker.check(sm.State.VOICE_ASSISTANT, ctx)
        assert any(v.invariant_name == "mutual_exclusion" for v in checker.violations)

    def test_voice_without_call_passes(self, checker):
        ctx = make_ctx(call_active=False)
        checker.check(sm.State.VOICE_ASSISTANT, ctx)
        assert not any(v.invariant_name == "mutual_exclusion" for v in checker.violations)

    def test_phone_incall_without_voice_passes(self, checker):
        ctx = make_ctx(call_active=True, phone_connected=True)
        checker.check(sm.State.PHONE_INCALL, ctx)
        assert not any(v.invariant_name == "mutual_exclusion" for v in checker.violations)

    def test_home_with_call_active_passes(self, checker):
        """HOME state should never trigger mutual exclusion even if call_active is set."""
        ctx = make_ctx(call_active=True)
        checker.check(sm.State.HOME, ctx)
        assert not any(v.invariant_name == "mutual_exclusion" for v in checker.violations)


# ---- InvariantChecker API --------------------------------------------------

class TestInvariantCheckerAPI:
    def test_check_returns_true_when_no_violations(self, checker):
        ctx = make_ctx()
        result = checker.check(sm.State.HOME, ctx)
        assert result is True

    def test_check_returns_false_on_violation(self, checker):
        ctx = make_ctx(speed_kmh=100.0)
        result = checker.check(sm.State.SETTINGS_HOME, ctx)
        assert result is False

    def test_has_violations_false_initially(self, checker):
        assert not checker.has_violations()

    def test_has_violations_true_after_violation(self, checker):
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx)
        assert checker.has_violations()

    def test_clear_resets_violations(self, checker):
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx)
        checker.clear()
        assert not checker.has_violations()

    def test_assert_no_violations_raises_on_violation(self, checker):
        ctx = make_ctx(speed_kmh=999.0)
        checker.check(sm.State.SETTINGS_HOME, ctx)
        with pytest.raises(AssertionError) as exc:
            checker.assert_no_violations()
        assert "speed_lock" in str(exc.value)

    def test_assert_no_violations_passes_when_clean(self, checker):
        ctx = make_ctx()
        checker.check(sm.State.HOME, ctx)
        checker.assert_no_violations()  # must not raise

    def test_multiple_violations_accumulated(self, checker):
        ctx = make_ctx(speed_kmh=100.0, in_reverse=False)
        checker.check(sm.State.SETTINGS_HOME, ctx)    # speed_lock
        checker.check(sm.State.PARK_ASSIST_REAR, ctx) # reverse_only
        assert len(checker.violations) >= 2

    def test_step_number_recorded(self, checker):
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx, step=7)
        assert checker.violations[0].sequence_step == 7

    def test_summary_mentions_count(self, checker):
        ctx = make_ctx(speed_kmh=100.0)
        checker.check(sm.State.NAV_ROUTE_PLAN, ctx)
        summary = checker.summary()
        assert "1" in summary

    def test_summary_clean_message(self, checker):
        summary = checker.summary()
        assert "satisfied" in summary.lower()


# ---- Message-content tests (kill string-mutation survivors) ----------------

class TestViolationMessages:
    """Verify exact keywords in violation messages to kill mutmut string mutants."""

    def test_speed_lock_message_starts_with_speed(self, checker):
        """Kills mutants 24/25: start check + endswith check."""
        ctx = make_ctx(speed_kmh=10.0)
        checker.check(sm.State.SETTINGS_HOME, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("Speed-locked"), f"Got: {msg!r}"
        assert msg.endswith("km/h)"), f"Got: {msg!r}"  # kills mutant 25 ("XX" suffix)

    def test_speed_lock_message_contains_speed_value(self, checker):
        ctx = make_ctx(speed_kmh=42.0)
        checker.check(sm.State.NAV_ROUTE_PLAN, ctx)
        msg = checker.violations[0].message
        assert "42.0" in msg
        assert "(limit: 5 km/h)" in msg

    def test_reverse_message_starts_correctly(self, checker):
        """Kills mutants 29/30: start + end checks."""
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("Park-assist state"), f"Got: {msg!r}"
        assert msg.endswith("reverse gear"), f"Got: {msg!r}"  # kills mutant 30

    def test_phone_message_starts_correctly(self, checker):
        """Kills mutants 34/35: start + end checks."""
        ctx = make_ctx(phone_connected=False)
        checker.check(sm.State.PHONE_INCALL, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("Phone state"), f"Got: {msg!r}"
        assert msg.endswith("connected phone"), f"Got: {msg!r}"  # kills mutant 35

    def test_carplay_message_exact(self, checker):
        """Kills mutant 39."""
        ctx = make_ctx(carplay_connected=False)
        checker.check(sm.State.MEDIA_CARPLAY, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("MEDIA_CARPLAY"), f"Got: {msg!r}"
        assert "CarPlay connection" in msg

    def test_android_auto_message_exact(self, checker):
        """Kills mutant 43."""
        ctx = make_ctx(android_auto_connected=False)
        checker.check(sm.State.MEDIA_ANDROID_AUTO, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("MEDIA_ANDROID_AUTO"), f"Got: {msg!r}"
        assert "Android Auto" in msg

    def test_usb_message_exact(self, checker):
        """Kills mutant 47."""
        ctx = make_ctx(usb_connected=False)
        checker.check(sm.State.MEDIA_USB, ctx)
        msg = checker.violations[0].message
        assert "USB" in msg and not msg.startswith("XX")

    def test_aux_message_exact(self, checker):
        """Kills mutant 51."""
        ctx = make_ctx(aux_connected=False)
        checker.check(sm.State.MEDIA_AUX, ctx)
        msg = checker.violations[0].message
        assert "AUX" in msg and not msg.startswith("XX")

    def test_ev_message_exact(self, checker):
        """Kills mutant 55."""
        ctx = make_ctx(ev_plugged_in=False)
        checker.check(sm.State.CHARGING_STATUS, ctx)
        msg = checker.violations[0].message
        assert "CHARGING_STATUS" in msg and not msg.startswith("XX")

    def test_mutual_exclusion_message_starts_correctly(self, checker):
        """Kills mutants 58/59: start + end checks."""
        ctx = make_ctx(call_active=True)
        checker.check(sm.State.VOICE_ASSISTANT, ctx)
        msg = checker.violations[0].message
        assert msg.startswith("Mutual-exclusion violation"), f"Got: {msg!r}"
        assert "call_active=True" in msg
        assert msg.endswith("modal state)"), f"Got: {msg!r}"  # kills mutant 59

    def test_assert_no_violations_error_format(self, checker):
        """Kills mutants 77/79/81: check exact format of each violation line."""
        ctx = make_ctx(speed_kmh=100.0)
        checker.check(sm.State.SETTINGS_HOME, ctx, step=0)
        try:
            checker.assert_no_violations()
            assert False
        except AssertionError as e:
            err = str(e)
            assert "1 invariant violation" in err
            # Kills mutant 77: violation line must start with "  [" not "XX  ["
            assert "\n  [0] speed_lock" in err, f"Format wrong: {err!r}"

    def test_assert_no_violations_multi_line_format(self, checker):
        """Kills mutant 81: multi-violation lines must be newline-separated, not XX-joined."""
        ctx = make_ctx(speed_kmh=100.0, in_reverse=False)
        checker.check(sm.State.SETTINGS_HOME, ctx, step=0)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx, step=1)
        try:
            checker.assert_no_violations()
        except AssertionError as e:
            err = str(e)
            # Normal: "...  [0] speed_lock...\n  [1] reverse_only..."
            # Mutant 81: "...  [0]...XX\nXX  [1]..."
            assert "\n  [1] reverse_only" in err, f"Multi-line format wrong: {err!r}"

    def test_summary_with_violations_format(self, checker):
        """Kills mutants 84/86/88: exact line format in summary."""
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx, step=5)
        summary = checker.summary()
        assert summary is not None, "summary() must not return None"
        assert "1 violation" in summary
        # Kills mutant 84: line must start with "  step", not "XX  step"
        assert "\n  step 5 | reverse_only" in summary, f"Format wrong: {summary!r}"
        # Kills mutant 88: must end with message content, not be truncated
        assert summary.endswith("reverse gear"), f"Summary truncated: {summary!r}"

    def test_summary_clean_exact(self):
        """Kills mutant 83: summary must be exactly 'All invariants satisfied.'"""
        from python.invariant_checker import InvariantChecker
        c = InvariantChecker()
        result = c.summary()
        assert result is not None
        assert result == "All invariants satisfied."

    def test_invariant_names_are_correct_strings(self, checker):
        """Invariant name strings tested by triggering each and checking name."""
        for state, ctx_kwargs, expected_name in [
            (sm.State.PARK_ASSIST_REAR, {"in_reverse": False},         "reverse_only"),
            (sm.State.PHONE_INCALL,     {"phone_connected": False},     "phone_connected"),
            (sm.State.VOICE_ASSISTANT,  {"call_active": True},          "mutual_exclusion"),
            (sm.State.MEDIA_CARPLAY,    {"carplay_connected": False},   "carplay"),
            (sm.State.MEDIA_ANDROID_AUTO,{"android_auto_connected":False},"android_auto"),
            (sm.State.MEDIA_USB,        {"usb_connected": False},       "usb_connected"),
            (sm.State.MEDIA_AUX,        {"aux_connected": False},       "aux_connected"),
            (sm.State.CHARGING_STATUS,  {"ev_plugged_in": False},       "ev_plugged_in"),
        ]:
            checker.clear()
            checker.check(state, make_ctx(**ctx_kwargs))
            assert checker.violations[0].invariant_name == expected_name, \
                f"Expected {expected_name}, got {checker.violations[0].invariant_name}"


# ---- Default-value tests (kill dataclass default mutants) ------------------

class TestDefaultValues:
    def test_sequence_step_defaults_to_zero(self, checker):
        """Kills mutants 6, 7, 71: default step must be 0, not 1 or None."""
        ctx = make_ctx(in_reverse=False)
        checker.check(sm.State.PARK_ASSIST_REAR, ctx)  # no step arg → default
        assert checker.violations[0].sequence_step == 0

    def test_check_without_step_records_zero(self, checker):
        ctx = make_ctx(speed_kmh=100.0)
        checker.check(sm.State.SETTINGS_HOME, ctx)
        assert checker.violations[0].sequence_step == 0

    def test_check_with_explicit_step_records_it(self, checker):
        ctx = make_ctx(speed_kmh=100.0)
        checker.check(sm.State.SETTINGS_HOME, ctx, step=5)
        assert checker.violations[0].sequence_step == 5
