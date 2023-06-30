from dataclasses import dataclass, field

from typing import List

from app.utilities.data import Data, Prefab
from app.utilities.typing import NID

@dataclass
class Team(Prefab):
    nid: NID
    palette: NID = None  # Used for map sprites
    combat_variant_palette: str = None  # Used for battle animation
    combat_color: str = 'red'
    _allies: List[NID] = field(default_factory=list)

    @property
    def allies(self) -> List[NID]:
        return [self.nid] + self._allies

    def set_allies(self, allies: List[NID]):
        self._allies = allies[:]

class TeamCatalog(Data[Team]):
    datatype = Team
    # Order determine phase order
    # These teams cannot be removed
    default_teams = [
        'player', 'enemy', 'enemy2', 'other',
    ]
    default_combat_palettes = [
        'GenericBlue', 'GenericRed', 'GenericPurple', 'GenericGreen',
    ]
    default_colors = [
        'blue', 'red', 'purple', 'green',
    ]
    default_allies = [
        ['other'], [], [], ['player'],
    ]

    def __init__(self):
        super().__init__()
        print("TEAM CATALOG ASSEMBLE")
        self.add_defaults()

    def add_defaults(self):
        for idx, nid in enumerate(self.default_teams):
            if nid not in self.keys():
                team = Team(
                    nid, '%s_team_palette', self.default_combat_palettes[idx], 
                    self.default_colors[idx], self.default_allies[idx])
                self.append(team)

    def restore(self, vals):
        super().restore(vals)
        self.add_defaults()
        return self

    def player(self) -> Team:
        # player is a special team that is used often throughout the engine
        # because it is the user's controlled team
        return self.get('player')

    @property    
    def allies(self) -> List[NID]:
        return self.player().allies

    @property    
    def enemies(self) -> List[NID]:
        return [team.nid for team in self if team.nid not in self.allies]
