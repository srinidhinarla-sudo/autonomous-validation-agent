#pragma once
#include <functional>
#include <string>
#include <vector>
#include <stdexcept>
#include <utility>

namespace infotainment {

// 60 states across 10 subsystems
enum class State {
    BOOT = 0,
    HOME,
    // Radio (7)
    RADIO_HOME,
    RADIO_FM,
    RADIO_AM,
    RADIO_DAB,
    RADIO_PRESETS,
    RADIO_SCAN,
    RADIO_INFO,
    // Navigation (7)
    NAV_HOME,
    NAV_MAP,
    NAV_ROUTE_PLAN,
    NAV_DESTINATION_INPUT,
    NAV_TURN_BY_TURN,
    NAV_POI_SEARCH,
    NAV_FAVORITES,
    // Phone (7)
    PHONE_HOME,
    PHONE_DIALING,
    PHONE_INCALL,
    PHONE_INCOMING,
    PHONE_CONTACTS,
    PHONE_RECENT_CALLS,
    PHONE_VOICEMAIL,
    // Media (8)
    MEDIA_HOME,
    MEDIA_USB,
    MEDIA_USB_BROWSE,
    MEDIA_BLUETOOTH_AUDIO,
    MEDIA_STREAMING,
    MEDIA_AUX,
    MEDIA_CARPLAY,
    MEDIA_ANDROID_AUTO,
    // Settings (9)
    SETTINGS_HOME,
    SETTINGS_DISPLAY,
    SETTINGS_SOUND,
    SETTINGS_CONNECTIVITY,
    SETTINGS_VEHICLE,
    SETTINGS_LANGUAGE,
    SETTINGS_CLOCK,
    SETTINGS_PRIVACY,
    SETTINGS_DIAGNOSTICS,
    // Climate (5)
    CLIMATE_HOME,
    CLIMATE_ZONES,
    CLIMATE_SEAT_HEATING,
    CLIMATE_STEERING_HEATING,
    CLIMATE_VENTILATION,
    // Park Assist (3)
    PARK_ASSIST_REAR,
    PARK_ASSIST_FRONT,
    PARK_ASSIST_360,
    // Vehicle Info (4)
    VEHICLE_INFO_HOME,
    VEHICLE_INFO_FUEL,
    VEHICLE_INFO_TRIP,
    VEHICLE_INFO_TIRES,
    // Apps (3)
    APPS_HOME,
    APPS_SPOTIFY,
    APPS_GOOGLE_MAPS,
    // Modal overlays (6)
    NOTIFICATION_CENTER,
    VOICE_ASSISTANT,
    CHARGING_STATUS,
    DRIVER_PROFILE,
    AMBIENT_LIGHTING,
    ERROR_SCREEN,
    STATE_COUNT
};

enum class Event {
    POWER_ON = 0,
    POWER_OFF,
    HOME_BUTTON,
    BACK_BUTTON,
    SELECT_RADIO,
    SELECT_NAV,
    SELECT_PHONE,
    SELECT_MEDIA,
    SELECT_SETTINGS,
    SELECT_CLIMATE,
    SELECT_PARK_ASSIST,
    SELECT_VEHICLE_INFO,
    SELECT_APPS,
    TUNE_FM,
    TUNE_AM,
    TUNE_DAB,
    OPEN_PRESETS,
    START_SCAN,
    VIEW_INFO,
    OPEN_MAP,
    PLAN_ROUTE,
    ENTER_DESTINATION,
    CONFIRM_DESTINATION,
    START_NAVIGATION,
    STOP_NAVIGATION,
    SEARCH_POI,
    OPEN_FAVORITES,
    CALL_INITIATE,
    CALL_ANSWER,
    CALL_END,
    CALL_REJECT,
    INCOMING_CALL,
    OPEN_CONTACTS,
    OPEN_RECENT_CALLS,
    OPEN_VOICEMAIL,
    SELECT_USB,
    SELECT_BLUETOOTH_AUDIO,
    SELECT_STREAMING,
    SELECT_AUX,
    SELECT_CARPLAY,
    SELECT_ANDROID_AUTO,
    USB_BROWSE,
    USB_ROOT,
    OPEN_DISPLAY_SETTINGS,
    OPEN_SOUND_SETTINGS,
    OPEN_CONNECTIVITY,
    OPEN_VEHICLE_SETTINGS,
    OPEN_LANGUAGE,
    OPEN_CLOCK,
    OPEN_PRIVACY,
    OPEN_DIAGNOSTICS,
    OPEN_ZONES,
    OPEN_SEAT_HEATING,
    OPEN_STEERING_HEATING,
    OPEN_VENTILATION,
    ACTIVATE_REAR_ASSIST,
    ACTIVATE_FRONT_ASSIST,
    ACTIVATE_360_ASSIST,
    OPEN_FUEL_INFO,
    OPEN_TRIP_INFO,
    OPEN_TIRE_INFO,
    OPEN_SPOTIFY,
    OPEN_GOOGLE_MAPS,
    OPEN_NOTIFICATIONS,
    CLOSE_NOTIFICATIONS,
    ACTIVATE_VOICE,
    DEACTIVATE_VOICE,
    OPEN_CHARGING,
    OPEN_DRIVER_PROFILE,
    OPEN_AMBIENT,
    CLOSE_OVERLAY,
    FAULT_DETECTED,
    FAULT_CLEARED,
    EVENT_COUNT
};

struct VehicleContext {
    float speed_kmh        = 0.0f;
    bool  in_reverse       = false;
    bool  engine_running   = false;
    bool  phone_connected  = false;
    bool  carplay_connected     = false;
    bool  android_auto_connected = false;
    bool  usb_connected    = false;
    bool  aux_connected    = false;
    bool  ev_plugged_in    = false;
    bool  dab_available    = false;
    bool  streaming_connected = false;
    bool  call_active      = false;   // true while PHONE_INCALL — used by mutual-exclusion guard
};

// Plain-data transition descriptor returned to Python
struct TransitionInfo {
    State       from;
    State       to;
    Event       event;
    std::string guard_name;
    std::string description;
};

struct Transition {
    State from;
    State to;
    Event event;
    std::function<bool(const VehicleContext&)> guard;
    std::string guard_name;
    std::string description;
};

class StateMachineError : public std::runtime_error {
public:
    explicit StateMachineError(const std::string& m) : std::runtime_error(m) {}
};

class InfotainmentStateMachine {
public:
    InfotainmentStateMachine();

    bool            transition(Event event);
    State           get_state()   const { return current_state_; }
    VehicleContext  get_context() const { return context_; }
    void            set_context(const VehicleContext& ctx) { context_ = ctx; }
    void            reset();

    std::vector<Event>          get_available_events() const;
    std::vector<Event>          get_valid_events()     const;
    std::vector<TransitionInfo> get_all_transitions()  const;

    static std::string state_name(State s);
    static std::string event_name(Event e);
    static std::vector<std::string> all_state_names();
    static std::vector<std::string> all_event_names();

    size_t transition_count() const { return transition_count_; }
    const std::vector<std::pair<State,State>>& visited_transitions() const {
        return visited_transitions_;
    }

private:
    void register_transitions();
    void add(State from, State to, Event ev,
             std::function<bool(const VehicleContext&)> guard = nullptr,
             std::string guard_name = "",
             std::string desc = "");

    State   current_state_;
    VehicleContext context_;
    std::vector<Transition> transitions_;
    size_t  transition_count_;
    std::vector<std::pair<State,State>> visited_transitions_;
};

} // namespace infotainment
