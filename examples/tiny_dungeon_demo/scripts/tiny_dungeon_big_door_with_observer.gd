extends Node2D

@onready var anim_sprite: AnimatedSprite2D = $AnimatedSprite2D


func on_area_activated(_area: BooleanArea2D):
	anim_sprite.play("open")


func on_area_deactivated(_area: BooleanArea2D):
	anim_sprite.play("close")
