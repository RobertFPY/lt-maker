from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QMessageBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QSlider
from app.editor.sound_editor.audio_controller import AudioController
import os


class SoundPlayer:
    def __init__(self, view, parent_layout):
        self.view = view
        self.layout = parent_layout

        self.audio_controller = AudioController()
        self.audio_controller.init()    # Init audio mixer 

        self.current_track_name = None  # To assign track name through ui
        self.is_track_loaded = False    # To check if audio file is loaded

        self.init_ui()
        self.connect_signals_ui()

    # ----- UI Init -----
    def init_ui(self):
        # Main Widget
        self.audio_player_widget = QWidget()
        self.layout.addWidget(self.audio_player_widget)
        self.audio_player_widget.setEnabled(False)
        self.player_layout = QVBoxLayout(self.audio_player_widget)

        # Info Labels
        self.file_label = QLabel("No track selected")
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.player_layout.addWidget(self.file_label)

        # Progress bar
        self.init_progress_ui()
        self.init_progress_timer()

        # Control buttons
        self.init_controls_ui()

    def init_progress_ui(self):
        self.current_time_label = QLabel("--:--")
        self.duration_label = QLabel("--:--")

        self.progress_slider = ClickableSlider(Qt.Horizontal)
        self.progress_slider.setMinimum(0)
        self.progress_slider.setMaximum(10000)

        progress_row = QHBoxLayout()
        progress_row.addWidget(self.current_time_label)
        progress_row.addWidget(self.progress_slider, 1)
        progress_row.addWidget(self.duration_label)

        self.player_layout.addLayout(progress_row)
    
    def init_controls_ui(self):
        self.play_pause_button = QPushButton("Play")
        self.stop_button = QPushButton("Stop")

        controls = QHBoxLayout()
        controls.addWidget(self.play_pause_button)
        controls.addWidget(self.stop_button)
        self.player_layout.addLayout(controls)

    def connect_signals_ui(self):
        # Control buttons
        self.play_pause_button.clicked.connect(self.toggle_play_pause)
        self.stop_button.clicked.connect(self.stop_track)

        # Progress slider
        self.progress_slider.sliderReleased.connect(self.on_seek)

        # Progress timer
        self.timer.timeout.connect(self.update_progress_ui)

    def init_progress_timer(self):
        self.timer = QTimer()
        self.timer.start(100)

    # ----- UI Update -----
    def update_progress_ui(self):
        if not self.current_track_name:
            return

        current_ms = self.audio_controller.get_position()
        duration_ms = self.audio_controller.duration_ms

        if duration_ms > 0:

            slider_value = int((current_ms / duration_ms) * 10000)

            # don't overwrite while user dragging
            if not self.progress_slider.isSliderDown():
                self.progress_slider.setValue(slider_value)

        self.update_time_label(current_ms, duration_ms)

        if self.audio_controller.duration_ms > 0 and current_ms >= self.audio_controller.duration_ms:
            self.audio_controller.reset()
            self.reset_ui_track_loaded()

    def update_time_label(self, current_ms: int, duration_ms: int):
        self.current_time_label.setText(self._fmt_time(current_ms))
        self.duration_label.setText(self._fmt_time(duration_ms))

    # ----- Load audio file and its metadata -----
    def load_track(self, file_path: str):
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")

            meta = self.audio_controller.get_metadata(file_path)

            self.audio_controller.duration_ms = meta["duration"]
            self.is_track_loaded = True

            self.audio_controller.load(file_path)

        except Exception as e:
            QMessageBox.critical(self.view, "Audio Error", str(e))
            self.reset_to_no_track()

    def handle_audio_player_on_select(self, has_selection: bool, selected_track):
        """
        Handle audio selection from user interactions on ui.
        Including: select, unselect, select another
        """

        self.audio_player_widget.setEnabled(has_selection)

        if not has_selection or not selected_track:
            self.reset_to_no_track()
            return

        file_path = selected_track.full_path
        track_name = getattr(selected_track, "nid", "Unknown")

        if self.current_track_name and self.current_track_name != track_name:
            # Check if a new track is selected
            self.reset_to_no_track()

        if not os.path.exists(file_path):
            self.file_label.setText("File not found")
            return

        self.current_track_name = track_name
        self.file_label.setText(
            f"Track name: {self.current_track_name}\nFile path: {file_path}"
        )

        self.load_track(file_path)
        self.update_time_label(0, self.audio_controller.duration_ms)

    # ----- Audio Controls -----
    def toggle_play_pause(self):
        if not self.current_track_name:
            return

        if not self.audio_controller.is_playing and not self.audio_controller.is_paused:
            self.play_track()
            return

        if self.audio_controller.is_paused:
            self.unpause_track()
        else:
            self.pause_track()

    def play_track(self):
        if not self.current_track_name:
            return

        self.audio_controller.play()
        self.play_pause_button.setText("Pause")

    def pause_track(self):
        self.audio_controller.pause()
        self.play_pause_button.setText("Play")

    def unpause_track(self):
        self.audio_controller.resume()
        self.play_pause_button.setText("Pause")

    def on_seek(self):

        if self.audio_controller.duration_ms <= 0:
            return

        value = self.progress_slider.value()

        position_ms = int((value / 10000) * self.audio_controller.duration_ms)

        self.audio_controller.seek(position_ms)

    def stop_track(self):
        self.audio_controller.stop()
        self.reset_ui_track_loaded()

    def stop_track_on_close_event(self):
        """
        Stop track when closing parent ui. 
        Used this function inside closeEvent() for Qt SoundTab
        """
        
        self.audio_controller.shutdown()
            
    # ----- State reset handlers -----
    def reset_to_no_track(self):
        self.audio_controller.stop()
        self.audio_controller.unload()

        self.current_track_name = None
        self.is_track_loaded = False

        self.reset_ui_no_track()

    def reset_ui_no_track(self):
        self.file_label.setText("No track selected")
        self.play_pause_button.setText("Play")
        self.progress_slider.setValue(0)
        self.current_time_label.setText("--:--")
        self.duration_label.setText("--:--")

    def reset_ui_track_loaded(self):
        self.play_pause_button.setText("Play")
        self.progress_slider.setValue(0)
        self.update_time_label(0, self.audio_controller.duration_ms)

    # ----- Utils -----
    def _fmt_time(self, ms: int) -> str:
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        return f"{m:02}:{s:02}.{ms:03}"
    

class ClickableSlider(QSlider):
    """
    A custom QSlider that supports clicking on the track to jump to a position.
    """

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            distance = (self.maximum() - self.minimum()) * event.x()
            value = self.minimum() + distance / self.width()
            self.setValue(int(value))
            self.sliderMoved.emit(int(value))
            self.sliderPressed.emit()

        super().mousePressEvent(event)