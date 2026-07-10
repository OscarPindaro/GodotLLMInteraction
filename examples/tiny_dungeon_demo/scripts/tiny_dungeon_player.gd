extends CharacterBody2D

@export var tilemap: TileMapLayer
@export var movement_indicator: Sprite2D

var is_moving: bool = false
var raycast_length: float

@onready var sprite: Sprite2D = $Sprite2D
@onready var ray_cast: RayCast2D = $RayCast2D


func _ready() -> void:
	assert(tilemap != null, "Tilemap can not be null")
	raycast_length = ray_cast.target_position.length()


func _physics_process(_delta: float) -> void:
	if is_moving == false:
		return


func _process(_delta):
	if is_moving:
		return
	if Input.is_action_pressed("ui_up"):
		move(Vector2.UP)
	elif Input.is_action_pressed("ui_down"):
		move(Vector2.DOWN)
	elif Input.is_action_pressed("ui_left"):
		move(Vector2.LEFT)
	elif Input.is_action_pressed("ui_right"):
		move(Vector2.RIGHT)


func move(direction: Vector2):
	# get current vector tile Vector2i
	var current_tile: Vector2i = tilemap.local_to_map(self.global_position)
	# get target tile Vector2i
	var target_tile: Vector2i = Vector2i(current_tile.x + direction.x, current_tile.y + direction.y)
	# get custom data layer from the targe tile
	var tile_data: TileData = tilemap.get_cell_tile_data(target_tile)
	if tile_data.get_custom_data("walkable") == false:
		return

	ray_cast.target_position = direction * raycast_length
	# i need to force it NOW to do the collision
	ray_cast.force_raycast_update()

	if ray_cast.is_colliding():
		return
	# move the player
	var tween = get_tree().create_tween()
	is_moving = true
	var target_position = tilemap.map_to_local(target_tile)
	tween.tween_property(self, "global_position", target_position, 0.2)
	tween.tween_callback(self.on_movement_end)
	movement_indicator.global_position = target_position


func on_movement_end():
	is_moving = false
