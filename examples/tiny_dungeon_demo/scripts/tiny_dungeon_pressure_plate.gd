extends Node2D

@export_range(0, 16, 0.5) var activation_offset: float = 2
@export var target_modulate_color: Color
var _old_color: Color

@onready var plate_sprite: Sprite2D = $Sprite2D


func _ready():
	print_debug(plate_sprite)


func _on_pressure_plate_area_2d_activated() -> void:
	plate_sprite.global_position.y += activation_offset
	_old_color = plate_sprite.modulate
	plate_sprite.modulate = target_modulate_color


func _on_pressure_plate_area_2d_deactivated() -> void:
	plate_sprite.global_position.y -= activation_offset
	plate_sprite.modulate = _old_color
