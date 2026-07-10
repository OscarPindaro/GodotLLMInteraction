class_name SpacePartition
extends Node

@export var map_size: Vector2i = Vector2i(64, 64)
@export var min_splits: int = 1
@export var max_splits: int = 4
@export var min_size_partition: int = 10
@export var preference_ratio: float = 1.24

@export var min_perc_size: float = 0.4
@export var max_perc_size: float = 0.8

@export var generation_seed: int = 0
@export var split_prob: float = 0.6

var rng: RandomNumberGenerator


# First, let's add a corridor property to the BSPNode class
class BSPNode:
	extends Node
	var left: BSPNode = null
	var right: BSPNode = null
	var rect: Rect2i
	var room: Rect2i
	var corridors: Array[Rect2i] = []  # Will store corridor rectangles

	func _init(r: Rect2i) -> void:
		rect = r

	func is_leaf():
		return left == null and right == null

	func width():
		return rect.size[0]

	func height():
		return rect.size[1]

	func create_random_room(min_perc_size: float, max_perc_size: float, rng: RandomNumberGenerator):
		var room_width = int(rng.randf_range(min_perc_size, max_perc_size) * self.width())
		var room_height = int(rng.randf_range(min_perc_size, max_perc_size) * self.height())

		var room_x = rng.randi_range(1, self.width() - room_width - 1) + self.rect.position.x
		var room_y = rng.randi_range(1, self.height() - room_height - 1) + self.rect.position.y
		self.room = Rect2i(room_x, room_y, room_width, room_height)
		return self.room


var tree: BSPNode


func _ready() -> void:
	rng = RandomNumberGenerator.new()
	rng.seed = generation_seed

	# create tree
	self.tree = BSPNode.new(Rect2i(0, 0, self.map_size.x, self.map_size.y))


# func generate():
# 	self.recursive_split(self.tree, 0)
# 	self.create_rooms(self.tree)


func recursive_split(node: BSPNode, iteration: int) -> BSPNode:
	var keep_going: bool = true
	# if the iteration is too low, i force the node to be splitted
	if iteration < self.min_splits:
		keep_going = true
	# otherwise if it's between min and max splits, the split is stochastic
	elif iteration >= self.min_splits and iteration > self.max_splits:
		if rng.randf() >= self.split_prob:
			keep_going = false
		else:
			keep_going = true
	else:
		keep_going = false

	# stop iterating if keep_goind condition is not met
	if !keep_going:
		return tree

	# now choose split direction. prioritize a directin when it's much bigger than the other
	var split_vertical: bool = true
	if node.width() / node.height() >= 1.25:
		split_vertical = true
	elif node.height() / node.width() >= 1.25:
		split_vertical = false
	else:
		split_vertical = rng.randf() >= 0.5
	if split_vertical:
		# split only if there is enough space
		if node.width() < 2 * self.min_size_partition:
			# don't actually split
			return
		# if you split, chosse a random
		var left_width: int = rng.randi_range(min_size_partition, node.width() - min_size_partition)
		var right_width: int = node.width() - left_width

		var left_rect = Rect2i()
		left_rect.position = node.rect.position
		left_rect.size = Vector2i(left_width, node.height())
		node.left = BSPNode.new(left_rect)

		var right_rect = Rect2i()
		right_rect.position = left_rect.position + Vector2i(left_width, 0)
		right_rect.size = Vector2i(right_width, node.height())
		node.right = BSPNode.new(right_rect)

	else:
		if node.height() < 2 * self.min_size_partition:
			# dont' split
			return
		var top_height: int = rng.randi_range(
			min_size_partition, node.height() - min_size_partition
		)
		var bottom_height: int = node.height() - top_height

		var top_rect = Rect2i()
		top_rect.position = node.rect.position
		top_rect.size = Vector2i(node.width(), top_height)
		node.left = BSPNode.new(top_rect)

		var bottom_rect = Rect2i()
		bottom_rect.position = node.rect.position + Vector2i(0, top_height)
		bottom_rect.size = Vector2i(node.width(), bottom_height)
		node.right = BSPNode.new(bottom_rect)

	# now, call recursively
	self.recursive_split(node.left, iteration + 1)
	self.recursive_split(node.right, iteration + 1)

	return tree


func create_rooms(node: BSPNode):
	if node.is_leaf():
		node.create_random_room(self.min_perc_size, self.max_perc_size, self.rng)
	else:
		self.create_rooms(node.left)
		self.create_rooms(node.right)


func generate_room_matrix() -> Array:
	# Initialize a 2D matrix filled with zeros
	var matrix = []
	for y in range(map_size.y):
		var row = []
		for x in range(map_size.x):
			row.append(0)
		matrix.append(row)

	# Fill the matrix with rooms
	fill_matrix_with_rooms(tree, matrix)

	return matrix


func fill_matrix_with_rooms(node: BSPNode, matrix: Array) -> Array:
	if node == null:
		return matrix

	# If this is a leaf node, add its room to the matrix
	if node.is_leaf():
		var room = node.room
		for y in range(room.position.y, room.position.y + room.size.y):
			for x in range(room.position.x, room.position.x + room.size.x):
				# Check if the point is within map bounds
				if x >= 0 and x < map_size.x and y >= 0 and y < map_size.y:
					matrix[y][x] = 1
	else:
		# Recursively process child nodes
		# Add corridors for this node
		for corridor in node.corridors:
			for y in range(corridor.position.y, corridor.position.y + corridor.size.y):
				for x in range(corridor.position.x, corridor.position.x + corridor.size.x):
					# Check if the point is within map bounds
					if x >= 0 and x < map_size.x and y >= 0 and y < map_size.y:
						matrix[y][x] = 2
		fill_matrix_with_rooms(node.left, matrix)
		fill_matrix_with_rooms(node.right, matrix)
	return matrix


func generate_room_matrix_debug() -> Array:
	# Initialize a 2D matrix filled with zeros
	var matrix = []
	for y in range(map_size.y):
		var row = []
		for x in range(map_size.x):
			row.append(0)
		matrix.append(row)

	# Fill the matrix with rooms
	fill_matrix_with_rooms_debug(tree, matrix)

	return matrix


func fill_matrix_with_rooms_debug(node: BSPNode, matrix: Array) -> Array:
	if node == null:
		return matrix
	var rect = node.rect
	for y in [rect.position.y, rect.position.y + rect.size.y - 1]:
		for x in range(rect.position.x, rect.position.x + rect.size.x - 1):
			matrix[y][x] = 1
	for x in [rect.position.x, rect.position.x + rect.size.x - 1]:
		for y in range(rect.position.y, rect.position.y + rect.size.y - 1):
			matrix[y][x] = 1

	# If this is a leaf node, add its room to the matrix
	if node.is_leaf():
		# colour the borders
		# orizontal lines
		var room = node.room

		for y in range(room.position.y, room.position.y + room.size.y - 1):
			for x in range(room.position.x, room.position.x + room.size.x - 1):
				# Check if the point is within map bounds
				if x >= 0 and x < map_size.x and y >= 0 and y < map_size.y:
					matrix[y][x] = 1
	else:
		# Recursively process child nodes
		fill_matrix_with_rooms_debug(node.left, matrix)
		fill_matrix_with_rooms_debug(node.right, matrix)
	return matrix


# Main function to create corridors throughout the tree
func create_corridors():
	_create_corridors_recursive(tree)


func _create_corridors_recursive(node: BSPNode) -> void:
	if node == null:
		return

	# If this is not a leaf node, we need to create corridors between its children
	if not node.is_leaf():
		# First, make sure both children have rooms
		_create_corridors_recursive(node.left)
		_create_corridors_recursive(node.right)

		# Connect the rooms of the left and right children
		connect_rooms(node, node.left, node.right)


func connect_rooms(parent: BSPNode, left_node: BSPNode, right_node: BSPNode) -> void:
	# Find center points for left and right rooms
	var left_room: Rect2i = get_room_from_node(left_node)
	var right_room: Rect2i = get_room_from_node(right_node)

	if left_room.size.x == 0 or right_room.size.x == 0:
		return  # Skip if either room doesn't exist

	var left_center = Vector2i(
		left_room.position.x + left_room.size.x / 2, left_room.position.y + left_room.size.y / 2
	)

	var right_center = Vector2i(
		right_room.position.x + right_room.size.x / 2, right_room.position.y + right_room.size.y / 2
	)

	# Choose a random corridor shape (L-shape or Z-shape)
	if rng.randf() > 0.5:
		# L-shaped corridor (horizontal then vertical)
		create_h_corridor(parent, left_center.x, right_center.x, left_center.y)
		create_v_corridor(parent, left_center.y, right_center.y, right_center.x)
	else:
		# Z-shaped corridor (vertical then horizontal)
		create_v_corridor(parent, left_center.y, right_center.y, left_center.x)
		create_h_corridor(parent, left_center.x, right_center.x, right_center.y)


# Helper function to get the room from a node (either direct or from children)
func get_room_from_node(node: BSPNode) -> Rect2i:
	if node.is_leaf():
		return node.room

	# If it's not a leaf, we assume at least one child has a room
	var left_result = get_room_from_node(node.left) if node.left else Rect2i()

	if left_result.size.x > 0:
		return left_result

	return get_room_from_node(node.right) if node.right else Rect2i()


# Create a horizontal corridor
func create_h_corridor(node: BSPNode, x1: int, x2: int, y: int) -> void:
	var start_x = min(x1, x2)
	var end_x = max(x1, x2)
	var corridor_width = 1  # Width of the corridor

	var corridor = Rect2i(start_x, y - corridor_width / 2, end_x - start_x, corridor_width)

	node.corridors.append(corridor)


# Create a vertical corridor
func create_v_corridor(node: BSPNode, y1: int, y2: int, x: int) -> void:
	var start_y = min(y1, y2)
	var end_y = max(y1, y2)
	var corridor_width = 1  # Width of the corridor

	var corridor = Rect2i(x - corridor_width / 2, start_y, corridor_width, end_y - start_y)

	node.corridors.append(corridor)


# Update your generate function to include corridor creation
func generate():
	self.recursive_split(self.tree, 0)
	self.create_rooms(self.tree)
	self.create_corridors()  # Add this line
