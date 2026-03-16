from app.data.database.database import Database
from app.data.resources.resources import Resources
from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
from app.events.event_prefab import EventPrefab
from app.events.event_validators import (
    Integer, Validator,
    Float, PositiveInteger, WholeNumber, Time, Volume,
    String, EvaluableString, Nid,
    Bool, IntegerList, BoolList, StringList,
    ScreenPosition, Slide, Direction, Orientation,
    AnimationType, CardinalDirection, EntryType, Placement, MovementType, RemoveType,
    RegionType, Weather,
    Align, HAlign, VAlign, AlignOrPosition,
    GrowthMethod, CombatScript, ExpressionList, IllegalCharacterList,
    PositionOffset, Size, Color3,
    Speaker, ShopFlavor,
    FogOfWarType, ShakeType, TableEntryType, LayerTransition,
    SpritePose, SpriteDirection, SpecialMusicType, RNGType,
    Music, Sound, PortraitNid, Portrait,
    Team, Tag, SupportRank, TagList,
    GlobalUnit, GlobalUnitOrConvoy, UniqueUnit,
    SaveSlot,
    Panorama, MapAnim, Tilemap,
    Affinity, AI, Skill, Item, Ability, ItemList,
    Klass, Faction, WeaponType, Lore, Chapter, Party,
    StatList, KlassList, ArgList,
    UnitField, Region,
    Width, Speed, DifficultyMode,
    SkillAttrValidator, ItemAttrValidator,
    RawDataValidator, UnitFieldValidator, VarValidator,
    Achievement, GeneralVar, EventFunction, DialogVariant,
    PointList, Position, FloatPosition,
    Group, StartingGroup, Event,
    OverworldNID, OverworldLocation, OverworldNodeNID, OverworldNodeMenuOption, OverworldEntity,
    ItemComponent, SkillComponent,
    Sprite, MaybeSprite, PhaseMusic,
)
from app.data.database.units import UnitPrefab
from app.data.database.skills import SkillPrefab
from app.data.database.items import ItemPrefab
from app.data.database.klass import Klass as KlassPrefab
from app.data.database.factions import Faction as FactionPrefab
from app.data.database.weapons import WeaponType as WeaponTypePrefab
from app.data.database.lore import Lore as LorePrefab
from app.data.database.supports import Affinity as AffinityPrefab, SupportRank as SupportRankPrefab
from app.data.database.teams import Team as TeamPrefab
from app.data.database.tags import Tag as TagPrefab, TagCatalog
from app.data.database.ai import AIPrefab
from app.data.database.parties import PartyPrefab
from app.data.database.levels import LevelPrefab
from app.data.database.stats import StatPrefab
from app.data.database.difficulty_modes import DifficultyModePrefab
from app.data.resources.sounds import SFXPrefab
from app.data.resources.portraits import PortraitPrefab
from app.data.resources.panoramas import Panorama as PanoramaResource
from app.data.resources.map_animations import MapAnimation as MapAnimationResource
from app.data.resources.tiles import TileMapPrefab
from app.data.database.overworld import OverworldPrefab, OverworldNodePrefab
from app.data.database.levels import UnitGroup
from app.events.node_events import NodeMenuEvent
from app.events.speak_style import SpeakStyle, SpeakStyleLibrary
from app.events.triggers import GenericTrigger
from app.events.screen_positions import horizontal_screen_positions, vertical_screen_positions
from app.sprites import SPRITES
from app.engine import item_component_access as ICA
from app.engine import skill_component_access as SCA
from typing import List, Optional, Tuple
import unittest
from unittest.mock import MagicMock, patch, call

from app.tests.mocks.mock_game import get_mock_game
from app.events.event_commands import EventCommand, parse_text_to_command
from app.utilities.enums import Alignments
from app.engine.codegen import source_generator
from app.utilities.str_utils import SHIFT_NEWLINE
from app.utilities.typing import NID

class EventValidateUnitTests(unittest.TestCase):
    def setUp(self):
        self.db: Database = Database()
        self.resources: Resources = Resources()
        source_generator.event_command_codegen()

    def assert_validator_fails(self, validator: Validator, value: str, level: Optional[str] = None):
        self.assertFalse(validator.validate(value, level), f"Expected validator to fail for value: {value}")

    def assert_validator_passes(self, validator: Validator, value: str, level: Optional[str] = None):
        self.assertTrue(validator.validate(value, level), f"Expected validator to pass for value: {value}")

    def assert_valid_entries(self, validator: Validator, valid_values: List[Tuple[Optional[str], NID]], text: Optional[str], level: Optional[str] = None):
        self.assertEqual(set(validator.valid_entries(level, text)), set(valid_values))

    def test_integer_validator(self):
        validator = Integer()
        self.assert_validator_passes(validator, "10")
        self.assert_validator_passes(validator, "-5")
        self.assert_validator_fails(validator, "abc")

    # --- pure numeric validators ---

    def test_float_validator(self):
        v = Float()
        self.assert_validator_passes(v, "3.14")
        self.assert_validator_passes(v, "-1.5")
        self.assert_validator_fails(v, "abc")

    def test_positive_integer_validator(self):
        v = PositiveInteger()
        self.assert_validator_passes(v, "5")
        self.assert_validator_fails(v, "0")
        self.assert_validator_fails(v, "-1")
        self.assert_validator_fails(v, "abc")

    def test_whole_number_validator(self):
        v = WholeNumber()
        self.assert_validator_passes(v, "5")
        self.assert_validator_fails(v, "-1")
        self.assert_validator_fails(v, "abc")

    def test_time_validator(self):
        v = Time()
        self.assert_validator_passes(v, "500")
        self.assert_validator_fails(v, "abc")

    def test_volume_validator(self):
        v = Volume()
        self.assert_validator_passes(v, "0.5")
        self.assert_validator_passes(v, "1.0")
        self.assert_validator_fails(v, "abc")

    def test_width_validator(self):
        v = Width()
        self.assert_validator_passes(v, "64")
        self.assert_validator_fails(v, "abc")

    def test_speed_validator(self):
        v = Speed()
        self.assert_validator_passes(v, "200")
        self.assert_validator_fails(v, "abc")

    def test_integer_list_validator(self):
        v = IntegerList()
        self.assert_validator_passes(v, "1,2,3")
        self.assert_validator_fails(v, "1,abc,3")

    def test_bool_list_validator(self):
        v = BoolList()
        self.assert_validator_passes(v, "true,false,true")
        self.assert_validator_fails(v, "true,maybe,false")

    def test_position_offset_validator(self):
        v = PositionOffset()
        self.assert_validator_passes(v, "2,-3")
        self.assert_validator_fails(v, "2,3,4")  # too many elements

    def test_size_validator(self):
        v = Size()
        self.assert_validator_passes(v, "64,32")
        self.assert_validator_fails(v, "64,32,16")  # too many elements

    def test_color3_validator(self):
        v = Color3()
        self.assert_validator_passes(v, "128,160,136")
        self.assert_validator_fails(v, "256,0,0")   # out of range
        self.assert_validator_fails(v, "128,160")    # wrong element count

    # --- string-type validators ---

    def test_nid_validator(self):
        v = Nid()
        self.assert_validator_passes(v, "anything")

    def test_string_validator(self):
        v = String()
        self.assert_validator_passes(v, "hello world")

    def test_evaluable_string_validator(self):
        v = EvaluableString()
        self.assert_validator_passes(v, "hello world")

    def test_string_list_validator(self):
        v = StringList()
        self.assert_validator_passes(v, "Water,Earth,Fire")

    def test_speaker_validator(self):
        v = Speaker()
        self.assert_validator_passes(v, "anyone")
        self.assert_valid_entries(v, [], text=None)  # always returns [] (no speak styles in empty db)

    def test_shop_flavor_validator(self):
        v = ShopFlavor()
        self.assert_validator_passes(v, "armory")
        self.assert_valid_entries(v, [(None, "vendor"), (None, "armory")], text=None)

    def test_unit_field_validator(self):
        v = UnitField()
        self.assert_validator_passes(v, "any_field")
        self.assert_valid_entries(v, [], text=None)  # no units with fields in empty db

    def test_region_validator(self):
        v = Region()
        self.assert_validator_passes(v, "any_region")
        self.assert_valid_entries(v, [], text=None)  # no level → empty

    # --- bool validator ---

    def test_bool_validator(self):
        v = Bool()
        for val in ['t', 'true', '1', 'y', 'yes', 'f', 'false', '0', 'n', 'no']:
            self.assert_validator_passes(v, val)
        self.assert_validator_fails(v, "maybe")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    # --- option validators ---

    def test_slide_validator(self):
        v = Slide()
        self.assert_validator_passes(v, "normal")
        self.assert_validator_passes(v, "left")
        self.assert_validator_fails(v, "diagonal")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_direction_validator(self):
        v = Direction()
        self.assert_validator_passes(v, "open")
        self.assert_validator_passes(v, "close")
        self.assert_validator_fails(v, "sideways")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_orientation_validator(self):
        v = Orientation()
        self.assert_validator_passes(v, "h")
        self.assert_validator_passes(v, "vertical")
        self.assert_validator_fails(v, "diagonal")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_animation_type_validator(self):
        v = AnimationType()
        self.assert_validator_passes(v, "north")
        self.assert_validator_passes(v, "fade")
        self.assert_validator_fails(v, "teleport")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_cardinal_direction_validator(self):
        v = CardinalDirection()
        self.assert_validator_passes(v, "north")
        self.assert_validator_passes(v, "south")
        self.assert_validator_fails(v, "fade")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_entry_type_validator(self):
        v = EntryType()
        self.assert_validator_passes(v, "fade")
        self.assert_validator_passes(v, "warp")
        self.assert_validator_fails(v, "teleport")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_placement_validator(self):
        v = Placement()
        self.assert_validator_passes(v, "giveup")
        self.assert_validator_passes(v, "closest")
        self.assert_validator_fails(v, "random")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_movement_type_validator(self):
        v = MovementType()
        self.assert_validator_passes(v, "normal")
        self.assert_validator_passes(v, "warp")
        self.assert_validator_fails(v, "teleport")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_remove_type_validator(self):
        v = RemoveType()
        self.assert_validator_passes(v, "fade")
        self.assert_validator_passes(v, "immediate")
        self.assert_validator_fails(v, "poof")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_region_type_validator(self):
        v = RegionType()
        self.assert_validator_passes(v, "normal")
        self.assert_validator_passes(v, "event")
        self.assert_validator_fails(v, "invalid")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_weather_validator(self):
        v = Weather()
        self.assert_validator_passes(v, "rain")
        self.assert_validator_passes(v, "snow")
        self.assert_validator_fails(v, "hail")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_fog_of_war_type_validator(self):
        v = FogOfWarType()
        self.assert_validator_passes(v, "gba")
        self.assert_validator_passes(v, "thracia")
        self.assert_validator_fails(v, "sacred_stones")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_shake_type_validator(self):
        v = ShakeType()
        self.assert_validator_passes(v, "default")
        self.assert_validator_passes(v, "combat")
        self.assert_validator_fails(v, "explosion")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_table_entry_type_validator(self):
        v = TableEntryType()
        self.assert_validator_passes(v, "type_skill")
        self.assert_validator_passes(v, "type_unit")
        self.assert_validator_fails(v, "type_invalid")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_layer_transition_validator(self):
        v = LayerTransition()
        self.assert_validator_passes(v, "fade")
        self.assert_validator_passes(v, "immediate")
        self.assert_validator_fails(v, "warp")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_sprite_pose_validator(self):
        v = SpritePose()
        self.assert_validator_passes(v, "normal")
        self.assert_validator_passes(v, "active")
        self.assert_validator_fails(v, "dancing")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_sprite_direction_validator(self):
        v = SpriteDirection()
        self.assert_validator_passes(v, "up")
        self.assert_validator_passes(v, "down")
        self.assert_validator_fails(v, "northeast")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_special_music_type_validator(self):
        v = SpecialMusicType()
        self.assert_validator_passes(v, "promotion")
        self.assert_validator_passes(v, "game_over")
        self.assert_validator_fails(v, "battle")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_growth_method_validator(self):
        v = GrowthMethod()
        self.assert_validator_passes(v, "random")
        self.assert_validator_passes(v, "fixed")
        self.assert_validator_fails(v, "magic")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_rng_type_validator(self):
        v = RNGType()
        self.assert_validator_passes(v, "Classic")
        self.assert_validator_passes(v, "True Hit")
        self.assert_validator_fails(v, "NotARNGType")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    # --- enum validators ---

    def test_align_validator(self):
        v = Align()
        self.assert_validator_passes(v, "top_left")
        self.assert_validator_passes(v, "center")
        self.assert_validator_fails(v, "not_an_alignment")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_halign_validator(self):
        v = HAlign()
        self.assert_validator_passes(v, "left")
        self.assert_validator_passes(v, "center")
        self.assert_validator_fails(v, "diagonal")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_valign_validator(self):
        v = VAlign()
        self.assert_validator_passes(v, "top")
        self.assert_validator_passes(v, "bottom")
        self.assert_validator_fails(v, "diagonal")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    def test_align_or_position_validator(self):
        v = AlignOrPosition()
        self.assert_validator_passes(v, "center")
        self.assert_validator_passes(v, "10,20")
        self.assert_validator_fails(v, "not_an_alignment")
        self.assert_validator_fails(v, "10,abc")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    # --- sequence validators ---

    def test_expression_list_validator(self):
        v = ExpressionList()
        self.assert_validator_passes(v, "Smile,NoSmile")
        self.assert_validator_fails(v, "Smile,InvalidExpression")
        self.assert_valid_entries(v, [(None, e) for e in v.valid_expressions], text=None)

    def test_illegal_character_list_validator(self):
        v = IllegalCharacterList()
        self.assert_validator_passes(v, "uppercase,lowercase")
        self.assert_validator_fails(v, "uppercase,invalid_set")
        self.assert_valid_entries(v, [(None, s) for s in v.valid_sets], text=None)

    def test_combat_script_validator(self):
        v = CombatScript()
        self.assert_validator_passes(v, "hit1,hit2,end")
        self.assert_validator_fails(v, "hit1,invalid_command")
        self.assert_valid_entries(v, [(None, c) for c in v.valid_commands], text=None)

    def test_arg_list_validator(self):
        v = ArgList()
        self.assert_validator_passes(v, "Color,Purple,Animal,Dog")
        self.assert_validator_fails(v, "Color,Purple,Odd")

    # --- screen position validator ---

    def test_screen_position_validator(self):
        v = ScreenPosition()
        self.assert_validator_passes(v, "Left")
        self.assert_validator_passes(v, "5")
        self.assert_validator_passes(v, "Left,Top")
        self.assert_validator_fails(v, "foobar")
        self.assert_validator_fails(v, "Left,Right")  # two horizontal components
        expected = [(None, o) for o in horizontal_screen_positions] + [(None, o) for o in vertical_screen_positions]
        self.assert_valid_entries(v, expected, text=None)

    # --- validators with special-string pass cases ---

    def test_music_validator(self):
        v = Music()
        self.assert_validator_passes(v, "None")
        self.assert_validator_fails(v, "nonexistent_track")
        self.assert_valid_entries(v, [], text=None)  # resources.music is empty

    def test_portrait_validator(self):
        self.db.units.append(UnitPrefab("test_unit_portrait", "Test Unit"))
        self.resources.portraits.append(PortraitPrefab("test_portrait_img"))
        v = Portrait(db=self.db, resources=self.resources)
        self.assert_validator_passes(v, "{unit}")                  # special string
        self.assert_validator_passes(v, "{unit1}")                 # special string
        self.assert_validator_passes(v, "{unit2}")                 # special string
        self.assert_validator_passes(v, "test_unit_portrait")      # unit nid
        self.assert_validator_passes(v, "test_portrait_img")       # portrait nid
        self.assert_validator_fails(v, "nonexistent_portrait")
        self.assert_valid_entries(v, [
            (None, "test_portrait_img"),
            ("Test Unit", "test_unit_portrait"),
            (None, "{unit}"), (None, "{unit1}"), (None, "{unit2}"),
        ], text=None)

    def test_global_unit_validator(self):
        self.db.units.append(UnitPrefab("test_unit_global", "Test Unit"))
        v = GlobalUnit(db=self.db)
        self.assert_validator_passes(v, "{unit}")              # special string
        self.assert_validator_passes(v, "{unit1}")             # special string
        self.assert_validator_passes(v, "test_unit_global")    # db unit nid
        self.assert_validator_fails(v, "nonexistent_unit")
        self.assert_valid_entries(v, [
            ("Test Unit", "test_unit_global"),
            (None, "{unit}"), (None, "{unit1}"), (None, "{unit2}"),
        ], text=None)

    def test_global_unit_or_convoy_validator(self):
        self.db.units.append(UnitPrefab("test_unit_convoy", "Test Unit"))
        v = GlobalUnitOrConvoy(db=self.db)
        self.assert_validator_passes(v, "convoy")               # special string
        self.assert_validator_passes(v, "{unit}")               # special string
        self.assert_validator_passes(v, "test_unit_convoy")     # db unit nid
        self.assert_validator_fails(v, "nonexistent_unit")
        self.assert_valid_entries(v, [
            ("Test Unit", "test_unit_convoy"),
            (None, "{unit}"), (None, "{unit1}"), (None, "{unit2}"),
            (None, "convoy"),
        ], text=None)

    def test_save_slot_validator(self):
        v = SaveSlot(db=self.db)
        self.assert_validator_passes(v, "suspend")
        self.assert_validator_passes(v, "0")
        self.assert_validator_passes(v, "2")
        self.assert_validator_fails(v, "3")  # num_save_slots defaults to 3
        self.assert_validator_fails(v, "abc")
        self.assert_valid_entries(v, [(None, "0"), (None, "1"), (None, "2"), (None, "suspend")], text=None)

    # --- validators with default db data ---

    def test_team_validator(self):
        self.db.teams.append(TeamPrefab("test_team"))
        v = Team(db=self.db)
        self.assert_validator_passes(v, "player")     # default
        self.assert_validator_passes(v, "test_team")  # added
        self.assert_validator_fails(v, "nonexistent_team")
        self.assert_valid_entries(v, [
            (None, "player"), (None, "enemy"), (None, "enemy2"), (None, "other"), (None, "test_team"),
        ], text=None)

    def test_tag_validator(self):
        self.db.tags.append(TagPrefab("test_tag"))
        v = Tag(db=self.db)
        self.assert_validator_passes(v, "Lord")       # default
        self.assert_validator_passes(v, "test_tag")   # added
        self.assert_validator_fails(v, "NonexistentTag")
        tagListV = TagList(db=self.db)
        self.assert_validator_passes(tagListV, "Lord,Boss")          # defaults
        self.assert_validator_passes(tagListV, "Lord,test_tag")    # mixed
        self.assert_validator_fails(tagListV, "Lord,NotATag")
        self.assert_valid_entries(v, [
            (None, t) for t in
            TagCatalog.default_tags + ["test_tag"]
        ], text=None)

    def test_support_rank_validator(self):
        self.db.support_ranks.append(SupportRankPrefab("S"))
        v = SupportRank(db=self.db)
        self.assert_validator_passes(v, "C")   # default
        self.assert_validator_passes(v, "S")   # added
        self.assert_validator_fails(v, "Z")
        self.assert_valid_entries(v, [(None, "C"), (None, "B"), (None, "A"), (None, "S")], text=None)

    # --- validators backed by db/resources ---

    def test_sound_validator(self):
        self.resources.sfx.append(SFXPrefab("test_sfx"))
        v = Sound(resources=self.resources)
        self.assert_validator_passes(v, "test_sfx")
        self.assert_validator_fails(v, "nonexistent_sfx")
        self.assert_valid_entries(v, [(None, "test_sfx")], text=None)

    def test_portrait_nid_validator(self):
        self.resources.portraits.append(PortraitPrefab("test_portrait"))
        v = PortraitNid(resources=self.resources)
        self.assert_validator_passes(v, "test_portrait")
        self.assert_validator_fails(v, "nonexistent_portrait")
        self.assert_valid_entries(v, [(None, "test_portrait")], text=None)

    def test_panorama_validator(self):
        self.resources.panoramas.append(PanoramaResource("test_panorama"))
        v = Panorama(resources=self.resources)
        self.assert_validator_passes(v, "test_panorama")
        self.assert_validator_fails(v, "nonexistent_panorama")
        self.assert_valid_entries(v, [(None, "test_panorama")], text=None)

    def test_map_anim_validator(self):
        self.resources.animations.append(MapAnimationResource("test_anim"))
        v = MapAnim(resources=self.resources)
        self.assert_validator_passes(v, "test_anim")
        self.assert_validator_fails(v, "nonexistent_anim")
        self.assert_valid_entries(v, [(None, "test_anim")], text=None)

    def test_tilemap_validator(self):
        self.resources.tilemaps.append(TileMapPrefab("test_tilemap"))
        v = Tilemap(resources=self.resources)
        self.assert_validator_passes(v, "test_tilemap")
        self.assert_validator_fails(v, "nonexistent_tilemap")
        self.assert_valid_entries(v, [(None, "test_tilemap")], text=None)

    def test_affinity_validator(self):
        self.db.affinities.append(AffinityPrefab(nid="test_affinity"))
        v = Affinity(db=self.db)
        self.assert_validator_passes(v, "test_affinity")
        self.assert_validator_fails(v, "nonexistent_affinity")
        self.assert_valid_entries(v, [(None, "test_affinity")], text=None)

    def test_ai_validator(self):
        self.db.ai.append(AIPrefab("test_ai", 0))
        v = AI(db=self.db)
        self.assert_validator_passes(v, "test_ai")
        self.assert_validator_fails(v, "nonexistent_ai")
        self.assert_valid_entries(v, [(None, "test_ai")], text=None)

    def test_skill_validator(self):
        self.db.skills.append(SkillPrefab("test_skill", "Test Skill", ""))
        v = Skill(db=self.db)
        self.assert_validator_passes(v, "test_skill")
        self.assert_validator_fails(v, "nonexistent_skill")
        self.assert_valid_entries(v, [("Test Skill", "test_skill")], text=None)

    def test_item_validator(self):
        self.db.items.append(ItemPrefab("test_item", "Test Item", ""))
        v = Item(db=self.db)
        self.assert_validator_passes(v, "test_item")
        self.assert_validator_fails(v, "nonexistent_item")
        self.assert_valid_entries(v, [("Test Item", "test_item")], text=None)

    def test_ability_validator(self):
        self.db.items.append(ItemPrefab("test_ability_item", "Test Item", ""))
        self.db.skills.append(SkillPrefab("test_ability_skill", "Test Skill", ""))
        v = Ability(db=self.db)
        self.assert_validator_passes(v, "test_ability_item")
        self.assert_validator_passes(v, "test_ability_skill")
        self.assert_validator_fails(v, "nonexistent_ability")
        self.assert_valid_entries(v, [("Test Item", "test_ability_item"), ("Test Skill", "test_ability_skill")], text=None)

    def test_item_list_validator(self):
        self.db.items.append(ItemPrefab("item_a", "Item A", ""))
        self.db.items.append(ItemPrefab("item_b", "Item B", ""))
        v = ItemList(db=self.db)
        self.assert_validator_passes(v, "item_a,item_b")
        self.assert_validator_fails(v, "item_a,nonexistent_item")
        self.assert_valid_entries(v, [(None, "item_a"), (None, "item_b")], text=None)

    def test_klass_validator(self):
        self.db.classes.append(KlassPrefab(nid="test_klass"))
        v = Klass(db=self.db)
        self.assert_validator_passes(v, "test_klass")
        self.assert_validator_fails(v, "nonexistent_class")
        self.assert_valid_entries(v, [(None, "test_klass")], text=None)

    def test_klass_list_validator(self):
        self.db.classes.append(KlassPrefab(nid="klass_a"))
        self.db.classes.append(KlassPrefab(nid="klass_b"))
        v = KlassList(db=self.db)
        self.assert_validator_passes(v, "klass_a,klass_b")
        self.assert_validator_fails(v, "klass_a,nonexistent_class")
        self.assert_valid_entries(v, [(None, "klass_a"), (None, "klass_b")], text=None)

    def test_faction_validator(self):
        self.db.factions.append(FactionPrefab(nid="test_faction"))
        v = Faction(db=self.db)
        self.assert_validator_passes(v, "test_faction")
        self.assert_validator_fails(v, "nonexistent_faction")
        self.assert_valid_entries(v, [(None, "test_faction")], text=None)

    def test_weapon_type_validator(self):
        self.db.weapons.append(WeaponTypePrefab(nid="test_weapon"))
        v = WeaponType(db=self.db)
        self.assert_validator_passes(v, "test_weapon")
        self.assert_validator_fails(v, "nonexistent_weapon")
        self.assert_valid_entries(v, [(None, "test_weapon")], text=None)

    def test_lore_validator(self):
        self.db.lore.append(LorePrefab(nid="test_lore"))
        v = Lore(db=self.db)
        self.assert_validator_passes(v, "test_lore")
        self.assert_validator_fails(v, "nonexistent_lore")
        self.assert_valid_entries(v, [(None, "test_lore")], text=None)

    def test_chapter_validator(self):
        self.db.levels.append(LevelPrefab("test_level", "Test Level"))
        v = Chapter(db=self.db)
        self.assert_validator_passes(v, "test_level")
        self.assert_validator_fails(v, "nonexistent_chapter")
        self.assert_valid_entries(v, [(None, "test_level")], text=None)

    def test_party_validator(self):
        self.db.parties.append(PartyPrefab(nid="test_party"))
        v = Party(db=self.db)
        self.assert_validator_passes(v, "test_party")
        self.assert_validator_fails(v, "nonexistent_party")
        self.assert_valid_entries(v, [(None, "test_party")], text=None)

    def test_stat_list_validator(self):
        self.db.stats.append(StatPrefab(nid="STR"))
        v = StatList(db=self.db)
        self.assert_validator_passes(v, "STR,2")
        self.assert_validator_fails(v, "MISSING_STAT,2")
        self.assert_valid_entries(v, [(None, "STR")], text=None)

    def test_unique_unit_validator(self):
        self.db.units.append(UnitPrefab("test_unit", "Test Unit"))
        v = UniqueUnit(db=self.db)
        self.assert_validator_passes(v, "test_unit")
        self.assert_validator_fails(v, "nonexistent_unit")
        self.assert_valid_entries(v, [("Test Unit", "test_unit")], text=None)

    def test_difficulty_mode_validator(self):
        self.db.difficulty_modes.append(DifficultyModePrefab(nid="test_difficulty"))
        v = DifficultyMode(db=self.db)
        self.assert_validator_passes(v, "test_difficulty")
        self.assert_validator_fails(v, "nonexistent_difficulty")
        self.assert_valid_entries(v, [(None, "test_difficulty")], text=None)


    # --- eval validators (use base validate, always pass) ---

    def test_raw_data_validator(self):
        v = RawDataValidator()
        self.assert_validator_passes(v, "any_text")
        self.assert_valid_entries(v, [], text=None)  # returns [] when text is None/empty

    def test_unit_field_eval_validator(self):
        v = UnitFieldValidator()
        self.assert_validator_passes(v, "any_text")
        # with empty db, level 0 (no dot in text) returns only the special unit placeholders
        self.assert_valid_entries(v, [(None, "_unit"), (None, "_unit2")], text="")

    def test_var_validator(self):
        v = VarValidator()
        self.assert_validator_passes(v, "any_var")
        self.assert_valid_entries(v, [], text=None)  # no game_var_slots or level vars in empty db

    def test_achievement_validator(self):
        v = Achievement()
        self.assert_validator_passes(v, "any_achievement")
        self.assert_valid_entries(v, [], text=None)  # no CreateAchievement calls in empty db

    def test_general_var_validator(self):
        v = GeneralVar()
        self.assert_validator_passes(v, "any_var")
        self.assert_valid_entries(v, [], text=None)  # no game_var_slots in empty db

    def test_overworld_entity_validator(self):
        v = OverworldEntity()
        self.assert_validator_passes(v, "any_entity")
        self.assert_valid_entries(v, [], text=None)  # no parties in empty db

    # --- eval validators with real logic ---

    def test_skill_attr_validator(self):
        self.db.skills.append(SkillPrefab("test_skill_attr", "Test Skill", ""))
        v = SkillAttrValidator(db=self.db)
        self.assert_validator_passes(v, "test_skill_attr.nid")
        self.assert_validator_fails(v, "test_skill_attr")        # no dot
        self.assert_validator_fails(v, "nonexistent_skill.nid")  # unknown skill
        # with text="" (0 dots), returns all skill nids
        self.assert_valid_entries(v, [(None, "test_skill_attr")], text="")

    def test_item_attr_validator(self):
        self.db.items.append(ItemPrefab("test_item_attr", "Test Item", ""))
        v = ItemAttrValidator(db=self.db)
        self.assert_validator_passes(v, "test_item_attr.nid")
        self.assert_validator_fails(v, "test_item_attr")          # no dot
        self.assert_validator_fails(v, "nonexistent_item.nid")    # unknown item
        # with text="" (0 dots), returns all item nids
        self.assert_valid_entries(v, [(None, "test_item_attr")], text="")

    # --- event function and dialog ---

    def test_event_function_validator(self):
        v = EventFunction()
        self.assert_validator_passes(v, "comment")
        self.assert_validator_fails(v, "not_a_command")
        from app.events import event_commands as ec
        expected = [(None, cmd.nid) for cmd in ec.get_commands() if cmd.tag not in (ec.Tags.HIDDEN,)]
        self.assert_valid_entries(v, expected, text=None)

    def test_dialog_variant_validator(self):
        v = DialogVariant(db=self.db)
        self.assert_validator_passes(v, "narration")
        self.assert_validator_passes(v, "thought_bubble")
        self.assert_validator_fails(v, "nonexistent_variant")
        # no SpeakStyle calls in empty db, so only built_in styles are returned
        self.assert_valid_entries(v, [(None, s) for s in DialogVariant.built_in], text=None)

    # --- position validators (special strings work without level) ---

    def test_position_validator(self):
        v = Position()
        self.assert_validator_passes(v, "{unit}")
        self.assert_validator_passes(v, "{position}")
        self.assert_validator_passes(v, "3,5")    # no level → skips tilemap check, returns text
        self.assert_validator_fails(v, "unknown_unit")
        self.assert_valid_entries(v, [], text=None)  # no level nid in db → empty

    def test_float_position_validator(self):
        v = FloatPosition()
        self.assert_validator_passes(v, "{unit}")
        self.assert_validator_passes(v, "3.5,5.2")  # no level → skips tilemap check
        self.assert_validator_fails(v, "unknown_unit")

    # --- group validators ---

    def test_group_validator(self):
        lp = LevelPrefab("test_level_g", "Test Level")
        lp.unit_groups.append(UnitGroup("test_group"))
        self.db.levels.append(lp)
        v = Group(db=self.db)
        self.assert_validator_passes(v, "test_group", level=lp)
        self.assert_validator_fails(v, "nonexistent_group", level=lp)
        self.assert_validator_fails(v, "test_group")  # no level → None
        self.assert_valid_entries(v, [(None, "test_group")], text=None, level="test_level_g")

    def test_starting_group_validator(self):
        lp = LevelPrefab("test_level_sg", "Test Level")
        self.db.levels.append(lp)
        v = StartingGroup(db=self.db)
        self.assert_validator_passes(v, "starting", level=lp)
        self.assert_validator_passes(v, "1,2", level=lp)
        self.assert_validator_fails(v, "starting")  # no level → None
        # valid_entries uses level nid lookup: only "starting" since no unit_groups
        self.assert_valid_entries(v, [(None, "starting")], text=None, level="test_level_sg")

    # --- event validator ---

    def test_event_validator(self):
        self.db.events.append(EventPrefab("test_event"))
        v = Event(db=self.db)
        self.assert_validator_passes(v, "test_event")
        self.assert_validator_fails(v, "nonexistent_event")
        # get_by_level(None) returns all events; EventPrefab("test_event").nid = "Global test_event"
        self.assert_valid_entries(v, [("test_event", "Global test_event")], text=None)

    # --- overworld validators ---

    def test_overworld_nid_validator(self):
        self.db.overworlds.append(OverworldPrefab("test_ow", "Test OW"))
        v = OverworldNID(db=self.db)
        self.assert_validator_passes(v, "test_ow")
        self.assert_validator_fails(v, "nonexistent_ow")
        self.assert_valid_entries(v, [("Test OW", "test_ow")], text=None)

    def test_overworld_location_validator(self):
        v = OverworldLocation()
        self.assert_validator_passes(v, "1.5,2.5")   # parsed as coordinate tuple
        self.assert_validator_fails(v, "nonexistent_node")
        self.assert_valid_entries(v, [], text=None)  # no overworld nodes in empty db

    def test_overworld_node_nid_validator(self):
        ow = OverworldPrefab("test_ow_nodes", "Test OW")
        ow.overworld_nodes.append(OverworldNodePrefab("test_node", "Test Node", (0, 0)))
        self.db.overworlds.append(ow)
        v = OverworldNodeNID(db=self.db)
        self.assert_validator_passes(v, "test_node")
        self.assert_validator_fails(v, "nonexistent_node")
        self.assert_valid_entries(v, [("Test Node", "test_node")], text=None)

    def test_overworld_node_menu_option_validator(self):
        ow = OverworldPrefab("test_ow_menus", "Test OW")
        node = OverworldNodePrefab("test_node_menu", "Test Node", (0, 0))
        node.menu_options.append(NodeMenuEvent("test_option"))
        ow.overworld_nodes.append(node)
        self.db.overworlds.append(ow)
        v = OverworldNodeMenuOption(db=self.db)
        self.assert_validator_passes(v, "test_option")
        self.assert_validator_fails(v, "nonexistent_option")
        # NodeMenuEvent.option_name defaults to '' (empty string)
        self.assert_valid_entries(v, [("", "test_option")], text=None)

    # --- component validators ---

    def test_item_component_validator(self):
        v = ItemComponent()
        self.assert_validator_passes(v, "additional_item_command")
        self.assert_validator_fails(v, "nonexistent_component")
        expected = [(None, c.nid) for c in ICA.get_item_components()]
        self.assert_valid_entries(v, expected, text=None)

    def test_skill_component_validator(self):
        v = SkillComponent()
        self.assert_validator_passes(v, "hidden")
        self.assert_validator_fails(v, "nonexistent_component")
        expected = [(None, c.nid) for c in SCA.get_skill_components()]
        self.assert_valid_entries(v, expected, text=None)

    # --- sprite validators (uses global SPRITES, already populated) ---

    def test_sprite_validator(self):
        v = Sprite()
        self.assert_validator_passes(v, "bg_black_tile")
        self.assert_validator_fails(v, "nonexistent_sprite")
        self.assert_valid_entries(v, [(name, name) for name in SPRITES], text=None)

    def test_maybe_sprite_validator(self):
        v = MaybeSprite()
        self.assert_validator_passes(v, "None")
        self.assert_validator_passes(v, "bg_black_tile")
        self.assert_validator_fails(v, "nonexistent_sprite")
        self.assert_valid_entries(v, [(name, name) for name in SPRITES.keys()] + [(None, "None")], text=None)

    # --- phase music (uses db.music_keys defaults) ---

    def test_phase_music_validator(self):
        v = PhaseMusic(db=self.db)
        self.assert_validator_passes(v, "player_phase")
        self.assert_validator_passes(v, "enemy_phase")
        self.assert_validator_fails(v, "nonexistent_phase")
        self.assert_valid_entries(v, [(None, o) for o in v.valid], text=None)

    # --- point list (validate takes a list, not a string) ---

    def test_point_list_validator(self):
        v = PointList()
        self.assertTrue(v.validate([(1.0, 1.0), (3.5, 3.0)], None))
        self.assertIsNone(v.validate("not_a_list", None))


if __name__ == '__main__':
    unittest.main()
