import unittest
from unittest.mock import patch

from app.utilities import file_utils


class AndroidStartfileTests(unittest.TestCase):
    @patch("app.utilities.file_utils.subprocess.call")
    def test_android_does_not_invoke_desktop_opener(self, subprocess_call):
        with patch.dict("os.environ", {"ANDROID_ARGUMENT": "/data/user/0/test"}, clear=False):
            self.assertFalse(file_utils.startfile("saves/debug.log"))

        subprocess_call.assert_not_called()
