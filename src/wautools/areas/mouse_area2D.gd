class_name MouseFollowingArea2D
extends Area2D
## An Area2D that follows the mouse cursor position at every frame.
##
## This class creates an Area2D that automatically tracks the mouse cursor position
## in real-time. It can be configured to follow the mouse in global coordinates or
## relative to a specific viewport. The following behavior can be enabled/disabled
## at runtime.
##
## @tutorial: https://docs.godotengine.org/en/stable/classes/class_area2d.html

## Emitted when the area starts following the mouse.
signal following_started

## Emitted when the area stops following the mouse.
signal following_stopped

## Whether the area should follow the mouse cursor.
@export var follow_mouse: bool = true:
	set(value):
		var was_following = follow_mouse
		follow_mouse = value

		if follow_mouse and not was_following:
			following_started.emit()
		elif not follow_mouse and was_following:
			following_stopped.emit()

## The viewport to get mouse position from. If null, uses the current viewport.
@export var target_viewport: Viewport = null

## Offset applied to the mouse position.
@export var offset: Vector2 = Vector2.ZERO

## Whether to use global mouse position instead of viewport-relative position.
@export var use_global_position: bool = false

## Smoothing factor for mouse following (0.0 = no smoothing, 1.0 = instant).
@export_range(0.0, 1.0, 0.01) var smoothing: float = 1.0


func _ready() -> void:
	# Set default viewport if none specified
	if target_viewport == null:
		target_viewport = get_viewport()


func _process(_delta: float) -> void:
	if not follow_mouse:
		return

	var mouse_pos = _get_mouse_position()
	var target_position = mouse_pos + offset

	if smoothing >= 1.0:
		# Instant following
		global_position = target_position
	else:
		# Smooth following
		global_position = global_position.lerp(target_position, smoothing)


## Gets the current mouse position based on the configuration.
func _get_mouse_position() -> Vector2:
	return target_viewport.get_mouse_position()


## Enables mouse following and emits the appropriate signal.
func start_following() -> void:
	follow_mouse = true


## Disables mouse following and emits the appropriate signal.
func stop_following() -> void:
	follow_mouse = false


## Teleports the area to the current mouse position without smoothing.
func snap_to_mouse() -> void:
	if not follow_mouse:
		return

	var mouse_pos = _get_mouse_position()
	global_position = mouse_pos + offset
