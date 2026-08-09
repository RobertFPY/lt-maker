from types import SimpleNamespace
import importlib
import os
import pickle
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
import pygame

if pygame.display.get_surface() is None:
    pygame.display.set_mode((1, 1))

from app.engine import bmpfont, fonts, game_board, general_states, save
from app.engine.objects.overworld import overworld as overworld_module


class IncrementalGameBoardTests(unittest.TestCase):
    def test_board_builder_yields_inside_large_movement_grids(self):
        tilemap = SimpleNamespace(width=20, height=20)
        terrain = SimpleNamespace(mtype='plain', opaque=False)
        terrain_catalog = MagicMock()
        terrain_catalog.get.return_value = terrain
        terrain_catalog.__getitem__.return_value = terrain
        fake_db = SimpleNamespace(
            terrain=terrain_catalog,
            mcost=SimpleNamespace(
                unit_types=('foot', 'horse'),
                get_mcost=lambda _mode, _mtype: 1,
            ),
            teams=(SimpleNamespace(nid='player'), SimpleNamespace(nid='enemy')),
        )

        with patch.object(game_board, 'DB', fake_db), \
                patch.object(game_board.game, 'get_terrain_nid', return_value='grass'):
            builder = game_board.GameBoard.build_iter(tilemap, batch_size=32)
            phases = []
            while True:
                try:
                    phases.append(next(builder))
                except StopIteration as completed:
                    board = completed.value
                    break

        self.assertGreaterEqual(phases.count('movement'), 24)
        self.assertEqual(400, len(board.mcost_grids['foot'].cells()))
        self.assertEqual(400, len(board.mcost_grids['horse'].cells()))
        self.assertEqual(400, len(board.unit_grid.cells()))
        self.assertEqual(400, len(board.opacity_grid.cells()))


class OverworldRestoreOptimizationTests(unittest.TestCase):
    def test_restore_does_not_build_prefab_tilemap_before_restoring_saved_tilemap(self):
        prefab = SimpleNamespace(nid='world')
        restored_tilemap = object()
        blank_overworld = overworld_module.OverworldObject()
        blank_overworld.prefab = prefab
        game = SimpleNamespace(parties={}, unit_registry={})
        payload = {
            'prefab_nid': 'world', 'tilemap': {'nid': 'saved'},
            'enabled_nodes': [], 'enabled_roads': [],
            'overworld_entities': [], 'selected_party_nid': None,
        }

        with patch.object(overworld_module.DB.overworlds, 'get', return_value=prefab), \
                patch.object(overworld_module.OverworldObject, 'from_prefab',
                             return_value=blank_overworld) as from_prefab, \
                patch.object(overworld_module.TileMapObject, 'restore',
                             return_value=restored_tilemap):
            restored = overworld_module.OverworldObject.restore(payload, game)

        from_prefab.assert_called_once_with(
            prefab, game.parties, game.unit_registry, build_tilemap=False)
        self.assertIs(restored_tilemap, restored.tilemap)


class LevelAssetLoadingTests(unittest.TestCase):
    def test_loading_delegates_audio_preload_without_exposing_game_to_worker(self):
        controller = MagicMock()
        worker = MagicMock()
        controller.prepare_level_songs.return_value = worker

        state = general_states.LoadingState()
        fake_game = SimpleNamespace(level=None, level_nid='chapter')
        with patch.object(general_states, 'game', fake_game), \
                patch.object(general_states, 'get_sound_thread',
                             return_value=controller):
            state.start()

        controller.clear.assert_called_once_with()
        controller.prepare_level_songs.assert_called_once_with(set())
        self.assertEqual([worker], state.loading_threads)


class FontLoadingOptimizationTests(unittest.TestCase):
    def test_color_variant_shares_surfaces_but_keeps_independent_defaults(self):
        base = bmpfont.BmpFont.__new__(bmpfont.BmpFont)
        base.surfaces = {"white": object(), "blue": object()}
        base.default_color = "white"
        base.memory = {"white": {"cached": (object(), 1)}}

        blue = base.color_variant("blue")

        self.assertIsNot(base, blue)
        self.assertIs(base.surfaces, blue.surfaces)
        self.assertEqual("white", base.default_color)
        self.assertEqual("blue", blue.default_color)
        self.assertEqual({}, blue.memory)
        self.assertIsNot(base.memory, blue.memory)
        self.assertIs(blue.surfaces["blue"], blue.get_base_surf())

        with self.assertRaisesRegex(ValueError, "Unknown font color"):
            base.color_variant("missing")

    def test_load_fonts_constructs_each_font_once(self):
        text = SimpleNamespace(
            nid="text",
            palettes={"white": [], "blue": [], "red": []},
        )
        old_fonts = fonts.RESOURCES.fonts
        constructed = []

        class FakeBmpFont:
            def __init__(self, font, headless=False):
                self.font = font
                self.headless = headless
                self.default_color = "white"
                self.surfaces = object()
                constructed.append(self)

            def color_variant(self, default_color):
                variant = SimpleNamespace(
                    default_color=default_color,
                    surfaces=self.surfaces,
                )
                return variant

        try:
            fonts.RESOURCES.fonts = {"text": text}
            with patch.object(fonts.bmpfont, "BmpFont", FakeBmpFont):
                fonts.load_fonts(headless=True)

            self.assertEqual(1, len(constructed))
            base = fonts.FONT["text"]
            self.assertIs(base, constructed[0])
            for color in text.palettes:
                alias = fonts.FONT[f"text-{color}"]
                self.assertEqual(color, alias.default_color)
                self.assertIs(base.surfaces, alias.surfaces)
        finally:
            fonts.RESOURCES.fonts = old_fonts
            fonts.FONT.clear()


class SpriteLoadingOptimizationTests(unittest.TestCase):
    def test_android_import_does_not_decode_sprites_before_runtime_setup(self):
        from app.engine import sprites

        old_loaded = sprites._images_loaded
        try:
            with patch.dict(
                sprites.os.environ,
                {"ANDROID_ARGUMENT": "org.example.game"},
            ), patch.object(sprites.engine, "image_load") as decode:
                importlib.reload(sprites)
                decode.assert_not_called()
        finally:
            sprites._images_loaded = old_loaded

    def test_desktop_import_decodes_sprites_for_early_module_attributes(self):
        from app.engine import sprites

        old_loaded = sprites._images_loaded
        old_images = [
            (sprite, sprite.image)
            for sprite in sprites.SPRITES.values()
            if sprite.full_path
        ]
        try:
            with patch.dict(
                sprites.os.environ,
                {"ANDROID_ARGUMENT": ""},
            ), patch.object(
                sprites.engine,
                "image_load",
                return_value=object(),
            ) as decode:
                importlib.reload(sprites)
                self.assertGreater(decode.call_count, 0)
        finally:
            for sprite, image in old_images:
                sprite.image = image
            sprites._images_loaded = old_loaded

    def test_resource_reset_decodes_desktop_sprites_before_components(self):
        from app.data.resources import resources
        from app.engine import sprites

        with patch.dict(
            resources.os.environ,
            {"ANDROID_ARGUMENT": ""},
        ), patch.object(sprites, "load_images") as load_images:
            resources._decode_desktop_sprites_before_component_imports()

        load_images.assert_called_once_with(force=True)

    def test_resource_reset_keeps_android_sprite_decode_deferred(self):
        from app.data.resources import resources
        from app.engine import sprites

        with patch.dict(
            resources.os.environ,
            {"ANDROID_ARGUMENT": "org.example.game"},
        ), patch.object(sprites, "load_images") as load_images:
            resources._decode_desktop_sprites_before_component_imports()

        load_images.assert_not_called()

    def test_sprite_decode_is_idempotent_and_detects_resource_reset(self):
        from app.engine import sprites

        old_sprites = sprites.SPRITES
        old_loaded = sprites._images_loaded
        first = SimpleNamespace(full_path="first.png", image=None)
        replacement = SimpleNamespace(full_path="replacement.png", image=None)
        decoded = []

        def decode(path):
            decoded.append(path)
            return f"decoded:{path}"

        try:
            sprites.SPRITES = {"first": first}
            sprites._images_loaded = False
            with patch.object(sprites.engine, "image_load", side_effect=decode):
                sprites.load_images()
                sprites.load_images()
                self.assertEqual(["first.png"], decoded)

                # Mirrors app.sprites.reset(): new sprite objects, same module.
                sprites.SPRITES = {"replacement": replacement}
                sprites.load_images()
                self.assertEqual(
                    ["first.png", "replacement.png"],
                    decoded,
                )

                sprites.load_images(force=True)
                self.assertEqual(
                    ["first.png", "replacement.png", "replacement.png"],
                    decoded,
                )
        finally:
            sprites.SPRITES = old_sprites
            sprites._images_loaded = old_loaded

    def test_loaded_sprites_are_converted_once_for_the_active_display_format(self):
        from app.engine import sprites

        old_sprites = sprites.SPRITES
        old_loaded = sprites._images_loaded
        old_format = sprites._optimized_display_format
        sprite = SimpleNamespace(full_path="sprite.png", image="decoded")
        try:
            sprites.SPRITES = {"sprite": sprite}
            sprites._images_loaded = True
            sprites._optimized_display_format = None
            with patch.object(
                sprites.engine, "display_format_signature", return_value=(32, (1, 2, 3, 4))
            ), patch.object(
                sprites.engine, "convert_for_display", side_effect=lambda image: f"display:{image}"
            ) as convert:
                sprites.load_images(optimize_for_display=True)
                sprites.load_images(optimize_for_display=True)

            self.assertEqual("display:decoded", sprite.image)
            convert.assert_called_once_with("decoded")
        finally:
            sprites.SPRITES = old_sprites
            sprites._images_loaded = old_loaded
            sprites._optimized_display_format = old_format

    def test_display_optimization_does_not_assign_to_special_sprite(self):
        from app.engine import sprites

        class ReadOnlySprite:
            full_path = None

            @property
            def image(self):
                return "generated"

        old_sprites = sprites.SPRITES
        sprite = ReadOnlySprite()
        try:
            sprites.SPRITES = {"generated": sprite}
            with patch.object(sprites.engine, "convert_for_display") as convert:
                sprites._optimize_loaded_images((32, (1, 2, 3, 4)))
            convert.assert_not_called()
            self.assertEqual("generated", sprite.image)
        finally:
            sprites.SPRITES = old_sprites

    def test_particles_resolve_sprites_when_reset_after_early_import(self):
        from app.engine import particles

        decoded_surface = object()

        def subsurface(surface, rect):
            return surface, rect

        with patch.object(
            particles.SPRITES,
            "get",
            return_value=decoded_surface,
        ), patch.object(
            particles.engine,
            "subsurface",
            side_effect=subsurface,
        ):
            raindrop = particles.Raindrop().reset((1, 2))
            smoke = particles.Smoke().reset((3, 4))
            fire = particles.Fire().reset((5, 6))
            snow = particles.Snow().reset((7, 8))

        self.assertIs(decoded_surface, raindrop.sprite)
        self.assertEqual((decoded_surface, (3, 0, 3, 4)), smoke.bottom_sprite)
        self.assertEqual((decoded_surface, (0, 0, 3, 4)), smoke.top_sprite)
        self.assertEqual(6, len(fire.sprites))
        self.assertIs(decoded_surface, fire.sprites[0][0])
        self.assertIs(decoded_surface, snow.sprite[0])

    def test_map_health_bar_resolves_sprites_at_draw_time(self):
        from app.engine import health_bar

        outline_surface = object()
        bar_surface = object()
        cropped_bar = object()
        target_surface = SimpleNamespace(blit=Mock())
        map_health_bar = health_bar.MapHealthBar.__new__(health_bar.MapHealthBar)
        map_health_bar.unit = SimpleNamespace(get_max_hp=lambda: 20)
        map_health_bar.displayed_val = 10

        def get_sprite(nid, fallback="bg_black_tile"):
            return {
                "map_health_outline": outline_surface,
                "map_health_bar": bar_surface,
            }[nid]

        with patch.object(
            health_bar.SPRITES,
            "get",
            side_effect=get_sprite,
        ) as get, patch.object(
            health_bar.engine,
            "subsurface",
            return_value=cropped_bar,
        ) as subsurface:
            result = map_health_bar.draw(target_surface, 4, 8)

        self.assertIs(target_surface, result)
        get.assert_any_call("map_health_outline")
        get.assert_any_call("map_health_bar")
        subsurface.assert_called_once_with(bar_surface, (0, 0, 7, 1))
        target_surface.blit.assert_any_call(outline_surface, (4, 21))
        target_surface.blit.assert_any_call(cropped_bar, (5, 22))

    def test_help_dialog_resolves_logo_at_draw_time(self):
        # Establish the normal engine import order before loading help_menu.
        from app.engine import health_bar  # noqa: F401
        from app.engine import help_menu

        decoded_logo = object()
        help_surface = object()
        dialog_surface = SimpleNamespace(blit=Mock())
        target_surface = SimpleNamespace(blit=Mock())
        help_dialog = help_menu.HelpDialog.__new__(help_menu.HelpDialog)
        help_dialog.h_surf = object()
        help_dialog.transition_in = False
        help_dialog.transition_out = 0

        with patch.object(
            help_menu.SPRITES,
            "get",
            return_value=decoded_logo,
        ) as get, patch.object(
            help_menu.engine,
            "copy_surface",
            return_value=dialog_surface,
        ):
            result = help_dialog.final_draw(
                target_surface,
                (12, 16),
                100,
                help_surface,
            )

        self.assertIs(target_surface, result)
        get.assert_called_once_with("help_logo")
        dialog_surface.blit.assert_any_call(help_surface, (0, 3))
        dialog_surface.blit.assert_any_call(decoded_logo, (9, 0))
        target_surface.blit.assert_called_once_with(dialog_surface, (12, 16))

    def test_pennant_resolves_background_at_draw_time(self):
        from app.engine import health_bar  # noqa: F401
        from app.engine import banner

        background = object()
        target_surface = SimpleNamespace(blit=Mock())
        pennant = banner.Pennant.__new__(banner.Pennant)
        pennant.sprite_offset = 4
        pennant.text_counter = 0
        pennant.width = 0
        pennant.height = 16
        pennant.last_update = 0
        pennant.text_width = 1
        pennant.text = ''

        with patch.object(
            banner.SPRITES,
            "get",
            return_value=background,
        ) as get, patch.object(
            banner.engine,
            "get_time",
            return_value=0,
        ):
            pennant.draw(target_surface)

        get.assert_called_once_with("pennant_bg")
        target_surface.blit.assert_called_once_with(
            background,
            (0, banner.WINHEIGHT - 16),
        )


class LegacySaveMetadataTests(unittest.TestCase):
    def test_null_realtime_remains_sortable(self):
        metadata = {
            "level_title": "Legacy",
            "playtime": 0,
            "realtime": None,
            "kind": "start",
        }
        with tempfile.TemporaryDirectory() as temporary_dir:
            metadata_path = f"{temporary_dir}/legacy.pmeta"
            with open(metadata_path, "wb") as metadata_file:
                pickle.dump(metadata, metadata_file)

            legacy = save.SaveSlot(metadata_path, 0)
            empty = save.SaveSlot(f"{temporary_dir}/empty.pmeta", 1)

        self.assertEqual(0, legacy.realtime)
        self.assertIs(legacy, max([legacy, empty], key=lambda slot: slot.realtime))


if __name__ == "__main__":
    unittest.main()
