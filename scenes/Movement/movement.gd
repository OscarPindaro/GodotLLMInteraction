extends Node
class_name Movement

@export var body: CharacterBody2D = null 
@export var linear_velocity = 200
@export var look_at: bool = true


# Called when the node enters the scene tree for the first time.
func _ready():
	if body == null:
		assert(typeof(get_parent()==CharacterBody2D), "If body is null, the parent should be a CharacterBody so it works")
		body = get_parent()

	



func _physics_process(_delta):
	move(_delta, body)

	
func move(_delta, _body_to_move: CharacterBody2D):
	pass