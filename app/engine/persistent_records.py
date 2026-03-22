import logging
from app.utilities.data import Data, Prefab

from app.engine import persistent_data

from app.data.database.database import DB

class PersistentRecord(Prefab):
    def __init__(self, nid: str = '', value=None):
        self.nid = nid
        self.value = value

class PersistentRecordManager(Data):
    datatype = PersistentRecord

    def __init__(self, location):
        super().__init__()
        self.location = location

    def get(self, nid):
        if nid in self:
            return super().get(nid).value
        return None

    def create(self, nid, value=None):
        if nid in self:
            logging.info("Record with nid of %s already exists")
            return
        self.append(PersistentRecord(nid, value))
        persistent_data.serialize(self.location, self.save())

    def update(self, nid, value):
        if nid in self:
            record = super().get(nid)
            record.value = value
            persistent_data.serialize(self.location, self.save())
        else:
            logging.info("Record with nid of %s doesn't exist")

    def replace(self, nid, value):
        if nid in self:
            record = super().get(nid)
            record.value = value
        else:
            self.append(PersistentRecord(nid, value))
        persistent_data.serialize(self.location, self.save())

    def delete(self, nid):
        if nid in self:
            self.remove_key(nid)
            persistent_data.serialize(self.location, self.save())
        else:
            logging.info("Record with nid of %s doesn't exist")
    
    def unlock_difficulty(self, difficultyMode: str):
        if difficultyMode in self:
            logging.info("Difficulty with nid of %s already unlocked")
            return
        else:
            self.append(PersistentRecord(difficultyMode, True))
        persistent_data.serialize(self.location, self.save())
    
    def check_difficulty_unlocked(self, difficultyMode: str):
        if difficultyMode in self:
            return super().get(difficultyMode).value
        else:
            return False

    def unlock_song(self, music: str):
        if music in self:
            logging.info("Music with nid of %s already unlocked")
            return
        else:
            self.append(PersistentRecord(music, True))
        persistent_data.serialize(self.location, self.save())

    def check_song_unlocked(self, music: str):
        if music in self:
            return super().get(music).value
        else:
            return False

    def unlock_support_rank(self, support_pair: str, rank: str):
        if support_pair not in self:
            self.append(PersistentRecord(support_pair, []))
        unlocked_ranks = super().get(support_pair).value

        if rank in unlocked_ranks:
            logging.info("Support Pair with nid of %s already unlocked rank %s" % (support_pair, rank))
            return
        else:
            unlocked_ranks.append(rank)
        persistent_data.serialize(self.location, self.save())

    def check_support_unlocked(self, support_pair: str, rank: str):
        if support_pair in self:
            return rank in super().get(support_pair).value
        else:
            return False

    def mark_unit_as_loaded(self, unit_nid: str):
        key = '_loaded_units'
        if key not in self:
            self.append(PersistentRecord(key, []))
        loaded_units = super().get(key).value

        if unit_nid in loaded_units:
            logging.info("Unit with nid of %s already unlocked" % unit_nid)
            return
        else:
            loaded_units.append(unit_nid)
        persistent_data.serialize(self.location, self.save())

    def check_unit_loaded(self, unit_nid: str):
        key = '_loaded_units'
        if key in self:
            return unit_nid in super().get(key).value
        else:
            return False

    def unlock_support_room(self):
        self.create('_support_room_unlocked', True)

    def check_support_room_unlocked(self):
        return self.get('_support_room_unlocked')

def reset():
    game_id = str(DB.constants.value('game_nid'))
    location = 'saves/' + game_id + '-persistent_records.p'
    RECORDS.location = location
    data = persistent_data.deserialize(location)
    if data:
        RECORDS.restore(data)
    else:
        RECORDS.clear()

# Make sure to reload all persistent records whenever we start the engine
game_id = str(DB.constants.value('game_nid'))
location = 'saves/' + game_id + '-persistent_records.p'
data = persistent_data.deserialize(location)
RECORDS = PersistentRecordManager(location)
if data:
    RECORDS.restore(data)
