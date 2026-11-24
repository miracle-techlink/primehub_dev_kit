import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from pack import pack


class PackTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.skill = self.root / "demo"
        self.output = self.root / "demo.rpk"
        for relative, content in (
            ("cfg/pkg.yaml", "package_name: demo"),
            ("src/main.py", "print('demo')"),
            ("src/helpers.py", "# helpers"),
            ("readme.md", "# Demo"),
            ("media/audio/clip.mp3", "fixture"),
        ):
            path = self.skill / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_archive_has_runtime_entrypoint_and_optional_files(self):
        self.output.write_bytes(b"previous package")
        self.assertEqual(pack(self.skill, self.root), self.output)
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(
                set(archive.namelist()),
                {
                    "cfg/pkg.yaml",
                    "src/main.py",
                    "src/helpers.py",
                    "readme.md",
                    "media/audio/clip.mp3",
                },
            )
            self.assertEqual(archive.read("src/main.py"), b"print('demo')")

    def test_cli_requires_entrypoint_even_with_optimized_python(self):
        (self.skill / "src/main.py").unlink()
        self.output.write_bytes(b"previous package")
        script = Path(__file__).resolve().parents[1] / "pack.py"
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-O", str(script), str(self.skill), str(self.root)],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("src/main.py", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"previous package")

    def test_write_failure_keeps_existing_package_and_cleans_temp_file(self):
        self.output.write_bytes(b"previous package")
        write = zipfile.ZipFile.write

        def fail_on_main(archive, path, arcname):
            if arcname == "src/main.py":
                raise OSError("simulated write failure")
            return write(archive, path, arcname)

        with patch.object(zipfile.ZipFile, "write", fail_on_main):
            with self.assertRaisesRegex(OSError, "simulated"):
                pack(self.skill, self.root)

        self.assertEqual(self.output.read_bytes(), b"previous package")
        self.assertEqual(set(self.root.iterdir()), {self.skill, self.output})
