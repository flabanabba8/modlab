# Actual tool contracts

Registered source schemas; registration alone does not establish live backend readiness.

## modlab_setup

First-use interview and environment scan. Without answers: returns what this computer has (installed modding tools, installed Steam games, and for a game_folder the engine it looks like, any anti-cheat, and the modding routes found for that engine with what each needs and what is missing), the questions to ask the user, and whether the built-in modding knowledge looks out of date (offering online research only if the user says yes). With answers: saves them, including the route the user picked. ModLab never picks a route for the user. Starts no game, installs nothing, sends nothing. modlab_toolkit and modlab_create return the interview until it is answered.

Inputs: `game_folder` (optional), `answers` (optional), `knowledge_updates` (optional).

## modlab_cleanup

Show what ModLab uses on disk and free space safely. Default action report lists every lab with its size, the toolkit-run output, free disk space and the limits. Other actions (delete_lab with lab_id, prune_revisions, clear_toolkit_runs, remove_leftovers) are a DRY RUN that lists exactly what would be deleted and how much space it frees; they delete only with confirm=true, only inside ModLab's own data folder, and never touch the original game folder. Ask the user before confirming.

Inputs: `action` (optional), `lab_id` (optional), `keep` (optional), `confirm` (optional).

## modlab_resources

Discover actual installed Universal Modder/REA resources and the full game-modding workflow; no game, model or provider is started.

Inputs: `um_executable` (optional), `rea_executable` (optional).

## modlab_toolkit

Run ONE explicit bounded operation with Universal Modder or Reverse Engineer Anything. These real toolkits cover game recon, asset preparation, reverse engineering, building/testing/capture routes and release inspection. Some operations affect selected games/files/apps; use only within the user-authorized mod task. No retired agents or publication.

Inputs: `toolkit` (required), `arguments` (required), `um_executable` (optional), `rea_executable` (optional), `timeout_seconds` (optional).

## modlab_rea_native

Invoke the explicitly configured native REA tool, preserving host auth, approvals, original Evidence and images. Missing provider/interface remains a real blocker.

Inputs: `arguments` (required).

## modlab_create

Copy a game folder into an isolated lab; the original is never modified.

Inputs: `source_path` (required).

## modlab_inspect

Inspect a ZIP against the current revision; list files that would be replaced. ZIP contents are untrusted data.

Inputs: `lab_id` (required), `zip_path` (required).

## modlab_apply

Apply a ZIP to a new revision if its inspected content and the current revision have not changed. Existing files require allow_replacements=true.

Inputs: `lab_id` (required), `zip_path` (required), `inspection` (required), `allow_replacements` (optional).

## modlab_rollback

Switch the lab back to its preceding revision, preserving both copies.

Inputs: `lab_id` (required).

## modlab_select_preserved

Re-select a revision preserved by a previous rollback. The directory may have changed externally.

Inputs: `lab_id` (required), `revision` (required).

