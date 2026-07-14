from __future__ import annotations

CURRENT_DEFAULTS = {
    "current_patients": 50.0,
    "current_scanners": 2,
    "current_injection_rooms": 6,
    "current_uptake_rooms": 6,
    "current_batches": 2,
}

CURRENT_KEYS = {
    "current_patients": "cp",
    "current_scanners": "cs",
    "current_injection_rooms": "ci",
    "current_uptake_rooms": "cu",
    "current_batches": "cb",
}

BACKUP_KEYS = {name: f"_expansion_{name}" for name in CURRENT_KEYS}


def initialize_project_state(state) -> None:
    state.setdefault("mode", "Expansion")
    for name, widget_key in CURRENT_KEYS.items():
        default = CURRENT_DEFAULTS[name]
        state.setdefault(widget_key, default)
        state.setdefault(BACKUP_KEYS[name], default)


def apply_project_mode(state) -> None:
    """Synchronize current-state widgets with the selected project mode.

    Greenfield stores the last Expansion values, then forces every current
    quantity to zero. Returning to Expansion restores the saved values.
    """
    initialize_project_state(state)
    mode = state.get("mode", "Expansion")

    if mode == "Greenfield":
        if state.get("_last_applied_mode") != "Greenfield":
            for name, widget_key in CURRENT_KEYS.items():
                state[BACKUP_KEYS[name]] = state.get(widget_key, CURRENT_DEFAULTS[name])
        for widget_key in CURRENT_KEYS.values():
            state[widget_key] = 0.0 if widget_key == "cp" else 0
    else:
        if state.get("_last_applied_mode") == "Greenfield":
            for name, widget_key in CURRENT_KEYS.items():
                state[widget_key] = state.get(BACKUP_KEYS[name], CURRENT_DEFAULTS[name])

    state["_last_applied_mode"] = mode
