# ModLab

Create an isolated working copy of a game folder, review the files a ZIP mod would replace, apply it to a new full-copy revision, and roll back to the preceding revision. The selected game folder is read but never deliberately modified. No game or mod code is executed.

1. Ask Hermes to create a lab from a specific local game folder. The result includes the working `game_path` and a lab ID.
2. Ask it to inspect a local ZIP against that lab. Review its additions and replacements. The returned inspection identifies the exact current content and ZIP.
3. Apply with that inspection. Set `allow_replacements` only after reviewing replacements. If the ZIP or any file in the current revision changes, inspect again.
4. Roll back to select the preceding revision; the newer copy is retained. Use the returned path when launching a game yourself. A revision preserved by a rollback can be explicitly reselected; inspect it first because its files may have changed outside ModLab. Rollbacks made by older versions did not record the preserved revision for reselection.

Each revision is a full copy. Expect substantial local disk and hashing time; use a game that runs from a copied folder. Locked files, launchers, DRM, saves outside the folder, installers, symbolic links, extended file metadata and platform-specific integrations may prevent a copy from working. Regular-file hashing and copying refuse final symlinks and reject changed or atomically replaced files; copying preserves file mode and timestamps; it is not an adversarial filesystem sandbox. This prototype supports ordinary ZIP file overlays only: it does not resolve logical mod conflicts, run installers, track external saves, or guarantee that a game launches. Rolling back switches the selected directory; it does not stop an already-running game. ZIPs and game files are untrusted data.

Tested on Linux with synthetic local folders, including a small executable fixture run from the original, modified and rolled-back copies. No real game or Windows test has been completed. Private data and revisions reside in the Hermes plugin data directory, and persist until removed by the user. Do not share a lab directory without reviewing its contents.
