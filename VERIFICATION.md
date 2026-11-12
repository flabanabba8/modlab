# Verification

- Mixed-case private-directory boundaries were checked using synthetic paths on Linux and native Windows; no real credentials were used.

- Twelve synthetic Linux tests passed for guarded ZIP application, replacement consent, file identity, rollback, preserved revision selection, locking, safe timestamp fallback and a self-authored executable fixture.
- An initial native Windows run failed because `utime` lacked no-follow support. After the safe fallback, native Windows synthetic copy, replacement approval, rollback, root and nested junction rejection, cross-process locking and writable copies of read-only source files passed. Timestamps are not preserved where safe no-follow updates are unavailable; Windows ACLs and adversarial symlink races were not tested.
- A separate read-only test copied an existing local game distribution into a temporary lab, applied a synthetic marker file to a new revision, rolled back and verified the original executable's hash was unchanged. The game was not launched and no original installation was modified.
- This file-handling check does not establish that a copied game launches, that a real mod works, or that external saves and installers are handled. Broader Windows behavior, a reviewed demonstration and the full publication audit remain unverified.

## 0.3.1 - maintainer review (2026-11-12)

Maintainer review. um_executable and rea_executable are owner settings, not tool arguments; modlab_toolkit asks for approval; toolkit subprocesses get a minimal environment; a bug that left toolkit-run output unpruned is fixed. Re-tested: 64 offline tests, all passing; plugin preflight reports no findings.

Live test through Hermes 0.23.0 (2026-11-12, own profile) on a real game folder: interview, lab created (107 MB), inspect, apply, rollback, cleanup dry run with the limits shown; the real um binary ran with a clean environment. Found and fixed: approval was asked before the interview had been done.

## 2026-11-10 maintained scope revision

Fifteen tests pass: existing isolated revision tests plus blocked retired/publication/setup routes and actual installed UM/REA read-only help calls, plus native original-result/context preservation and recursive-backend refusal. No new game modification/build was performed; these checks do not prove every toolkit provider/platform. Hermes admission and retirement preflight pass; detailed local receipts are retained in the contest maintenance evidence. Old evidence above keeps its original scope.

## 0.3.0 - scan, ask, never pick; and ModLab can no longer fill a disk (2026-11-12)

- Disk safety (a lab is a full copy of a game): ModLab now checks free space and its own total cap before writing every file, stops and removes its own partial work if a copy would pass the reserve (10 GB or 10 percent of the disk, whichever is larger) or the cap (default 25 GB), uses copy-on-write clones where the filesystem supports them (not on ext4, which this machine uses), keeps only the last 2 revisions of a lab, prunes toolkit output to 20 runs / 64 MB, removes unfinished lab folders left by a crash, and adds `modlab_cleanup` (report; dry-run-first deletion; only inside ModLab's own folder; only with confirm=true). Before this change every apply copied the whole game again, every revision was kept forever and the only guard was "free space at least twice the game". Settings: `modlab_max_total_gb`, `modlab_min_free_gb`, `modlab_keep_revisions`. A test fails the build if the shipped plugin grows big files or archives.
- New `modlab_setup`: scans the computer (installed modding tools, installed Steam games with duplicates, runtime components and unmounted libraries handled), identifies the engine and any anti-cheat of a chosen game folder by file signatures, lists the modding routes found for that engine with what each needs and what is missing, asks the user, and saves the route the user picked. ModLab never picks a route. `modlab_toolkit` and `modlab_create` return the interview until it is answered.
- New wiki `llmwiki/modding-routes.md` and `modding_catalog.json`: 12 engines, 18 routes, 39 tools, anti-cheat statements and upload rules, each with source and date (read 2026-11-12); RPG Maker, Creation Kit and several signatures are marked UNVERIFIED or "convention". Knowledge freshness: stale after 30 days or a passed deadline, and the plugin offers online research only if the user says yes; approved research is stored as dated overrides.
- Tested here: 57 Python tests (Game Lab's copy: 121). The engine scan was run on a real Steam library of 20 games on this machine and corrected three times from the result (nested game folders, Source 2 two levels deep, Godot with an embedded pack). Not tested: the game-folder scan on Windows or macOS, any loader install, or any mod run.
