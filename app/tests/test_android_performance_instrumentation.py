from pathlib import Path
import unittest


class AndroidPerformanceInstrumentationTests(unittest.TestCase):
    def test_map_profile_breaks_down_all_unmeasured_overlay_layers(self):
        source = (Path(__file__).parents[1] / 'engine' / 'map_view.py').read_text(
            encoding='utf-8'
        )

        for section in (
            'map_auras', 'map_boundary', 'map_fog', 'map_highlight',
            'map_grid', 'map_anims', 'map_high_anims', 'map_foreground',
            'map_region_text', 'map_cursor', 'map_weather',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % section, source)

    def test_combat_profile_breaks_down_final_surface_composition(self):
        source = (
            Path(__file__).parents[1] / 'engine' / 'combat' / 'animation_combat.py'
        ).read_text(encoding='utf-8')

        for section in (
            'combat_final_compose', 'combat_bars', 'combat_guard_gauges',
            'combat_names', 'combat_ui_cache_build', 'combat_ui_tint_build',
            'combat_ui_blit', 'combat_ui_arrows', 'combat_foreground', 'combat_fade',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % section, source)

    def test_combat_profile_breaks_down_battle_frame_work_without_frame_cache(self):
        root = Path(__file__).parents[1] / 'engine'
        combat_source = (root / 'combat' / 'animation_combat.py').read_text(encoding='utf-8')
        battle_source = (root / 'battle_animation.py').read_text(encoding='utf-8')

        for section in (
            'combat_battle_under', 'combat_battle_first',
            'combat_battle_second', 'combat_battle_over',
        ):
            self.assertIn("RUNTIME_PROFILER.section('%s')" % section, combat_source)
        self.assertIn("RUNTIME_PROFILER.section('combat_frame_fetch')", battle_source)
        self.assertIn("RUNTIME_PROFILER.count('combat_frame_surface')", battle_source)
        self.assertNotIn('PERF combat-frame-surface', battle_source)
        self.assertNotIn('_android_frame_cache', battle_source)


if __name__ == '__main__':
    unittest.main()
