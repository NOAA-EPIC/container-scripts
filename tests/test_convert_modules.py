import importlib.util
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch


MODULE_PATH = Path(__file__).resolve().parents[1] / "convert-modules.py"
SPEC = importlib.util.spec_from_file_location("convert_modules", MODULE_PATH)
convert_modules = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(convert_modules)


class GetBindDirsTests(TestCase):
    def test_returns_both_logical_and_real_roots_for_symlinked_paths(self):
        with patch.object(convert_modules.os.path, "realpath", return_value="/work5/project/modulefiles"):
            bind_dirs = convert_modules.get_bind_dirs("/work/project/modulefiles")

        self.assertEqual(bind_dirs, ["/work", "/work5"])

    def test_deduplicates_when_real_and_logical_paths_match(self):
        with patch.object(convert_modules.os.path, "realpath", return_value="/work/project/modulefiles"):
            bind_dirs = convert_modules.get_bind_dirs("/work/project/modulefiles")

        self.assertEqual(bind_dirs, ["/work"])
