extends Node
class_name Log

## Centralized logger with levels, colored output, and per-label filtering.

# ── Usage ───────────────────────────────────────────────────────────────

##   Log.debug("NPC", "Spawned at ", position)
##   Log.info("Revenue", "Year ended with ", total)
##   Log.warn("Camera", "Zoom out of bounds")
##   Log.error("Game", "No spawn positions found")

## For logging inside frame functions use _frame variants, disabled by default
## E.g:  Log.debug_frame("NPC", "Spawned at ", position)

# ── Configuration ───────────────────────────────────────────────────────────────

##   Log.min_level = Log.Level.WARN              # suppress DEBUG and INFO globally
##   Log.enable_label("NPC")                     # only show NPC logs (allowlist mode)
##   Log.disable_label("Camera")                 # hide Camera logs (blocklist mode)
##   Log.set_label_level("NPC", Log.Level.DEBUG) # per-label override
##   Log.set_label_color("NPC", "green")         # custom label color
##   Log.show_timestamp = true                   # enable timestamps
##   Log.frame_log_time_s = n                    # if n > 0, log once every n seconds 
##												 # in frame functions, set fps to 60

# ── Attributes ───────────────────────────────────────────────────────────────

enum Level {DEBUG = 0, INFO = 1, WARN = 2, ERROR = 3, NONE = 4}

## Global minimum log level. Messages below this are discarded.
static var min_level: Level = Level.DEBUG

## Per-label level overrides. If a label is here, its threshold takes priority
## over min_level.
static var _label_levels: Dictionary = {}

## If non-empty, ONLY these labels will produce output (allowlist mode).
## Takes priority over _disabled_labels.
static var _enabled_labels: Dictionary = {}

## Labels in this set are silenced (blocklist mode). Ignored if _enabled_labels
## is non-empty.
static var _disabled_labels: Dictionary = {}

## Per-label color overrides. Default is "cyan" for all labels.
## Accepts any BBCode color name: "red", "green", "yellow", "magenta", etc.
## or hex: "#ff8800".
static var _label_colors: Dictionary = {}

## Whether to include a timestamp in each log line.
static var show_timestamp: bool = false

## If > 0, sets the time window for frame logs (in seconds).
static var frame_log_time_s: int = -1:
	set(value):
		frame_log_time_s = value
		Engine.max_fps = 60 if value > 0 else 0

static var frame_number: int = 0


# ── Colors (BBCode for print_rich) ──────────────────────────────────────────

const _DEFAULT_LABEL_COLOR: String = "cyan"

const _LEVEL_COLORS: Dictionary = {
	Level.DEBUG: "gray",
	Level.INFO: "white",
	Level.WARN: "yellow",
	Level.ERROR: "red",
}

const _LEVEL_NAMES: Dictionary = {
	Level.DEBUG: "DEBUG",
	Level.INFO: "INFO ",
	Level.WARN: "WARN ",
	Level.ERROR: "ERROR",
}


# ── Public API ───────────────────────────────────────────────────────────────

##### LOG LEVEL #####
## WARN and ERROR also push a Godot warning/error (shows in Debugger panel).
static func debug(label: String, ...args: Array) -> void:
	_log(Level.DEBUG, label, args)


static func info(label: String, ...args: Array) -> void:
	_log(Level.INFO, label, args)


static func warn(label: String, ...args: Array) -> void:
	_log(Level.WARN, label, args)


static func error(label: String, ...args: Array) -> void:
	_log(Level.ERROR, label, args)


##### LABEL FILTERING #####
## Allowlist mode: only show logs from this label. Call multiple times to allow
## several labels. Call clear_enabled_labels() to return to default (show all).
static func enable_label(label: String) -> void:
	_enabled_labels[label] = true


static func remove_enabled_label(label: String) -> void:
	_enabled_labels.erase(label)


static func clear_enabled_labels() -> void:
	_enabled_labels.clear()


## Blocklist mode: hide logs from this label.
static func disable_label(label: String) -> void:
	_disabled_labels[label] = true


static func remove_disabled_label(label: String) -> void:
	_disabled_labels.erase(label)


## Set a per-label minimum level (overrides the global min_level for this label).
static func set_label_level(label: String, level: Level) -> void:
	_label_levels[label] = level


static func clear_label_level(label: String) -> void:
	_label_levels.erase(label)


##### LABEL COLORS #####

## Assign a color to a label. Accepts BBCode color names ("red", "green",
## "magenta", "orange") or hex ("#ff8800").
static func set_label_color(label: String, color: String) -> void:
	_label_colors[label] = color


static func clear_label_color(label: String) -> void:
	_label_colors.erase(label)


##### FRAME LOGGING #####
## Frame logging is enabled only if frame_log_time_s > 0
## when enabled, fps are set to 60

static func debug_frame(label: String, ...args: Array) -> void:
	_log_frame(Level.DEBUG, label, args)


static func info_frame(label: String, ...args: Array) -> void:
	_log_frame(Level.INFO, label, args)


static func warn_frame(label: String, ...args: Array) -> void:
	_log_frame(Level.WARN, label, args)


static func error_frame(label: String, ...args: Array) -> void:
	_log_frame(Level.ERROR, label, args)


# ── Internals ────────────────────────────────────────────────────────────────

static func _should_log(level: Level, label: String) -> bool:
	# Check allowlist first
	if not _enabled_labels.is_empty() and not _enabled_labels.has(label):
		return false

	# Then blocklist
	if _enabled_labels.is_empty() and _disabled_labels.has(label):
		return false

	# Check level threshold (per-label override or global)
	var threshold: Level = _label_levels.get(label, min_level)
	return level >= threshold


static func _log(level: Level, label: String, args: Array) -> void:
	if not _should_log(level, label):
		return

	var level_color: String = _LEVEL_COLORS[level]
	var label_color: String = _label_colors.get(label, _DEFAULT_LABEL_COLOR)
	var level_name: String = _LEVEL_NAMES[level]

	var msg := ""
	for arg in args:
		msg += str(arg)

	var timestamp := ""
	if show_timestamp:
		var ticks := Time.get_ticks_msec()
		var secs := ticks / 1000
		var ms := ticks % 1000
		var mins := secs / 60
		secs = secs % 60
		timestamp = "[color=dimgray]%02d:%02d.%03d[/color] " % [mins, secs, ms]

	var line := "%s[color=%s][b]%s[/b][/color] [color=%s][%s][/color] %s" % [
		timestamp, level_color, level_name, label_color, label, msg
	]

	print_rich(line)

	# Also integrate with Godot's built-in warning/error system
	if level == Level.WARN:
		push_warning("[%s] %s" % [label, msg])
	elif level == Level.ERROR:
		push_error("[%s] %s" % [label, msg])

static func _log_frame(level: Level, label: String, args: Array) -> void:
	if frame_log_time_s <= 0:
		return
	
	frame_number += 1

	if frame_number < frame_log_time_s * 60:
		return

	frame_number = 0
	_log(level, label, args)