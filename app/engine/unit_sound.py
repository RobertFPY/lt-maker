from app.engine.sound import get_sound_thread

class UnitSound():
    sound_catalog = {
        'Flier': {0: 'Flier', 20: 'repeat'},
        'FDragon': {0: 'FDragon', 20: 'repeat'},
        'Mounted': {0: 'Mounted1', 3: 'Mounted2', 10: 'Mounted3', 21: 'repeat'},
        'Armor': {0: 'Armor1', 16: 'Armor2', 32: 'repeat'},
        'Infantry': {0: 'Infantry1', 8: 'Infantry2', 16: 'repeat'},
        'MautheDoog': {0: 'MautheDoog', 21: 'repeat'},
        'Bael': {0: 'Bael', 21: 'repeat'},
        'Gorgon': {0: 'Gorgon', 20: 'repeat'},
        'Skeleton': {0: 'Skeleton', 16: 'repeat'},
        'Zombie': {0: 'Zombie', 16: 'repeat'},
        'Tarvos': {0: 'Tarvos', 21: 'repeat'},
        'Mogall': {0: 'Mogall', 19: 'repeat'}}

    def __init__(self, unit):
        self.unit = unit
        self.frame = 0
        self.current_sound = 0
        self.playing_sound = 0

    def play(self):
        if 'Mogall' in self.unit.tags:
            self.current_sound = 'Mogall'
        elif 'Tarvos' in self.unit.tags:
            self.current_sound = 'Tarvos'
        elif 'Zombie' in self.unit.tags:
            self.current_sound = 'Zombie'
        elif 'Skeleton' in self.unit.tags:
            self.current_sound = 'Skeleton'
        elif 'Gorgon' in self.unit.tags:
            self.current_sound = 'Gorgon'
        elif 'Bael' in self.unit.tags:
            self.current_sound = 'Bael'
        elif 'MautheDoog' in self.unit.tags:
            self.current_sound = 'MautheDoog'
        elif 'Dragon2' in self.unit.tags:
            self.current_sound = 'FDragon'
        elif 'Wyvern' in self.unit.tags:
            self.current_sound = 'FDragon' 
        elif 'Flying' in self.unit.tags:
            self.current_sound = 'Flier'
        elif 'Mounted' in self.unit.tags:
            self.current_sound = 'Mounted'
        elif 'Armor' in self.unit.tags:
            self.current_sound = 'Armor'
        else:
            self.current_sound = 'Infantry'

    def update(self, volume=1):
        if self.current_sound:
            if self.frame in self.sound_catalog[self.current_sound]:
                sound = self.sound_catalog[self.current_sound][self.frame]
                if sound == 'repeat':
                    self.frame = -1
                else:
                    self.playing_sound = 'Map_Step_' + sound
                    get_sound_thread().play_sfx(self.playing_sound, volume=volume)
            self.frame += 1

    def stop(self):
        get_sound_thread().stop_sfx(self.playing_sound)
        self.current_sound, self.playing_sound = None, None
        self.frame = 0
