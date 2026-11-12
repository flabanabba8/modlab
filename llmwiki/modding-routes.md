---
status: SOURCE-DERIVED (tool repositories, engine docs and vendor pages read on 2026-11-12; nothing here was run by us except the Steam and engine-signature scan, which was tested on a real library)
curated: 2026-11-12
---
# Modding routes by engine: how ModLab recognises a game and what each route needs

Read this before recommending a route. It is what `modlab_setup` draws its suggestions from (`modding_catalog.json`, the same data). **ModLab never picks a route
for the user:** it scans, lists the routes found for the detected engine with what each needs and what is missing, asks, and uses only the route the user chose.

Release dates, versions and statuses change often; every row carries its source link and the date it was read (2026-11-12). Re-open the link before quoting a version.
UNVERIFIED means no primary page confirmed it. Signatures marked *convention* are widely used file names that no primary page confirmed in our research:
they only suggest an engine, the user confirms. When matched files sit in a subfolder the setup says so, because that can be a bundled tool, not the game.

## 1. Engines, how they are recognised, and their routes

### Unity (Mono)

Recognised by (at least 2 of): `UnityPlayer.dll`, `UnityPlayer.so`, `*_Data/Managed`, `*/UnityPlayer.dll` (convention), `*/*_Data/Managed` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| BepInEx plugin (Mono) | loader | BepInEx, .NET SDK / runtime | any | maintained; stable releases exist for Unity Mono on Windows, macOS and Linux | Use the x86 build for 32-bit games, x64 for 64-bit; macOS supports 64-bit only. Under Proton use the Windows build with WINEDLLOVERRIDES="winhttp.dll=n,b" %command%. | https://github.com/BepInEx/BepInEx |
| MelonLoader mod (Mono) | loader | MelonLoader, .NET SDK / runtime | any | maintained | Windows, Linux (native, Wine, Proton) and macOS per its docs. Proton launch option WINEDLLOVERRIDES="version=n,b" %command%. | https://github.com/LavaGang/MelonLoader |
| Edit assets (AssetRipper / UnityPy / UABEA) | data | AssetRipper, UnityPy | any | maintained | Extract, change and repack assets without code. | https://github.com/AssetRipper/AssetRipper |

Reverse-engineering and asset tools: ILSpy / ilspycmd, dnSpyEx, AssetRipper. Data-only option: Config files via BepInEx/config; asset extraction and repack with AssetRipper or UnityPy. Pitfalls: 32-bit vs 64-bit loader build must match the game; Online games with anti-cheat reject modified files

### Unity (IL2CPP)

Recognised by (at least 2 of): `UnityPlayer.dll`, `UnityPlayer.so`, `GameAssembly.dll`, `GameAssembly.so`, `*_Data/il2cpp_data`, `*/GameAssembly.dll` (convention), `*/*_Data/il2cpp_data` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| MelonLoader mod (Il2Cpp) | loader | MelonLoader, .NET SDK / runtime | any | maintained; recommended first for IL2CPP | Needs the .NET 6 Desktop Runtime. Under Proton install it with "protontricks <appid> dotnetdesktop6" and prefer a clean prefix. | https://github.com/LavaGang/MelonLoader |
| BepInEx IL2CPP | loader | BepInEx, .NET SDK / runtime | windows, linux | only via Bleeding Edge builds; docs and README disagree (build dates UNVERIFIED) | README says only Unity Mono has stable releases; IL2CPP is Windows and Linux, not macOS. | https://github.com/BepInEx/BepInEx |
| Edit assets (AssetRipper / UnityPy / UABEA) | data | AssetRipper, UnityPy | any | maintained | - | https://github.com/AssetRipper/AssetRipper |

Reverse-engineering and asset tools: Cpp2IL, Il2CppDumper, AssetRipper, Ghidra. Data-only option: Asset extraction and repack with AssetRipper or UnityPy. Pitfalls: Cpp2IL has only pre-release builds; Il2CppDumper is stale; IL2CPP loader support is less stable than Mono

### Unreal Engine 4/5

Recognised by (at least 2 of): `*/Binaries/Win64` (convention), `*/Content/Paks` (convention), `*/Content/Paks/*.pak` (convention), `*/Content/Paks/*.utoc` (convention), `Engine` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| UE4SS scripting mods | loader | UE4SS | windows | maintained (v4.0.0); native Linux builds unsupported, no Proton guidance in its docs | Installs into {game}/GameName/Binaries/Win64 as a dwmapi.dll proxy; the top-level exe is a launcher wrapper. Expect per-game fixes. | https://github.com/UE4SS-RE/RE-UE4SS |
| Browse and repack assets (FModel / repak / UAssetGUI) | data | FModel, repak, UAssetGUI | any | maintained | Pak files may be AES-encrypted or signed (Epic project settings); IoStore (.utoc/.ucas) is a different container. | https://github.com/trumank/repak |

Reverse-engineering and asset tools: FModel, UAssetGUI, repak, Ghidra. Data-only option: Replace or add .pak contents with repak after unpacking; encrypted paks need the AES key. Pitfalls: Easy Anti-Cheat blocks modified files in protected multiplayer; Encrypted or signed paks cannot be edited without the key

### Godot

Recognised by (at least 1 of): `*.pck`, `*godot*` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Patch pack (.pck / .zip) loaded by the game | data | nothing extra | any | official Godot feature (ProjectSettings.load_resource_pack / --main-pack) | Works only if the game loads extra packs; check with GDRE Tools first. | https://docs.godotengine.org/en/stable/tutorials/export/exporting_pcks.html |
| Inspect or recover the project (GDRE Tools) | re | GDRE Tools (gdsdecomp) | any | maintained (v2.7.4) | Godot 2, 3 and 4; encrypted PCKs need the key. | https://github.com/GDRETools/gdsdecomp |

Reverse-engineering and asset tools: GDRE Tools (gdsdecomp). Data-only option: Patch PCK or ZIP resource packs. Pitfalls: A pack can be embedded in the exe (no .pck file); the Godot 3 vs 4 pack-format mapping is UNVERIFIED; Encrypted PCKs

### Ren'Py

Recognised by (at least 2 of): `renpy`, `game/*.rpyc`, `game/*.rpa`

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Edit scripts (unrpa + unrpyc, or add .rpy files) | data | unrpa, unrpyc, Python 3 | any | unrpyc active; unrpa stale | unrpa extracts .rpa archives; unrpyc decompiles .rpyc (it does not extract archives). Ren'Py reads loose .rpy files placed in game/. | https://github.com/CensoredUsername/unrpyc |

Reverse-engineering and asset tools: unrpa, unrpyc. Data-only option: Loose .rpy/.rpyc files and replacement assets in game/. Pitfalls: unrpa has not had a release since 2019

### GameMaker

Recognised by (at least 1 of): `data.win`, `game.ios`, `game.unx`, `game.droid`

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| UndertaleModTool (edit data.win) | re | UndertaleModTool, .NET SDK / runtime | windows, any | maintained (0.9.2.0); GUI Windows only, CLI on Windows/Ubuntu/macOS | No official GUI on Linux/macOS: use the CLI, a WIP cross-platform port, or Wine. | https://github.com/UnderminersTeam/UndertaleModTool |

Reverse-engineering and asset tools: UndertaleModTool. Data-only option: Edit sprites, text and code inside data.win with the tool. Pitfalls: Runner exe name is not documented; detect by the data file

### Electron / NW.js

Recognised by (at least 1 of): `resources/app.asar`, `resources/app.asar.unpacked`, `package.nw`, `nw.exe`

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Unpack app.asar, edit JavaScript, repack | data | Node.js | any | standard Electron tooling | Keep app.asar.unpacked beside it. NW.js apps are package.nw (a zip) or loose files with package.json. | https://github.com/electron/electron/blob/main/docs/tutorial/asar-archives.md |

Reverse-engineering and asset tools: Node.js. Data-only option: Edit the JavaScript and JSON data directly. Pitfalls: RPG Maker MV/MZ games are NW.js apps

### LÖVE (Love2D)

Recognised by (at least 1 of): `*.love`, `love.dll`, `lua51.dll`

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Edit the .love archive (a zip with main.lua) | data | nothing extra | any | documented format | A fused Windows exe is love.exe + the .love zip appended; unzip the exe to reach the Lua files. | https://love2d.org/wiki/Game_Distribution |

Reverse-engineering and asset tools: none listed. Data-only option: Lua source and assets inside the zip. Pitfalls: none listed.

### Source / Source 2

Recognised by (at least 1 of): `gameinfo.txt`, `*/gameinfo.txt`, `liblist.gam`, `*/gameinfo.gi`, `*/*/gameinfo.gi` (convention), `*/*_dir.vpk`, `*/*/pak01_dir.vpk` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Loose files or custom content via gameinfo SearchPaths and VPK | data | nothing extra | any | documented on the Valve Developer Community | gameinfo.txt (Source), gameinfo.gi (Source 2) and liblist.gam (GoldSrc) set the search order. Source 2 Workshop Tools details are UNVERIFIED. | https://developer.valvesoftware.com/wiki/Gameinfo.txt |

Reverse-engineering and asset tools: none listed. Data-only option: Custom content folders and VPK repacking. Pitfalls: VAC bans modifications to executables and DLLs on VAC-secured servers

### RPG Maker (MV, MZ, XP, VX, VX Ace)

Recognised by (at least 1 of): `www/js/rpg_core.js` (convention), `js/rmmz_core.js` (convention), `Game.ini` (convention), `Data/*.rxdata` (convention), `Data/*.rvdata2` (convention), `RGSS*.dll` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Edit data and scripts (JSON / JavaScript for MV and MZ; Ruby scripts for XP/VX/Ace) | data | nothing extra | any | UNVERIFIED: no official RPG Maker page was reachable in research | MV and MZ games run on NW.js, so the Electron/NW.js route also applies. Treat file names and routes as unconfirmed; check the RPG Maker documentation. | https://github.com/nwjs/nw.js |

Reverse-engineering and asset tools: none listed. Data-only option: JSON data files and plugin scripts (MV/MZ). Pitfalls: All RPG Maker facts here are UNVERIFIED

### Bethesda Creation Engine (Skyrim, Fallout 4)

Recognised by (at least 1 of): `Data/Skyrim.esm` (convention), `Data/Fallout4.esm` (convention), `Data/SkyrimSE.esm` (convention)

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| SKSE / F4SE with Mod Organizer 2 or Vortex, xEdit for plugins | loader | SKSE / F4SE, Mod Organizer 2, xEdit (TES5Edit) | windows | updated per game patch (SKSE page carries a warning dated 2026-08-14 about an incoming Skyrim update) | Match the script extender build to the exact game version. Creation Kit basics were UNVERIFIED in research. | https://skse.silverlock.org/ |

Reverse-engineering and asset tools: xEdit (TES5Edit). Data-only option: Plugins (.esp/.esm) and loose assets via a mod manager. Pitfalls: A game update breaks script-extender mods until they are updated

### Native game with no known mod support (fallback)

Recognised by (at least 1 of): none: used when no other engine matches

| Route | Kind | Needs | Platforms | Status | Notes | Source |
|---|---|---|---|---|---|---|
| Reverse engineering: Ghidra / x64dbg / Frida / RenderDoc | re | Ghidra, Frida | any | maintained tools (Cheat Engine last release 2023) | Use only on a game you own, offline; run the game-recon step first to identify the engine. | https://github.com/NationalSecurityAgency/ghidra |

Reverse-engineering and asset tools: Ghidra, Frida, x64dbg, RenderDoc. Data-only option: Look for loose data files before touching the executable. Pitfalls: Modifying executables is blocked by most anti-cheat

## 2. Tools

| Tool | What it is | Status | Licence | Detected on PATH as | Source |
|---|---|---|---|---|---|
| .NET SDK / runtime | builds and runs C# mod loaders and tools (MelonLoader Il2Cpp needs the .NET 6 desktop runtime; UndertaleModTool builds on .NET 10) | - | - | dotnet | https://github.com/dotnet/sdk |
| Python 3 | runs UnityPy, unrpa, unrpyc, Frida scripts and most asset tools | - | - | python3, python | https://www.python.org/downloads/ |
| Java (JDK) | needed by Minecraft loaders and Java/Kotlin build tools | - | - | java | https://adoptium.net/ |
| Node.js | runs and unpacks Electron/NW.js game scripts | - | - | node | https://nodejs.org/ |
| Git | version control for mod source | - | - | git | https://git-scm.com/ |
| Wine | runs Windows loaders and tools on Linux | - | - | wine | https://www.winehq.org/ |
| protontricks | installs Windows components (for example dotnet) into a Steam Proton prefix | - | - | protontricks | https://github.com/Matoking/protontricks |
| Universal Modder | ModLab's game-modding toolkit (scan, sprite, render3d, video, win, backup, kb, publish groups) | - | - | um | https://github.com/ |
| Reverse Engineer Anything (REA) | reverse-engineering toolkit used by ModLab (analysis operations only) | - | - | rea | https://github.com/ |
| BepInEx | Unity (and some .NET) mod loader; 5.4.23.6 stable (2026-10-23); stable releases are Unity Mono only | maintained (v5.4.23.6, 2026-10-23; v6 only pre-release) | LGPL-2.1 | not on PATH (lives in the game folder or is a library) | https://github.com/BepInEx/BepInEx |
| MelonLoader | Unity Mono and IL2CPP mod loader; Wine/Proton and native Linux supported | maintained (v0.7.3, 2026-05-14) | Apache-2.0 | not on PATH (lives in the game folder or is a library) | https://github.com/LavaGang/MelonLoader |
| UE4SS | Unreal Engine 4/5 scripting and modding loader (Windows binaries; native Linux builds unsupported) | maintained (v4.0.0, 2026-11-12) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/UE4SS-RE/RE-UE4SS |
| Harmony / HarmonyX | runtime patching library for .NET mods | maintained (Harmony 2.4.3, 2026-10-11) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/pardeike/Harmony |
| dnSpyEx | .NET decompiler and debugger (Windows) | maintained (v6.6.0, 2026-06-20) | GPL-3.0 | not on PATH (lives in the game folder or is a library) | https://github.com/dnSpyEx/dnSpy |
| ILSpy / ilspycmd | .NET decompiler (cross-platform CLI ilspycmd) | maintained (v11.2, 2026-10-27) | MIT | ilspycmd | https://github.com/icsharpcode/ILSpy |
| Cpp2IL | recovers .NET metadata from IL2CPP games | active, pre-release builds only (latest non-pre-release is from 2022) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/SamboyCoding/Cpp2IL |
| Il2CppDumper | dumps IL2CPP metadata (older tool) | stale (last release 2024-07) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/Perfare/Il2CppDumper |
| AssetRipper | extracts Unity assets and projects (Unity 3.5 to 6000.4) | maintained (2.0.0, 2026-08-24) | GPL-3.0 | not on PATH (lives in the game folder or is a library) | https://github.com/AssetRipper/AssetRipper |
| UnityPy | Python library to read and write Unity asset bundles | maintained (push 2026-10-05) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/K0lb3/UnityPy |
| UABEA | Unity asset bundle editor | low activity (v8, 2024-11) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/nesrak1/UABEA |
| FModel | Unreal asset browser and exporter | maintained (2026-10-31) | GPL-3.0 | not on PATH (lives in the game folder or is a library) | https://github.com/4sval/FModel |
| UAssetGUI | edits Unreal .uasset files | maintained (v1.1.0, 2026-05-01) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/atenfyr/UAssetGUI |
| repak | library and CLI for Unreal .pak files (list, unpack, pack, --aes-key); does not mention IoStore | maintained (v0.2.3, 2026-01-02) | Apache-2.0 | repak | https://github.com/trumank/repak |
| GDRE Tools (gdsdecomp) | recovers and extracts Godot PCK/EXE/APK (Godot 2, 3, 4; --key for encrypted packs) | maintained (v2.7.4, 2026-10-11) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/GDRETools/gdsdecomp |
| unrpa | extracts Ren'Py .rpa archives | stale (last release 2019, Python 3.7+) | GPL-3.0 | unrpa | https://github.com/Lattyware/unrpa |
| unrpyc | decompiles Ren'Py .rpyc scripts | active (v2.0.4, 2026-02-24) | see repo | not on PATH (lives in the game folder or is a library) | https://github.com/CensoredUsername/unrpyc |
| UndertaleModTool | edits GameMaker data.win/game.* files (GUI Windows only; CLI for Windows, Ubuntu, macOS) | maintained (0.9.2.0, 2026-08-23; push 2026-11-12) | see repo | not on PATH (lives in the game folder or is a library) | https://github.com/UnderminersTeam/UndertaleModTool |
| Ghidra | disassembler/decompiler for native code | maintained (12.2, 2026-10-22) | Apache-2.0 | ghidraRun | https://github.com/NationalSecurityAgency/ghidra |
| Frida | dynamic instrumentation for native and managed games | maintained (17.26.2, 2026-11-07) | see repo | frida | https://github.com/frida/frida |
| x64dbg | Windows debugger | maintained (2026.05.27) | see repo | not on PATH (lives in the game folder or is a library) | https://github.com/x64dbg/x64dbg |
| Cheat Engine | memory scanner (Windows; last release 2023) | last release 2023-02 | - | not on PATH (lives in the game folder or is a library) | https://github.com/cheat-engine/cheat-engine |
| RenderDoc | graphics frame capture and debugger | maintained (v1.47, 2026-10-31) | MIT | qrenderdoc, renderdoccmd | https://github.com/baldurk/renderdoc |
| ReShade | post-processing injector (can be blocked by some anti-cheat) | maintained (v6.8.0) | BSD-3-Clause | not on PATH (lives in the game folder or is a library) | https://github.com/crosire/reshade |
| Mod Organizer 2 | mod manager with virtual file system | maintained (v2.5.2, 2024-08) | GPL-3.0 | not on PATH (lives in the game folder or is a library) | https://github.com/ModOrganizer2/modorganizer |
| Vortex | Nexus Mods manager | maintained (v2.10.1, 2026-11-05) | GPL-3.0 | not on PATH (lives in the game folder or is a library) | https://github.com/Nexus-Mods/Vortex |
| r2modman | Thunderstore mod manager | maintained (v3.2.21, 2026-10-30) | MIT | not on PATH (lives in the game folder or is a library) | https://github.com/ebkr/r2modmanPlus |
| xEdit (TES5Edit) | Bethesda plugin editor | maintained (4.1.5f, 2024-04; pushes 2026-11) | MPL-2.0 | not on PATH (lives in the game folder or is a library) | https://github.com/TES5Edit/TES5Edit |
| SKSE / F4SE | Skyrim and Fallout 4 script extenders, matched to the game version | updated per game patch (SKSE AE 2.3.1 for game 1.7.104; F4SE 0.7.9 for runtime 1.11.240) | - | not on PATH (lives in the game folder or is a library) | https://skse.silverlock.org/ |
| Fabric / NeoForge / Quilt | Minecraft Java mod loaders | maintained (Fabric Loader 0.20.1; NeoForge 26.3.0.102; Quilt 0.31.0-beta.5) | Apache-2.0 (Fabric) | not on PATH (lives in the game folder or is a library) | https://github.com/FabricMC/fabric-loader |

## 3. Anti-cheat: what to tell the user

| System | Recognised by | What the vendor says | Source |
|---|---|---|---|
| Easy Anti-Cheat | `EasyAntiCheat`, `EasyAntiCheat_EOS`, `*/EasyAntiCheat` | Epic says its integrity tool uses a signed catalog of file hashes: modified cataloged files can block you from protected multiplayer sessions, while offline, solo and unprotected modes still run. | https://dev.epicgames.com/docs/game-services/anti-cheat/using-anti-cheat |
| BattlEye | `BattlEye`, `*/BattlEye` | BattlEye's FAQ says it generally bans only for actual cheats or components built to bypass it; overlays and tools like ReShade are generally supported unless the developer says otherwise (blocked in some games), and some programs can get you kicked. | https://www.battleye.com/support/faq/ |

VAC (Valve) says third-party modifications to a game that give an advantage, including edits to executables and DLLs, trigger a permanent ban when connecting to VAC-secured servers (source: https://help.steampowered.com/en/faqs/view/571A-97DA-70E9-FF74). Vanguard (Riot) is a client plus a kernel driver; its page says nothing about mods. A vendor
statement for every system was not available, so treat any online or multiplayer game with anti-cheat as unsafe to mod unless the game's own support page says otherwise. Keep mods offline and single-player.

## 4. Where to publish: upload rules (read 2026-11-12)

| Host | Rules found | Source |
|---|---|---|
| Nexus Mods | Prohibits uploads that include copyrighted game files or images without permission from the owner; crediting is no substitute. AI policy: disclosure is mandatory for anything made with generative AI (tiers AI-Generated Content, AI Media, AI Assisted); enforced from 2027-01-02 after a 60-day grace period. | https://help.nexusmods.com/article/180-ai-policy-changes-2026 |
| Thunderstore | Do not distribute game files like Assembly-CSharp.dll without permission. AI-generated assets or code should use the AI Generated category where it exists (not enforced for READMEs or icons); untested or non-functional AI mods are spam. A package is a zip with icon.png (256x256), README.md and manifest.json at the root. | https://wiki.thunderstore.io/moderation/global-rules |
| Steam Workshop | Valve may remove Workshop contributions for any reason (Subscriber Agreement 6.B); app-specific terms can add rules. Steam's AI disclosure survey applies to games on Steam, not Workshop items. A Workshop-specific AI rule: UNVERIFIED. | https://store.steampowered.com/subscriber_agreement/ |
| mod.io | Uploads grant mod.io and the game admin a content licence and you warrant the content does not infringe others' rights; the Acceptable Use Policy applies. No AI clause found in the terms (Acceptable Use Policy not read). | https://mod.io/terms |

Never upload game files or decompiled game code; a mod should contain only your changes. AI-made art, audio or code must be disclosed where the host asks for it.

## 5. Finding installed games

`modlab_setup` reads Steam locally: the roots (`~/.steam/steam`, `~/.local/share/Steam`, the Flatpak folder `~/.var/app/com.valvesoftware.Steam`, `~/Library/Application Support/Steam`, `C:\Program Files (x86)\Steam`),
each library listed in `steamapps/libraryfolders.vdf` (`path` entries; numbered blocks), and each `appmanifest_<appid>.acf` (`appid`, `name`, `installdir`; game folder `steamapps/common/<installdir>`). The key names were observed on a
real install; the Windows, macOS and native-Linux default roots were not confirmed on a Valve page and are UNVERIFIED. It de-duplicates symlinked roots, leaves out Proton and runtime components, and reports libraries on drives that are not mounted.

## 6. Staleness: how the plugin checks its own knowledge

`modlab_setup` returns `knowledge_freshness`. Knowledge is stale when last checked more than 30 days ago (counting approved research) or when a known deadline passed after the last check:

| Date | What changes | Source |
|---|---|---|
| 2027-01-02 | Nexus Mods begins enforcing its AI-content disclosure rules after the 60-day grace period | https://help.nexusmods.com/article/180-ai-policy-changes-2026 |

If stale or a deadline is near, tell the user and **ask whether they want you to research the current facts online. Never research without their yes.** If they agree, read the source link of each affected row
(primary pages only) and save only what you verified with `knowledge_updates` (`{id, field, value, source, date}`; stored as dated overrides in the user's plugin data, the shipped catalog is unchanged; unknown ids/fields, non-https
sources and future dates are refused). Tell the user what changed and what you could not verify.

Still UNVERIFIED on 2026-11-12: every RPG Maker fact (file names and routes); Unreal `Engine/` and `Content/Paks` names, UnrealPak packing usage and FModel behaviour; UE4SS under Proton; the Godot 3 vs 4 pack mapping; the GameMaker runner exe name;
Source 2 `.vpk_c` layout and Doom-family PK3/WAD handling; Steam default roots on Windows, macOS and native Linux and the `StateFlags` meaning; the Easy Anti-Cheat FAQ on Linux/Proton; Riot's statement on mods; the Steam Workshop AI rule;
Creation Kit basics; mod.io AI rules beyond the terms; BepInEx Bleeding Edge IL2CPP build dates.

## 7. Evidence boundary

Documentation review plus a tested local scan. Nothing here installs a tool, starts a game or uploads anything. A catalog entry is not an installation and not authorization to modify a game.
