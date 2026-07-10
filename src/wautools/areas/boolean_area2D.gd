class_name BooleanArea2D
extends Area2D
## An abstract boolean state area that provides core functionality for state tracking.
##
## BooleanArea2D provides the foundation for creating interactive areas that can track
## their active state and emit appropriate signals. This base class handles signal
## management and state changes, while subclasses implement the specific logic for
## when and how the state should change.
##
## The area automatically connects to body/area enter/exit signals based on the
## [member track_bodies] and [member track_areas] properties. When objects interact
## with the area, the corresponding virtual methods are called, allowing subclasses
## to implement their own activation logic.
##
## [b]Example usage:[/b]
## [codeblock]
## extends BooleanArea2D
## class_name PressurePlate
##
## func _on_object_entered(object):
##     if _get_tracked_object_count() > 0:
##         set_active(true)
##
## func _on_object_exited(object):
##     if _get_tracked_object_count() == 0:
##         set_active(false)
## [/codeblock]

## Emitted when the area becomes active
## (when [member active] changes from [code]false[/code] to [code]true[/code]).
signal activated

## Emitted when the area becomes inactive
## (when [member active] changes from [code]true[/code] to [code]false[/code]).
signal deactivated

## If [code]true[/code], the area will track interactions with bodies (PhysicsBody2D nodes).
## At least one of [member track_bodies] or [member track_areas] must be [code]true[/code].
@export_group("Tracking")
@export var track_bodies: bool = true:
	set = set_track_bodies

## If [code]true[/code], the area will track interactions with other areas (Area2D nodes).
## At least one of [member track_bodies] or [member track_areas] must be [code]true[/code].
@export var track_areas: bool = true:
	set = set_track_areas

## The current active state of the area.
## When this value changes, it automatically emits [signal activated] or [signal deactivated].
var active: bool = false:
	set = set_active

## Counter to track how many bodies are currently inside the area.
var _bodies_inside: int = 0

## Counter to track how many areas are currently overlapping with this area.
var _areas_inside: int = 0


func _init(initial_active: bool = false) -> void:
	active = initial_active


func _ready() -> void:
	# Connect to Area2D signals based on tracking settings
	_update_signal_connections()


## Updates signal connections based on the current tracking settings.
func _update_signal_connections() -> void:
	# Disconnect all signals first to avoid double connections
	if body_entered.is_connected(_on_body_entered_internal):
		body_entered.disconnect(_on_body_entered_internal)
	if body_exited.is_connected(_on_body_exited_internal):
		body_exited.disconnect(_on_body_exited_internal)
	if area_entered.is_connected(_on_area_entered_internal):
		area_entered.disconnect(_on_area_entered_internal)
	if area_exited.is_connected(_on_area_exited_internal):
		area_exited.disconnect(_on_area_exited_internal)

	# Connect signals based on tracking settings
	if track_bodies:
		body_entered.connect(_on_body_entered_internal)
		body_exited.connect(_on_body_exited_internal)

	if track_areas:
		area_entered.connect(_on_area_entered_internal)
		area_exited.connect(_on_area_exited_internal)


## Sets the track_bodies property and validates that at least one tracking mode is enabled.
##
## [param value]: Whether to track body interactions.
func set_track_bodies(value: bool) -> void:
	if not value and not track_areas:
		push_error("BooleanArea2D: At least one of track_bodies or track_areas must be true.")
		return

	track_bodies = value
	if is_inside_tree():
		_update_signal_connections()


## Sets the track_areas property and validates that at least one tracking mode is enabled.
##
## [param value]: Whether to track area interactions.
func set_track_areas(value: bool) -> void:
	if not value and not track_bodies:
		push_error("BooleanArea2D: At least one of track_bodies or track_areas must be true.")
		return

	track_areas = value
	if is_inside_tree():
		_update_signal_connections()


## Sets the active state and emits the appropriate signal if the value changed.
##
## This method is automatically called when [member active] is assigned a new value.
## It compares the new value with the current state and only emits signals when
## there's an actual change, preventing unnecessary signal emissions.
##
## [param value]: The new boolean state to set for the area.
func set_active(value: bool) -> void:
	if active != value:
		active = value
		if active:
			activated.emit()
		else:
			deactivated.emit()


## Returns the number of bodies currently inside the area.
##
## [return]: The current count of bodies inside the area.
func get_bodies_count() -> int:
	return _bodies_inside


## Returns the number of areas currently overlapping with this area.
##
## [return]: The current count of areas overlapping this area.
func get_areas_count() -> int:
	return _areas_inside


## Returns the total number of tracked objects currently inside the area.
##
## This combines both body and area counts based on the current tracking settings.
##
## [return]: The total count of tracked objects inside the area.
func get_tracked_object_count() -> int:
	var total = 0
	if track_bodies:
		total += _bodies_inside
	if track_areas:
		total += _areas_inside
	return total


## Manually resets the area state.
##
## This clears all internal counters. The active state is not changed automatically;
## subclasses should handle the state change logic in their implementation.
## Use this if you need to reset the area's counters programmatically,
## for example when restarting a level or teleporting objects.
func reset_counters() -> void:
	_bodies_inside = 0
	_areas_inside = 0


## Virtual method called when any tracked object (body or area) enters the area.
##
## Subclasses should override this method to implement their specific activation logic.
## This method is called after the internal counters have been updated.
##
## [param object]: The [Node2D] that entered the area (either a body or area).
func _on_object_entered(_object: Node2D) -> void:
	pass  # To be overridden by subclasses


## Virtual method called when any tracked object (body or area) exits the area.
##
## Subclasses should override this method to implement their specific deactivation logic.
## This method is called after the internal counters have been updated.
##
## [param object]: The [Node2D] that exited the area (either a body or area).
func _on_object_exited(_object: Node2D) -> void:
	pass  # To be overridden by subclasses


## Internal handler for body_entered signal.
##
## Updates the internal counter and calls the virtual method for subclasses.
##
## [param body]: The [PhysicsBody2D] that entered the area.
func _on_body_entered_internal(body: Node2D) -> void:
	_bodies_inside += 1
	_on_object_entered(body)


## Internal handler for body_exited signal.
##
## Updates the internal counter and calls the virtual method for subclasses.
##
## [param body]: The [PhysicsBody2D] that exited the area.
func _on_body_exited_internal(body: Node2D) -> void:
	_bodies_inside -= 1
	if _bodies_inside < 0:
		_bodies_inside = 0  # Ensure it doesn't go negative
	_on_object_exited(body)


## Internal handler for area_entered signal.
##
## Updates the internal counter and calls the virtual method for subclasses.
##
## [param area]: The [Area2D] that entered this area.
func _on_area_entered_internal(area: Area2D) -> void:
	_areas_inside += 1
	_on_object_entered(area)


## Internal handler for area_exited signal.
##
## Updates the internal counter and calls the virtual method for subclasses.
##
## [param area]: The [Area2D] that exited this area.
func _on_area_exited_internal(area: Area2D) -> void:
	_areas_inside -= 1
	if _areas_inside < 0:
		_areas_inside = 0  # Ensure it doesn't go negative
	_on_object_exited(area)
