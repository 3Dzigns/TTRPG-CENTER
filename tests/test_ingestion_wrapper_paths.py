import os
import tempfile
from pathlib import Path
from unittest import TestCase

from ingestion import ingestion_wrapper
from ingestion.path_utils import ENV_TRANSFER_ROOT


class IngestionWrapperPathTest(TestCase):
    def setUp(self) -> None:
        self._orig_root = ingestion_wrapper.TRANSFER_ROOT
        self._orig_env = os.environ.get(ENV_TRANSFER_ROOT)

    def tearDown(self) -> None:
        ingestion_wrapper._refresh_paths(self._orig_root)
        if self._orig_env is None:
            os.environ.pop(ENV_TRANSFER_ROOT, None)
        else:
            os.environ[ENV_TRANSFER_ROOT] = self._orig_env

    def test_refresh_paths_updates_globals_and_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            new_root = Path(tmpdir)
            ingestion_wrapper._refresh_paths(new_root)
            os.environ[ENV_TRANSFER_ROOT] = str(new_root)

            self.assertEqual(ingestion_wrapper.TRANSFER_ROOT, new_root)
            self.assertEqual(ingestion_wrapper.GATE_0_OUT, new_root / "Gate_0_Out")
            self.assertEqual(ingestion_wrapper.PASS_A_OUT, new_root / "Pass_A_Out")
