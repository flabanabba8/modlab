# modlab: setup and task guide

Source-reviewed 2026-11-09. Use [actual schemas](contracts.json) for argument details.

## Choose tools from the game contract

Discover the installation, engine/version, managed versus native code, loaders, offline test mode and save location before designing a hook. A data-file replacement can need only a copy lab and archive tools. A managed game may need a selected compatible loader and assembly inspection. A native or packaged target may need REA static analysis and an actual runtime adapter. Universal Modder and REA are optional installed tools, not bundled private distributions. Their platform/provider capabilities differ; use operation-specific evidence and preserve original structured native observations/images.

## Worked modding flow

For a requested crossover character, establish where character definitions, dialogue, sprites and portraits actually live. Use modlab_resources and toolkit --help, then the supported scan/analysis operation for this version. Keep originals and saves; modlab_create is suitable for a full-copy file-mod lab if sufficient disk exists. Author the data/code and create complete assets using the selected native main-session tools. Prepare exact engine formats with the toolkit's asset commands. Inspect the ZIP manifest/conflicts with modlab_inspect; apply only its unchanged inspection token and explicit replacements. Loader-based changes need their own supported build/install route in the lab.

Launch the actual offline game in its supported runtime, exercise the changed character and unrelated regression scenes, then capture only its window/audio. A successful archive or file hash is not an in-game result. Retain source, build evidence, screenshots/video and rollback. Universal Modder's publish check is release inspection; publishing or KB PRs are not allowed through this interface.

## Diagnose and accept

Missing executable: choose the available native REA interface or record that toolkit's exact unavailable capability. Missing provider/platform backend: keep independent source and copy-lab work usable; do not install/configure it silently. Browser fails on an NW.js game: use its genuine runtime rather than shimming away integrity or claiming web support. Conflicting ZIP: inspect replacements, never erase originals. Changed inspection/source: re-inspect once with the changed contract. Acceptance needs a working feature in the real game, a preserved rollback and an honest result video; checkpoint creation alone is not a mod.

Read the [verification record](../VERIFICATION.md) for dated tested scope. This guide does not install tools or claim new live execution.

## Disk safety (read this: a lab is a full copy of a game)

A lab holds real copies of a game folder, which can be many gigabytes. ModLab therefore:

- never lets free disk space fall below a reserve (10 GB or 10 percent of the disk, whichever is larger; setting `modlab_min_free_gb`) and checks before every file it writes, so a copy that would breach it stops and removes its own partial work;
- keeps all labs together under a total cap (default 25 GB; setting `modlab_max_total_gb`) and refuses a game larger than the cap before copying a byte;
- uses copy-on-write cloning when the filesystem supports it (Btrfs, XFS, APFS), so a new revision costs almost no space; on ext4 and NTFS it makes real copies, so the cap matters;
- keeps only the last revisions of a lab (default 2, the current one and the one before for rollback; setting `modlab_keep_revisions`) and deletes older ones after each apply; your original game folder is never touched, so the pristine copy is always the game itself;
- keeps toolkit output to the newest 20 runs and 64 MB, and removes unfinished lab folders left by a crash;
- offers `modlab_cleanup`: a report of what ModLab uses, and dry-run-first deletion that only ever touches ModLab's own data folder and only with `confirm=true`. Tell the user what it would delete and free before confirming.

The shipped plugin contains no game files, archives or lab data (a test enforces a small release).
