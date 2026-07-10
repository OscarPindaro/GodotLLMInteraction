extends Control

# TO SET UP THEMES FOR THE DIALOG BOX, SET UP A THEME ON THE MASTER CONTROL NODE 
# (DialogueSystem node), it will automatically be passed down to all the children

@onready var dialogue_handler: EzDialogue = $EzDialogue
@onready var dialogue_choice_button = preload("res://dialogues/DialogueButton.tscn")
@onready var textbox: Label = $CanvasLayer/PanelContainer/VBoxContainer/text
@onready var vbox: VBoxContainer = $CanvasLayer/PanelContainer/VBoxContainer


@export var dialogue_json: JSON
@export var font_size: int = 16
@export var state: Dictionary
@export var writing_velocity: float = 10 # charcaters per second
@export var pause_tree_if_dialogue_running: bool = false # Pauses all the tree, except this node, if a dialogue is running

var dialogue_finished = false
var is_writing = false
var time_to_next_char: float = 0

signal dialogue_is_over(dialogue_system)

var button_cache: Array[DialogueButton] = []

#############################################
## UTILITIES FUNCTIONS FOR OTHER SCENES 
#############################################
func hide_all():
	for child in get_children():
		if "visible" in child:
			child.visible = false
		
func show_all():
	for child in get_children():
		if "visible" in child:
			child.visible = true

func pause_tree():
	if not pause_tree_if_dialogue_running:
		return
		
	if get_tree().paused:
		process_mode = Node.PROCESS_MODE_INHERIT
		get_tree().paused = false
	else:
		process_mode = Node.PROCESS_MODE_ALWAYS
		get_tree().paused = true

#############################################
## INTERNAL FUNCTIONS
#############################################
func _ready() -> void:
	$CanvasLayer/PanelContainer.theme = self.theme
	textbox.label_settings.font_size = font_size
	
	# CONNECT TO HANDLER SIGNALS
	dialogue_handler.dialogue_generated.connect(_on_ez_dialogue_dialogue_generated)
	
	dialogue_finished = false
	is_writing = false
	dialogue_handler.start_dialogue(dialogue_json, state)
			
	pass

func _process(delta: float) -> void:
	if textbox.visible_characters < len(textbox.text):
		animate_label(delta)
	else:
		for button in button_cache:
			button.visible = true
		
			
func clear_dialogue():
	textbox.text = ""
	for child in button_cache:
		if child is Button:
			button_cache.erase(child)
			child.queue_free()

func add_text(text: String):
	textbox.text = text
	textbox.visible_characters = 0

func animate_label(delta: float) -> void:
	if is_writing:
		time_to_next_char += delta
		if time_to_next_char >= 1.0/writing_velocity:
			if textbox.visible_characters < len(textbox.text):
				textbox.visible_characters += 1
				time_to_next_char = 0
			else:
				print('setting visible buttons')
				for button in button_cache:
					button.visible = true
	
	
func add_choice(choice_text: String, id: int):
	if button_cache.size() < id + 1:
		var new_button = dialogue_choice_button.instantiate()
		new_button.choice_id = id
		button_cache.push_back(new_button)
		vbox.add_child(new_button)
		new_button.dialogue_selected.connect(_on_choice_button_down)
		new_button.visible = false

	var button = button_cache[id]
	button.text = choice_text
	# button.show()

func _on_choice_button_down(choice_id: int):
	clear_dialogue()
	if !dialogue_finished:
		dialogue_handler.next(choice_id)

func _on_ez_dialogue_dialogue_generated(response: DialogueResponse):
	if (response.eod_reached) or (response.is_empty()):
		print('dialog finished')
		button_cache = []
		dialogue_finished = true
		$CanvasLayer.visible = false
		self.visible = false
		pause_tree()
		dialogue_is_over.emit(self)

	else:
		is_writing = true
		add_text(response.text)
		if not response.choices.is_empty():
			for i in response.choices.size():
				add_choice(response.choices[i], i)
