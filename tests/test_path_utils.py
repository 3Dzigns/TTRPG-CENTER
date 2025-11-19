import os
import tempfile
from pathlib import Path
from unittest import TestCase

from ingestion import path_utils


class PathUtilsTest(TestCase):
    def setUp(self) -> None:
        self._original_value = os.environ.get(path_utils.ENV_TRANSFER_ROOT)

    def tearDown(self) -> None:
        if self._original_value is None:
            os.environ.pop(path_utils.ENV_TRANSFER_ROOT, None)
        else:
            os.environ[path_utils.ENV_TRANSFER_ROOT] = self._original_value

    def test_env_override_controls_transfer_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            override = Path(tmpdir) / "station"
            os.environ[path_utils.ENV_TRANSFER_ROOT] = str(override)

            root = path_utils.get_transfer_root()
            self.assertEqual(root, override)

            subpath = path_utils.resolve_transfer_path("Gate_0_Out")
            self.assertEqual(subpath, override / "Gate_0_Out")
