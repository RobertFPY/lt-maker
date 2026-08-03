import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.utilities import user_data


class UserDataPathTests(unittest.TestCase):
    def test_desktop_uses_repository_saves_directory(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(Path("saves"), user_data.save_dir())
            self.assertEqual(
                Path("saves") / "config.ini",
                user_data.save_path("config.ini"),
            )

    def test_android_override_uses_persistent_user_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch.dict(
                os.environ,
                {"LT_USER_DATA_DIR": temporary_dir},
                clear=True,
            ):
                expected = Path(temporary_dir) / "saves"
                self.assertEqual(expected, user_data.save_dir())
                self.assertEqual(
                    expected / "slot.p",
                    user_data.save_path("slot.p"),
                )

                user_data.ensure_save_dir()

                self.assertTrue(expected.is_dir())

    def test_save_path_rejects_paths_that_escape_player_data(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch.dict(
                os.environ,
                {"LT_USER_DATA_DIR": temporary_dir},
                clear=True,
            ):
                with self.assertRaisesRegex(ValueError, "save directory"):
                    user_data.save_path("..", "outside.p")
                with self.assertRaisesRegex(ValueError, "save directory"):
                    user_data.save_path(str(Path(temporary_dir).parent / "outside.p"))

    def test_engine_config_reads_options_from_android_override(self):
        from app.engine import config

        with tempfile.TemporaryDirectory() as temporary_dir:
            save_directory = Path(temporary_dir) / "saves"
            save_directory.mkdir()
            (save_directory / "config.ini").write_text(
                "music_volume=0.17\ntext_speed=15\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"LT_USER_DATA_DIR": temporary_dir},
                clear=True,
            ):
                fake_pygame = SimpleNamespace(
                    K_x=1,
                    K_z=2,
                    K_c=3,
                    K_a=4,
                    K_s=5,
                    K_SPACE=6,
                    K_LEFT=7,
                    K_RIGHT=8,
                    K_UP=9,
                    K_DOWN=10,
                )
                with patch.dict(sys.modules, {"pygame": fake_pygame}):
                    settings = config.read_config_file()

            self.assertEqual(0.17, settings["music_volume"])
            self.assertEqual(15, settings["text_speed"])

    def test_save_achievement_and_record_locations_follow_override(self):
        from app.engine import achievements, persistent_records, save

        with tempfile.TemporaryDirectory() as temporary_dir:
            with patch.dict(
                os.environ,
                {"LT_USER_DATA_DIR": temporary_dir},
                clear=True,
            ):
                expected = Path(temporary_dir) / "saves"
                self.assertEqual(
                    expected / "slot.p",
                    Path(save._save_location("slot.p")),
                )
                self.assertEqual(
                    expected / "golden-achievements.p",
                    achievements._achievement_location("golden"),
                )
                self.assertEqual(
                    expected / "golden-persistent_records.p",
                    persistent_records._persistent_records_location("golden"),
                )


if __name__ == "__main__":
    unittest.main()
