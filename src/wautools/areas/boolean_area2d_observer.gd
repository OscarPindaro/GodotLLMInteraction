class_name BooleanArea2DObserver
extends Node2D
## Observes a single BooleanArea2D instance and relays its activation signals.
##
## The BooleanArea2DObserver provides a simple way to connect to a single BooleanArea2D's
## signals and relay them with optional processing. This is useful for creating decoupled
## systems where the observer can be placed as a child of nodes that need to respond
## to area activation without directly connecting to the area.
##
## The observer acts as a relay, emitting the same signals as the observed area,
## but can also provide additional functionality like state queries and validation.
## Optionally, if the parent of the observer has two methods, called
## 'on_area_activated' and 'on_area_deactivated', they will be automatically
## called, so you don't have to setup any signal.
##
## [b]Example usage:[/b]
## [codeblock]
## # In a Door scene, add BooleanArea2DObserver as child
## # Set the observed_area property to point to a pressure plate
##
## # In the Door script:
## @onready var observer = $BooleanArea2DObserver
##
## func _ready():
##     observer.activated.connect(_open_door)
##     observer.deactivated.connect(_close_door)
##
## func _open_door():
##     play_animation("open")
##
## func _close_door():
##     play_animation("close")
## [/codeblock]
##
## [b] Duck Typing Example Usage: [/b]
## [codeblock]
## # In a Door scene, add BooleanArea2DObserver as child
## # Set the observed_area property to point to a pressure plate
##
## # In the Door script:
## @onready var observer = $BooleanArea2DObserver
##
## func _ready():
##     observer.activated.connect(_open_door)
##     observer.deactivated.connect(_close_door)
##
## func on_area_activated(area: BooleanArea2D):
##     _open_door()
##
## func on_area_deactivated(area: BooleanArea2D):
##     _close_door()
##
## func _open_door():
##     play_animation("open")
##
## func _close_door():
##     play_animation("close")
## [/codeblock]

## Emitted when the observed area becomes active.
## This signal is relayed from the observed area's [signal BooleanArea2D.activated] signal.
signal activated

## Emitted when the observed area becomes inactive.
## This signal is relayed from the observed area's [signal BooleanArea2D.deactivated] signal.
signal deactivated

## Emitted whenever the observed area's state changes.
## [param is_active]: The new active state of the observed area.
signal state_changed(is_active: bool)

## The BooleanArea2D instance to observe. Can be set in the editor.
@export var observed_area: BooleanArea2D = null:
	set = set_observed_area

## Returns [code]true[/code] if the observed area is currently active.
## Returns [code]false[/code] if no area is being observed or if the area is inactive.
var is_active: bool:
	get = get_is_active


func _ready() -> void:
	_connect_area_signals()


## Sets the observed area and updates signal connections.
##
## [param area]: The BooleanArea2D to observe. Can be [code]null[/code] to stop observing.
func set_observed_area(area: BooleanArea2D) -> void:
	# Disconnect from the previous area
	_disconnect_area_signals()

	observed_area = area

	# Connect to the new area
	if is_inside_tree():
		_connect_area_signals()

		# Emit initial state if we have an area
		if observed_area != null:
			_emit_state_signals(false)  # Don't emit change signal on setup


## Returns whether the observed area is currently active.
##
## [return]: [code]true[/code] if the observed area exists and is active,
## [code]false[/code] otherwise.
func get_is_active() -> bool:
	if observed_area == null:
		return false
	return observed_area.active


## Returns whether an area is currently being observed.
##
## [return]: [code]true[/code] if [member observed_area] is not [code]null[/code],
## [code]false[/code] otherwise.
func has_observed_area() -> bool:
	return observed_area != null


## Manually refresh the connection to the observed area.
##
## This method can be useful if the observed area was changed programmatically
## or if you suspect the connection might have been broken.
func refresh_connection() -> void:
	if observed_area != null:
		_disconnect_area_signals()
		_connect_area_signals()


## Returns the observed area's body count if available.
##
## [return]: Number of bodies in the observed area, or 0 if no area is observed.
func get_observed_bodies_count() -> int:
	if observed_area == null:
		return 0
	return observed_area.get_bodies_count()


## Returns the observed area's area count if available.
##
## [return]: Number of areas overlapping the observed area, or 0 if no area is observed.
func get_observed_areas_count() -> int:
	if observed_area == null:
		return 0
	return observed_area.get_areas_count()


## Returns the observed area's total tracked object count if available.
##
## [return]: Total number of tracked objects in the observed area, or 0 if no area is observed.
func get_observed_tracked_count() -> int:
	if observed_area == null:
		return 0
	return observed_area.get_tracked_object_count()


## Connects to the observed area's signals if an area is set.
func _connect_area_signals() -> void:
	if observed_area == null:
		return

	if not observed_area.activated.is_connected(_on_area_activated):
		observed_area.activated.connect(_on_area_activated)
	if not observed_area.deactivated.is_connected(_on_area_deactivated):
		observed_area.deactivated.connect(_on_area_deactivated)


## Disconnects from the currently observed area's signals.
func _disconnect_area_signals() -> void:
	if observed_area == null:
		return

	if not is_instance_valid(observed_area):
		return

	if observed_area.activated.is_connected(_on_area_activated):
		observed_area.activated.disconnect(_on_area_activated)
	if observed_area.deactivated.is_connected(_on_area_deactivated):
		observed_area.deactivated.disconnect(_on_area_deactivated)


## Handles when the observed area becomes activated.


## When the observed area is activated, this object emits the same signal.
## This method uses duck typing to call a default 'on_area_activated' method on the parent,
## passing the BooleanArea. If the parent does not have the method, nothing happens
## and you can wire your objects with signals
func _on_area_activated() -> void:
	activated.emit()
	_emit_state_signals(true)

	var parent = get_parent()
	if parent.has_method("on_area_activated"):
		parent.on_area_activated(self.observed_area)


## Handles when the observed area becomes deactivated.
func _on_area_deactivated() -> void:
	deactivated.emit()
	_emit_state_signals(true)
	var parent = get_parent()
	if parent.has_method("on_area_deactivated"):
		parent.on_area_deactivated(self.observed_area)


## Emits the state_changed signal with the current state.
##
## [param emit_change_signal]: Whether to emit the state_changed signal.
func _emit_state_signals(emit_change_signal: bool) -> void:
	if emit_change_signal and observed_area != null:
		state_changed.emit(observed_area.active)


## Cleanup when the node is removed from the scene.
func _exit_tree() -> void:
	_disconnect_area_signals()


func _get_configuration_warnings() -> PackedStringArray:
	var warnings: PackedStringArray = []

	if observed_area == null:
		warnings.append("No area to observe. Set 'observed_area' to make this observer functional.")

	return warnings
