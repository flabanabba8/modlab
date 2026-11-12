import datetime
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('modlab_resources_under_test', ROOT / 'resources.py')
R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)

CAT = {'verified': '2026-11-12', 'expiries': [{'date': '2027-01-01', 'what': 'a loader drops support'}],
       'tools': [{'id': 'dotnet', 'name': '.NET SDK', 'commands': ['dotnet']}, {'id': 'ilspy', 'name': 'ILSpy', 'commands': ['ilspycmd']}, {'id': 'ghidra', 'name': 'Ghidra', 'commands': ['ghidraRun']}],
       'engines': [
           {'id': 'unity-mono', 'name': 'Unity (Mono)', 'signatures': [{'glob': 'UnityPlayer.dll'}, {'glob': '*_Data/Managed/Assembly-CSharp.dll'}], 'min_hits': 2,
            'routes': [{'id': 'bepinex', 'name': 'BepInEx plugin', 'kind': 'loader', 'needs_tools': ['dotnet'], 'platforms': ['any'], 'status': 'maintained', 'source': 'https://github.com/BepInEx/BepInEx', 'verified': '2026-11-12'},
                       {'id': 'data-edit', 'name': 'Edit data files', 'kind': 'data', 'needs_tools': [], 'platforms': ['any'], 'status': 'n/a'}],
            're_tools': ['ilspy'], 'data_only': 'config files', 'pitfalls': ['IL2CPP differs']},
           {'id': 'godot', 'name': 'Godot', 'signatures': [{'glob': '*.pck'}], 'routes': [{'id': 'gdre', 'name': 'GDRE Tools', 'kind': 're', 'needs_tools': ['ghidra'], 'platforms': ['windows'], 'status': 'maintained'}]}],
       'anticheat': [{'id': 'eac', 'name': 'Easy Anti-Cheat', 'signatures': [{'glob': 'EasyAntiCheat'}], 'meaning': 'online play will reject modified files', 'source': 'https://example.test'}],
       'hubs': []}
ANSWERS = {'game': 'Fixture Game', 'idea': 'a new sword', 'single_player_offline': True, 'experience': 'some experience', 'publish': 'private', 'ai_assets': False, 'has': 'dotnet'}


def make_game(base, *files):
    g = Path(base) / 'steamapps' / 'common' / 'FixtureGame'
    for f in files:
        p = g / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'x') if not f.endswith('/') else p.mkdir(parents=True, exist_ok=True)
    return g


class Environment(unittest.TestCase):
    def test_tools_are_found_by_presence_only(self):
        t = {x['id']: x for x in R.installed_tools(CAT, which=lambda c: '/bin/' + c if c == 'dotnet' else None)}
        self.assertTrue(t['dotnet']['installed']); self.assertFalse(t['ilspy']['installed'])

    def test_steam_library_games_are_read_from_manifests(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / 'Steam'; (root / 'steamapps').mkdir(parents=True)
            other = Path(d) / 'Lib2'; (other / 'steamapps' / 'common' / 'Second').mkdir(parents=True)
            (root / 'steamapps' / 'common' / 'First').mkdir(parents=True)
            (root / 'steamapps' / 'libraryfolders.vdf').write_text('"libraryfolders"\n{\n "1"\n {\n  "path"\t\t"%s"\n }\n}\n' % other)
            (root / 'steamapps' / 'appmanifest_10.acf').write_text('"AppState"\n{\n "appid"\t"10"\n "name"\t"First Game"\n "installdir"\t"First"\n}\n')
            (other / 'steamapps' / 'appmanifest_20.acf').write_text('"AppState"\n{\n "appid"\t"20"\n "name"\t"Second Game"\n "installdir"\t"Second"\n}\n')
            (root / 'steamapps' / 'appmanifest_30.acf').write_text('"AppState"\n{\n "appid"\t"30"\n "name"\t"Gone"\n "installdir"\t"NotThere"\n}\n')
            games = R.steam_games(roots=[root])
            self.assertEqual([g['name'] for g in games], ['First Game', 'Second Game'])   # uninstalled one is skipped

    def test_a_symlinked_root_runtime_components_and_unmounted_libraries_are_handled(self):
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / 'real'; (real / 'steamapps' / 'common' / 'Game').mkdir(parents=True); (real / 'steamapps' / 'common' / 'Proton 9').mkdir()
            (real / 'steamapps' / 'appmanifest_1.acf').write_text('"AppState"\n{\n "appid"\t"1"\n "name"\t"Real Game"\n "installdir"\t"Game"\n}\n')
            (real / 'steamapps' / 'appmanifest_2.acf').write_text('"AppState"\n{\n "appid"\t"2"\n "name"\t"Proton 9.0"\n "installdir"\t"Proton 9"\n}\n')
            link = Path(d) / 'link'; link.symlink_to(real)
            (real / 'steamapps' / 'libraryfolders.vdf').write_text('"libraryfolders"\n{\n "0"\n {\n  "path"\t\t"%s"\n }\n "1"\n {\n  "path"\t\t"%s"\n }\n}\n' % (real, Path(d) / 'unmounted'))
            note = {}
            games = R.steam_games(roots=[link], report=note)
            self.assertEqual([g['name'] for g in games], ['Real Game'])          # once, not twice; Proton is not a game
            self.assertEqual(note['libraries_not_available'], [str(Path(d) / 'unmounted')])

    def test_no_steam_is_an_empty_list_not_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(R.steam_games(platform='linux', home=d), [])


class Identify(unittest.TestCase):
    def test_engine_and_anticheat_come_from_file_signatures(self):
        with tempfile.TemporaryDirectory() as d:
            g = make_game(d, 'UnityPlayer.dll', 'Fixture_Data/Managed/Assembly-CSharp.dll', 'EasyAntiCheat/x.dll')
            r = R.identify_game(g, CAT)
            self.assertEqual([e['id'] for e in r['engines']], ['unity-mono']); self.assertEqual(r['anticheat'][0]['id'], 'eac')

    def test_min_hits_stops_a_single_coincidence_from_naming_an_engine(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(R.identify_game(make_game(d, 'UnityPlayer.dll'), CAT)['engines'], [])

    def test_unsafe_patterns_and_symlinks_are_ignored_and_a_non_folder_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            g = make_game(d, 'a.txt')
            self.assertFalse(R._signature_hit(g, {'glob': '../*'})); self.assertFalse(R._signature_hit(g, {'glob': '**/*.txt'})); self.assertFalse(R._signature_hit(g, {'glob': '/etc/*'}))
            (g / 'link.pck').symlink_to(g / 'a.txt')
            self.assertEqual(R.identify_game(g, CAT)['engines'], [])
            with self.assertRaises(ValueError):
                R.identify_game(g / 'a.txt', CAT)


class Recommend(unittest.TestCase):
    def test_routes_say_what_they_need_and_what_is_missing_and_nothing_is_picked(self):
        tools = R.installed_tools(CAT, which=lambda c: None)
        r = R.recommend({'unity-mono'}, tools, CAT, 'linux')[0]
        by = {x['id']: x for x in r['routes']}
        self.assertEqual(by['bepinex']['missing_tools'], ['.NET SDK']); self.assertFalse(by['bepinex']['ready_to_use']); self.assertTrue(by['data-edit']['ready_to_use'])
        self.assertEqual(r['reverse_engineering_tools'], ['ILSpy'])

    def test_a_route_for_another_operating_system_is_marked(self):
        tools = R.installed_tools(CAT, which=lambda c: '/bin/' + c)
        r = R.recommend({'godot'}, tools, CAT, 'linux')[0]['routes'][0]
        self.assertFalse(r['works_on_this_os'])


class Interview(unittest.TestCase):
    def report(self, d, with_game=True):
        g = make_game(d, 'UnityPlayer.dll', 'Fixture_Data/Managed/Assembly-CSharp.dll', 'EasyAntiCheat/x.dll')
        with mock.patch.object(R, 'load_catalog', lambda *a, **k: CAT), mock.patch.object(R, 'steam_games', lambda *a, **k: []):
            return R.survey(Path(d) / 'ns', g if with_game else None, CAT, which=lambda c: None)

    def test_first_use_returns_questions_the_found_routes_and_an_instruction_not_to_choose(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(R, 'load_catalog', lambda *a, **k: CAT):
            out = R.interview(Path(d) / 'ns', self.report(d))
            self.assertEqual(out['state'], 'interview_needed'); self.assertGreaterEqual(len(out['questions']), 7)
            self.assertIn('Do not choose a modding route for the user', out['instructions_for_agent'])
            self.assertIn('knowledge_freshness', out); self.assertIn('never research without their yes', out['instructions_for_agent'])
            self.assertIsNone(R.load_profile(Path(d) / 'ns'))

    def test_answers_need_a_route_when_routes_exist_and_the_route_must_be_one_offered(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(R, 'load_catalog', lambda *a, **k: CAT):
            rep = self.report(d); root = Path(d) / 'ns'
            with self.assertRaisesRegex(ValueError, 'Ask the user which'):
                R.interview(root, rep, ANSWERS)
            with self.assertRaisesRegex(ValueError, 'not one of the routes offered'):
                R.interview(root, rep, {**ANSWERS, 'route': 'invented'})
            out = R.interview(root, rep, {**ANSWERS, 'route': 'bepinex'})
            self.assertEqual((out['state'], out['you_chose']), ('saved', 'bepinex'))
            self.assertTrue(any('Easy Anti-Cheat' in w for w in out['warnings']))
            self.assertEqual(oct(R.profile_path(root).stat().st_mode & 0o777), '0o600')

    def test_validation(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ({}, {**ANSWERS, 'game': ''}, {**ANSWERS, 'single_player_offline': 'yes'}, {**ANSWERS, 'experience': 'wizard'}, {**ANSWERS, 'publish': 'maybe'}, {**ANSWERS, 'idea': ''}, {**ANSWERS, 'has': 'x' * 500}):
                with self.assertRaises(ValueError):
                    R.save_profile(Path(d) / 'ns', bad)

    def test_publishing_with_ai_assets_warns_about_disclosure(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(R, 'load_catalog', lambda *a, **k: CAT):
            rep = R.survey(Path(d) / 'ns', None, CAT, which=lambda c: None)
            out = R.interview(Path(d) / 'ns', rep, {**ANSWERS, 'publish': 'share publicly', 'ai_assets': True})
            self.assertTrue(any('disclos' in w for w in out['warnings']))


class Freshness(unittest.TestCase):
    def day(self, y, m, d): return datetime.date(y, m, d)

    def test_stale_by_age_or_by_a_passed_deadline_and_the_offer_asks_first(self):
        self.assertFalse(R.freshness('2026-11-12', CAT['expiries'], None, self.day(2026, 11, 20))['stale'])
        old = R.freshness('2026-09-01', [], None, self.day(2026, 11, 20))
        self.assertTrue(old['stale']); self.assertIn('ASK whether', old['offer']); self.assertIn('Do not research without their yes', old['offer'])
        self.assertTrue(R.freshness('2026-12-30', CAT['expiries'], None, self.day(2027, 1, 2))['stale'])

    def test_research_updates_are_validated_and_overlay_without_touching_the_shipped_catalog(self):
        ok = {'id': 'bepinex', 'field': 'status', 'value': 'maintained (v6.1)', 'source': 'https://github.com/BepInEx/BepInEx/releases', 'date': '2026-11-12'}
        cat_file = Path(tempfile.mkdtemp()) / 'modding_catalog.json'
        cat_file.write_text(json.dumps({**CAT, 'engines': [dict(e) for e in CAT['engines']]}))
        with tempfile.TemporaryDirectory() as d, mock.patch.object(R, 'known_ids', lambda: {'unity-mono', 'dotnet', 'godot', 'eac'}):
            root = Path(d) / 'ns'
            with self.assertRaises(ValueError):
                R.save_updates(root, [{**ok, 'id': 'nope'}], R.known_ids(), self.day(2026, 11, 12))
            R.save_updates(root, [{**ok, 'id': 'unity-mono', 'field': 'status'}], R.known_ids(), self.day(2026, 11, 12))
            cat = R.load_catalog(cat_file, update_root=root)
            self.assertEqual([e for e in cat['engines'] if e['id'] == 'unity-mono'][0]['status'], 'maintained (v6.1)')
            self.assertEqual(cat['last_refresh'], '2026-11-12')
            self.assertNotIn('status', json.loads(cat_file.read_text())['engines'][0])


class RealLayouts(unittest.TestCase):
    """Layouts seen in a real Steam library, checked against the shipped catalog."""
    def setUp(self):
        self.cat = R.load_catalog()
        if not self.cat['engines']:
            self.skipTest('catalog not built')

    def ids(self, base, *files):
        g = make_game(base, *files)
        return {e['id']: e for e in R.identify_game(g, self.cat)['engines']}

    def test_unity_il2cpp_with_easy_anti_cheat(self):
        with tempfile.TemporaryDirectory() as d:
            g = make_game(d, 'UnityPlayer.dll', 'GameAssembly.dll', 'Game_Data/il2cpp_data/Metadata/global-metadata.dat', 'EasyAntiCheat/x.dll')
            r = R.identify_game(g, self.cat)
            self.assertIn('unity-il2cpp', [e['id'] for e in r['engines']]); self.assertEqual([a['id'] for a in r['anticheat']], ['eac'])
            self.assertIn('modified', r['anticheat'][0]['meaning'])

    def test_a_game_nested_in_a_subfolder_is_found_and_flagged_for_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            e = self.ids(d, 'Game/UnityPlayer.dll', 'Game/X_Data/Managed/Assembly-CSharp.dll', 'Mod Tool/readme.txt')['unity-mono']
            self.assertTrue(e['maybe_a_bundled_tool']); self.assertIn('Game/UnityPlayer.dll', e['matched_paths']); self.assertIn('confirm', e['check'])

    def test_source2_keeps_gameinfo_two_levels_down(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('source', self.ids(d, 'game/hlvr/gameinfo.gi', 'game/hlvr/pak01_dir.vpk', 'game/bin/x'))

    def test_godot_with_an_embedded_pack_is_found_by_its_godot_library(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('godot', self.ids(d, 'Game.x86_64', 'libgodotsteam.linux.template_release.x86_64.so'))

    def test_rpg_maker_mz_and_the_unreal_layout(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('rpgmaker', self.ids(d, 'Game.exe', 'js/rmmz_core.js', 'package.json'))
        with tempfile.TemporaryDirectory() as d:
            self.assertIn('unreal', self.ids(d, 'Engine/x', 'Game/Content/Paks/pakchunk0.pak', 'Game/Binaries/Win64/Game-Win64-Shipping.exe'))

    def test_a_native_game_with_nothing_recognised_gets_the_generic_route_and_says_the_engine_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            g = make_game(d, 'game.exe', 'data/a.bin')
            rep = R.survey(Path(d) / 'ns', g, self.cat, which=lambda c: None)
            self.assertTrue(rep['engine_unknown']); self.assertEqual([x['id'] for x in rep['routes']], ['native'])

    def test_tools_that_live_in_the_game_folder_are_checked_per_game_not_reported_missing(self):
        tools = R.installed_tools(self.cat, which=lambda c: None)
        by = {t['id']: t for t in tools}
        self.assertIsNone(by['bepinex']['installed']); self.assertFalse(by['dotnet']['installed'])
        r = R.recommend({'unity-mono'}, tools, self.cat, 'linux')[0]['routes']
        bep = [x for x in r if x['id'] == 'bepinex-mono'][0]
        self.assertEqual(bep['missing_tools'], ['.NET SDK / runtime']); self.assertIn('BepInEx', bep['check_in_game_folder'])

    def test_every_engine_route_has_a_source_and_unverified_ones_say_so(self):
        for e in self.cat['engines']:
            for r in e['routes']:
                self.assertTrue(r['source'].startswith('https://'), r['id'])
        rpg = [r for e in self.cat['engines'] if e['id'] == 'rpgmaker' for r in e['routes']][0]
        self.assertIn('UNVERIFIED', rpg['status'])

    def test_wiki_lists_every_engine_tool_hub_and_anticheat_with_its_source(self):
        wiki = (ROOT / 'llmwiki' / 'modding-routes.md').read_text()
        for key in ('engines', 'tools', 'anticheat', 'hubs'):
            for row in self.cat[key]:
                self.assertIn(row['name'], wiki)
        for row in self.cat['tools'] + self.cat['hubs'] + self.cat['anticheat']:
            self.assertIn(row['source'], wiki)
        self.assertIn('Never research without their yes', wiki)

    def test_generic_block_matches_the_speech_plugins(self):
        def block(path):
            t = Path(path).read_text()
            return t[t.index('# ---- knowledge freshness'):t.index('# ---- end knowledge freshness ----')]
        other = ROOT.parent / 'creator-studio' / 'common' / 'speech_resources.py'
        if other.exists():
            self.assertEqual(block(other), block(ROOT / 'resources.py'))


class Shipped(unittest.TestCase):
    def test_the_shipped_catalog_is_dated_sourced_and_every_route_names_real_tools(self):
        cat = R.load_catalog()
        if not cat['engines']:
            self.skipTest('catalog not built yet')
        ids = {t['id'] for t in cat['tools']}
        self.assertRegex(cat['verified'], r'^\d{4}-\d\d-\d\d$')
        for e in cat['engines']:
            self.assertTrue(e['signatures'] or e.get('fallback'), e['id'])
            for r in e['routes']:
                self.assertTrue(r['source'].startswith('https://'), r['id'])
                for n in r.get('needs_tools', []):
                    self.assertIn(n, ids, '%s needs unknown tool %s' % (r['id'], n))
            for n in e.get('re_tools', []):
                self.assertIn(n, ids)
        for t in cat['tools']:
            self.assertTrue(t['source'].startswith('https://'), t['id'])


if __name__ == '__main__':
    unittest.main()
