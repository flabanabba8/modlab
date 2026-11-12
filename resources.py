"""ModLab environment scan, first-use interview and recommendations. Nothing here starts a game, installs a tool, changes a file
or sends anything over the network: it looks at what is installed, which Steam games exist, which engine a chosen game folder
looks like (by file signatures from modding_catalog.json), and then ASKS the user which route they want. The plugin never picks a
modding route for the user. The knowledge it carries is dated, checked for staleness, and the user can approve online research
to refresh it (see the freshness block)."""
import json
import os
import re
import shutil
import sys
from pathlib import Path

MAX_ENTRIES = 4000


def profile_path(root):
    return Path(root) / 'modlab-profile' / 'profile.json'


# ---- knowledge freshness (generic block; identical in modlab/resources.py) ----
import datetime as _dt
MAX_AGE_DAYS = 30
UPDATE_FIELDS = ('free_tier', 'paid', 'needs', 'caveats', 'models', 'min_vram_gb', 'vram_basis', 'min_ram_gb', 'license', 'commercial', 'cloning', 'languages',
                 'status', 'notes', 'openai_endpoint', 'openai_style', 'install', 'platforms', 'how_to_run', 'smaller_variants', 'gpu_requirements', 'recommend',
                 'cost', 'price', 'limits', 'finding', 'rules', 'meaning', 'transparent_background', 'reference_image_edit', 'timestamps', 'subtitle_output', 'diarization',
                 'data_use', 'works_with_this_plugin', 'word_timestamps', 'rtf', 'free_minutes')


def _today(today=None):
    return today or _dt.date.today()


def _parse_day(text):
    try:
        return _dt.date.fromisoformat(str(text))
    except ValueError:
        return None


def freshness(verified, expiries=(), last_refresh=None, today=None, max_age_days=MAX_AGE_DAYS):
    """Is the shipped knowledge out of date? Returns {'verified', 'age_days', 'stale', 'reasons', 'coming_up', 'offer'}.
    Stale when older than max_age_days (counting the latest user-approved research refresh) or when a known deadline has passed."""
    now = _today(today)
    days = [d for d in (_parse_day(verified), _parse_day(last_refresh)) if d]
    newest = max(days) if days else None
    age = (now - newest).days if newest else None
    reasons, coming = [], []
    if age is None:
        reasons.append('the knowledge has no verification date')
    elif age > max_age_days:
        reasons.append('it was last checked %d days ago (checked %s; this plugin treats more than %d days as stale)' % (age, newest.isoformat(), max_age_days))
    for e in expiries:
        d = _parse_day(e.get('date'))
        if not d:
            continue
        if d <= now:
            if newest is None or d > newest:   # a deadline that passed before the last check is already reflected in what was checked
                reasons.append('a known deadline has passed (%s): %s' % (d.isoformat(), e.get('what')))
        elif (d - now).days <= max_age_days:
            coming.append('%s (%s): %s' % (d.isoformat(), '%d days away' % (d - now).days, e.get('what')))
    stale = bool(reasons)
    offer = None
    if stale or coming:
        offer = ('Some of this built-in knowledge may be out of date%s. Tell the user plainly what may have changed and ASK whether they want you to research '
                 'the current facts on the internet now, using the source links in the wiki (primary pages only). Do not research without their yes. If they say yes, '
                 'read the primary pages, then save only what you verified with the setup tool\'s knowledge_updates argument (each with its source link and date), '
                 'and tell the user what changed and what you could not verify. If they say no, carry on and say the numbers may be old.') % (' (' + '; '.join(reasons) + ')' if reasons else '')
    return {'verified': newest.isoformat() if newest else None, 'age_days': age, 'stale': stale, 'reasons': reasons, 'coming_up': coming, 'offer': offer}


def _updates_path(root):
    return profile_path(root).parent / 'knowledge-updates.json'


def load_updates(root):
    try:
        data = json.loads(_updates_path(root).read_text())
        return data if isinstance(data, dict) and isinstance(data.get('updates'), list) else {'updates': [], 'last_refresh': None}
    except (OSError, ValueError):
        return {'updates': [], 'last_refresh': None}


def save_updates(root, updates, known_ids, today=None):
    """Store research results the user approved. Each update: {id, field, value, source (https URL), date}. Nothing is trusted blindly:
    unknown ids/fields, non-https sources, future dates and oversized values are refused. Returns the stored file contents."""
    now = _today(today)
    if not isinstance(updates, list) or not 1 <= len(updates) <= 100:
        raise ValueError('knowledge_updates must be a list of 1 to 100 items')
    clean = []
    for u in updates:
        if not isinstance(u, dict) or set(u) - {'id', 'field', 'value', 'source', 'date', 'note'}:
            raise ValueError('each update needs id, field, value, source and date (note is optional)')
        if u.get('id') not in known_ids:
            raise ValueError('unknown id "%s"; use an id from the wiki tables' % u.get('id'))
        if u.get('field') not in UPDATE_FIELDS:
            raise ValueError('field "%s" cannot be updated; allowed: %s' % (u.get('field'), ', '.join(UPDATE_FIELDS)))
        value = u.get('value')
        if not (isinstance(value, (str, bool, int, float, list)) or value is None) or len(json.dumps(value)) > 1500:
            raise ValueError('value is too large or not plain data')
        src = u.get('source')
        if not isinstance(src, str) or not src.startswith('https://') or len(src) > 500:
            raise ValueError('every update needs the https source page it was verified on')
        day = _parse_day(u.get('date'))
        if not day or day > now:
            raise ValueError('every update needs the date you read the source (not in the future)')
        clean.append({'id': u['id'], 'field': u['field'], 'value': value, 'source': src, 'date': day.isoformat(), 'note': str(u.get('note', ''))[:300]})
    data = load_updates(root)
    data['updates'] = (data['updates'] + clean)[-500:]
    data['last_refresh'] = max(c['date'] for c in clean)
    path = _updates_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)
    return data


def apply_updates(rows, updates):
    """Overlay approved research on catalog rows (the shipped catalog file is never modified). Later updates win."""
    by = {r['id']: r for r in rows}
    for u in updates:
        r = by.get(u['id'])
        if r is not None:
            r[u['field']] = u['value']
            r.setdefault('updated_by_research', {})[u['field']] = {'source': u['source'], 'date': u['date']}
    return rows
# ---- end knowledge freshness ----

# ---------------------------------------------------------------- catalog
def load_catalog(path=None, update_root=None):
    path = Path(path) if path else Path(__file__).resolve().parent / 'modding_catalog.json'
    try:
        cat = json.loads(path.read_text())
    except (OSError, ValueError):
        return {'verified': None, 'engines': [], 'tools': [], 'anticheat': [], 'hubs': [], 'expiries': []}
    if update_root is not None:
        data = load_updates(update_root)
        for key in ('engines', 'tools', 'anticheat', 'hubs'):
            apply_updates(cat.get(key, []), data['updates'])
        cat['last_refresh'] = data.get('last_refresh')
    return cat


def known_ids():
    cat = load_catalog()
    return {r['id'] for k in ('engines', 'tools', 'anticheat', 'hubs') for r in cat.get(k, [])}


def modlab_freshness(root, today=None):
    cat = load_catalog(update_root=root)
    return freshness(cat.get('verified'), cat.get('expiries', []), cat.get('last_refresh'), today)


# ---------------------------------------------------------------- environment
def os_name(platform=None):
    platform = platform or sys.platform
    return 'windows' if platform.startswith('win') else 'macos' if platform == 'darwin' else 'linux'


def installed_tools(catalog=None, which=shutil.which):
    """Which catalogued tools have a command on PATH (presence only; nothing is executed). Tools that live inside a game folder or
    are Python/Java libraries have no command to look for: they report installed = None (checked per game, not missing)."""
    cat = catalog or load_catalog()
    out = []
    for t in cat.get('tools', []):
        cmds = t.get('commands', [])
        if not cmds:
            out.append({'id': t['id'], 'name': t['name'], 'installed': None, 'path': None, 'how_detected': t.get('detect_note', 'not on PATH; lives in the game folder or is a library')})
            continue
        found = next((which(c) for c in cmds if which(c)), None)
        out.append({'id': t['id'], 'name': t['name'], 'installed': bool(found), 'path': found, 'how_detected': 'command on PATH'})
    return out


def steam_roots(platform=None, home=None):
    home = Path(home or Path.home())
    osn = os_name(platform)
    if osn == 'linux':
        c = [home / '.steam/steam', home / '.local/share/Steam', home / '.var/app/com.valvesoftware.Steam/.local/share/Steam']
    elif osn == 'macos':
        c = [home / 'Library/Application Support/Steam']
    else:
        c = [Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Steam']
    return [p for p in c if p.is_dir()]


def _vdf_values(text, key):
    return re.findall(r'"%s"\s+"([^"]*)"' % re.escape(key), text)


NOT_GAMES = re.compile(r'^(Proton\b|Steam Linux Runtime|Legacy Steam Runtime|Steamworks Common Redistributables|SteamVR$)', re.I)


def steam_games(platform=None, home=None, roots=None, report=None):
    """Installed Steam games found in the libraries' appmanifest files: [{name, appid, folder}]. Read-only, local.
    Libraries are de-duplicated by real path (Steam's own ~/.steam/steam is a symlink to the install, which libraryfolders.vdf also lists),
    Proton and runtime components are left out, and libraries that are not mounted are reported in report['libraries_not_available'] if given."""
    seen_libs, seen_games, games = set(), set(), []
    for root in (roots if roots is not None else steam_roots(platform, home)):
        libs = [Path(root)]
        try:
            libs += [Path(p.replace('\\\\', '\\')) for p in _vdf_values((Path(root) / 'steamapps/libraryfolders.vdf').read_text(errors='replace'), 'path')]
        except OSError:
            pass
        for lib in libs:
            try:
                real = lib.resolve()
            except OSError:
                real = lib
            if str(real) in seen_libs:
                continue
            seen_libs.add(str(real))
            steamapps = real / 'steamapps'
            if not steamapps.is_dir():
                if report is not None:
                    report.setdefault('libraries_not_available', []).append(str(lib))
                continue
            try:
                manifests = sorted(steamapps.glob('appmanifest_*.acf'))[:MAX_ENTRIES]
            except OSError:
                continue
            for m in manifests:
                try:
                    text = m.read_text(errors='replace')
                except OSError:
                    continue
                name = (_vdf_values(text, 'name') or [''])[0]
                inst = (_vdf_values(text, 'installdir') or [''])[0]
                appid = (_vdf_values(text, 'appid') or [''])[0]
                folder = steamapps / 'common' / inst
                if name and inst and not NOT_GAMES.search(name) and folder.is_dir() and (appid, str(folder.resolve())) not in seen_games:
                    seen_games.add((appid, str(folder.resolve())))
                    games.append({'name': name, 'appid': appid, 'folder': str(folder)})
    return sorted(games, key=lambda g: g['name'].lower())


def _signature_first(folder, sig):
    """Relative path of the first file or folder matching one signature ({'glob': pattern}), or None. Bounded; no recursion beyond the pattern."""
    pattern = sig['glob']
    if '**' in pattern or pattern.startswith('/') or '..' in pattern:
        return None
    try:
        for i, hit in enumerate(Path(folder).glob(pattern)):
            if i > 50:
                break
            if not hit.is_symlink():
                return hit.relative_to(folder).as_posix()
    except (OSError, ValueError):
        return None
    return None


def _signature_hit(folder, sig):
    return _signature_first(folder, sig) is not None


def identify_game(folder, catalog=None):
    """Which engines and anti-cheat systems the folder looks like, from file signatures in the catalog. Reads names only."""
    cat = catalog or load_catalog()
    p = Path(folder)
    if not p.is_dir() or p.is_symlink():
        raise ValueError('That is not a game folder on this computer')
    engines = []
    for e in cat.get('engines', []):
        hits = [(s_['glob'], _signature_first(p, s_)) for s_ in e.get('signatures', [])]
        hits = [(g, path) for g, path in hits if path]
        if hits and len(hits) >= e.get('min_hits', 1):
            nested = [path for _, path in hits if '/' in path and not path.startswith(('Data/', 'game/'))]
            engines.append({'id': e['id'], 'name': e['name'], 'matched': [g for g, _ in hits], 'matched_paths': [path for _, path in hits][:8],
                            'maybe_a_bundled_tool': bool(nested) and len(nested) == len(hits) and any(path.count('/') >= 1 and not path.startswith('game/') for path in nested),
                            'check': 'Files were found inside a subfolder; confirm that is the game and not a bundled tool or launcher.' if nested else None})
    anti = []
    for a in cat.get('anticheat', []):
        hits = [_signature_first(p, s_) for s_ in a.get('signatures', [])]
        hits = [h for h in hits if h]
        if hits:
            anti.append({'id': a['id'], 'name': a['name'], 'matched': hits[:4], 'meaning': a.get('meaning'), 'source': a.get('source')})
    return {'engines': engines, 'anticheat': anti}


# ---------------------------------------------------------------- recommendations
def recommend(engine_ids, tools, catalog=None, os_label=None):
    """Routes for the matched engine(s), each with what it needs and whether those tools are installed. Suggestions only."""
    cat = catalog or load_catalog()
    state = {t['id']: t['installed'] for t in tools}
    by_tool = {t['id']: t for t in cat.get('tools', [])}
    out = []
    for e in cat.get('engines', []):
        if e['id'] not in engine_ids:
            continue
        routes = []
        for r in e.get('routes', []):
            needs = r.get('needs_tools', [])
            missing = [by_tool[n]['name'] if n in by_tool else n for n in needs if state.get(n) is False]
            unchecked = [by_tool[n]['name'] if n in by_tool else n for n in needs if state.get(n) is None]
            osok = not r.get('platforms') or os_label is None or os_label in r['platforms'] or 'any' in r['platforms']
            routes.append({'id': r['id'], 'name': r['name'], 'kind': r.get('kind'), 'status': r.get('status'), 'platforms': r.get('platforms'), 'works_on_this_os': osok,
                           'needs': [by_tool[n]['name'] if n in by_tool else n for n in needs], 'missing_tools': missing, 'check_in_game_folder': unchecked, 'ready_to_use': not missing and osok,
                           'notes': r.get('notes'), 'source': r.get('source'), 'verified': r.get('verified')})
        out.append({'engine': e['name'], 'id': e['id'], 'routes': routes, 'data_only_option': e.get('data_only'), 'pitfalls': e.get('pitfalls'), 'reverse_engineering_tools': [by_tool[n]['name'] if n in by_tool else n for n in e.get('re_tools', [])]})
    return out


# ---------------------------------------------------------------- interview / profile
QUESTIONS = [
    {'key': 'game', 'ask': 'Which game do you want to mod? Pick one of the installed games found on this computer, or give the folder path.', 'type': 'choice-or-path'},
    {'key': 'idea', 'ask': 'What should the mod do (new item, character, texture, rule change, translation, a crossover)?', 'type': 'text'},
    {'key': 'single_player_offline', 'ask': 'Is this only for offline single-player use? (Modified files can get you banned in online games with anti-cheat.)', 'type': 'yes/no'},
    {'key': 'experience', 'ask': 'How comfortable are you with code and modding tools?', 'type': 'choice', 'choices': ['new to modding', 'some experience', 'experienced']},
    {'key': 'publish', 'ask': 'Do you plan to share the mod publicly (Nexus Mods, Thunderstore, Steam Workshop, mod.io) or keep it private?', 'type': 'choice', 'choices': ['private', 'share publicly']},
    {'key': 'ai_assets', 'ask': 'Is it OK to use AI-generated art or audio in the mod? (Several mod sites require you to disclose it.)', 'type': 'yes/no'},
    {'key': 'has', 'ask': 'What do you already have or are willing to install (a decompiler, a mod loader, Universal Modder, Reverse Engineer Anything, Wine/Proton)?', 'type': 'text'},
]


def save_profile(root, answers, game_ids=None, route_ids=None):
    if not isinstance(answers, dict):
        raise ValueError('answers must be an object with the interview keys')
    out = {'answered': True}
    game = answers.get('game')
    if not isinstance(game, str) or not game.strip() or len(game) > 500:
        raise ValueError('game: give the game name or its folder path')
    out['game'] = game.strip()
    for key, limit in (('idea', 600), ('has', 400)):
        v = answers.get(key, '')
        if not isinstance(v, str) or len(v) > limit or (key == 'idea' and not v.strip()):
            raise ValueError('%s: up to %d characters%s' % (key, limit, ' and not empty' if key == 'idea' else ''))
        out[key] = v.strip()
    for key in ('single_player_offline', 'ai_assets'):
        if type(answers.get(key)) is not bool:
            raise ValueError('%s must be true or false' % key)
        out[key] = answers[key]
    if answers.get('experience') not in ('new to modding', 'some experience', 'experienced'):
        raise ValueError('experience must be: new to modding, some experience or experienced')
    out['experience'] = answers['experience']
    if answers.get('publish') not in ('private', 'share publicly'):
        raise ValueError('publish must be private or share publicly')
    out['publish'] = answers['publish']
    route = answers.get('route')
    if route is not None:
        if not isinstance(route, str) or len(route) > 200:
            raise ValueError('route must be the id of one of the routes you were shown')
        if route_ids is not None and route not in route_ids:
            raise ValueError('route "%s" is not one of the routes offered: %s' % (route, ', '.join(sorted(route_ids)) or 'none'))
    out['route'] = route or None
    path = profile_path(root)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(out, indent=2))
    tmp.chmod(0o600)
    tmp.replace(path)
    return out


def load_profile(root):
    try:
        data = json.loads(profile_path(root).read_text())
        return data if isinstance(data, dict) and data.get('answered') else None
    except (OSError, ValueError):
        return None


def survey(root, game_folder=None, catalog=None, which=shutil.which, platform=None, home=None):
    """The environment report the interview is built on. Local reads only."""
    cat = catalog or load_catalog(update_root=root)
    tools = installed_tools(cat, which)
    notes = {}
    games = steam_games(platform, home, report=notes)
    rep = {'os': os_name(platform), 'tools': tools, 'steam_games': games, 'steam_libraries_not_available': notes.get('libraries_not_available', []), 'tools_missing_that_matter': [t['name'] for t in tools if t['installed'] is False][:20]}
    if game_folder:
        rep['game_folder'] = str(game_folder)
        rep['identified'] = identify_game(game_folder, cat)
        ids = {e['id'] for e in rep['identified']['engines']} or {e['id'] for e in cat.get('engines', []) if e.get('fallback')}
        rep['engine_unknown'] = not rep['identified']['engines']
        rep['routes'] = recommend(ids, tools, cat, rep['os'])
    return rep


def interview(root, report, answers=None):
    """Without answers: the report, the questions, the routes found for the chosen game and the freshness of the knowledge.
    With answers: validates and saves, including the route the user picked. Never picks a route for the user."""
    offered = {r['id'] for e in report.get('routes', []) for r in e['routes']}
    if answers is not None:
        if offered and not (isinstance(answers, dict) and answers.get('route')):
            raise ValueError('Ask the user which of these routes to use and pass it as route (nothing was saved): ' + ', '.join(sorted(offered)))
        profile = save_profile(root, answers, route_ids=offered if offered else None)
        warnings = []
        if profile['publish'] == 'share publicly' and profile['ai_assets']:
            warnings.append('Several mod sites require disclosure of AI-generated content; check the site rules in the wiki before uploading.')
        for a in report.get('identified', {}).get('anticheat', []):
            warnings.append('%s was detected in the game folder: %s' % (a['name'], a.get('meaning') or 'modified files can get you banned online; keep this offline and single-player'))
        return {'state': 'saved', 'profile': profile, 'you_chose': profile['route'], 'warnings': warnings, 'report': report}
    existing = load_profile(root)
    state = 'interview_needed' if not existing or (offered and not existing.get('route')) else 'answered'
    return {'state': state, 'profile': existing, 'report': report, 'questions': QUESTIONS, 'knowledge_freshness': modlab_freshness(root),
            'instructions_for_agent': 'Do not choose a modding route for the user. Show them what was found on this computer (installed tools, installed games, and for a chosen game folder the engine it looks like and any anti-cheat), then the routes found for that engine with what each needs, what is missing and how mature it is (status and source/date). Ask which route they want, together with the other questions, in one short message. If this is not their game folder yet, call the setup tool again with game_folder to identify it. Do not install anything or start a game without their yes. Read knowledge_freshness: if it says stale (or something is coming up), tell the user what may be old and ask whether they want you to research the current facts online; never research without their yes. Then call the setup tool again with answers = {game, idea, single_player_offline, experience, publish, ai_assets, has, route}. Do not start recon or building until the answers are saved.'}


def apply_setup(root, report, answers=None, knowledge_updates=None):
    saved = None
    if knowledge_updates is not None:
        saved = len(save_updates(root, knowledge_updates, known_ids())['updates'])
    out = interview(root, report, answers)
    if saved is not None:
        out['knowledge_updates_saved'] = saved
    return out
