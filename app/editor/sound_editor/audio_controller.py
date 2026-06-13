import pygame
import time
import logging


class AudioController:
    def __init__(self):
        self.is_playing = False
        self.is_paused = False
        self.start_ms = 0
        self.current_ms = 0
        self.duration_ms = 0

    def init(self):
        """
        Init pygame mixer
        """

        if not pygame.mixer.get_init():
            pygame.mixer.init()
        pygame.mixer.set_num_channels(8)

    def load(self, file_path: str):
        """
        Load track into pygame music as stream (partial loading)
        """

        pygame.mixer.music.load(file_path)

    def unload(self):
        """
        Unload track from pygame music
        """

        pygame.mixer.music.unload()

    def shutdown(self):
        """
        Free mem and shutdown mixer
        """

        if not pygame.mixer.get_init():
            return

        try:
            pygame.mixer.music.stop()
        except pygame.error as e:
            logging.error("Audio Controller | Error", e)

        pygame.mixer.quit()

    def play(self):
        pygame.mixer.music.play(start=self.current_ms / 1000)
        self.start_ms = self._now() - self.current_ms
        self.is_playing = True
        self.is_paused = False

    def pause(self):
        pygame.mixer.music.pause()
        self.current_ms = self._now() - self.start_ms
        self.is_paused = True
        self.is_playing = False

    def resume(self):
        pygame.mixer.music.unpause()
        self.start_ms = self._now() - self.current_ms
        self.is_paused = False
        self.is_playing = True

    def stop(self):
        """
        Stop pygame music and reset audio control states back to default
        """
        
        pygame.mixer.music.stop()
        self.reset()

    def reset(self):
        """
        Reset audio control states back to default
        """
        
        self.is_playing = False
        self.is_paused = False
        self.start_ms = 0
        self.current_ms = 0

    def get_position(self):
        """
        Get audio position
        """

        if self.is_paused:
            return self.current_ms

        if self.is_playing:
            return self._now() - self.start_ms

        return self.current_ms
    
    def seek(self, position_ms: int):
        """
        Seek audio to specific position in milliseconds
        """

        if self.duration_ms <= 0:
            return

        position_ms = max(0, min(position_ms, self.duration_ms))

        self.current_ms = position_ms

        # only move playback if currently active
        if self.is_playing:
            pygame.mixer.music.play(start=position_ms / 1000)
            self.start_ms = self._now() - position_ms
            self.is_playing = True
            self.is_paused = False

        elif self.is_paused:
            pygame.mixer.music.play(start=position_ms / 1000)
            pygame.mixer.music.pause()
    
    def get_metadata(self, file_path: str):
        """
        Get metadata from audio file.
        (add more attributes if needed in the future)

        Return: 
            dict: { duration:int }  (duration is in miliseconds)
        """

        try:
            duration_ms = pygame.mixer.Sound(file_path).get_length()
        except Exception as e:
            logging.error(f"Fail to load sound file '{file_path}': {e}\nAssign var duration_ms = 0")
            duration_ms = 0

        return {"duration": int(duration_ms * 1000)}
    
    def _now(self):
        return int(time.monotonic() * 1000)