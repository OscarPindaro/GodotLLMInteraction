extends Label

@export var area: BooleanArea2D


func _ready() -> void:
	area.activated.connect(on_activation)
	area.deactivated.connect(on_deactivation)


func on_activation() -> void:
	self.text = "Activated"
	print_debug("Activated")


func on_deactivation() -> void:
	self.text = "Deactivated"
	print_debug("Deactivated")
