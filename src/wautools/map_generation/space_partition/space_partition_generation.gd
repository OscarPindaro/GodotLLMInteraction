@tool
class_name SpacePartitionGenerationDemo
extends Node2D

@export var map_size: Vector2i = Vector2i(64, 64)
@export var min_splits: int = 1
@export var max_splits: int = 4
@export var min_size_partition: int = 10
@export var preference_ratio: float = 1.25

@export var min_perc_size: float = 0.4
@export var max_perc_size: float = 0.8

@export var generation_seed: int = 0
@export var split_prob: float = 0.6

@export_tool_button("Generate Map") var tool_compute = generate.bind()

var map_generator: SpacePartition
@onready var sprite: Sprite2D = $Sprite2D


func _ready() -> void:
	generate()


func generate():
	map_generator = SpacePartition.new()
	map_generator.map_size = map_size
	map_generator.min_splits = min_splits
	map_generator.max_splits = max_splits
	map_generator.generation_seed = randi()
	# map_generator.generation_seed = generation_seed
	map_generator.split_prob = split_prob
	map_generator.min_size_partition = min_size_partition
	map_generator.preference_ratio = preference_ratio
	map_generator.min_perc_size = min_perc_size
	map_generator.max_perc_size = max_perc_size

	map_generator._ready()
	map_generator.generate()
	var map_image: Image = Image.create_empty(
		map_generator.map_size.x, map_generator.map_size.y, false, Image.Format.FORMAT_L8
	)
	var map_matrix: Array = map_generator.generate_room_matrix()
	for i in range(map_image.get_width()):
		for j in range(map_image.get_height()):
			var color = Color.WHITE
			if map_matrix[i][j] == 0:
				color = Color.BLACK
			elif map_matrix[i][j] == 1:
				color = Color.WHITE
			else:
				color = Color.GRAY
			map_image.set_pixel(i, j, color)
	sprite.texture = ImageTexture.create_from_image(map_image)
