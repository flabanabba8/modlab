"""Maintainer review asks: the model cannot choose what runs; Hermes approves each toolkit call; subprocesses get a clean environment."""
import ast
import importlib.util
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('modlab_review_pkg', ROOT / '__init__.py', submodule_search_locations=[str(ROOT)])
pkg = importlib.util.module_from_spec(spec); sys.modules[spec.name] = pkg; spec.loader.exec_module(pkg)
toolkit = importlib.import_module('modlab_review_pkg.toolkit')


class Ctx:
    def __init__(self, cfg=None): self.cfg = cfg or {}; self.tools = {}; self.hooks = []
    def get_config(self, key, default=None): return self.cfg.get(key, default)
    def register_tool(self, name, toolset=None, schema=None, handler=None, **k): self.tools[name] = schema
    def register_skill(self, *a, **k): pass
    def register_hook(self, name, fn): self.hooks.append((name, fn))


class Schemas(unittest.TestCase):
    def test_no_tool_lets_the_model_name_a_program(self):
        ctx = Ctx(); pkg.register(ctx)
        for name, schema in ctx.tools.items():
            props = set(schema['parameters']['properties'])
            self.assertFalse({'um_executable', 'rea_executable', 'executable', 'command_argv'} & props, name)

    def test_the_programs_come_from_owner_settings_or_path(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'um'; exe.write_text('#!/bin/sh\necho "{}"\n'); exe.chmod(0o755)
            self.assertEqual(pkg.owner_settings(Ctx({'um_executable': str(exe)})), {'um_executable': str(exe)})
            self.assertEqual(toolkit.resources({'um_executable': str(exe)})['universal_modder']['executable'], str(exe))
            self.assertTrue(toolkit.resources({'um_executable': str(exe)})['universal_modder']['installed'])
            out = toolkit.run(d, 'universal-modder', ['--help'], settings={'um_executable': str(exe)})
            self.assertEqual(out['exit_code'], 0)


class Approval(unittest.TestCase):
    def test_every_toolkit_call_is_put_to_the_user(self):
        ctx = Ctx(); pkg.register(ctx)
        self.assertEqual([h[0] for h in ctx.hooks], ['pre_tool_call'])
        fn = ctx.hooks[0][1]
        call = {'toolkit': 'rea', 'arguments': ['inventory', '--json'], 'timeout_seconds': 30}
        from plugins.plugin_storage import plugin_data_dir
        res = importlib.import_module('modlab_review_pkg.resources')
        self.assertIsNone(fn('modlab_toolkit', call))  # interview not done: the tool answers with the interview, so nothing to approve
        path = res.profile_path(plugin_data_dir('modlab')); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({'answered': True}))
        ask = fn('modlab_toolkit', call)
        self.assertEqual(ask['action'], 'approve'); self.assertIn('inventory --json', ask['message']); self.assertIn('clean environment', ask['message'])
        self.assertIsNone(fn('modlab_inspect', {})); self.assertIsNone(fn('modlab_cleanup', {}))

    def test_the_manifest_declares_the_hook_and_the_settings(self):
        text = (ROOT / 'plugin.yaml').read_text()
        self.assertIn('provides_hooks', text); self.assertIn('um_executable', text); self.assertIn('rea_executable', text)


class CleanEnvironment(unittest.TestCase):
    def test_the_toolkit_child_does_not_see_provider_keys(self):
        os.environ['OPENAI_API_KEY'] = 'sk-secret'
        try:
            with tempfile.TemporaryDirectory() as d:
                exe = Path(d) / 'um'; exe.write_text('#!/bin/sh\nenv | grep -c _API_KEY || true\n'); exe.chmod(0o755)
                out = toolkit.run(d, 'universal-modder', ['--help'], settings={'um_executable': str(exe)})
                self.assertIn('0', json.dumps(out['result']))
        finally:
            del os.environ['OPENAI_API_KEY']

    def test_every_subprocess_call_passes_an_env(self):
        missing = []
        for f in ROOT.glob('*.py'):
            for n in ast.walk(ast.parse(f.read_text())):
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == 'subprocess' and n.func.attr in ('run', 'Popen', 'check_output', 'check_call', 'call'):
                    if not any(k.arg == 'env' or k.arg is None for k in n.keywords): missing.append('%s:%d' % (f.name, n.lineno))
        self.assertEqual(missing, [])


class Pruning(unittest.TestCase):
    def test_pruning_runs_in_real_use_not_only_when_called_directly(self):
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'um'; exe.write_text('#!/bin/sh\necho "{}"\n'); exe.chmod(0o755)
            runs = Path(d) / 'toolkit-runs'; runs.mkdir()
            for i in range(30):
                r = runs / ('run-old%02d' % i); r.mkdir(); (r / 'stdout.txt').write_text('x'); os.utime(r, (1000 + i, 1000 + i))
            toolkit.run(d, 'universal-modder', ['--help'], settings={'um_executable': str(exe)})
            self.assertLessEqual(len([p for p in runs.iterdir()]), toolkit.MAX_RUN_FOLDERS)


if __name__ == '__main__':
    unittest.main()
