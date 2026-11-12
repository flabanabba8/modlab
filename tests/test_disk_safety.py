"""ModLab must never fill a disk: bounded copies, pruned revisions, safe cleanup, a small release."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
import zipfile
from collections import namedtuple
from pathlib import Path
from unittest import mock

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('modlab_disk_fixture', root / '__init__.py', submodule_search_locations=[str(root)])
package = importlib.util.module_from_spec(spec); sys.modules[spec.name] = package; spec.loader.exec_module(package)
core = sys.modules['modlab_disk_fixture.core']
Usage = namedtuple('Usage', 'total used free')
GIB = 1024**3
MB = 1024**2


def game(base, files=3, size=200_000):
    g = Path(base) / 'game'; g.mkdir()
    for i in range(files):
        (g / ('f%d.bin' % i)).write_bytes(os.urandom(size))
    return g


def mod_zip(base, name='mod.zip', body=b'new'):
    z = Path(base) / name
    with zipfile.ZipFile(z, 'w') as f:
        f.writestr('added.txt', body)
    return z


def apply_one(lab, lab_id, zip_path):
    plan = lab.inspect(lab_id, str(zip_path))
    return lab.apply(lab_id, str(zip_path), plan['inspection'], allow_replacements=True)


class Guard(unittest.TestCase):
    def test_copy_stops_before_free_space_falls_below_the_reserve_and_leaves_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d); data = Path(d) / 'data'
            lab = core.Lab(data, core.Limits(min_free=5 * GIB))
            with mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(100 * GIB, 96 * GIB, 4 * GIB)):
                with self.assertRaisesRegex(core.DiskGuard, 'Stopped before the disk filled up'):
                    lab.create(str(g))
            self.assertEqual([p for p in data.iterdir() if core.is_lab_id(p.name)], [])      # no half-made lab

    def test_a_copy_that_would_pass_the_total_cap_is_refused_and_cleaned_up(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d, files=4, size=300_000); data = Path(d) / 'data'
            lab = core.Lab(data, core.Limits(max_total=500_000, min_free=1))
            with mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(1000 * GIB, 1 * GIB, 999 * GIB)):
                with self.assertRaisesRegex(core.DiskGuard, 'size limit'):
                    lab.create(str(g))
            self.assertEqual([p for p in data.iterdir() if core.is_lab_id(p.name)], [])

    def test_a_game_bigger_than_the_whole_limit_is_refused_before_copying_a_byte(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d, files=2, size=400_000)
            lab = core.Lab(Path(d) / 'data', core.Limits(max_total=100_000, min_free=1))
            with mock.patch.object(core, 'copy_regular', side_effect=AssertionError('copied')):
                with self.assertRaisesRegex(core.DiskGuard, 'larger than ModLab'):
                    lab.create(str(g))

    def test_a_normal_copy_works_and_reports_what_it_used(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d); lab = core.Lab(Path(d) / 'data', core.Limits(min_free=1))
            with mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(1000 * GIB, 1 * GIB, 999 * GIB)):
                r = lab.create(str(g))
            self.assertIn('disk_used_by_this_copy', r); self.assertIn('modlab_cleanup', r['disk_note'])
            self.assertEqual(sorted(p.name for p in g.iterdir()), ['f0.bin', 'f1.bin', 'f2.bin'])      # the original is untouched

    def test_a_file_is_cloned_when_the_filesystem_can_and_charged_when_it_cannot(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / 'a.bin'; src.write_bytes(b'x' * 1000)
            charged = []
            class B:
                def charge(self, n): charged.append(n)
            core.copy_regular(src, Path(d) / 'b.bin', B())
            self.assertEqual((Path(d) / 'b.bin').read_bytes(), b'x' * 1000)
            self.assertIn(charged, ([], [1000]))                     # 0 if this filesystem clones, else exactly the file size
            with mock.patch.dict(sys.modules, {'fcntl': mock.Mock(ioctl=mock.Mock(side_effect=OSError))}):
                charged.clear(); core.copy_regular(src, Path(d) / 'c.bin', B())
            self.assertEqual(charged, [1000])


class Revisions(unittest.TestCase):
    def test_only_the_last_revisions_are_kept_so_disk_use_stays_flat(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d); data = Path(d) / 'data'
            lab = core.Lab(data, core.Limits(min_free=1, keep=2))
            with mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(1000 * GIB, 1 * GIB, 999 * GIB)):
                made = lab.create(str(g)); sizes = []
                for i in range(5):
                    r = apply_one(lab, made['lab_id'], mod_zip(d, 'm%d.zip' % i, ('v%d' % i).encode()))
                    sizes.append(core.dir_bytes(data / made['lab_id']))
                    revs = [p for p in (data / made['lab_id']).iterdir() if p.is_dir()]
                    self.assertLessEqual(len(revs), 2)
            self.assertLessEqual(max(sizes), sizes[0] * 1.2)          # flat, not growing by a game copy each time
            self.assertEqual(r['old_revisions_deleted'], 1)

    def test_rollback_still_works_after_pruning_and_the_previous_revision_exists(self):
        with tempfile.TemporaryDirectory() as d:
            g = game(d); lab = core.Lab(Path(d) / 'data', core.Limits(min_free=1, keep=2))
            with mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(1000 * GIB, 1 * GIB, 999 * GIB)):
                made = lab.create(str(g))
                for i in range(3):
                    r = apply_one(lab, made['lab_id'], mod_zip(d, 'n%d.zip' % i, ('w%d' % i).encode()))
                back = lab.rollback(made['lab_id'])
            self.assertTrue(Path(back['game_path']).is_dir())

    def test_the_minimum_kept_is_two_even_if_asked_for_less(self):
        self.assertEqual(core.Limits(keep=1).keep, 2)


class Cleanup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.d = Path(self.tmp.name); self.addCleanup(self.tmp.cleanup)
        self.g = game(self.d); self.data = self.d / 'data'
        self.lab = core.Lab(self.data, core.Limits(min_free=1))
        self.patch = mock.patch.object(core.shutil, 'disk_usage', lambda p: Usage(1000 * GIB, 1 * GIB, 999 * GIB)); self.patch.start(); self.addCleanup(self.patch.stop)
        self.made = self.lab.create(str(self.g))

    def test_report_lists_sizes_free_space_and_limits_and_changes_nothing(self):
        r = self.lab.cleanup()
        self.assertEqual(r['labs'][0]['lab_id'], self.made['lab_id']); self.assertIn('disk_free', r); self.assertTrue(r['the_original_game_folders_are_never_touched'])
        self.assertTrue((self.data / self.made['lab_id']).is_dir())

    def test_deleting_is_a_dry_run_until_confirmed(self):
        dry = self.lab.cleanup('delete_lab', self.made['lab_id'])
        self.assertFalse(dry['deleted']); self.assertTrue((self.data / self.made['lab_id']).is_dir()); self.assertIn('Dry run', dry['next'])
        done = self.lab.cleanup('delete_lab', self.made['lab_id'], confirm=True)
        self.assertTrue(done['deleted']); self.assertFalse((self.data / self.made['lab_id']).exists())
        self.assertTrue(self.g.is_dir() and (self.g / 'f0.bin').exists())          # the original game is untouched

    def test_cleanup_cannot_be_pointed_outside_its_own_folder(self):
        outside = self.d / 'precious'; outside.mkdir(); (outside / 'x').write_text('keep')
        for bad in ('../precious', str(outside), 'a' * 32):
            with self.assertRaises(ValueError):
                self.lab.cleanup('delete_lab', bad, confirm=True)
        link = self.data / ('b' * 32); link.symlink_to(outside)
        with self.assertRaises(ValueError):
            self.lab.cleanup('delete_lab', 'b' * 32, confirm=True)
        self.assertEqual((outside / 'x').read_text(), 'keep')

    def test_unfinished_labs_from_a_crash_are_found_and_removed_only_when_old(self):
        stale = self.data / ('c' * 32); stale.mkdir(); (stale / 'junk.bin').write_bytes(b'x' * 5000)
        fresh = self.data / ('d' * 32); fresh.mkdir(); (fresh / 'junk.bin').write_bytes(b'x' * 5000)
        old = time.time() - 7200; os.utime(stale, (old, old))
        self.assertEqual([x['lab'] for x in self.lab.remove_leftovers()], ['c' * 32])
        self.assertFalse(stale.exists()); self.assertTrue(fresh.exists())          # a lab being made right now is left alone

    def test_toolkit_run_output_is_pruned_to_a_small_fixed_size(self):
        from modlab_disk_fixture import toolkit
        runs = self.data / 'toolkit-runs'; runs.mkdir()
        for i in range(30):
            r = runs / ('run-%02d' % i); r.mkdir(); (r / 'stdout.txt').write_bytes(b'x' * 1000); os.utime(r, (1000 + i, 1000 + i))
        toolkit.prune_runs(self.data)
        left = sorted(p.name for p in runs.iterdir())
        self.assertEqual(len(left), toolkit.MAX_RUN_FOLDERS); self.assertIn('run-29', left); self.assertNotIn('run-00', left)

    def test_limits_come_from_settings_with_safe_fallbacks(self):
        l = core.limits_from(lambda k: {'modlab_max_total_gb': '5', 'modlab_min_free_gb': 'oops', 'modlab_keep_revisions': '3'}.get(k))
        self.assertEqual((l.max_total, l.min_free, l.keep), (5 * GIB, core.DEFAULT_MIN_FREE, 3))
        self.assertEqual(core.limits_from(None).keep, core.DEFAULT_KEEP)


class Release(unittest.TestCase):
    def test_the_shipped_plugin_contains_no_big_files_or_lab_artifacts(self):
        biggest = []
        for p in root.rglob('*'):
            if p.is_file() and '__pycache__' not in p.parts and '.git' not in p.parts:
                biggest.append((p.stat().st_size, p.relative_to(root).as_posix()))
        biggest.sort(reverse=True)
        total = sum(s for s, _ in biggest)
        self.assertLess(total, 3 * MB, biggest[:3])
        for size, name in biggest:
            self.assertLess(size, 1 * MB, name)                               # no archives, labs, game files or recordings
            self.assertFalse(name.endswith(('.zip', '.7z', '.rar', '.pak', '.dll', '.exe', '.so', '.wav', '.mp4', '.webm')), name)
        self.assertFalse([n for _, n in biggest if core.is_lab_id(n.split('/')[0])])

    def test_the_tool_and_settings_for_disk_safety_are_declared(self):
        text = (root / 'plugin.yaml').read_text()
        for key in ('modlab_cleanup', 'modlab_max_total_gb', 'modlab_min_free_gb', 'modlab_keep_revisions'):
            self.assertIn(key, text)


if __name__ == '__main__':
    unittest.main()
