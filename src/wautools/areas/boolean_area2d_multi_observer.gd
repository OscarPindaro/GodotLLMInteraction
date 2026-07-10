class_name BooleanArea2DMultiObserver
extends Node2D
## Observes one or more BooleanArea2D instances and emits signals based on their collective state.
##
## The BooleanArea2DObserver can track multiple BooleanArea2D instances either through
## an exported array that can be configured in the editor, or by automatically finding
## all BooleanArea2D nodes in a specified group. It monitors their activated/deactivated
## signals and emits its own signals based on the collective state.
##
## This is useful for creating systems that need to respond to multiple areas, such as:
## - Doors that open when all pressure plates are activated
## - Bridges that extend when any switch is activated
## - Puzzles that require specific combinations of area states
##
## [b]Example usage:[/b]
## [codeblock]
## # Connect to observer signals in a door script
## func _ready():
##     var observer = $BooleanArea2DObserver
##     observer.all_activated.connect(_on_all_areas_activated)
##     observer.all_deactivated.connect(_on_all_areas_deactivated)
##
## func _on_all_areas_activated():
##     # Open the door
##     play_animation("open")
##
## func _on_all_areas_deactivated():
##     # Close the door
##     play_animation("close")
## [/codeblock]

## Emitted when at least one observed area becomes active.
signal any_activated

## Emitted when all observed areas become inactive.
signal any_deactivated

## Emitted when all observed areas become active.
signal all_activated

## Emitted when at least one observed area becomes inactive (but not all).
signal all_deactivated

## Emitted whenever the activation state of any observed area changes.
## [param active_count]: Number of currently active areas.
## [param total_count]: Total number of observed areas.
signal state_changed(active_count: int, total_count: int)

## Array of BooleanArea2D nodes to observe. Can be set in the editor.
@export_group("Area Configuration")
@export var observed_areas: Array[BooleanArea2D] = []:
	set = set_observed_areas

## Name of a group to automatically observe all BooleanArea2D nodes within it.
## If empty, only the [member observed_areas] array will be used.
@export var observe_group: String = "":
	set = set_observe_group

## The current number of active (activated) areas being observed.
var active_count: int = 0:
	get = get_active_count

## The total number of areas being observed.
var total_count: int = 0:
	get = get_total_count

## Internal array that holds all currently observed areas (from both array and group).
var _all_observed_areas: Array[BooleanArea2D] = []


func _ready() -> void:
	_update_observed_areas()


## Sets the observed_areas array and updates connections.
##
## [param areas]: Array of BooleanArea2D nodes to observe.
func set_observed_areas(areas: Array[BooleanArea2D]) -> void:
	observed_areas = areas
	if is_inside_tree():
		_update_observed_areas()


## Sets the observe_group property and updates connections.
##
## [param group_name]: Name of the group to observe BooleanArea2D nodes from.
func set_observe_group(group_name: String) -> void:
	observe_group = group_name
	if is_inside_tree():
		_update_observed_areas()


## Returns the current number of active areas.
##
## [return]: Number of currently active areas.
func get_active_count() -> int:
	return active_count


## Returns the total number of observed areas.
##
## [return]: Total number of areas being observed.
func get_total_count() -> int:
	return total_count


## Returns whether all observed areas are currently active.
##
## [return]: [code]true[/code] if all areas are active, [code]false[/code] otherwise.
## Returns [code]false[/code] if no areas are being observed.
func are_all_active() -> bool:
	return total_count > 0 and active_count == total_count


## Returns whether any observed areas are currently active.
##
## [return]: [code]true[/code] if at least one area is active, [code]false[/code] otherwise.
func is_any_active() -> bool:
	return active_count > 0


## Returns whether all observed areas are currently inactive.
##
## [return]: [code]true[/code] if all areas are inactive, [code]false[/code] otherwise.
## Returns [code]true[/code] if no areas are being observed.
func are_all_inactive() -> bool:
	return active_count == 0


## Manually refresh the list of observed areas.
##
## This method re-evaluates both the exported array and the group membership,
## updating all signal connections accordingly. Useful if group membership
## changes during runtime.
func refresh_observed_areas() -> void:
	_update_observed_areas()


## Updates the complete list of observed areas and reconnects all signals.
func _update_observed_areas() -> void:
	# Disconnect from all current areas
	_disconnect_all_signals()

	# Clear the internal array
	_all_observed_areas.clear()

	# Add areas from the exported array
	for area in observed_areas:
		if area != null and not _all_observed_areas.has(area):
			_all_observed_areas.append(area)

	# Add areas from the group (if specified)
	if observe_group != "":
		var group_nodes = get_tree().get_nodes_in_group(observe_group)
		for node in group_nodes:
			if node is BooleanArea2D and not _all_observed_areas.has(node):
				_all_observed_areas.append(node as BooleanArea2D)

	# Update counters
	total_count = _all_observed_areas.size()

	# Connect to all areas and count currently active ones
	active_count = 0
	for area in _all_observed_areas:
		_connect_area_signals(area)
		if area.active:
			active_count += 1

	# Emit initial state
	_emit_state_signals(false)  # Don't emit change-based signals on initialization


## Connects to the signals of a specific BooleanArea2D.
##
## [param area]: The BooleanArea2D to connect signals from.
func _connect_area_signals(area: BooleanArea2D) -> void:
	if not area.activated.is_connected(_on_area_activated):
		area.activated.connect(_on_area_activated.bind(area))
	if not area.deactivated.is_connected(_on_area_deactivated):
		area.deactivated.connect(_on_area_deactivated.bind(area))


## Disconnects from all currently observed areas.
func _disconnect_all_signals() -> void:
	for area in _all_observed_areas:
		if is_instance_valid(area):
			if area.activated.is_connected(_on_area_activated):
				area.activated.disconnect(_on_area_activated)
			if area.deactivated.is_connected(_on_area_deactivated):
				area.deactivated.disconnect(_on_area_deactivated)


## Handles when an observed area becomes activated.
##
## [param area]: The BooleanArea2D that became activated.
func _on_area_activated(_area: BooleanArea2D) -> void:
	var was_any_active = active_count > 0
	var were_all_active = active_count == total_count

	active_count += 1

	# Emit appropriate signals
	if not was_any_active:
		any_activated.emit()

	if active_count == total_count:
		all_activated.emit()

	_emit_state_signals(true)


## Handles when an observed area becomes deactivated.
##
## [param area]: The BooleanArea2D that became deactivated.
func _on_area_deactivated(_area: BooleanArea2D) -> void:
	var was_any_active = active_count > 0
	var were_all_active = active_count == total_count

	active_count -= 1
	if active_count < 0:  # Safety check
		active_count = 0

	# Emit appropriate signals
	if were_all_active:
		all_deactivated.emit()

	if active_count == 0:
		any_deactivated.emit()

	_emit_state_signals(true)


## Emits the state_changed signal and handles initial state signals.
##
## [param emit_change_signals]: Whether to emit change-based signals (for runtime changes).
func _emit_state_signals(emit_change_signals: bool) -> void:
	state_changed.emit(active_count, total_count)

	if not emit_change_signals:
		return

	# Note: The specific change signals (any_activated, all_activated, etc.)
	# are emitted in the individual handler methods above, not here.


## Cleanup when the node is removed from the scene.
func _exit_tree() -> void:
	_disconnect_all_signals()


func _get_configuration_warnings() -> PackedStringArray:
	var warnings: PackedStringArray = []

	if observed_areas.is_empty() and observe_group == "":
		(
			warnings
			. append(
				(
					"No areas to observe."
					+ " Set either 'observed_areas' or 'observe_group' to make this observer functional."
				)
			)
		)

	# Check if any areas in the array are null or invalid
	for i in range(observed_areas.size()):
		if observed_areas[i] == null:
			warnings.append("Element %d in 'observed_areas' is null." % i)

	return warnings
