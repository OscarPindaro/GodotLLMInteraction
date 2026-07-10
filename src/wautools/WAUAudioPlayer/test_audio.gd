extends Node2D

@onready var audio: AudioStreamPlayer2D = $Sounds

# Called when the node enters the scene tree for the first time.
func _ready() -> void:
	pass # Replace with function body.


# Called every frame. 'delta' is the elapsed time since the previous frame.
func _process(delta: float) -> void:
	if Input.is_action_pressed('dmg'):
		audio.play_sound_now("DMG", false)


	if Input.is_action_pressed('stop'):
		audio.play_sound_now("STOP_MOVING", true)


	if Input.is_action_pressed('walk'):
		audio.play_sound_if_previous_finished("STEP")
