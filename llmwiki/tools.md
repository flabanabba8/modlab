# Actual tool contracts

Registered source schemas; registration alone does not establish live backend readiness.

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

