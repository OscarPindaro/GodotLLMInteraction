@tool
extends AudioStreamPlayer2D
class_name NewWAUAudioPlayer

@export var sound_collection: NewSoundsCollection:
	set(value):
		sounds = {}
		sound_collection = value
		create_sounds()

@export var track_name: String = "":
	set(value):
		track_name = value
		if value in sounds:
			stream = sounds[track_name]


var sounds: Dictionary = {}
#var active_sound = []

func create_sounds():
	for track in sound_collection.sounds:
		track.track_player = AudioStreamPlayer2D.new()
		track.track_player.volume_db = track.volume_db
		track.track_player.bus = track.bus
		track.track_player.max_distance = self.max_distance
		sounds[track.track_name] = {
			"file": track.track_file,
			"player": track.track_player
		}
		add_child(track.track_player)
		

#func _ready():
	#for sound in sounds:
		#sounds[sound].player.finished.connect(_on_sound_finished)
	##self.finished.connect(_on_sound_finished)
#
#func _on_sound_finished():
	#self.active_sound = null
	#
func _play(sound_name):
	sounds[sound_name].player.stream = sounds[sound_name].file
	sounds[sound_name].player.play()
	

func play_sound_now(sound_name, stop_other_sounds, _from_position = 0.):
	if sounds.size() <= 0:
		return
	if sound_name not in sounds.keys():
		return
	
	if stop_other_sounds:
		# Stop all other sounds
		stop_all()
	_play(sound_name)


func play_sound_if_previous_finished(sound_name, _from_position = 0.):
	if sounds.size() <= 0:
		return
	if sound_name not in sounds.keys():
		return

	if !sounds[sound_name].player.playing:
		_play(sound_name)


func stop_all():
	for sound in sounds:
		sounds[sound].player.stop()
		

func stop_sound(sound_name):
	sounds[sound_name].player.stop()
