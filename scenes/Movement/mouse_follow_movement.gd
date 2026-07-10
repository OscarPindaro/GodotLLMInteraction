class_name MouseFollowMovement
extends Movement


# Called when the node enters the scene tree for the first time.
func _ready():
	super._ready()


func move(_delta, body_to_move: CharacterBody2D):
	var mouse_position = body_to_move.get_global_mouse_position()
	var direction: Vector2 = (mouse_position - body_to_move.position).normalized()
	body_to_move.velocity = direction * linear_velocity
	body_to_move.move_and_slide()
	if look_at:
		body_to_move.look_at(mouse_position)
