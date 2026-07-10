@tool
extends Movement
class_name RandomMovement
# a movement that moves a kinematic body in a random fashion



# how ofter the random movement is updated
@export var control_step: float = 1. : set = set_control_step

var timer: Timer = null


func set_control_step(new_control_step: float):
	if is_inside_tree():
		# stop current timer, remove it
		timer.stop()
		timer.wait_time = control_step
		timer.start()

	control_step = new_control_step



func create_timer():
	timer = Timer.new()
	add_child(timer)
	# i want it to loop
	timer.one_shot = false
	timer.wait_time = control_step
	timer.timeout.connect(_on_control_step)
	timer.start()

# Called when the node enters the scene tree for the first time.
func _ready():
	super._ready()
	create_timer()

func _on_control_step():
	body.velocity = Vector2(randf_range(-1,1), randf_range(-1,1)).normalized() * linear_velocity


func move(_delta, body_to_move: CharacterBody2D):
	body_to_move.move_and_slide()
	if look_at:
		body_to_move.look_at(body_to_move.velocity)
