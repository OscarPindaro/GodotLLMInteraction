extends Node2D

@onready var animation_sprites: AnimatedSprite2D = $AnimatedSprite2D


func open() -> void:
	animation_sprites.play("open")


func close() -> void:
	animation_sprites.play("close")
