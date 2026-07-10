@tool
extends Node2D

@export var texture: ImageTexture

@export_tool_button("Generate Map") var generate_map = generate.bind()
var color_tile_info: Dictionary[Vector3i, TileInfo] = {}
@onready var space_partition_generator: SpacePartitionGenerationDemo = $SpacePartitionGeneration

@onready var tilemap: TileMapLayer = $TileMapLayer


class TileInfo:
	var source_id: int
	var tile_id: Vector2i

	func _init(id: int, t_id: Vector2i):
		self.source_id = id
		self.tile_id = t_id


func create_color_association():
	# iterate over all of the possible tile set
	color_tile_info = {}
	var tileset: TileSet = tilemap.tile_set
	var n_sources: int = tileset.get_source_count()
	for source_idx in range(n_sources):
		# for each source, load the tileset atlas source
		# this works onl if your tiles are not scenes, i think, otherwise you need to check
		# that the type is TileSetScenesCollectionSource
		var tile_source: TileSetAtlasSource = tileset.get_source(source_idx)
		for i in range(tile_source.get_tiles_count()):
			var tile_id: Vector2i = tile_source.get_tile_id(i)
			var tile_info = TileInfo.new(source_idx, tile_id)

			# now let's get the color. This script assumes that there is this value
			var tile_data: TileData = tile_source.get_tile_data(tile_id, 0)
			if tile_data.has_custom_data("color"):
				var tile_color = tile_data.get_custom_data("color")
				# use the rgb value as key for a dictionary
				var key: Vector3i = color_to_vector(tile_color)
				assert(
					key not in color_tile_info.keys(),
					"This implementation can have only a single color associated to a single tile"
				)
				color_tile_info[key] = tile_info
	# of course, at least one color should have been found
	assert(
		len(color_tile_info) > 0,
		"No color found. Check if you added a color field to the custom data"
	)
	return color_tile_info


func color_to_vector(color: Color) -> Vector3i:
	return Vector3i(color.r8, color.g8, color.b8)


func generate():
	# first of all, let's populate the color_tile_info field
	empty_tilemap()
	create_color_association()
	print(color_tile_info)
	# now, for each pixel of the image, let's check the color,
	# look in the dictionary and set the corrensponding tile.
	var image: Image = null
	if space_partition_generator == null:
		print("ciao")
		image = texture.get_image()
	else:
		print("come va")
		space_partition_generator.generate()
		image = space_partition_generator.sprite.texture.get_image()

	for h_idx in range(image.get_height()):
		# for h_idx in range(5):
		for w_idx in range(image.get_width()):
			# for w_idx in range(5):
			var pixel_color: Color = image.get_pixel(h_idx, w_idx)
			var dict_key: Vector3i = color_to_vector(pixel_color)
			assert(
				dict_key in color_tile_info,
				"The color provided does not have a corrensponding tile."
			)
			var tile_info: TileInfo = color_tile_info[dict_key]
			tilemap.set_cell(Vector2i(h_idx, w_idx), tile_info.source_id, tile_info.tile_id)
	print("fine generationze")


func empty_tilemap():
	print("emptying the tilemap")
	tilemap.clear()
