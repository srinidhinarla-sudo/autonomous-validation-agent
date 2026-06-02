"""
Unit tests — individual transitions, guard enforcement, state invariants.
"""

import pytest

try:
    import infotainment_sm as sm
    _SM_AVAILABLE = True
except ImportError:
    _SM_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _SM_AVAILABLE,
    reason="infotainment_sm C++ module not built")


# ---- Boot / power -----------------------------------------------------------

class TestBoot:
    def test_initial_state_is_boot(self, raw_machine):
        assert raw_machine.get_state() == sm.State.BOOT

    def test_power_on_requires_engine_running(self, raw_machine):
        ctx = sm.VehicleContext()
        ctx.engine_running = False
        raw_machine.set_context(ctx)
        assert not raw_machine.transition(sm.Event.POWER_ON)
        assert raw_machine.get_state() == sm.State.BOOT

    def test_power_on_with_engine_succeeds(self, raw_machine):
        ctx = sm.VehicleContext()
        ctx.engine_running = True
        raw_machine.set_context(ctx)
        assert raw_machine.transition(sm.Event.POWER_ON)
        assert raw_machine.get_state() == sm.State.HOME

    def test_power_off_returns_to_boot(self, machine):
        assert machine.get_state() == sm.State.HOME
        assert machine.transition(sm.Event.POWER_OFF)
        assert machine.get_state() == sm.State.BOOT


# ---- Radio ------------------------------------------------------------------

class TestRadio:
    def test_select_radio_from_home(self, machine):
        assert machine.transition(sm.Event.SELECT_RADIO)
        assert machine.get_state() == sm.State.RADIO_HOME

    def test_tune_fm(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition(sm.Event.TUNE_FM)
        assert machine.get_state() == sm.State.RADIO_FM

    def test_tune_am(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition(sm.Event.TUNE_AM)
        assert machine.get_state() == sm.State.RADIO_AM

    def test_tune_dab_requires_dab_available(self, machine):
        ctx = machine.get_context()
        ctx.dab_available = False
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_RADIO)
        assert not machine.transition(sm.Event.TUNE_DAB)
        assert machine.get_state() == sm.State.RADIO_HOME

    def test_tune_dab_with_hardware(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition(sm.Event.TUNE_DAB)
        assert machine.get_state() == sm.State.RADIO_DAB

    def test_back_button_from_radio_fm(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        machine.transition(sm.Event.TUNE_FM)
        assert machine.transition(sm.Event.BACK_BUTTON)
        assert machine.get_state() == sm.State.RADIO_HOME

    def test_home_button_from_radio_fm(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        machine.transition(sm.Event.TUNE_FM)
        assert machine.transition(sm.Event.HOME_BUTTON)
        assert machine.get_state() == sm.State.HOME

    def test_presets_from_radio_home(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition(sm.Event.OPEN_PRESETS)
        assert machine.get_state() == sm.State.RADIO_PRESETS

    def test_scan_from_radio_home(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition(sm.Event.START_SCAN)
        assert machine.get_state() == sm.State.RADIO_SCAN


# ---- Navigation guard tests -------------------------------------------------

class TestNavigation:
    def test_open_map_from_nav_home(self, machine):
        machine.transition(sm.Event.SELECT_NAV)
        assert machine.transition(sm.Event.OPEN_MAP)
        assert machine.get_state() == sm.State.NAV_MAP

    def test_plan_route_blocked_when_driving(self, machine):
        ctx = machine.get_context()
        ctx.speed_kmh = 60.0
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_NAV)
        assert not machine.transition(sm.Event.PLAN_ROUTE)
        assert machine.get_state() == sm.State.NAV_HOME

    def test_plan_route_allowed_when_stopped(self, machine):
        ctx = machine.get_context()
        ctx.speed_kmh = 0.0
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_NAV)
        assert machine.transition(sm.Event.PLAN_ROUTE)
        assert machine.get_state() == sm.State.NAV_ROUTE_PLAN

    def test_destination_input_blocked_above_5kmh(self, machine):
        ctx = machine.get_context()
        ctx.speed_kmh = 10.0
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_NAV)
        assert not machine.transition(sm.Event.ENTER_DESTINATION)

    def test_full_nav_flow(self, machine):
        machine.transition(sm.Event.SELECT_NAV)
        machine.transition(sm.Event.PLAN_ROUTE)
        machine.transition(sm.Event.ENTER_DESTINATION)
        assert machine.transition(sm.Event.CONFIRM_DESTINATION)
        assert machine.get_state() == sm.State.NAV_MAP

    def test_turn_by_turn_navigation(self, machine):
        machine.transition(sm.Event.SELECT_NAV)
        machine.transition(sm.Event.OPEN_MAP)
        assert machine.transition(sm.Event.START_NAVIGATION)
        assert machine.get_state() == sm.State.NAV_TURN_BY_TURN

    def test_stop_navigation(self, machine):
        machine.transition(sm.Event.SELECT_NAV)
        machine.transition(sm.Event.OPEN_MAP)
        machine.transition(sm.Event.START_NAVIGATION)
        assert machine.transition(sm.Event.STOP_NAVIGATION)
        assert machine.get_state() == sm.State.NAV_MAP


# ---- Phone ------------------------------------------------------------------

class TestPhone:
    def test_phone_requires_connection(self, machine):
        ctx = machine.get_context()
        ctx.phone_connected = False
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_PHONE)
        assert not machine.transition(sm.Event.CALL_INITIATE)

    def test_call_flow(self, machine):
        machine.transition(sm.Event.SELECT_PHONE)
        assert machine.transition(sm.Event.CALL_INITIATE)
        assert machine.get_state() == sm.State.PHONE_DIALING
        assert machine.transition(sm.Event.CALL_ANSWER)
        assert machine.get_state() == sm.State.PHONE_INCALL
        assert machine.transition(sm.Event.CALL_END)
        assert machine.get_state() == sm.State.PHONE_HOME

    def test_reject_incoming(self, machine):
        machine.transition(sm.Event.SELECT_PHONE)
        machine.transition(sm.Event.INCOMING_CALL)
        assert machine.get_state() == sm.State.PHONE_INCOMING
        assert machine.transition(sm.Event.CALL_REJECT)
        assert machine.get_state() == sm.State.PHONE_HOME

    def test_incoming_call_interrupt_from_radio(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        machine.transition(sm.Event.TUNE_FM)
        assert machine.transition(sm.Event.INCOMING_CALL)
        assert machine.get_state() == sm.State.PHONE_INCOMING


# ---- Media ------------------------------------------------------------------

class TestMedia:
    def test_usb_requires_device(self, machine):
        ctx = machine.get_context()
        ctx.usb_connected = False
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_MEDIA)
        assert not machine.transition(sm.Event.SELECT_USB)

    def test_usb_browse(self, machine):
        machine.transition(sm.Event.SELECT_MEDIA)
        assert machine.transition(sm.Event.SELECT_USB)
        assert machine.transition(sm.Event.USB_BROWSE)
        assert machine.get_state() == sm.State.MEDIA_USB_BROWSE
        assert machine.transition(sm.Event.USB_ROOT)
        assert machine.get_state() == sm.State.MEDIA_USB

    def test_carplay_requires_connection(self, machine):
        ctx = machine.get_context()
        ctx.carplay_connected = False
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_MEDIA)
        assert not machine.transition(sm.Event.SELECT_CARPLAY)

    def test_android_auto_requires_connection(self, machine):
        ctx = machine.get_context()
        ctx.android_auto_connected = False
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_MEDIA)
        assert not machine.transition(sm.Event.SELECT_ANDROID_AUTO)

    def test_bluetooth_audio_no_guard(self, machine):
        machine.transition(sm.Event.SELECT_MEDIA)
        assert machine.transition(sm.Event.SELECT_BLUETOOTH_AUDIO)
        assert machine.get_state() == sm.State.MEDIA_BLUETOOTH_AUDIO


# ---- Settings (speed-locked) ------------------------------------------------

class TestSettings:
    def test_settings_locked_while_driving(self, machine):
        ctx = machine.get_context()
        ctx.speed_kmh = 30.0
        machine.set_context(ctx)
        assert not machine.transition(sm.Event.SELECT_SETTINGS)

    def test_settings_accessible_when_stopped(self, machine):
        assert machine.transition(sm.Event.SELECT_SETTINGS)
        assert machine.get_state() == sm.State.SETTINGS_HOME

    def test_all_settings_sub_pages_speed_locked(self, machine):
        machine.transition(sm.Event.SELECT_SETTINGS)
        ctx = machine.get_context()
        ctx.speed_kmh = 20.0
        machine.set_context(ctx)
        for event in [
            sm.Event.OPEN_DISPLAY_SETTINGS,
            sm.Event.OPEN_SOUND_SETTINGS,
            sm.Event.OPEN_CONNECTIVITY,
        ]:
            assert not machine.transition(event), f"{sm.event_name(event)} should be blocked"

    def test_display_settings(self, machine):
        machine.transition(sm.Event.SELECT_SETTINGS)
        assert machine.transition(sm.Event.OPEN_DISPLAY_SETTINGS)
        assert machine.get_state() == sm.State.SETTINGS_DISPLAY
        machine.transition(sm.Event.BACK_BUTTON)
        assert machine.get_state() == sm.State.SETTINGS_HOME


# ---- Park Assist (reverse-locked) -------------------------------------------

class TestParkAssist:
    def test_park_assist_blocked_when_not_in_reverse(self, machine):
        ctx = machine.get_context()
        ctx.in_reverse = False
        machine.set_context(ctx)
        assert not machine.transition(sm.Event.SELECT_PARK_ASSIST)

    def test_park_assist_in_reverse(self, machine):
        ctx = machine.get_context()
        ctx.in_reverse = True
        machine.set_context(ctx)
        assert machine.transition(sm.Event.SELECT_PARK_ASSIST)
        assert machine.get_state() == sm.State.PARK_ASSIST_REAR

    def test_360_assist_from_rear(self, machine):
        ctx = machine.get_context()
        ctx.in_reverse = True
        machine.set_context(ctx)
        machine.transition(sm.Event.SELECT_PARK_ASSIST)
        assert machine.transition(sm.Event.ACTIVATE_360_ASSIST)
        assert machine.get_state() == sm.State.PARK_ASSIST_360


# ---- Modal overlays ---------------------------------------------------------

class TestModals:
    def test_notifications(self, machine):
        assert machine.transition(sm.Event.OPEN_NOTIFICATIONS)
        assert machine.get_state() == sm.State.NOTIFICATION_CENTER
        assert machine.transition(sm.Event.CLOSE_NOTIFICATIONS)
        assert machine.get_state() == sm.State.HOME

    def test_voice_assistant(self, machine):
        assert machine.transition(sm.Event.ACTIVATE_VOICE)
        assert machine.get_state() == sm.State.VOICE_ASSISTANT
        assert machine.transition(sm.Event.DEACTIVATE_VOICE)
        assert machine.get_state() == sm.State.HOME

    def test_charging_requires_ev_plugged(self, machine):
        ctx = machine.get_context()
        ctx.ev_plugged_in = False
        machine.set_context(ctx)
        assert not machine.transition(sm.Event.OPEN_CHARGING)

    def test_charging_status_with_ev(self, machine):
        assert machine.transition(sm.Event.OPEN_CHARGING)
        assert machine.get_state() == sm.State.CHARGING_STATUS

    def test_error_screen(self, machine):
        assert machine.transition(sm.Event.FAULT_DETECTED)
        assert machine.get_state() == sm.State.ERROR_SCREEN
        assert machine.transition(sm.Event.FAULT_CLEARED)
        assert machine.get_state() == sm.State.HOME


# ---- State machine introspection -------------------------------------------

class TestIntrospection:
    def test_all_state_names_count(self):
        names = sm.InfotainmentStateMachine.all_state_names()
        # STATE_COUNT is included in the list
        state_count = int(sm.State.STATE_COUNT)
        assert len(names) == state_count

    def test_state_count_at_least_50(self):
        # Project requirement: 50+ states
        assert int(sm.State.STATE_COUNT) >= 50

    def test_get_all_transitions_nonempty(self):
        m = sm.InfotainmentStateMachine()
        transitions = m.get_all_transitions()
        assert len(transitions) >= 100  # we have 160+

    def test_transition_count_increments(self, machine):
        initial = machine.transition_count()
        machine.transition(sm.Event.SELECT_RADIO)
        assert machine.transition_count() == initial + 1

    def test_visited_transitions_tracked(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        machine.transition(sm.Event.TUNE_FM)
        visited = machine.visited_transitions()
        assert len(visited) >= 2

    def test_get_available_events(self, machine):
        events = machine.get_available_events()
        assert sm.Event.SELECT_RADIO in events
        assert sm.Event.SELECT_NAV   in events

    def test_reset_clears_state(self, machine):
        machine.transition(sm.Event.SELECT_RADIO)
        machine.transition(sm.Event.TUNE_FM)
        machine.reset()
        assert machine.get_state() == sm.State.BOOT
        assert machine.transition_count() == 0
