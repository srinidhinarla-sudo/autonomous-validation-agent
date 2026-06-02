#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include "infotainment_sm.h"

namespace py = pybind11;
using namespace infotainment;

PYBIND11_MODULE(infotainment_sm, m) {
    m.doc() = "Infotainment state machine — pybind11 bindings";

    // ------------------------------------------------------------------ State
    py::enum_<State>(m, "State")
#define S(x) .value(#x, State::x)
        S(BOOT) S(HOME)
        S(RADIO_HOME) S(RADIO_FM) S(RADIO_AM) S(RADIO_DAB)
        S(RADIO_PRESETS) S(RADIO_SCAN) S(RADIO_INFO)
        S(NAV_HOME) S(NAV_MAP) S(NAV_ROUTE_PLAN) S(NAV_DESTINATION_INPUT)
        S(NAV_TURN_BY_TURN) S(NAV_POI_SEARCH) S(NAV_FAVORITES)
        S(PHONE_HOME) S(PHONE_DIALING) S(PHONE_INCALL) S(PHONE_INCOMING)
        S(PHONE_CONTACTS) S(PHONE_RECENT_CALLS) S(PHONE_VOICEMAIL)
        S(MEDIA_HOME) S(MEDIA_USB) S(MEDIA_USB_BROWSE)
        S(MEDIA_BLUETOOTH_AUDIO) S(MEDIA_STREAMING) S(MEDIA_AUX)
        S(MEDIA_CARPLAY) S(MEDIA_ANDROID_AUTO)
        S(SETTINGS_HOME) S(SETTINGS_DISPLAY) S(SETTINGS_SOUND)
        S(SETTINGS_CONNECTIVITY) S(SETTINGS_VEHICLE) S(SETTINGS_LANGUAGE)
        S(SETTINGS_CLOCK) S(SETTINGS_PRIVACY) S(SETTINGS_DIAGNOSTICS)
        S(CLIMATE_HOME) S(CLIMATE_ZONES) S(CLIMATE_SEAT_HEATING)
        S(CLIMATE_STEERING_HEATING) S(CLIMATE_VENTILATION)
        S(PARK_ASSIST_REAR) S(PARK_ASSIST_FRONT) S(PARK_ASSIST_360)
        S(VEHICLE_INFO_HOME) S(VEHICLE_INFO_FUEL)
        S(VEHICLE_INFO_TRIP) S(VEHICLE_INFO_TIRES)
        S(APPS_HOME) S(APPS_SPOTIFY) S(APPS_GOOGLE_MAPS)
        S(NOTIFICATION_CENTER) S(VOICE_ASSISTANT) S(CHARGING_STATUS)
        S(DRIVER_PROFILE) S(AMBIENT_LIGHTING) S(ERROR_SCREEN)
        S(STATE_COUNT)
#undef S
        .export_values();

    // ------------------------------------------------------------------ Event
    py::enum_<Event>(m, "Event")
#define E(x) .value(#x, Event::x)
        E(POWER_ON) E(POWER_OFF) E(HOME_BUTTON) E(BACK_BUTTON)
        E(SELECT_RADIO) E(SELECT_NAV) E(SELECT_PHONE) E(SELECT_MEDIA)
        E(SELECT_SETTINGS) E(SELECT_CLIMATE) E(SELECT_PARK_ASSIST)
        E(SELECT_VEHICLE_INFO) E(SELECT_APPS)
        E(TUNE_FM) E(TUNE_AM) E(TUNE_DAB)
        E(OPEN_PRESETS) E(START_SCAN) E(VIEW_INFO)
        E(OPEN_MAP) E(PLAN_ROUTE) E(ENTER_DESTINATION) E(CONFIRM_DESTINATION)
        E(START_NAVIGATION) E(STOP_NAVIGATION) E(SEARCH_POI) E(OPEN_FAVORITES)
        E(CALL_INITIATE) E(CALL_ANSWER) E(CALL_END) E(CALL_REJECT)
        E(INCOMING_CALL) E(OPEN_CONTACTS) E(OPEN_RECENT_CALLS) E(OPEN_VOICEMAIL)
        E(SELECT_USB) E(SELECT_BLUETOOTH_AUDIO) E(SELECT_STREAMING)
        E(SELECT_AUX) E(SELECT_CARPLAY) E(SELECT_ANDROID_AUTO)
        E(USB_BROWSE) E(USB_ROOT)
        E(OPEN_DISPLAY_SETTINGS) E(OPEN_SOUND_SETTINGS) E(OPEN_CONNECTIVITY)
        E(OPEN_VEHICLE_SETTINGS) E(OPEN_LANGUAGE) E(OPEN_CLOCK)
        E(OPEN_PRIVACY) E(OPEN_DIAGNOSTICS)
        E(OPEN_ZONES) E(OPEN_SEAT_HEATING) E(OPEN_STEERING_HEATING)
        E(OPEN_VENTILATION)
        E(ACTIVATE_REAR_ASSIST) E(ACTIVATE_FRONT_ASSIST) E(ACTIVATE_360_ASSIST)
        E(OPEN_FUEL_INFO) E(OPEN_TRIP_INFO) E(OPEN_TIRE_INFO)
        E(OPEN_SPOTIFY) E(OPEN_GOOGLE_MAPS)
        E(OPEN_NOTIFICATIONS) E(CLOSE_NOTIFICATIONS)
        E(ACTIVATE_VOICE) E(DEACTIVATE_VOICE)
        E(OPEN_CHARGING) E(OPEN_DRIVER_PROFILE) E(OPEN_AMBIENT)
        E(CLOSE_OVERLAY) E(FAULT_DETECTED) E(FAULT_CLEARED)
        E(EVENT_COUNT)
#undef E
        .export_values();

    // --------------------------------------------------------- VehicleContext
    py::class_<VehicleContext>(m, "VehicleContext")
        .def(py::init<>())
        .def_readwrite("speed_kmh",             &VehicleContext::speed_kmh)
        .def_readwrite("in_reverse",            &VehicleContext::in_reverse)
        .def_readwrite("engine_running",        &VehicleContext::engine_running)
        .def_readwrite("phone_connected",       &VehicleContext::phone_connected)
        .def_readwrite("carplay_connected",     &VehicleContext::carplay_connected)
        .def_readwrite("android_auto_connected",&VehicleContext::android_auto_connected)
        .def_readwrite("usb_connected",         &VehicleContext::usb_connected)
        .def_readwrite("aux_connected",         &VehicleContext::aux_connected)
        .def_readwrite("ev_plugged_in",         &VehicleContext::ev_plugged_in)
        .def_readwrite("dab_available",         &VehicleContext::dab_available)
        .def_readwrite("streaming_connected",   &VehicleContext::streaming_connected)
        .def("__repr__", [](const VehicleContext& c) {
            return "<VehicleContext speed=" + std::to_string(c.speed_kmh)
                 + " reverse=" + std::to_string(c.in_reverse) + ">";
        });

    // --------------------------------------------------------- TransitionInfo
    py::class_<TransitionInfo>(m, "TransitionInfo")
        .def_readonly("from_state",  &TransitionInfo::from)
        .def_readonly("to_state",    &TransitionInfo::to)
        .def_readonly("event",       &TransitionInfo::event)
        .def_readonly("guard_name",  &TransitionInfo::guard_name)
        .def_readonly("description", &TransitionInfo::description)
        .def("__repr__", [](const TransitionInfo& t) {
            return "<Transition " + InfotainmentStateMachine::state_name(t.from)
                 + " --[" + InfotainmentStateMachine::event_name(t.event) + "]--> "
                 + InfotainmentStateMachine::state_name(t.to) + ">";
        });

    // ----------------------------------------------------- StateMachine class
    py::class_<InfotainmentStateMachine>(m, "InfotainmentStateMachine")
        .def(py::init<>())
        .def("transition",          &InfotainmentStateMachine::transition,
             py::arg("event"),
             "Fire an event; returns True if the transition was taken.")
        .def("get_state",           &InfotainmentStateMachine::get_state)
        .def("reset",               &InfotainmentStateMachine::reset)
        .def("set_context",         &InfotainmentStateMachine::set_context)
        .def("get_context",         &InfotainmentStateMachine::get_context)
        .def("get_available_events",&InfotainmentStateMachine::get_available_events,
             "All events defined for the current state (guards not checked).")
        .def("get_valid_events",    &InfotainmentStateMachine::get_valid_events,
             "Events whose guards pass in the current vehicle context.")
        .def("get_all_transitions", &InfotainmentStateMachine::get_all_transitions,
             "Full transition table (no guard evaluation).")
        .def("transition_count",    &InfotainmentStateMachine::transition_count)
        .def("visited_transitions", &InfotainmentStateMachine::visited_transitions)
        .def_static("state_name",   &InfotainmentStateMachine::state_name)
        .def_static("event_name",   &InfotainmentStateMachine::event_name)
        .def_static("all_state_names", &InfotainmentStateMachine::all_state_names)
        .def_static("all_event_names", &InfotainmentStateMachine::all_event_names);

    // Convenience module-level accessors
    m.def("state_name",  &InfotainmentStateMachine::state_name);
    m.def("event_name",  &InfotainmentStateMachine::event_name);
}
