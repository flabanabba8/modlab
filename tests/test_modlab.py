import importlib.util
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('modlab_core', Path(__file__).parents[1] / 'core.py')
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)

class ModLabTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir='/tmp')
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        self.game.mkdir()
        (self.game / 'data.txt').write_text('original')
        self.lab = core.Lab(self.root / 'labs')
        self.created = self.lab.create(str(self.game))
        self.id = self.created['lab_id']
        self.zip = self.root / 'mod.zip'
        self.make_zip({'data.txt': 'modified', 'new/file.txt': 'new'})

    def tearDown(self):
        self.tmp.cleanup()

    def make_zip(self, entries):
        with zipfile.ZipFile(self.zip, 'w') as z:
            for name, content in entries.items():
                z.writestr(name, content)

    def test_apply_and_rollback_preserve_both_and_original(self):
        plan = self.lab.inspect(self.id, str(self.zip))
        self.assertEqual(plan['replacements'], ['data.txt'])
        with self.assertRaisesRegex(ValueError, 'explicit'):
            self.lab.apply(self.id, str(self.zip), plan['inspection'])
        applied = self.lab.apply(self.id, str(self.zip), plan['inspection'], True)
        self.assertEqual((Path(applied['game_path']) / 'data.txt').read_text(), 'modified')
        self.assertEqual((self.game / 'data.txt').read_text(), 'original')
        rolled = self.lab.rollback(self.id)
        self.assertEqual((Path(rolled['game_path']) / 'data.txt').read_text(), 'original')
        self.assertEqual((Path(applied['game_path']) / 'data.txt').read_text(), 'modified')
        restored = self.lab.select_preserved(self.id, rolled['preserved_revision'])
        self.assertEqual((Path(restored['game_path']) / 'data.txt').read_text(), 'modified')
        with self.assertRaisesRegex(ValueError, 'not a recorded'):
            self.lab.select_preserved(self.id, rolled['preserved_revision'])

    def test_isolated_executable_fixture_across_revisions(self):
        (self.game / 'run.py').write_text('from pathlib import Path\nprint(Path("data.txt").read_text())\n')
        lab = self.lab.create(str(self.game))
        def launch(directory):
            return subprocess.check_output([sys.executable, '-I', 'run.py'], cwd=directory, env={'PATH': os.defpath}, timeout=5, text=True).strip()
        self.assertEqual(launch(lab['game_path']), 'original')
        plan = self.lab.inspect(lab['lab_id'], str(self.zip))
        changed = self.lab.apply(lab['lab_id'], str(self.zip), plan['inspection'], True)
        self.assertEqual(launch(changed['game_path']), 'modified')
        restored = self.lab.rollback(lab['lab_id'])
        self.assertEqual(launch(restored['game_path']), 'original')
        self.assertEqual(launch(str(self.game)), 'original')

    def test_stale_inspection(self):
        plan = self.lab.inspect(self.id, str(self.zip))
        (Path(self.created['game_path']) / 'data.txt').write_text('external change')
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.lab.apply(self.id, str(self.zip), plan['inspection'], True)
        plan = self.lab.inspect(self.id, str(self.zip))
        self.make_zip({'else.txt': 'changed'})
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.lab.apply(self.id, str(self.zip), plan['inspection'], True)

    def test_unsafe_archives(self):
        for name in ('../escape', '/absolute', 'C:/absolute', 'foo\\bar'):
            with self.subTest(name=name):
                self.make_zip({name: 'bad'})
                with self.assertRaises(ValueError):
                    self.lab.inspect(self.id, str(self.zip))
        self.make_zip({'Data.txt': 'bad'})
        with self.assertRaisesRegex(ValueError, 'case'):
            self.lab.inspect(self.id, str(self.zip))
        self.make_zip({'A': 'one', 'a': 'two'})
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.lab.inspect(self.id, str(self.zip))
        self.make_zip({'Folder/a': 'one', 'folder/b': 'two'})
        with self.assertRaisesRegex(ValueError, 'case'):
            self.lab.inspect(self.id, str(self.zip))
        self.make_zip({'a': 'one', 'a/b': 'two'})
        with self.assertRaisesRegex(ValueError, 'parent'):
            self.lab.inspect(self.id, str(self.zip))
        with zipfile.ZipFile(self.zip, 'w') as z:
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            z.writestr(info, 'target')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            self.lab.inspect(self.id, str(self.zip))

    def test_zip_parent_directory_case_collision(self):
        current = Path(self.created['game_path'])
        (current / 'Folder').mkdir()
        (current / 'Folder' / 'existing').write_text('x')
        self.make_zip({'folder/new': 'new'})
        with self.assertRaisesRegex(ValueError, 'case'):
            self.lab.inspect(self.id, str(self.zip))

    def test_empty_directory_change_invalidates_and_case_collision_rejected(self):
        current = Path(self.created['game_path'])
        plan = self.lab.inspect(self.id, str(self.zip))
        (current / 'Empty').mkdir()
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.lab.apply(self.id, str(self.zip), plan['inspection'], True)
        self.make_zip({'empty/file': 'new'})
        with self.assertRaisesRegex(ValueError, 'case'):
            self.lab.inspect(self.id, str(self.zip))

    def test_copy_does_not_follow_final_symlink(self):
        target = self.root / 'target'
        target.write_text('private fixture')
        link = self.root / 'link'
        link.symlink_to(target)
        with self.assertRaises(OSError):
            core.copy_regular(link, self.root / 'copied')
        self.assertFalse((self.root / 'copied').exists())

    def test_private_and_git_directories_not_copied(self):
        for name in ('.codex', '.git'):
            directory = self.game/name
            directory.mkdir()
            with self.assertRaisesRegex(ValueError, 'private configuration or Git'):
                self.lab.create(str(self.game))
            directory.rmdir()

    def test_symlink_in_source_rejected(self):
        (self.game / 'link').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'Symlinks'):
            self.lab.create(str(self.game))

if __name__ == '__main__':
    unittest.main()
