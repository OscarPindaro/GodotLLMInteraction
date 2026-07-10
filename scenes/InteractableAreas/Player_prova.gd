extends CharacterBody2D


func _ready():
	$VisionCone.area_entered.connect(on_vision_cone_entered)
	$VisionCone.area_exited.connect(on_vision_cone_exited)


func on_vision_cone_entered(area: Area2D):
	if area.is_in_group("enemies"):
		print("ciao entered")

func on_vision_cone_exited(area: Area2D):
	if area.is_in_group("enemies"):
		print("ciao exited")
