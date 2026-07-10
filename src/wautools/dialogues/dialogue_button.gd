class_name DialogueButton extends Button

signal dialogue_selected(choice_id: int)
var choice_id = -1


func _ready() -> void:
	pressed.connect(_on_pressed)


func _on_pressed():
	dialogue_selected.emit(choice_id)
