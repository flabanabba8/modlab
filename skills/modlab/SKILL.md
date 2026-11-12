---
name: modlab
description: Build and test game mods from an idea using Universal Modder and Reverse Engineer Anything, including recon, assets, safe revisions and showcase capture.
---

## First use: scan, ask, never pick the route

Do not choose a modding route for the user. `modlab_toolkit` and `modlab_create` return the interview until it is answered. Run `modlab_setup` first:

1. Show what it found: installed modding tools, the Steam games on this computer (pick one or give a folder), and for the chosen game folder the engine it looks like, any anti-cheat, and the routes found for that engine with what each needs and what is missing. Say how mature each route is (status, source and date) and that unverified items are unverified.
2. Ask in one short message which game, what the mod should do, whether it is offline single-player only, their experience, whether they will share it publicly and whether AI-made art or audio is OK, what they already have or will install, and which route they want. Install nothing and start no game without their yes.
3. Read `knowledge_freshness`: if the built-in modding knowledge looks stale, tell the user and ask whether you should research the current facts online. Never research without their yes; save only what you verified with `knowledge_updates`.
4. Save the answers (including the route they picked) with `modlab_setup`, then continue.

## Disk safety

A lab is a full copy of a game and can be many gigabytes. Check `modlab_cleanup` (report) before creating a lab for a large game, tell the user the size and the free space, and never raise `modlab_max_total_gb` or `modlab_min_free_gb` yourself. If ModLab stops with a disk message, do not retry in a loop: show the user the report and offer cleanup. Deletion is a dry run until the user agrees and you pass `confirm=true`.

Read the [bundled wiki](../../llmwiki/index.md). Identify the owned game/version, engine/platform, desired change and safe test installation. modlab_resources locates actual Universal Modder/REA CLIs; presence is not provider readiness. Use modlab_toolkit for one explicit supported operation or modlab_rea_native for a configured native REA tool. Inspect selected toolkit help/contracts before acting. Use REA for shipped artifacts/runtime evidence; ordinary source reading needs no reverse-engineering server.

Take the goal through recon → actual modding route → isolated lab → first playable change → real-game test → useful showcase. Generate/review assets with main-session native image tools. Universal Modder handles supported scan, asset preparation, rendering/capture, backup and release-inspection routes. REA handles the applicable native/managed/packaged formats and connected runtime capabilities. Do not claim every game or provider works merely because the CLI exists.

The modlab_create/inspect/apply/rollback/select_preserved tools provide full-copy ZIP revisions when that format fits. They support the broader toolkit rather than defining the entire product. For loaders, patching, scripts or injection, establish the game's real contract first. Do not touch live saves/anti-cheat sessions or call unsupported copy operations a verified mod. Publication and toolkit/client installation remain outside these adapters.

Start from the user's intended result. Reuse known resource choices; ask missing questions only in ordinary chat. Establish hardware, available local/remote tools, subscriptions versus verified API entitlements, privacy, acceptable waiting time and maximum API spend (zero is valid). Prefer free paths that meet quality needs. A subscription does not prove API access. Save non-secret choices in the private task, never credentials. Do not silently install/download, upload private inputs, switch providers or spend money. Reason/write in the active host; no secondary reasoning API or agent worker. Images are inspected/generated/edited directly in the MAIN session using native tools. Preserve accepted work, pauses and original inputs. Publishing requires separate explicit authorization.
