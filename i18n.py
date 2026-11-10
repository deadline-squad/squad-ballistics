"""The interface texts: tr("key", **values) formats the English string of `key`."""

STRINGS = {
    # Navigation
    "nav_calc": "Calculator",
    "nav_crosshair": "Crosshair",
    "nav_settings": "Settings",
    "nav_web": "SquadCalc",

    # Calculator
    "target": "Target",
    "solution": "Solution",
    "weapon": "Weapon",
    "search": "Search weapons…",
    "recent": "Recent",
    "nothing_found": "Nothing found",
    "found_in_notes": "Found in the notes",
    "arc_auto": "Auto",
    "arc_low": "Low",
    "arc_high": "High",
    "distance": "Distance, m",
    "height": "Height diff, m",
    "height_hint": "target higher +, lower −",
    "fov": "FOV",
    "fov_hint": "horizontal FOV",
    "info_printed_reticle": (
        "Put this mark on the target, not the game's printed range marks "
        "(they fit only at FOV 90)"
    ),
    "info_lift": "aim {lift} m",
    "info_pixel": "1 px = {m} m",
    "info_pixel_high": "1 px = {m} m high",
    "info_pixel_round": "(whole px: {error} m off)",
    "info_pixel_coarse": "too coarse for marker aiming",
    "info_offscreen_far": "mark off screen past {limit} m",
    "info_offscreen_near": "mark off screen closer than {limit} m",
    "calculate": "Calculate",
    "reset_aim": "Reset",
    "ready": "Enter the distance",
    "unreachable": "Unreachable",
    "enter_distance": "Enter the distance",
    "bad_fov": "FOV must be between 1 and 179",
    "bad_number": "The number is too large",
    "bad_distance": "Distance must be greater than 0",

    "stat_tof": "Flight time",
    "stat_apex": "Apex",
    "stat_offset": "Mark offset",
    "stat_impact": "Impact angle",
    "stat_velocity": "Avg. velocity",
    "stat_alt": "Other arc",
    "off_screen": "off-screen",
    "unit_s": "s",
    "unit_m": "m",
    "unit_px": "px",
    "unit_mps": "m/s",
    "mil": "mil",

    "open_failed": "Could not open: {target}",

    "how_to": "How to fire",
    "how_overlay_on": "Turn the overlay on ({hotkey}).",
    "how_overlay_1": (
        "Put the overlay mark on the target — the barrel is then raised "
        "exactly {angle} above the line to the target."
    ),
    "how_overlay_optic": (
        "Your in-game FOV must be {fov}° (the game's setting, not the sight's). "
        "The mark is for the sight's view, zoom ×{zoom}."
    ),
    "how_view_optic": (
        "Aim through the optic: hold RMB (zoom ×{zoom}). Without it pick "
        "\"{twin}\". Your in-game FOV must be {fov}° (the game's setting, "
        "not the sight's)."
    ),
    "how_view_plain": (
        "Aim without the optic: do not press RMB (no zoom). Through the optic "
        "pick \"{twin}\". Your in-game FOV must be {fov}°."
    ),
    "how_overlay_2": "Your in-game FOV must be {fov}°.",
    "how_overlay_offscreen": (
        "The mark is off-screen: raise the barrel {angle} above the target "
        "using the sight scale, or move closer."
    ),
    "to_horizon": "{angle} to the horizon",
    "how_elevation_1": "Turn to the target bearing (map or SquadCalc).",
    "how_elevation_2": "Set the elevation to {angle}.",
    "how_bearing": "Turn to bearing {b}° (from the SquadCalc map).",
    "hold_big": "S {t} s",
    "lay_short": "auto-lay: S {t} s",
    "lay_read": "Sight shows (mil):",
    "lay_calibrate": "Calibrate",
    "lay_reset": "Reset",
    "lay_done": "Auto-lay rate: {rate}°/s (game files: {base}°/s)",
    "lay_reset_done": "Auto-lay rate from the game files: {base}°/s",
    "lay_need_hold": "Lay first (auto-lay, or W then S for over {t} s)",
    "lay_out_of_range": "Unlikely: {rate}°/s against {base}°/s in the game files — check the mils",
    "how_lay": (
        "Or auto-lay: in the mortar sight press {hotkey} — the app reads the "
        "mils off the sight on the screen and holds W or S until it shows "
        "the target. If the sight cannot be read, it raises the barrel to "
        "its top (W) and lowers it by holding S for {t} s. The key again "
        "cancels."
    ),
    "sight_reading": "sight {mils} mil",
    "sight_reading_left": "sight {mils} mil ({left})",
    "compass_reading": "bearing {deg}°",
    "compass_reading_left": "bearing {deg}° ({left})",
    "lay_need_mils": "Type the mils the sight shows",
    "lay_after_sight": (
        "The last lay was on the sight (taps of W and S), which says nothing "
        "about the rate: press W, lay again without the sight, then calibrate"
    ),

    # Why the auto-lay key did nothing, or why a lay stopped short (overlay)
    "lay_key_weapon": "{key}: this weapon is not laid by holding a key",
    "lay_key_no_target": "{key}: no target, enter a distance in range",
    "lay_key_no_reader": (
        "{key}: the keyboard cannot be read (input group, or the game on "
        "X11/XWayland)"
    ),
    "lay_key_no_keys": "{key}: the app cannot send key presses here",
    "lay_key_no_w": "{key}: W cannot be sent, so the barrel cannot go to its top",
    "lay_key_held": "{key}: S is already held for the target time, press W to lay again",
    "lay_failed": "{what} lay stopped: {why}",
    "lay_bearing": "Bearing",
    "lay_elevation": "Elevation",
    "lay_why_target": "the target is gone",
    "lay_why_lost": "it is no longer seen on the screen",
    "lay_why_moves": "not on the target after {moves} moves",
    "lay_why_stalled": "the key moved nothing (end of travel?)",
    "lay_why_timeout": "the move took far too long",
    "lay_why_error": "an error (see crash.log in the settings folder)",
    "lay_no_grab": "The screen cannot be grabbed (Wayland without X11): type the mils the sight shows",
    "lay_no_sight": "The sight was not read: look through the mortar sight or type the mils. Grab: {path}",
    "how_lay_off": "Auto-lay (S {t} s) can be turned on in the settings: \"Auto-hold S\".",
    "how_hold_1": "Press W — the barrel goes back to the top.",
    "how_hold_2": "Hold S for {t} s, then release.",
    "direct_short": "direct fire {angle}",
    "blocked_short": "⛔ {d} m",
    "how_blocked": (
        "⛔ {arc} trajectory hits an obstacle after {d} m "
        "(terrain or a building, {h} m from you in height)"
    ),
    "how_blocked_use": "{arc} trajectory clears it: fire that one ({angle})",
    "how_blocked_all": "Both trajectories are blocked: move to another position",
    "how_direct_blocked": "Direct fire is blocked after {d} m: lob only",
    "how_hold_direct": (
        "Or direct fire: put the overlay mark on the target — the barrel is "
        "then raised {angle} above the line to the target."
    ),
    "how_hold_direct_offscreen": (
        "Or direct fire: barrel {angle} above the target (the mark is "
        "off-screen)."
    ),
    "how_tof_moving": "Flight time {tof} s: lead a target moving at 10 m/s by ≈ {lead} m.",
    "how_tof_adjust": "Impact after {tof} s. Short — add distance, long — reduce it.",
    "how_unreachable_range": (
        "The target is beyond maximum range (~{max} m). Move closer or "
        "pick another weapon."
    ),
    "how_unreachable_close": (
        "Too close: the minimum distance on level ground is {min} m."
    ),
    "how_unreachable_muzzle": "Too close: the target is not past the muzzle.",
    "how_unreachable_hold": (
        "The high arc needs {angle}, but holding S only moves the barrel "
        "from {low} to {high}. Try the low arc."
    ),
    "how_unreachable_limit": (
        "Needs {angle}, but the weapon only elevates from {low} to {high}."
    ),
    "how_unreachable_other_arc": "Try the other arc.",

    "chip_velocity": "{v} m/s",
    "chip_gravity": "gravity ×{g}",
    "chip_range": "up to {r} m",
    "chip_range_inf": "no drop",
    "chip_boost": "boost {a:+g} m/s² · {t:g} s",
    "chip_min": "from {m} m",
    "view_optic": "Aim through the optic: hold RMB (×{zoom})",
    "view_plain": "Aim without the optic: do not press RMB",
    "info_view_optic": "optic ×{zoom} (RMB)",
    "info_view_plain": "no optic",
    "info_focus_follows": "The mark follows Focus (Left Shift).",
    "info_focus_assumed": "The mark assumes Focus (Left Shift) is not held.",

    # Categories
    "cat_grenade_launchers": "Grenade launchers",
    "cat_agl": "Automatic grenade launchers",
    "cat_launchers": "Anti-tank launchers",
    "cat_guns": "Recoilless & field guns",
    "cat_tanks": "Tank guns",
    "cat_indirect": "Indirect fire",
    "cat_other": "Other",

    # Splash
    "splash_loading": "Starting…",
    "error_title": "Squad Ballistics — error",
    "error_saved": "Details saved to:\n{path}",
    "already_running": (
        "Squad Ballistics is already running. Two copies would draw two "
        "overlays and send every hotkey twice, so this one is closing."
    ),
    "config_unreadable": (
        "The settings file could not be read, so the defaults are used.\n"
        "The old file is kept here:\n{path}"
    ),
    "no_compositor_title": "Overlay needs a compositor",
    "no_compositor": (
        "The overlay is hidden: no compositing manager is running on this "
        "X11 desktop, so it would cover the whole screen in black instead of "
        "drawing only the mark.\n\n"
        "Turn compositing on (Xfce: Window Manager Tweaks → Compositor) or "
        "start a compositor such as picom. The overlay comes back by itself "
        "as soon as one runs, or press the overlay hotkey."
    ),
    "no_compositor_kde": (
        "The overlay is hidden: compositing is off on this X11 desktop, so "
        "it would cover the whole screen in black instead of drawing only "
        "the mark.\n\n"
        "KDE Plasma lets a fullscreen game turn compositing off, and games "
        "under Proton ask for it. In System Settings → Display & Monitor → "
        "Compositor, untick \"Allow applications to block compositing\", or "
        "add a rule for the game in System Settings → Window Management → "
        "Window Rules: \"Block compositing\", Force, No. If compositing is "
        "off altogether, tick \"Enable on startup\" there and press "
        "Alt+Shift+F12.\n\n"
        "The overlay comes back by itself as soon as compositing runs, or "
        "press the overlay hotkey."
    ),

    # Crosshair page
    "preview": "Preview",
    "mark_caption": "The mark shows where to put the target: it moves down with the range.",
    "align_title": "Align with the sight",
    "align_caption": "Move and scale the mark onto the sight in the game. Arrow keys step by 1; {key} clears the target, not the alignment.",
    "align_x": "Move left/right",
    "align_y": "Move up/down",
    "align_scale": "Scale",
    "align_reset": "Reset",
    "opt_ladder": "Range ladder",
    "opt_info": "Info text",

    # Settings page
    "s_interface": "Interface",
    "s_on_top": "Keep window on top",
    "s_calc": "Calculator",
    "s_units": "Primary angle unit",
    "s_units_auto": "Per weapon",
    "s_units_deg": "Degrees",
    "s_units_mil": "Mils",
    "s_auto_calc": "Calculate while typing",
    "s_step": "Distance step (wheel & keys)",
    "s_overlay": "Overlay",
    "s_monitor": "Monitor",
    "s_hotkeys": "Hotkeys",
    "s_hotkeys_hint": (
        "They work in game, and the game receives these keys too (keys are "
        "read like for the AGS-17 timer)."
    ),
    "hk_toggle_overlay": "Overlay on/off",
    "hk_reset_offset": "Reset mark",
    "hk_distance_up": "Distance +",
    "hk_distance_down": "Distance −",
    "hk_auto_hold": "Auto-hold S / mortar auto-lay",
    "hk_toggle_view": "Optic / no optic (RMB sights)",
    "hk_none": "None",
    "s_about": "About",
    "s_version": "Version {v}",
    "s_open_config": "Settings folder",
    "s_reset": "Reset settings",
    "s_reset_confirm": "Reset all crosshair and app settings?",
    # Map page
    "map_loading": "Loading the map…",
    "map_reload": "Reload",
    "map_retry": "Retry",
    "map_compat_button": "Compatibility mode",
    "map_compat_on": "compatibility mode",
    "map_failed_title": "The map did not load",
    "map_failed_text": (
        "Could not reach {host}. Check your connection and press "
        "Retry. If the site opens in your regular browser, use it there."
    ),
    "map_slow_title": "The map takes too long",
    "map_slow_text": (
        "The site responds very slowly or the connection is blocked. Wait, "
        "press Retry or open the map in your regular browser."
    ),
    "map_crashed_title": "The map stopped responding",
    "map_crashed_text": (
        "The embedded browser crashed. Press Retry. If it keeps happening, "
        "turn on compatibility mode."
    ),
    "map_black_title": "Is the map black?",
    "map_black_text": (
        "Your graphics driver does not seem to draw the embedded browser. "
        "Compatibility mode draws the map without the GPU (the app restarts)."
    ),
    "map_missing_title": "Embedded map unavailable",
    "map_missing_text": (
        "This build has no embedded browser. Open the map in your regular "
        "browser."
    ),
    "s_map": "Map",
    "s_map_source": "SquadCalc",
    "s_map_source_deadline": "Deadline (direct fire, AGS-17)",
    "s_map_follow": "Put the map target and weapon into the calculator",
    "map_target": "From the map: {t}",
    "map_follow_hint": (
        "Place the weapon and a target on the SquadCalc map — distance and "
        "height fill in by themselves, and the weapon selected in the "
        "Deadline SquadCalc is selected here too."
    ),
    "bearing_short": "bearing {b}°",
    "map_bridge_on": "targets go to the calculator",
    "map_bridge_off": "this map does not share targets (use the Deadline SquadCalc)",
    "map_external_opened": "Opened in the browser: {url}",
    "map_external_blocked": "Not opened, the map asked without a click: {url}",
    "s_map_render": "Map rendering",
    "s_map_render_auto": "Normal",
    "s_map_render_software": "Compatible",
    "s_map_render_hint": (
        "Compatible — if the map is black, flickers or lags: draws without the "
        "GPU, a bit slower. Applied after a restart."
    ),
    "s_map_render_in_use": "In use now: {mode}.",
    "s_map_render_in_use_hardware": "with the GPU",
    "s_map_render_in_use_software": "without the GPU (compatible)",
    "s_map_render_in_use_auto_software": (
        "without the GPU, picked automatically: Qt's OpenGL runs on the CPU "
        "({renderer})"
    ),
    "s_map_external": "Open the map in the regular browser",
    "s_map_clear": "Clear map cache",
    "s_map_cleared": "Cache cleared",
    "s_auto_hold": "Auto-hold S (key {key})",
    "s_auto_hold_hint": (
        "On the key the app holds S for the time left to the target and "
        "releases it (mortars: on the sight on the screen, or if it cannot "
        "be read, W to the top first, then S for the whole time); the key "
        "again or W cancels. Synthetic key presses may "
        "be treated as a macro by the anti-cheat (EAC) or server rules — "
        "enable at your own risk. Needs access to /dev/uinput "
        "(Steam rules) or the game on X11/XWayland."
    ),
    "s_sight_reader": "Read the mortar sight off the screen",
    "s_sight_reader_hint": (
        "While a mortar is selected the app reads the mils off its sight's "
        "scale (left of the screen centre) and shows them on the overlay "
        "next to the target ones. The auto-lay then lays on the screen: for "
        "a SquadCalc map target it first turns the mortar (D/A) on the "
        "compass at the bottom of the screen, then holds W or S until the "
        "sight shows the target within 0.5 mil. Lay from the mortar's own "
        "view, not zoomed in (right mouse button): it shows both the scale "
        "and the compass. The screen is grabbed under X11 and XWayland, not "
        "under pure Wayland."
    ),
    "auto_hold_unavailable": "Not possible: the app cannot send key presses on this system.",
    "restart_title": "Restart",
    "restart_text": "Restart the app now to apply the change?",

    "web_open": "Open in browser",

    "screen_not_16_9": (
        "The game's screen or window {size} is not 16:9. Reading the mortar "
        "sight and the compass off the screen works on 16:9 only (1920x1080, "
        "2560x1440); it may fail here."
    ),
}


def tr(string_id, /, **values):
    """The text of `string_id` with `values` put into its {placeholders}.

    An id with no entry is returned as it is, so a typo shows up on screen.
    """
    text = STRINGS.get(string_id, string_id)

    return text.format(**values) if values else text


def category_name(category):
    """The group title of a weapons.json `category` (the id if it has none)."""
    key = f"cat_{category}"
    return tr(key) if key in STRINGS else category
