import contextlib
import io
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


caffe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "caffe"))


class UpdateTests(unittest.TestCase):
    def update(self, url, argv0):
        with (
            patch.dict(caffe["self_update"].__globals__, INSTALL_URL=url),
            patch("sys.argv", [argv0, "update"]),
        ):
            return caffe["self_update"]()

    def test_update_reinstalls_into_the_folder_caffe_runs_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            installer = Path(tmp, "install.sh")
            installer.write_text(f'echo "$CAFFE_BIN_DIR" > "{tmp}/ran"; exit 3\n')
            code = self.update(installer.as_uri(), f"{tmp}/bin/caffe")
            self.assertEqual(code, 3)  # the installer's exit code is passed on
            self.assertEqual(Path(tmp, "ran").read_text().strip(), f"{tmp}/bin")

    def test_failed_download_runs_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = self.update(Path(tmp, "missing.sh").as_uri(), f"{tmp}/caffe")
            self.assertEqual(code, 1)
            self.assertIn("couldn't download", err.getvalue())


if __name__ == "__main__":
    unittest.main()
