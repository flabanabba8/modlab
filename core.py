"""Local revisions with hard disk limits; no game process or source directory is modified.

Every copy is bounded: a free-space reserve and a total-size cap are checked before each file is written, files are cloned (copy-on-write)
where the filesystem allows it, only the last few revisions are kept, and nothing outside ModLab's own data folder is ever deleted."""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import time
import uuid
import zipfile
from . import locking

MAX_FILES = 100_000
MAX_BYTES = 50 * 1024**3
MAX_ZIP_FILES = 10_000
MAX_ZIP_BYTES = 2 * 1024**3
GIB = 1024**3
DEFAULT_MAX_TOTAL = 25 * GIB       # all labs together (apparent size)
DEFAULT_MIN_FREE = 10 * GIB        # never let free space fall below this ...
RESERVE_FRACTION = 0.10            # ... or this share of the disk, whichever is larger
DEFAULT_KEEP = 2                   # revisions kept per lab: the current one and the one before it (for rollback)
KEEP_PRESERVED = 2
FICLONE = 0x40049409               # Linux ioctl: copy-on-write clone
PRIVATE = {'.ssh', '.gnupg', '.aws', '.azure', '.codex', '.docker', '.kube', '.pki', '.config', '.hermes'}


class DiskGuard(ValueError):
    """Raised before a write that would fill the disk or exceed ModLab's own budget. Nothing partial is left behind."""


class Limits:
    def __init__(self, max_total=DEFAULT_MAX_TOTAL, min_free=DEFAULT_MIN_FREE, keep=DEFAULT_KEEP):
        self.max_total, self.min_free, self.keep = int(max_total), int(min_free), max(2, int(keep))


def limits_from(get_config=None):
    """Read the three settings (GB, GB, count); anything missing or invalid falls back to the safe defaults."""
    def num(key, default, unit=1):
        try:
            value = float(get_config(key)) if get_config else None
        except (TypeError, ValueError):
            value = None
        return default if value is None or value <= 0 else value * unit
    return Limits(num('modlab_max_total_gb', DEFAULT_MAX_TOTAL, GIB), num('modlab_min_free_gb', DEFAULT_MIN_FREE, GIB), num('modlab_keep_revisions', DEFAULT_KEEP))


def dir_bytes(path):
    """Apparent size of a folder; symlinks are never followed."""
    total = 0
    for directory, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                info = os.lstat(os.path.join(directory, name))
            except OSError:
                continue
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def pretty(n):
    return '%.1f GB' % (n / GIB) if n >= GIB else '%.0f MB' % (n / 1024**2)


class Budget:
    """Charged for every byte that is physically written. Refuses before the write, so a stopped copy never leaves the disk full."""
    def __init__(self, root, used, limits):
        self.root, self.used, self.limits, self.written = Path(root), used, limits, 0

    def charge(self, n):
        usage = shutil.disk_usage(self.root)
        reserve = max(self.limits.min_free, int(usage.total * RESERVE_FRACTION))
        if usage.free - n < reserve:
            raise DiskGuard('Stopped before the disk filled up: this copy needs about %s more but only %s is free and ModLab always keeps %s free. Nothing was left behind. '
                            'Free some space, delete old labs with modlab_cleanup, or pick a smaller game.' % (pretty(self.written + n), pretty(usage.free), pretty(reserve)))
        if self.used + self.written + n > self.limits.max_total:
            raise DiskGuard('Stopped at ModLab\'s size limit: labs already use %s and this copy needs about %s more, but the limit is %s (setting modlab_max_total_gb). '
                            'Nothing was left behind. Delete old labs with modlab_cleanup first, or raise the limit only if you really have the space.' % (pretty(self.used), pretty(self.written + n), pretty(self.limits.max_total)))
        self.written += n


def identity(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def link_or_reparse(path):
    info = Path(path).lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def digest(path):
    if link_or_reparse(path): raise ValueError('Symlinks and reparse points are unsupported')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode): raise ValueError('Only regular files can be hashed')
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    if identity(before) != identity(after) or identity(after) != identity(current) or not stat.S_ISREG(current.st_mode):
        raise ValueError('File changed while hashing')
    return h.hexdigest()


def source_path(value):
    p = Path(value).expanduser()
    if any(part.casefold() in PRIVATE for part in p.parts):
        raise ValueError('Private configuration paths are not supported')
    if link_or_reparse(p):
        raise ValueError('Symlink and reparse-point inputs are not supported')
    p = p.resolve(strict=True)
    if any(part.casefold() in PRIVATE for part in p.parts):
        raise ValueError('Private configuration paths are not supported')
    return p


def copy_regular(source, destination, budget=None):
    """Copy a regular file, rejecting symlinks and detecting identity changes. Tries a copy-on-write clone first (no extra disk use);
    otherwise the bytes are charged to the budget before they are written."""
    if link_or_reparse(source): raise ValueError('Symlinks and reparse points are unsupported')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        with os.fdopen(fd, 'rb', closefd=False) as src:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Only regular files can be copied')
            with open(destination, 'xb') as dst:
                cloned = False
                try:
                    import fcntl
                    fcntl.ioctl(dst.fileno(), FICLONE, fd)
                    cloned = True
                except (ImportError, OSError):
                    cloned = False
                if not cloned:
                    if budget is not None: budget.charge(before.st_size)
                    shutil.copyfileobj(src, dst, 1024 * 1024)
                if os.name != 'nt': os.fchmod(dst.fileno(), stat.S_IMODE(before.st_mode))
            after = os.fstat(fd)
            current = Path(source).lstat()
            if identity(before) != identity(after) or identity(after) != identity(current) or not stat.S_ISREG(current.st_mode):
                raise ValueError('File changed while copying')
        if os.utime in os.supports_follow_symlinks:
            os.utime(destination, ns=(before.st_atime_ns, before.st_mtime_ns), follow_symlinks=False)
    finally:
        os.close(fd)
    return destination


def tree(root):
    result = {}
    directories = set()
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if name.casefold() in PRIVATE or name.casefold() == '.git':
                raise ValueError('Game folder contains a private configuration or Git directory')
            directories.add((Path(directory) / name).relative_to(root).as_posix())
        if len(result) + len(directories) > MAX_FILES:
            raise ValueError('Game exceeds lab size or file-count limit')
        for name in dirs + files:
            p = Path(directory) / name
            if link_or_reparse(p) or not (p.is_dir() or p.is_file()):
                raise ValueError('Symlinks, reparse points and special files are not supported')
        for name in files:
            p = Path(directory) / name
            rel = p.relative_to(root).as_posix()
            total += p.stat().st_size
            if len(result) + len(directories) >= MAX_FILES or total > MAX_BYTES:
                raise ValueError('Game exceeds lab size or file-count limit')
            result[rel] = digest(p)
    return result, total, sorted(directories)


def archive(path):
    if not path.is_file():
        raise ValueError('ZIP path must be a file')
    with zipfile.ZipFile(path) as z:
        entries = []
        seen = set()
        components = {}
        total = 0
        if len(z.infolist()) > MAX_ZIP_FILES:
            raise ValueError('ZIP exceeds extraction limits')
        for i in z.infolist():
            name = i.filename
            p = PurePosixPath(name)
            mode = i.external_attr >> 16
            if ('\\' in name or name.startswith('/') or not p.parts or p.as_posix() + ('/' if i.is_dir() else '') != name or
                any(x in ('..', '.') or ':' in x for x in p.parts) or
                stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)) or
                i.flag_bits & 1):
                raise ValueError('ZIP contains an unsafe path, special file, or encrypted entry')
            for component in (p, *p.parents):
                text = str(component)
                if text == '.': continue
                folded = text.casefold()
                if folded in components and components[folded] != text:
                    raise ValueError('ZIP contains duplicate or case-colliding paths')
                components[folded] = text
            if i.is_dir():
                continue
            normalized = p.as_posix()
            key = normalized.casefold()
            if key in seen:
                raise ValueError('ZIP contains duplicate or case-colliding paths')
            seen.add(key)
            total += i.file_size
            if len(entries) >= MAX_ZIP_FILES or total > MAX_ZIP_BYTES:
                raise ValueError('ZIP exceeds extraction limits')
            entries.append(normalized)
        if not entries:
            raise ValueError('ZIP contains no files')
        for name in entries:
            if any(str(parent).casefold() in seen for parent in PurePosixPath(name).parents if str(parent) != '.'):
                raise ValueError('ZIP file collides with a parent path')
    return entries, total


def is_lab_id(name):
    return len(name) == 32 and all(c in '0123456789abcdef' for c in name)


class Lab:
    def __init__(self, root, limits=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.limits = limits or Limits()

    def lab_dirs(self):
        return sorted(p for p in self.root.iterdir() if is_lab_id(p.name) and p.is_dir() and not p.is_symlink())

    def used_bytes(self):
        return sum(dir_bytes(p) for p in self.lab_dirs())

    def remove_leftovers(self, older_than=3600):
        """Delete lab folders that never finished (no state.json, older than an hour): what a crash or a power cut leaves behind."""
        gone = []
        for p in self.lab_dirs():
            if not (p / 'state.json').exists() and time.time() - p.stat().st_mtime > older_than:
                gone.append({'lab': p.name, 'bytes': dir_bytes(p)}); shutil.rmtree(p, ignore_errors=True)
        return gone

    def prune(self, lab, state, keep=None):
        """Delete the oldest revisions beyond the keep count (and old preserved ones). Never touches the current or the previous revision."""
        keep = max(2, keep or self.limits.keep)
        removed = []
        while len(state['history']) > keep:
            rev = state['history'].pop(0)
            removed.append({'revision': rev, 'bytes': dir_bytes(lab / rev)}); shutil.rmtree(lab / rev, ignore_errors=True)
        while len(state['preserved']) > KEEP_PRESERVED:
            rev = state['preserved'].pop(0)
            removed.append({'revision': rev, 'bytes': dir_bytes(lab / rev)}); shutil.rmtree(lab / rev, ignore_errors=True)
        return removed

    def cleanup(self, action='report', lab_id=None, keep=None, confirm=False):
        """Show what ModLab uses on disk, or free space. Only folders inside ModLab's own data folder are ever deleted, and only with confirm=true.
        Actions: report (default), delete_lab (needs lab_id), prune_revisions (optional lab_id, keep), clear_toolkit_runs, remove_leftovers."""
        if action not in ('report', 'delete_lab', 'prune_revisions', 'clear_toolkit_runs', 'remove_leftovers'):
            raise ValueError('action must be report, delete_lab, prune_revisions, clear_toolkit_runs or remove_leftovers')
        if type(confirm) is not bool:
            raise ValueError('confirm must be true or false')
        with self.locked():
            usage = shutil.disk_usage(self.root)
            labs = []
            for p in self.lab_dirs():
                try:
                    st = self.state(p); revs = len(st['history']) + len(st['preserved'])
                except (OSError, ValueError, KeyError):
                    st, revs = None, 0
                labs.append({'lab_id': p.name, 'bytes': dir_bytes(p), 'revisions': revs, 'finished': st is not None, 'last_used': time.strftime('%Y-%m-%d %H:%M', time.localtime(p.stat().st_mtime))})
            runs = self.root / 'toolkit-runs'
            report = {'data_folder': str(self.root), 'labs': labs, 'labs_total': pretty(sum(l['bytes'] for l in labs)), 'toolkit_runs': pretty(dir_bytes(runs)) if runs.is_dir() else '0 MB',
                      'disk_free': pretty(usage.free), 'limits': {'max_total': pretty(self.limits.max_total), 'always_keep_free': pretty(max(self.limits.min_free, int(usage.total * RESERVE_FRACTION))), 'revisions_kept_per_lab': self.limits.keep},
                      'the_original_game_folders_are_never_touched': True}
            if action == 'report':
                report['next'] = 'To free space: modlab_cleanup with action delete_lab and a lab_id, prune_revisions, clear_toolkit_runs or remove_leftovers. Nothing is deleted without confirm=true.'
                return report
            plan = []
            if action == 'delete_lab':
                target = self.lab(lab_id)
                plan = [{'delete_lab': target.name, 'bytes': dir_bytes(target)}]
            elif action == 'prune_revisions':
                for p in ([self.lab(lab_id)] if lab_id else self.lab_dirs()):
                    try: st = self.state(p)
                    except (OSError, ValueError, KeyError): continue
                    k = max(2, keep or self.limits.keep)
                    old = st['history'][:-k] if len(st['history']) > k else []
                    plan += [{'lab': p.name, 'delete_revision': r, 'bytes': dir_bytes(p / r)} for r in old]
                    plan += [{'lab': p.name, 'delete_preserved_revision': r, 'bytes': dir_bytes(p / r)} for r in st['preserved'][:-KEEP_PRESERVED]]
            elif action == 'clear_toolkit_runs':
                plan = [{'delete_toolkit_run': r.name, 'bytes': dir_bytes(r)} for r in sorted(runs.iterdir())] if runs.is_dir() else []
            else:
                plan = [{'delete_unfinished_lab': p.name, 'bytes': dir_bytes(p)} for p in self.lab_dirs() if not (p / 'state.json').exists()]
            report.update(action=action, would_free=pretty(sum(x['bytes'] for x in plan)), plan=plan, deleted=False)
            if not confirm:
                report['next'] = 'Dry run: nothing was deleted. Repeat with confirm=true after the user agrees.'
                return report
            if action == 'delete_lab':
                shutil.rmtree(target)
            elif action == 'prune_revisions':
                for p in ([self.lab(lab_id)] if lab_id else self.lab_dirs()):
                    try: st = self.state(p)
                    except (OSError, ValueError, KeyError): continue
                    self.prune(p, st, keep); self.save(p, st)
            elif action == 'clear_toolkit_runs':
                for r in (sorted(runs.iterdir()) if runs.is_dir() else []):
                    if r.is_dir() and not r.is_symlink(): shutil.rmtree(r, ignore_errors=True)
            else:
                for p in self.lab_dirs():
                    if not (p / 'state.json').exists(): shutil.rmtree(p, ignore_errors=True)
            report['deleted'] = True
            return report

    @contextlib.contextmanager
    def locked(self):
        with locking.exclusive_lock(self.root / '.lock', 'Another ModLab operation is running'):
            yield

    def lab(self, lab_id):
        if not isinstance(lab_id, str) or len(lab_id) != 32 or any(c not in '0123456789abcdef' for c in lab_id):
            raise ValueError('Invalid lab ID')
        p = self.root / lab_id
        if not p.is_dir() or link_or_reparse(p):
            raise ValueError('Lab not found')
        return p

    def state(self, lab):
        state = json.loads((lab / 'state.json').read_text())
        state.setdefault('preserved', [])
        if not isinstance(state['history'], list) or not isinstance(state['preserved'], list):
            raise ValueError('Invalid lab state')
        for rev in state['history'] + state['preserved']:
            if len(rev) != 32 or any(c not in '0123456789abcdef' for c in rev):
                raise ValueError('Invalid lab state')
        if not state['history']:
            raise ValueError('Invalid lab state')
        return state

    def save(self, lab, state):
        tmp = lab / '.state.tmp'
        tmp.write_text(json.dumps(state))
        os.replace(tmp, lab / 'state.json')

    def create(self, source_path):
        source = globals()['source_path'](source_path)
        if not source.is_dir() or source == Path(source.anchor) or source == Path.home().resolve():
            raise ValueError('Select a specific game directory')
        if source == self.root or source in self.root.parents or self.root in source.parents:
            raise ValueError('Game and lab directories must not overlap')
        with self.locked():
            leftovers = self.remove_leftovers()
            before, size, dirs_before = tree(source)
            if size > self.limits.max_total:
                raise DiskGuard('This game is %s, larger than ModLab\'s whole size limit of %s (setting modlab_max_total_gb). Nothing was copied. Raise the limit only if you have the space.' % (pretty(size), pretty(self.limits.max_total)))
            budget = Budget(self.root, self.used_bytes(), self.limits)
            lab_id, rev = uuid.uuid4().hex, uuid.uuid4().hex
            lab = self.root / lab_id
            lab.mkdir(mode=0o700)
            try:
                dest = lab / rev
                shutil.copytree(source, dest, symlinks=True, copy_function=lambda a, b: copy_regular(a, b, budget))
                after, _, dirs_after = tree(source)
                copied, _, dirs_copied = tree(dest)
                if before != after or before != copied or dirs_before != dirs_after or dirs_before != dirs_copied:
                    raise ValueError('Source changed while copying; no lab was created')
                self.save(lab, {'history': [rev]})
            except BaseException:
                shutil.rmtree(lab, ignore_errors=True)
                raise
            return {'lab_id': lab_id, 'revision': rev, 'game_path': str(dest), 'files': len(before), 'bytes': size, 'disk_used_by_this_copy': pretty(budget.written),
                    'cloned_without_extra_space': budget.written == 0 and size > 0, 'removed_unfinished_labs': len(leftovers),
                    'disk_note': 'ModLab keeps the last %d revisions of a lab, stops before free space falls below its reserve, and never changes your original game folder. See modlab_cleanup to free space.' % self.limits.keep}

    def inspect_locked(self, lab, zip_path):
        state = self.state(lab)
        current = lab / state['history'][-1]
        files, size, directories = tree(current)
        path = source_path(zip_path)
        if path == self.root or self.root in path.parents:
            raise ValueError('Keep ZIPs outside the lab data directory')
        zip_before = digest(path)
        entries, unpacked = archive(path)
        if digest(path) != zip_before:
            raise ValueError('ZIP changed during inspection')
        folded = {x.casefold(): x for x in files}
        if len(folded) != len(files):
            raise ValueError('Game has case-colliding files')
        components = {}
        for name in [*files, *directories]:
            path = PurePosixPath(name)
            for component in (path, *path.parents):
                text = str(component)
                if text == '.': continue
                key = text.casefold()
                if key in components and components[key] != text:
                    raise ValueError('Game has case-colliding paths')
                components[key] = text
        for name in entries:
            path = PurePosixPath(name)
            for component in (path, *path.parents):
                text = str(component)
                if text != '.' and text.casefold() in components and components[text.casefold()] != text:
                    raise ValueError('ZIP path differs in case from an existing path')
            for parent in PurePosixPath(name).parents:
                if str(parent) != '.' and str(parent).casefold() in folded:
                    raise ValueError('ZIP path collides with an existing file parent')
            if name.casefold() in folded and name != folded[name.casefold()]:
                raise ValueError('ZIP path differs in case from an existing file')
            if (current / name).is_dir():
                raise ValueError('ZIP file collides with an existing directory')
        evidence = {'revision': state['history'][-1], 'files': files, 'directories': directories, 'zip': zip_before}
        token = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        return {'revision': state['history'][-1], 'game_path': str(current), 'inspection': token,
                'replacements': [x for x in entries if x in files], 'additions': [x for x in entries if x not in files],
                'current_bytes': size, 'zip_unpacked_bytes': unpacked}

    def inspect(self, lab_id, zip_path):
        with self.locked():
            return self.inspect_locked(self.lab(lab_id), zip_path)

    def apply(self, lab_id, zip_path, inspection, allow_replacements=False):
        if not isinstance(allow_replacements, bool):
            raise ValueError('allow_replacements must be boolean')
        with self.locked():
            lab = self.lab(lab_id)
            plan = self.inspect_locked(lab, zip_path)
            if inspection != plan['inspection']:
                raise ValueError('Inspection is stale; inspect again')
            if plan['replacements'] and not allow_replacements:
                raise ValueError('ZIP replaces existing files; explicit allow_replacements is required')
            budget = Budget(self.root, self.used_bytes(), self.limits)
            state = self.state(lab)
            old = lab / state['history'][-1]
            rev = uuid.uuid4().hex
            dest = lab / rev
            try:
                original = tree(old)
                shutil.copytree(old, dest, symlinks=True, copy_function=lambda a, b: copy_regular(a, b, budget))
                budget.charge(plan['zip_unpacked_bytes'])
                if tree(old) != original or tree(dest) != original:
                    raise ValueError('Revision changed while copying; inspect again')
                # Recheck the archive against the inspection before using it.
                path = source_path(zip_path)
                with zipfile.ZipFile(path) as z:
                    for name in plan['replacements'] + plan['additions']:
                        target = dest / name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with z.open(name) as src, target.open('wb') as out:
                            shutil.copyfileobj(src, out, 1024 * 1024)
                if self.inspect_locked(lab, zip_path)['inspection'] != inspection:
                    raise ValueError('ZIP or current revision changed while applying; inspect again')
                state['history'].append(rev)
                pruned = self.prune(lab, state)
                self.save(lab, state)
            except BaseException:
                shutil.rmtree(dest, ignore_errors=True)
                raise
            return {'revision': rev, 'game_path': str(dest), 'previous_revision': state['history'][-2], 'disk_used_by_this_revision': pretty(budget.written),
                    'old_revisions_deleted': len(pruned), 'disk_freed_by_pruning': pretty(sum(x['bytes'] for x in pruned))}

    def rollback(self, lab_id):
        with self.locked():
            lab = self.lab(lab_id)
            state = self.state(lab)
            if len(state['history']) < 2:
                raise ValueError('No earlier revision')
            previous = state['history'].pop()
            target = lab / state['history'][-1]
            if not target.is_dir() or target.is_symlink():
                raise ValueError('Earlier revision is missing')
            state['preserved'].append(previous)
            self.save(lab, state)
            return {'revision': state['history'][-1], 'game_path': str(target), 'preserved_revision': previous}

    def select_preserved(self, lab_id, revision):
        with self.locked():
            lab = self.lab(lab_id)
            state = self.state(lab)
            if not isinstance(revision, str) or revision not in state['preserved']:
                raise ValueError('Revision is not a recorded preserved revision')
            target = lab / revision
            if not target.is_dir() or target.is_symlink(): raise ValueError('Preserved revision is missing')
            tree(target)
            state['preserved'].remove(revision)
            state['history'].append(revision)
            self.save(lab, state)
            return {'revision': revision, 'game_path': str(target),
                    'notice': 'The preserved directory may have been modified externally; inspect it before use.'}
