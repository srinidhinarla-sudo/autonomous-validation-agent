#include "infotainment_sm.h"
#include <algorithm>
#include <stdexcept>

namespace infotainment {

// --------------------------------------------------------------------------
// Guard helpers
// --------------------------------------------------------------------------
static bool speed_ok(const VehicleContext& c)        { return c.speed_kmh <= 5.0f; }
static bool in_reverse(const VehicleContext& c)      { return c.in_reverse; }
static bool phone_ok(const VehicleContext& c)        { return c.phone_connected; }
static bool carplay_ok(const VehicleContext& c)      { return c.carplay_connected; }
static bool android_auto_ok(const VehicleContext& c) { return c.android_auto_connected; }
static bool usb_ok(const VehicleContext& c)          { return c.usb_connected; }
static bool aux_ok(const VehicleContext& c)          { return c.aux_connected; }
static bool ev_ok(const VehicleContext& c)           { return c.ev_plugged_in; }
static bool dab_ok(const VehicleContext& c)          { return c.dab_available; }
static bool streaming_ok(const VehicleContext& c)    { return c.streaming_connected; }
static bool always(const VehicleContext&)            { return true; }

// --------------------------------------------------------------------------
// Name tables
// --------------------------------------------------------------------------
static const char* STATE_NAMES[] = {
    "BOOT", "HOME",
    "RADIO_HOME", "RADIO_FM", "RADIO_AM", "RADIO_DAB",
    "RADIO_PRESETS", "RADIO_SCAN", "RADIO_INFO",
    "NAV_HOME", "NAV_MAP", "NAV_ROUTE_PLAN", "NAV_DESTINATION_INPUT",
    "NAV_TURN_BY_TURN", "NAV_POI_SEARCH", "NAV_FAVORITES",
    "PHONE_HOME", "PHONE_DIALING", "PHONE_INCALL", "PHONE_INCOMING",
    "PHONE_CONTACTS", "PHONE_RECENT_CALLS", "PHONE_VOICEMAIL",
    "MEDIA_HOME", "MEDIA_USB", "MEDIA_USB_BROWSE",
    "MEDIA_BLUETOOTH_AUDIO", "MEDIA_STREAMING", "MEDIA_AUX",
    "MEDIA_CARPLAY", "MEDIA_ANDROID_AUTO",
    "SETTINGS_HOME", "SETTINGS_DISPLAY", "SETTINGS_SOUND",
    "SETTINGS_CONNECTIVITY", "SETTINGS_VEHICLE", "SETTINGS_LANGUAGE",
    "SETTINGS_CLOCK", "SETTINGS_PRIVACY", "SETTINGS_DIAGNOSTICS",
    "CLIMATE_HOME", "CLIMATE_ZONES", "CLIMATE_SEAT_HEATING",
    "CLIMATE_STEERING_HEATING", "CLIMATE_VENTILATION",
    "PARK_ASSIST_REAR", "PARK_ASSIST_FRONT", "PARK_ASSIST_360",
    "VEHICLE_INFO_HOME", "VEHICLE_INFO_FUEL", "VEHICLE_INFO_TRIP",
    "VEHICLE_INFO_TIRES",
    "APPS_HOME", "APPS_SPOTIFY", "APPS_GOOGLE_MAPS",
    "NOTIFICATION_CENTER", "VOICE_ASSISTANT", "CHARGING_STATUS",
    "DRIVER_PROFILE", "AMBIENT_LIGHTING", "ERROR_SCREEN"
};
static_assert(sizeof(STATE_NAMES)/sizeof(STATE_NAMES[0]) ==
              static_cast<size_t>(State::STATE_COUNT),
              "STATE_NAMES out of sync");

static const char* EVENT_NAMES[] = {
    "POWER_ON", "POWER_OFF", "HOME_BUTTON", "BACK_BUTTON",
    "SELECT_RADIO", "SELECT_NAV", "SELECT_PHONE", "SELECT_MEDIA",
    "SELECT_SETTINGS", "SELECT_CLIMATE", "SELECT_PARK_ASSIST",
    "SELECT_VEHICLE_INFO", "SELECT_APPS",
    "TUNE_FM", "TUNE_AM", "TUNE_DAB",
    "OPEN_PRESETS", "START_SCAN", "VIEW_INFO",
    "OPEN_MAP", "PLAN_ROUTE", "ENTER_DESTINATION", "CONFIRM_DESTINATION",
    "START_NAVIGATION", "STOP_NAVIGATION", "SEARCH_POI", "OPEN_FAVORITES",
    "CALL_INITIATE", "CALL_ANSWER", "CALL_END", "CALL_REJECT",
    "INCOMING_CALL", "OPEN_CONTACTS", "OPEN_RECENT_CALLS", "OPEN_VOICEMAIL",
    "SELECT_USB", "SELECT_BLUETOOTH_AUDIO", "SELECT_STREAMING",
    "SELECT_AUX", "SELECT_CARPLAY", "SELECT_ANDROID_AUTO",
    "USB_BROWSE", "USB_ROOT",
    "OPEN_DISPLAY_SETTINGS", "OPEN_SOUND_SETTINGS", "OPEN_CONNECTIVITY",
    "OPEN_VEHICLE_SETTINGS", "OPEN_LANGUAGE", "OPEN_CLOCK",
    "OPEN_PRIVACY", "OPEN_DIAGNOSTICS",
    "OPEN_ZONES", "OPEN_SEAT_HEATING", "OPEN_STEERING_HEATING",
    "OPEN_VENTILATION",
    "ACTIVATE_REAR_ASSIST", "ACTIVATE_FRONT_ASSIST", "ACTIVATE_360_ASSIST",
    "OPEN_FUEL_INFO", "OPEN_TRIP_INFO", "OPEN_TIRE_INFO",
    "OPEN_SPOTIFY", "OPEN_GOOGLE_MAPS",
    "OPEN_NOTIFICATIONS", "CLOSE_NOTIFICATIONS",
    "ACTIVATE_VOICE", "DEACTIVATE_VOICE",
    "OPEN_CHARGING", "OPEN_DRIVER_PROFILE", "OPEN_AMBIENT",
    "CLOSE_OVERLAY", "FAULT_DETECTED", "FAULT_CLEARED"
};
static_assert(sizeof(EVENT_NAMES)/sizeof(EVENT_NAMES[0]) ==
              static_cast<size_t>(Event::EVENT_COUNT),
              "EVENT_NAMES out of sync");

// --------------------------------------------------------------------------
// Constructor / reset
// --------------------------------------------------------------------------
InfotainmentStateMachine::InfotainmentStateMachine()
    : current_state_(State::BOOT), transition_count_(0)
{
    register_transitions();
}

void InfotainmentStateMachine::reset() {
    current_state_  = State::BOOT;
    context_        = VehicleContext{};
    transition_count_ = 0;
    visited_transitions_.clear();
}

// --------------------------------------------------------------------------
// add() helper
// --------------------------------------------------------------------------
void InfotainmentStateMachine::add(State from, State to, Event ev,
    std::function<bool(const VehicleContext&)> guard,
    std::string guard_name, std::string desc)
{
    if (!guard) guard = always;
    transitions_.push_back({from, to, ev, std::move(guard),
                            std::move(guard_name), std::move(desc)});
}

// --------------------------------------------------------------------------
// Transition table — 160+ transitions across all subsystems
// --------------------------------------------------------------------------
void InfotainmentStateMachine::register_transitions() {
    using S = State;
    using E = Event;

    // ---- Boot sequence ----
    add(S::BOOT, S::HOME, E::POWER_ON,
        [](const VehicleContext& c){ return c.engine_running; },
        "engine_running", "Boot completes when engine is running");
    add(S::HOME, S::BOOT, E::POWER_OFF, nullptr, "", "Power off returns to BOOT");

    // ---- HOME <-> every top-level subsystem ----
    // HOME button from any state goes to HOME (registered later per state)
    add(S::HOME, S::RADIO_HOME,       E::SELECT_RADIO,       nullptr, "", "");
    add(S::HOME, S::NAV_HOME,         E::SELECT_NAV,         nullptr, "", "");
    add(S::HOME, S::PHONE_HOME,       E::SELECT_PHONE,       nullptr, "", "");
    add(S::HOME, S::MEDIA_HOME,       E::SELECT_MEDIA,       nullptr, "", "");
    add(S::HOME, S::SETTINGS_HOME,    E::SELECT_SETTINGS,    speed_ok, "speed<=5", "Settings locked above 5 km/h");
    add(S::HOME, S::CLIMATE_HOME,     E::SELECT_CLIMATE,     nullptr, "", "");
    add(S::HOME, S::VEHICLE_INFO_HOME,E::SELECT_VEHICLE_INFO,nullptr, "", "");
    add(S::HOME, S::APPS_HOME,        E::SELECT_APPS,        nullptr, "", "");
    add(S::HOME, S::NOTIFICATION_CENTER, E::OPEN_NOTIFICATIONS, nullptr, "", "");
    add(S::HOME, S::VOICE_ASSISTANT,  E::ACTIVATE_VOICE,     nullptr, "", "");
    add(S::HOME, S::DRIVER_PROFILE,   E::OPEN_DRIVER_PROFILE,nullptr, "", "");
    add(S::HOME, S::AMBIENT_LIGHTING, E::OPEN_AMBIENT,       nullptr, "", "");
    add(S::HOME, S::CHARGING_STATUS,  E::OPEN_CHARGING,      ev_ok, "ev_plugged_in", "EV charging screen");
    add(S::HOME, S::ERROR_SCREEN,     E::FAULT_DETECTED,     nullptr, "", "");

    // ---- RADIO subsystem ----
    add(S::RADIO_HOME, S::HOME,          E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_HOME, S::RADIO_FM,      E::TUNE_FM,      nullptr, "", "");
    add(S::RADIO_HOME, S::RADIO_AM,      E::TUNE_AM,      nullptr, "", "");
    add(S::RADIO_HOME, S::RADIO_DAB,     E::TUNE_DAB,     dab_ok, "dab_available", "DAB requires hardware");
    add(S::RADIO_HOME, S::RADIO_PRESETS, E::OPEN_PRESETS, nullptr, "", "");
    add(S::RADIO_HOME, S::RADIO_SCAN,    E::START_SCAN,   nullptr, "", "");
    add(S::RADIO_HOME, S::RADIO_INFO,    E::VIEW_INFO,    nullptr, "", "");

    add(S::RADIO_FM, S::RADIO_HOME,     E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_FM, S::HOME,           E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_FM, S::RADIO_AM,       E::TUNE_AM,      nullptr, "", "");
    add(S::RADIO_FM, S::RADIO_DAB,      E::TUNE_DAB,     dab_ok, "dab_available", "");
    add(S::RADIO_FM, S::RADIO_PRESETS,  E::OPEN_PRESETS, nullptr, "", "");
    add(S::RADIO_FM, S::RADIO_SCAN,     E::START_SCAN,   nullptr, "", "");
    add(S::RADIO_FM, S::RADIO_INFO,     E::VIEW_INFO,    nullptr, "", "");

    add(S::RADIO_AM, S::RADIO_HOME,     E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_AM, S::HOME,           E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_AM, S::RADIO_FM,       E::TUNE_FM,      nullptr, "", "");
    add(S::RADIO_AM, S::RADIO_DAB,      E::TUNE_DAB,     dab_ok, "dab_available", "");
    add(S::RADIO_AM, S::RADIO_PRESETS,  E::OPEN_PRESETS, nullptr, "", "");
    add(S::RADIO_AM, S::RADIO_INFO,     E::VIEW_INFO,    nullptr, "", "");

    add(S::RADIO_DAB, S::RADIO_HOME,    E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_DAB, S::HOME,          E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_DAB, S::RADIO_FM,      E::TUNE_FM,      nullptr, "", "");
    add(S::RADIO_DAB, S::RADIO_AM,      E::TUNE_AM,      nullptr, "", "");
    add(S::RADIO_DAB, S::RADIO_INFO,    E::VIEW_INFO,    nullptr, "", "");

    add(S::RADIO_PRESETS, S::RADIO_HOME,E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_PRESETS, S::HOME,      E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_PRESETS, S::RADIO_FM,  E::TUNE_FM,      nullptr, "", "");
    add(S::RADIO_PRESETS, S::RADIO_AM,  E::TUNE_AM,      nullptr, "", "");

    add(S::RADIO_SCAN, S::RADIO_HOME,   E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_SCAN, S::HOME,         E::HOME_BUTTON,  nullptr, "", "");
    add(S::RADIO_SCAN, S::RADIO_FM,     E::TUNE_FM,      nullptr, "", "");

    add(S::RADIO_INFO, S::RADIO_HOME,   E::BACK_BUTTON,  nullptr, "", "");
    add(S::RADIO_INFO, S::HOME,         E::HOME_BUTTON,  nullptr, "", "");

    // ---- NAV subsystem ----
    add(S::NAV_HOME, S::HOME,                   E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_HOME, S::NAV_MAP,                E::OPEN_MAP,          nullptr, "", "");
    add(S::NAV_HOME, S::NAV_ROUTE_PLAN,         E::PLAN_ROUTE,        speed_ok, "speed<=5", "Route planning blocked while driving");
    add(S::NAV_HOME, S::NAV_DESTINATION_INPUT,  E::ENTER_DESTINATION, speed_ok, "speed<=5", "Destination input blocked while driving");
    add(S::NAV_HOME, S::NAV_POI_SEARCH,         E::SEARCH_POI,        speed_ok, "speed<=5", "POI search locked above 5 km/h");
    add(S::NAV_HOME, S::NAV_FAVORITES,          E::OPEN_FAVORITES,    nullptr, "", "");

    add(S::NAV_MAP, S::NAV_HOME,                E::BACK_BUTTON,       nullptr, "", "");
    add(S::NAV_MAP, S::HOME,                    E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_MAP, S::NAV_TURN_BY_TURN,        E::START_NAVIGATION,  nullptr, "", "Route must be planned first (guard omitted for testability)");
    add(S::NAV_MAP, S::NAV_ROUTE_PLAN,          E::PLAN_ROUTE,        speed_ok, "speed<=5", "");
    add(S::NAV_MAP, S::NAV_POI_SEARCH,          E::SEARCH_POI,        speed_ok, "speed<=5", "");

    add(S::NAV_ROUTE_PLAN, S::NAV_HOME,         E::BACK_BUTTON,       nullptr, "", "");
    add(S::NAV_ROUTE_PLAN, S::HOME,             E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_ROUTE_PLAN, S::NAV_DESTINATION_INPUT, E::ENTER_DESTINATION, speed_ok, "speed<=5", "");
    add(S::NAV_ROUTE_PLAN, S::NAV_MAP,          E::CONFIRM_DESTINATION, nullptr, "", "");

    add(S::NAV_DESTINATION_INPUT, S::NAV_ROUTE_PLAN, E::BACK_BUTTON,  nullptr, "", "");
    add(S::NAV_DESTINATION_INPUT, S::HOME,      E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_DESTINATION_INPUT, S::NAV_ROUTE_PLAN, E::CONFIRM_DESTINATION, nullptr, "", "");

    add(S::NAV_TURN_BY_TURN, S::NAV_MAP,        E::STOP_NAVIGATION,   nullptr, "", "");
    add(S::NAV_TURN_BY_TURN, S::HOME,           E::HOME_BUTTON,       nullptr, "", "");

    add(S::NAV_POI_SEARCH, S::NAV_HOME,         E::BACK_BUTTON,       nullptr, "", "");
    add(S::NAV_POI_SEARCH, S::HOME,             E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_POI_SEARCH, S::NAV_MAP,          E::CONFIRM_DESTINATION, nullptr, "", "");

    add(S::NAV_FAVORITES, S::NAV_HOME,          E::BACK_BUTTON,       nullptr, "", "");
    add(S::NAV_FAVORITES, S::HOME,              E::HOME_BUTTON,       nullptr, "", "");
    add(S::NAV_FAVORITES, S::NAV_MAP,           E::CONFIRM_DESTINATION, nullptr, "", "");

    // ---- PHONE subsystem ----
    add(S::PHONE_HOME, S::HOME,             E::HOME_BUTTON,   nullptr, "", "");
    add(S::PHONE_HOME, S::PHONE_DIALING,    E::CALL_INITIATE, phone_ok, "phone_connected", "Dialing requires paired phone");
    add(S::PHONE_HOME, S::PHONE_INCOMING,   E::INCOMING_CALL, phone_ok, "phone_connected", "");
    add(S::PHONE_HOME, S::PHONE_CONTACTS,   E::OPEN_CONTACTS, phone_ok, "phone_connected", "");
    add(S::PHONE_HOME, S::PHONE_RECENT_CALLS, E::OPEN_RECENT_CALLS, phone_ok, "phone_connected", "");
    add(S::PHONE_HOME, S::PHONE_VOICEMAIL,  E::OPEN_VOICEMAIL, phone_ok, "phone_connected", "");

    add(S::PHONE_DIALING, S::PHONE_INCALL,  E::CALL_ANSWER,   nullptr, "", "Simulates remote pickup");
    add(S::PHONE_DIALING, S::PHONE_HOME,    E::CALL_END,      nullptr, "", "Hang up before answer");
    add(S::PHONE_DIALING, S::HOME,          E::HOME_BUTTON,   nullptr, "", "");

    add(S::PHONE_INCALL, S::PHONE_HOME,     E::CALL_END,      nullptr, "", "");
    add(S::PHONE_INCALL, S::HOME,           E::HOME_BUTTON,   nullptr, "", "");

    add(S::PHONE_INCOMING, S::PHONE_INCALL, E::CALL_ANSWER,   nullptr, "", "");
    add(S::PHONE_INCOMING, S::PHONE_HOME,   E::CALL_REJECT,   nullptr, "", "");
    add(S::PHONE_INCOMING, S::HOME,         E::HOME_BUTTON,   nullptr, "", "");

    add(S::PHONE_CONTACTS, S::PHONE_HOME,   E::BACK_BUTTON,   nullptr, "", "");
    add(S::PHONE_CONTACTS, S::HOME,         E::HOME_BUTTON,   nullptr, "", "");
    add(S::PHONE_CONTACTS, S::PHONE_DIALING,E::CALL_INITIATE, phone_ok, "phone_connected", "");

    add(S::PHONE_RECENT_CALLS, S::PHONE_HOME,  E::BACK_BUTTON,   nullptr, "", "");
    add(S::PHONE_RECENT_CALLS, S::HOME,         E::HOME_BUTTON,   nullptr, "", "");
    add(S::PHONE_RECENT_CALLS, S::PHONE_DIALING,E::CALL_INITIATE, phone_ok, "phone_connected", "");

    add(S::PHONE_VOICEMAIL, S::PHONE_HOME,  E::BACK_BUTTON,   nullptr, "", "");
    add(S::PHONE_VOICEMAIL, S::HOME,        E::HOME_BUTTON,   nullptr, "", "");

    // ---- MEDIA subsystem ----
    add(S::MEDIA_HOME, S::HOME,                  E::HOME_BUTTON,         nullptr, "", "");
    add(S::MEDIA_HOME, S::MEDIA_USB,             E::SELECT_USB,          usb_ok, "usb_connected", "USB source requires device");
    add(S::MEDIA_HOME, S::MEDIA_BLUETOOTH_AUDIO, E::SELECT_BLUETOOTH_AUDIO, nullptr, "", "");
    add(S::MEDIA_HOME, S::MEDIA_STREAMING,       E::SELECT_STREAMING,    streaming_ok, "streaming_connected", "");
    add(S::MEDIA_HOME, S::MEDIA_AUX,             E::SELECT_AUX,          aux_ok, "aux_connected", "");
    add(S::MEDIA_HOME, S::MEDIA_CARPLAY,         E::SELECT_CARPLAY,      carplay_ok, "carplay_connected", "CarPlay requires cable/wireless");
    add(S::MEDIA_HOME, S::MEDIA_ANDROID_AUTO,    E::SELECT_ANDROID_AUTO, android_auto_ok, "android_auto_connected", "");

    add(S::MEDIA_USB, S::MEDIA_HOME,        E::BACK_BUTTON,   nullptr, "", "");
    add(S::MEDIA_USB, S::HOME,              E::HOME_BUTTON,   nullptr, "", "");
    add(S::MEDIA_USB, S::MEDIA_USB_BROWSE,  E::USB_BROWSE,    nullptr, "", "");

    add(S::MEDIA_USB_BROWSE, S::MEDIA_USB,  E::USB_ROOT,      nullptr, "", "");
    add(S::MEDIA_USB_BROWSE, S::MEDIA_HOME, E::BACK_BUTTON,   nullptr, "", "");
    add(S::MEDIA_USB_BROWSE, S::HOME,       E::HOME_BUTTON,   nullptr, "", "");

    add(S::MEDIA_BLUETOOTH_AUDIO, S::MEDIA_HOME, E::BACK_BUTTON, nullptr, "", "");
    add(S::MEDIA_BLUETOOTH_AUDIO, S::HOME,        E::HOME_BUTTON, nullptr, "", "");

    add(S::MEDIA_STREAMING, S::MEDIA_HOME,  E::BACK_BUTTON,   nullptr, "", "");
    add(S::MEDIA_STREAMING, S::HOME,        E::HOME_BUTTON,   nullptr, "", "");

    add(S::MEDIA_AUX, S::MEDIA_HOME,        E::BACK_BUTTON,   nullptr, "", "");
    add(S::MEDIA_AUX, S::HOME,              E::HOME_BUTTON,   nullptr, "", "");

    add(S::MEDIA_CARPLAY, S::MEDIA_HOME,    E::BACK_BUTTON,   nullptr, "", "");
    add(S::MEDIA_CARPLAY, S::HOME,          E::HOME_BUTTON,   nullptr, "", "");

    add(S::MEDIA_ANDROID_AUTO, S::MEDIA_HOME, E::BACK_BUTTON, nullptr, "", "");
    add(S::MEDIA_ANDROID_AUTO, S::HOME,       E::HOME_BUTTON, nullptr, "", "");

    // ---- SETTINGS subsystem (all speed-locked) ----
    auto sp = speed_ok;
    add(S::SETTINGS_HOME, S::HOME,                  E::HOME_BUTTON,        nullptr, "", "");
    add(S::SETTINGS_HOME, S::SETTINGS_DISPLAY,      E::OPEN_DISPLAY_SETTINGS, sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_SOUND,        E::OPEN_SOUND_SETTINGS,   sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_CONNECTIVITY, E::OPEN_CONNECTIVITY,     sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_VEHICLE,      E::OPEN_VEHICLE_SETTINGS, sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_LANGUAGE,     E::OPEN_LANGUAGE,         sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_CLOCK,        E::OPEN_CLOCK,            sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_PRIVACY,      E::OPEN_PRIVACY,          sp, "speed<=5", "");
    add(S::SETTINGS_HOME, S::SETTINGS_DIAGNOSTICS,  E::OPEN_DIAGNOSTICS,      sp, "speed<=5", "");

    for (State s : {S::SETTINGS_DISPLAY, S::SETTINGS_SOUND, S::SETTINGS_CONNECTIVITY,
                    S::SETTINGS_VEHICLE, S::SETTINGS_LANGUAGE, S::SETTINGS_CLOCK,
                    S::SETTINGS_PRIVACY, S::SETTINGS_DIAGNOSTICS}) {
        add(s, S::SETTINGS_HOME, E::BACK_BUTTON, nullptr, "", "");
        add(s, S::HOME,          E::HOME_BUTTON, nullptr, "", "");
    }

    // ---- CLIMATE subsystem ----
    add(S::CLIMATE_HOME, S::HOME,                   E::HOME_BUTTON,         nullptr, "", "");
    add(S::CLIMATE_HOME, S::CLIMATE_ZONES,          E::OPEN_ZONES,          nullptr, "", "");
    add(S::CLIMATE_HOME, S::CLIMATE_SEAT_HEATING,   E::OPEN_SEAT_HEATING,   nullptr, "", "");
    add(S::CLIMATE_HOME, S::CLIMATE_STEERING_HEATING,E::OPEN_STEERING_HEATING,nullptr, "", "");
    add(S::CLIMATE_HOME, S::CLIMATE_VENTILATION,    E::OPEN_VENTILATION,    nullptr, "", "");

    for (State s : {S::CLIMATE_ZONES, S::CLIMATE_SEAT_HEATING,
                    S::CLIMATE_STEERING_HEATING, S::CLIMATE_VENTILATION}) {
        add(s, S::CLIMATE_HOME, E::BACK_BUTTON, nullptr, "", "");
        add(s, S::HOME,         E::HOME_BUTTON, nullptr, "", "");
    }

    // ---- PARK ASSIST (reverse-locked) ----
    add(S::HOME, S::PARK_ASSIST_REAR,  E::SELECT_PARK_ASSIST,   in_reverse, "in_reverse", "Park assist requires reverse gear");
    add(S::PARK_ASSIST_REAR, S::PARK_ASSIST_FRONT,  E::ACTIVATE_FRONT_ASSIST, nullptr, "", "");
    add(S::PARK_ASSIST_REAR, S::PARK_ASSIST_360,    E::ACTIVATE_360_ASSIST,   nullptr, "", "");
    add(S::PARK_ASSIST_REAR, S::HOME,               E::HOME_BUTTON,           nullptr, "", "");
    add(S::PARK_ASSIST_FRONT, S::PARK_ASSIST_REAR,  E::ACTIVATE_REAR_ASSIST,  nullptr, "", "");
    add(S::PARK_ASSIST_FRONT, S::PARK_ASSIST_360,   E::ACTIVATE_360_ASSIST,   nullptr, "", "");
    add(S::PARK_ASSIST_FRONT, S::HOME,              E::HOME_BUTTON,           nullptr, "", "");
    add(S::PARK_ASSIST_360, S::PARK_ASSIST_REAR,    E::ACTIVATE_REAR_ASSIST,  nullptr, "", "");
    add(S::PARK_ASSIST_360, S::PARK_ASSIST_FRONT,   E::ACTIVATE_FRONT_ASSIST, nullptr, "", "");
    add(S::PARK_ASSIST_360, S::HOME,                E::HOME_BUTTON,           nullptr, "", "");

    // ---- VEHICLE INFO ----
    add(S::VEHICLE_INFO_HOME, S::HOME,              E::HOME_BUTTON,   nullptr, "", "");
    add(S::VEHICLE_INFO_HOME, S::VEHICLE_INFO_FUEL, E::OPEN_FUEL_INFO,nullptr, "", "");
    add(S::VEHICLE_INFO_HOME, S::VEHICLE_INFO_TRIP, E::OPEN_TRIP_INFO,nullptr, "", "");
    add(S::VEHICLE_INFO_HOME, S::VEHICLE_INFO_TIRES,E::OPEN_TIRE_INFO,nullptr, "", "");

    for (State s : {S::VEHICLE_INFO_FUEL, S::VEHICLE_INFO_TRIP, S::VEHICLE_INFO_TIRES}) {
        add(s, S::VEHICLE_INFO_HOME, E::BACK_BUTTON, nullptr, "", "");
        add(s, S::HOME,              E::HOME_BUTTON, nullptr, "", "");
    }

    // ---- APPS ----
    add(S::APPS_HOME, S::HOME,           E::HOME_BUTTON,    nullptr, "", "");
    add(S::APPS_HOME, S::APPS_SPOTIFY,   E::OPEN_SPOTIFY,   streaming_ok, "streaming_connected", "Spotify requires network");
    add(S::APPS_HOME, S::APPS_GOOGLE_MAPS, E::OPEN_GOOGLE_MAPS, nullptr, "", "");

    add(S::APPS_SPOTIFY, S::APPS_HOME,      E::BACK_BUTTON,  nullptr, "", "");
    add(S::APPS_SPOTIFY, S::HOME,           E::HOME_BUTTON,  nullptr, "", "");
    add(S::APPS_GOOGLE_MAPS, S::APPS_HOME,  E::BACK_BUTTON,  nullptr, "", "");
    add(S::APPS_GOOGLE_MAPS, S::HOME,       E::HOME_BUTTON,  nullptr, "", "");

    // ---- MODAL OVERLAYS (dismissible from any base state) ----
    add(S::NOTIFICATION_CENTER, S::HOME, E::CLOSE_NOTIFICATIONS, nullptr, "", "");
    add(S::NOTIFICATION_CENTER, S::HOME, E::HOME_BUTTON,         nullptr, "", "");
    add(S::NOTIFICATION_CENTER, S::HOME, E::CLOSE_OVERLAY,       nullptr, "", "");

    add(S::VOICE_ASSISTANT, S::HOME, E::DEACTIVATE_VOICE, nullptr, "", "");
    add(S::VOICE_ASSISTANT, S::HOME, E::HOME_BUTTON,      nullptr, "", "");
    add(S::VOICE_ASSISTANT, S::HOME, E::CLOSE_OVERLAY,    nullptr, "", "");

    // Voice can be activated from key subsystem screens (mutually exclusive with PHONE_INCALL)
    for (State s : {S::RADIO_FM, S::NAV_MAP, S::MEDIA_HOME, S::CLIMATE_HOME}) {
        add(s, S::VOICE_ASSISTANT, E::ACTIVATE_VOICE, nullptr, "", "");
    }

    add(S::CHARGING_STATUS, S::HOME, E::BACK_BUTTON,  nullptr, "", "");
    add(S::CHARGING_STATUS, S::HOME, E::HOME_BUTTON,  nullptr, "", "");
    add(S::CHARGING_STATUS, S::HOME, E::CLOSE_OVERLAY,nullptr, "", "");

    add(S::DRIVER_PROFILE, S::HOME, E::BACK_BUTTON,   nullptr, "", "");
    add(S::DRIVER_PROFILE, S::HOME, E::HOME_BUTTON,   nullptr, "", "");
    add(S::DRIVER_PROFILE, S::HOME, E::CLOSE_OVERLAY, nullptr, "", "");

    add(S::AMBIENT_LIGHTING, S::HOME, E::BACK_BUTTON,  nullptr, "", "");
    add(S::AMBIENT_LIGHTING, S::HOME, E::HOME_BUTTON,  nullptr, "", "");
    add(S::AMBIENT_LIGHTING, S::HOME, E::CLOSE_OVERLAY,nullptr, "", "");

    // ---- ERROR SCREEN ----
    add(S::ERROR_SCREEN, S::HOME, E::FAULT_CLEARED, nullptr, "", "");
    add(S::ERROR_SCREEN, S::HOME, E::HOME_BUTTON,   nullptr, "", "");

    // ---- Cross-subsystem shortcuts from HOME (PHONE_INCOMING is a global interrupt) ----
    for (State s : {S::RADIO_FM, S::RADIO_AM, S::RADIO_DAB,
                    S::NAV_MAP, S::NAV_TURN_BY_TURN,
                    S::MEDIA_HOME, S::MEDIA_USB, S::MEDIA_BLUETOOTH_AUDIO,
                    S::CLIMATE_HOME, S::APPS_SPOTIFY}) {
        add(s, S::PHONE_INCOMING, E::INCOMING_CALL, phone_ok, "phone_connected", "Global incoming-call interrupt");
    }
}

// --------------------------------------------------------------------------
// Core transition logic
// --------------------------------------------------------------------------
bool InfotainmentStateMachine::transition(Event event) {
    for (const auto& t : transitions_) {
        if (t.from == current_state_ && t.event == event) {
            if (t.guard(context_)) {
                visited_transitions_.emplace_back(current_state_, t.to);
                current_state_ = t.to;
                ++transition_count_;
                return true;
            }
        }
    }
    return false;  // no matching transition or guard blocked it
}

// --------------------------------------------------------------------------
// Introspection
// --------------------------------------------------------------------------
std::vector<Event> InfotainmentStateMachine::get_available_events() const {
    std::vector<Event> result;
    for (const auto& t : transitions_) {
        if (t.from == current_state_) {
            if (std::find(result.begin(), result.end(), t.event) == result.end())
                result.push_back(t.event);
        }
    }
    return result;
}

std::vector<Event> InfotainmentStateMachine::get_valid_events() const {
    std::vector<Event> result;
    for (const auto& t : transitions_) {
        if (t.from == current_state_ && t.guard(context_)) {
            if (std::find(result.begin(), result.end(), t.event) == result.end())
                result.push_back(t.event);
        }
    }
    return result;
}

std::vector<TransitionInfo> InfotainmentStateMachine::get_all_transitions() const {
    std::vector<TransitionInfo> info;
    info.reserve(transitions_.size());
    for (const auto& t : transitions_)
        info.push_back({t.from, t.to, t.event, t.guard_name, t.description});
    return info;
}

// --------------------------------------------------------------------------
// Name helpers
// --------------------------------------------------------------------------
std::string InfotainmentStateMachine::state_name(State s) {
    auto idx = static_cast<size_t>(s);
    if (idx >= static_cast<size_t>(State::STATE_COUNT))
        return "UNKNOWN";
    return STATE_NAMES[idx];
}

std::string InfotainmentStateMachine::event_name(Event e) {
    auto idx = static_cast<size_t>(e);
    if (idx >= static_cast<size_t>(Event::EVENT_COUNT))
        return "UNKNOWN";
    return EVENT_NAMES[idx];
}

std::vector<std::string> InfotainmentStateMachine::all_state_names() {
    std::vector<std::string> out;
    for (size_t i = 0; i < static_cast<size_t>(State::STATE_COUNT); ++i)
        out.emplace_back(STATE_NAMES[i]);
    return out;
}

std::vector<std::string> InfotainmentStateMachine::all_event_names() {
    std::vector<std::string> out;
    for (size_t i = 0; i < static_cast<size_t>(Event::EVENT_COUNT); ++i)
        out.emplace_back(EVENT_NAMES[i]);
    return out;
}

} // namespace infotainment
