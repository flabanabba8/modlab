"""Local, full-copy revisions; no game process or source directory is modified."""
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import uuid
import zipfile
from . import locking

MAX_FILES = 100_000
MAX_BYTES = 50 * 1024**3
MAX_ZIP_FILES = 10_000
MAX_ZIP_BYTES = 2 * 1024**3
PRIVATE = {'.ssh', '.gnupg', '.aws', '.azure', '.codex', '.docker', '.kube', '.pki', '.config', '.hermes'}


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


def copy_regular(source, destination):
    """Copy a regular file, rejecting symlinks and detecting identity changes."""
    if link_or_reparse(source): raise ValueError('Symlinks and reparse points are unsupported')
    fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        with os.fdopen(fd, 'rb', closefd=False) as src:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Only regular files can be copied')
            with open(destination, 'xb') as dst:
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


class Lab:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

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
            before, size, dirs_before = tree(source)
            if shutil.disk_usage(self.root).free < size * 2 + 16 * 1024**2:
                raise ValueError('Not enough free space for the copy and a subsequent revision')
            lab_id, rev = uuid.uuid4().hex, uuid.uuid4().hex
            lab = self.root / lab_id
            lab.mkdir(mode=0o700)
            try:
                dest = lab / rev
                shutil.copytree(source, dest, symlinks=True, copy_function=copy_regular)
                after, _, dirs_after = tree(source)
                copied, _, dirs_copied = tree(dest)
                if before != after or before != copied or dirs_before != dirs_after or dirs_before != dirs_copied:
                    raise ValueError('Source changed while copying; no lab was created')
                self.save(lab, {'history': [rev]})
            except BaseException:
                shutil.rmtree(lab, ignore_errors=True)
                raise
            return {'lab_id': lab_id, 'revision': rev, 'game_path': str(dest), 'files': len(before), 'bytes': size}

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
            if shutil.disk_usage(lab).free < plan['current_bytes'] + plan['zip_unpacked_bytes'] + 16 * 1024**2:
                raise ValueError('Not enough free space for a new revision')
            state = self.state(lab)
            old = lab / state['history'][-1]
            rev = uuid.uuid4().hex
            dest = lab / rev
            try:
                original = tree(old)
                shutil.copytree(old, dest, symlinks=True, copy_function=copy_regular)
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
                self.save(lab, state)
            except BaseException:
                shutil.rmtree(dest, ignore_errors=True)
                raise
            return {'revision': rev, 'game_path': str(dest), 'previous_revision': state['history'][-2]}

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
