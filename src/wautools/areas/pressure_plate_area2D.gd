class_name PressurePlateArea2D
extends BooleanArea2D
## A pressure plate area that activates when objects are on it.
##
## PressurePlateArea2D is a specialized boolean area that becomes active when
## one or more tracked objects (bodies and/or areas) are inside it, and becomes
## inactive when no tracked objects remain. This makes it perfect for implementing
## pressure plates, switches, or trigger zones in games.
##
## The behavior can be inverted using [member inverted], making the plate active
## by default and inactive when objects are present. This is useful for creating
## "release switches" or areas that need to be kept clear.
##
## [b]Example usage:[/b]
## [codeblock]
## # Create a pressure plate that activates doors
## @onready var pressure_plate = $PressurePlate
## @onready var door = $Door
##
## func _ready():
##     pressure_plate.activated.connect(_on_plate_activated)
##     pressure_plate.deactivated.connect(_on_plate_deactivated)
##
## func _on_plate_activated():
##     door.open()
##
## func _on_plate_deactivated():
##     door.close()
## [/codeblock]

## If [code]true[/code], inverts the pressure plate behavior.
## When inverted, the plate is active by default and becomes inactive when objects are present.
@export_group("Pressure Plate")
@export var inverted: bool = false:
	set = set_inverted


func _init(initial_inverted: bool = false) -> void:
	# Call parent constructor with initial active state based on inversion
	super(initial_inverted)
	inverted = initial_inverted


func _ready() -> void:
	super()
	# Set initial state based on inversion
	_update_active_state()


## Sets the inverted property and updates the active state accordingly.
##
## When inverted is changed, the active state is immediately updated to reflect
## the new behavior without waiting for object interactions.
##
## [param value]: Whether to invert the pressure plate behavior.
func set_inverted(value: bool) -> void:
	if inverted != value:
		inverted = value
		_update_active_state()


## Updates the active state based on the current object count and inversion setting.
##
## This is called whenever objects enter/exit the area or when the inversion setting changes.
func _update_active_state() -> void:
	if inverted:
		# When inverted: active when NO objects are present
		set_active(not has_objects())
	else:
		# Normal behavior: active when objects ARE present
		set_active(has_objects())


## Called when any tracked object enters the pressure plate area.
##
## Updates the pressure plate state based on the new object count and inversion setting.
##
## [param object]: The [Node2D] that entered the area.
func _on_object_entered(_object: Node2D) -> void:
	_update_active_state()


## Called when any tracked object exits the pressure plate area.
##
## Updates the pressure plate state based on the new object count and inversion setting.
##
## [param object]: The [Node2D] that exited the area.
func _on_object_exited(_object: Node2D) -> void:
	_update_active_state()


## Manually resets the pressure plate state.
##
## This clears all internal counters and updates the active state to match
## the current inversion setting (active if inverted, inactive if not).
func reset_counters() -> void:
	super()
	_update_active_state()


## Returns whether the pressure plate currently has any objects on it.
##
## [return]: [code]true[/code] if there are tracked objects in the area,
## [code]false[/code] otherwise.
func has_objects() -> bool:
	return get_tracked_object_count() > 0


## Returns whether the pressure plate should be considered "pressed".
##
## Takes into account the inversion setting:
## - Normal behavior: pressed when objects are present
## - Inverted behavior: pressed when no objects are present
##
## [return]: [code]true[/code] if the plate is in its "pressed" state.
func is_pressed() -> bool:
	var has_objects_value = self.has_objects()
	return has_objects_value if not inverted else not has_objects_value
