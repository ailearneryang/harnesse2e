import os
import sys
import unittest
from unittest import mock


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.join(ROOT, "engine")
if ENGINE_DIR not in sys.path:
    sys.path.insert(0, ENGINE_DIR)

import copilot_shim  # noqa: E402


class ResolveCopilotBinTests(unittest.TestCase):
    def test_prefers_explicit_env_path_when_executable(self):
        with mock.patch.dict(os.environ, {"COPILOT_CLI_PATH": "/tmp/copilot-custom"}, clear=False), \
             mock.patch("copilot_shim.os.path.isfile", side_effect=lambda path: path == "/tmp/copilot-custom"), \
             mock.patch("copilot_shim.os.access", side_effect=lambda path, mode: path == "/tmp/copilot-custom"), \
             mock.patch("copilot_shim.shutil.which", return_value="/usr/bin/copilot"):
            self.assertEqual(copilot_shim.resolve_copilot_bin(), "/tmp/copilot-custom")

    def test_falls_back_to_path_lookup(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch("copilot_shim.shutil.which", return_value="/Users/xing/.nvm/bin/copilot"):
            self.assertEqual(copilot_shim.resolve_copilot_bin(), "/Users/xing/.nvm/bin/copilot")

    def test_uses_known_location_when_path_lookup_missing(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
             mock.patch("copilot_shim.shutil.which", return_value=None), \
             mock.patch("copilot_shim.os.path.isfile", side_effect=lambda path: path == "/usr/local/bin/copilot"), \
             mock.patch("copilot_shim.os.access", side_effect=lambda path, mode: path == "/usr/local/bin/copilot"):
            self.assertEqual(copilot_shim.resolve_copilot_bin(), "/usr/local/bin/copilot")


if __name__ == "__main__":
    unittest.main()