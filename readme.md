<p align="center">
  <img src="assets/brand/hero-banner.webp" alt="Hookshot: Ocarina of Time running natively on Windows and Linux, with no emulator" width="800">
</p>

<p align="center">
  <strong>The Legend of Zelda: Ocarina of Time (Nintendo Switch 2) running natively on Windows and Linux. No emulator: the game is rebuilt on your PC, from your own copy.</strong>
</p>

<p align="center">
  <a href="https://github.com/NoobyGains/Hookshot/stargazers"><img src="https://img.shields.io/github/stars/NoobyGains/Hookshot?style=flat-square&color=f59e0b" alt="GitHub stars"></a>
  <a href="https://github.com/notquiteog/Hookshot/releases"><img src="https://img.shields.io/github/v/release/notquiteog/Hookshot?include_prereleases&style=flat-square&label=release&color=34d399" alt="Latest release"></a>
  <img src="https://img.shields.io/badge/Windows%20%7C%20Linux-64--bit-64748b?style=flat-square" alt="Windows and Linux, 64-bit">
  <img src="https://img.shields.io/badge/Vulkan-1.3%20%2B%20mesh%20shaders-ac162c?style=flat-square&logo=vulkan&logoColor=white" alt="Vulkan 1.3 with mesh shaders">
  <img src="https://img.shields.io/badge/DLSS%20%7C%20FSR%204%20%7C%20HDR-22d3ee?style=flat-square" alt="DLSS, FSR 4 and HDR">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-GPL--3.0--or--later-0ea5e9?style=flat-square" alt="License: GPL-3.0-or-later"></a>
</p>

<p align="center">
  <a href="#whats-new-here">What's new</a> •
  <a href="#roadmap">Roadmap</a> •
  <a href="#project-status">Status</a> •
  <a href="#install-and-play">Install and play</a> •
  <a href="#in-game-menu">In-game menu</a> •
  <a href="#if-something-goes-wrong">Problems</a> •
  <a href="#build-from-source">Build from source</a> •
  <a href="#how-it-works">How it works</a> •
  <a href="#want-to-help">Want to help?</a> •
  <a href="#credits">Credits</a> •
  <a href="#license">License</a>
</p>

> [!IMPORTANT]
> This repository **does not contain the game, keys or an executable**, and it does not explain how to get them. You
> need your own copy. Everything the build creates (`hookshot.exe`, the generated code, the shader caches and your
> saves) comes from your game and stays on your PC. Never share those files.

## Why Hookshot

<table>
  <tr>
    <td width="33%" valign="top">
      <h3>⚙️ Native, not emulated</h3>
      A static recompilation: the game's code is translated to C and compiled into a Windows or Linux program, and its Switch 2 graphics are rebuilt on Vulkan.
    </td>
    <td width="33%" valign="top">
      <h3>🔭 Sharper than the console</h3>
      Your monitor's resolution, with NVIDIA DLSS and DLAA, AMD FSR 3.1 and FSR 4, ultrawide and 4:3, and HDR10 out.
    </td>
    <td width="33%" valign="top">
      <h3>🚀 Faster than the console</h3>
      Frame rate caps from 60 to 240 FPS or uncapped, frame generation from 2x to 8x, NVIDIA Reflex and AMD Anti-Lag 2.
    </td>
  </tr>
  <tr>
    <td width="33%" valign="top">
      <h3>🧰 One Builder, one button</h3>
      Hookshot Builder brings its own compiler and tools, builds the game in about 10 to 45 minutes, and its launcher keeps it up to date.
    </td>
    <td width="33%" valign="top">
      <h3>🎮 Made for PC play</h3>
      An in-game menu for every setting, controller, keyboard and mouse camera, motion controls, layout presets and button prompts.
    </td>
    <td width="33%" valign="top">
      <h3>🧩 Mods and saves</h3>
      A <code>mods</code> folder in the layout emulators use, and saves that stay on your PC.
    </td>
  </tr>
</table>

## What's new here

Everything below is on `main` in this repository, tested in the game on a GeForce RTX 5090 and a Ryzen 9 9950X3D.

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/images/features/counters-and-timer.jpg" alt="The game with a speedrun timer and death counter at the top centre, and the rupee count in the bottom left corner">
      <b>Speedrun timer, death counter and classic rupee counter</b><br>
      Gameplay tab. The timer and the death count sit at the top centre, clear of the hearts; the rupees stay in the
      bottom left corner, as on the N64.
    </td>
    <td width="50%" valign="top">
      <img src="docs/images/features/above-60-fps.jpg" alt="Kakariko Village running at 93 frames per second with the FPS counter on">
      <b>Above 60 FPS, without the bugs</b><br>
      With a Frame rate cap above 60, Gohma now steers instead of sticking to the walls, slow motions keep their
      length and water keeps moving. (Pictured: Kakariko at 93 FPS.)
    </td>
  </tr>
</table>

<p align="center">
  <img src="docs/images/features/loading-screen.webp" alt="The start-up screen: the 3D Hookshot turning above the HOOKSHOT wordmark while the pipeline bar fills" width="520">
</p>

**The loading screen's Hookshot is the 3D one** from the header, turning while the game starts and its shaders and pipelines load.

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/images/launcher/wizard-3-build.png" alt="The Hookshot Launcher building the game: the 3D Hookshot turning beside the percentage, each stage with its time">
    </td>
    <td width="50%" valign="top">
      <img src="docs/images/launcher/saves-import-longshot.png" alt="The Hookshot Launcher's saves page with the shield, importing saves from Longshot">
    </td>
  </tr>
</table>

**The Hookshot Launcher** (preview): one program that installs the builder, builds the game, keeps versions side by
side, updates them and itself, and carries your saves (from Longshot and the emulators too), in the header's look with the
same 3D Hookshot turning while it builds ([Quick start](#hookshot-launcher)). Its checks pass and it installs the builder;
a full build through it is the next test.

**Just landed, being tested in the game now** (on `main`; the game builds and runs with all of them at 60 FPS):

- **Mod manager:** Gameplay > Mods lists your mods, turns them on and off, sets their load order and names the files two
  mods both replace, saved in `mods/hookshot-mods.ini` (no more renaming folders)
- **Hero mode and quiet Navi:** double damage and no recovery hearts; Navi's "Hey! Listen!" area hints off
- **Toggle buttons and Mono:** a Toggle column on the Controls page (tap to hold the shield or aim), Mono on Audio output
- **Walk, sprint and mouse look:** a walk key and speed, a sprint button, the mouse aiming, locking on and riding
- **Switch 2 Pro Controller over USB, and NFC tags** from your own files
- **Less memory:** video memory only where the game uses it, and the game's own memory levels off instead of growing
- **A steadier picture and faster start:** HUD labels, the Gossip Stones with frame generation, sharper scaling when the
  picture is larger than the window; the button prompts ready in about 20 s instead of 160; a new install starts at the
  game's 2560x1440
- **Intel and AMD fixes:** Intel Arc and Iris, the Radeon RX 6600 family; the mouse cursor hidden in play
- **Steam Deck profile:** settings made for the Deck, on by themselves on a Deck

<img src="docs/images/features/field-of-view.jpg" alt="Kakariko Village at field of view 60 percent, the game's 100 percent and 140 percent">

**Field of view** (Graphics tab, 50% to 300%): from a close, cinematic 60% to a wide 140%, where Kakariko's whole gate
and the cliffs around it fit on screen.

### Retro look: the game as the Nintendo 64 drew it

<img src="docs/images/features/retro-look.jpg" alt="Gerudo Valley with adult Link: Retro look off, and N64 with the picture at 240 lines and the console's dither, full frame and 1:1 pixels">

**Retro look** (Graphics tab, off by default) brings back the 1998 picture: **N64** draws the game at the console's 240
lines, with colours cut to 16 bits through the N64's own 4x4 "magic square" dither, scaled up soft. It costs nothing measurable (60 FPS either way on an RTX 5090), and
the Insert menu stays sharp over it.

<img src="docs/images/features/crt-look.jpg" alt="Gerudo Valley with N64 + CRT at 1:1 pixels: the default look, then a shadow mask with strong curvature, strong scanlines with a slot mask and high glow, and light scanlines with no mask">

**N64 + CRT** puts that picture on a CRT: each line is a beam that
widens where the picture is bright, so dark parts show the lines and bright parts fill out without the picture getting
darker, with a phosphor mask on your screen's own pixels, a soft glow and a curved screen. Five rows set it to taste:
**CRT scanlines** (Off to Strong), **CRT mask** (aperture grille, slot or shadow mask), **CRT mask strength**, **CRT glow**
and **CRT curvature**. The pictures above are 1:1: a shrunk screenshot of a mask shows stripes the screen does not.

### Brightness, colour vision and a screenshot key

<img src="docs/images/features/brightness-colour-vision.jpg" alt="Top: a shaded corner of Kokiri Forest at brightness 80, 100, 130 and 150 percent. Bottom: Kakariko Village with colour vision off, then protanopia, deuteranopia and tritanopia">

**Brightness** (Graphics tab, 70% to 150%) lifts or darkens the shadows and mid-tones while black stays black and white
stays white, for screens without HDR. **Colour vision** (Off, Protanopia, Deuteranopia, Tritanopia) moves the colours
each kind of colour blindness confuses to ones that can be told apart; greys and the HUD's text stay as they are. It is
meant to look different to other eyes.

**F12 saves a screenshot** as a PNG in a `screenshots` folder beside the game, as the window shows it (with the Retro
look, Colour grade, Brightness and the rest) but without the Insert menu or the FPS counter. Saving runs beside the game:
the frame rate held at 59 to 60 FPS through ten presses on an RTX 5090. The Screenshot key row (Controls tab) turns it off.

### DLSS 5 neural rendering, tested

<img src="docs/images/features/dlss5-face.jpg" alt="Adult Link's face in Gerudo Valley with DLSS 5 neural rendering off and on">

<img src="docs/images/features/dlss5-motion.webp" alt="Five seconds in Gerudo Valley, the camera circling adult Link, with DLSS 5 off on the left and on on the right">

Tested on a GeForce RTX 5090 at 4K: DLSS 5's neural rendering ran on 99.6% of frames at 4.6 ms a frame (60 FPS off,
51 on). It gives faces skin shading, hair that catches the light and eyes with depth. **Hookshot does not include DLSS
5:** NVIDIA has not released it to developers, so its runtime is not ours to ship. These pictures were taken with a
player's own runtime through RenoDX's DLSS 5 add-on for ReShade. The game's Neural tab already has the switch and the
model's settings for when NVIDIA does ([DLSS 5 neural rendering](#dlss-5-neural-rendering) below says what it needs).

### Colour grade

<img src="docs/images/features/colour-grade.jpg" alt="Kakariko Village four ways: colour grade off, Vivid, Cinematic and Cool">

**Colour grade** (Graphics tab: Rich, Vivid, Warm, Cool, Cinematic), with **Bloom** (a glow around bright light) and **FXAA**, plus **View distance, Grass and Shadow distance** rows that change
how far the game draws models, grass and shadows. Each has an Original setting that looks exactly like the game.
Fixed since the first version: Bloom, Colour grade, FXAA and the Retro look did nothing unless the Window scaling filter
or Sharpness was also on. They now work at the default settings.

Behind the scenes: the Builder's **"Preparing shaders" step no longer hangs at 99%** on a driver that never finishes a
shader, and closing the game while shaders build no longer counts against you. On Windows,
[`scripts/windows/launch-hdr.ps1`](scripts/windows/launch-hdr.ps1) turns Windows HDR on for one session and back off
when the game closes.

## Roadmap

<p align="center">
  <img src="assets/brand/roadmap.png" alt="Hookshot roadmap: 8 done, 13 in progress, 13 coming next, each as a card. The same items are listed as text below." width="820">
</p>

**Done** is on `main` now. **In progress** is being worked on at the moment. **Coming next** is planned but not
started. The order follows the scored [worklist](docs/worklist.md): how bad a problem is, times how many players it
reaches.

<details>
<summary><b>The roadmap as text</b></summary>

**✅ Done**: on `main` now, tested in the game

- **Smooth above 60 FPS:** Gohma steers instead of sticking to the walls, slow motions keep their length, water, ice
  and sand keep moving
- **New graphics options:** View distance, Grass and Shadow distance, Bloom, Colour grade and FXAA
- **Timer and counters:** Speedrun timer, Death counter and the N64's rupee counter
- **No more stuck at 99%:** the Builder's shader preparation carries on past a graphics driver that never finishes a
  shader, and closing the game while shaders build no longer counts against you
- **Retro N64 look:** the picture at the console's 240 lines with its own dither; the loading screen's 3D Hookshot
- **A better CRT look:** scanline beams, a phosphor mask, glow and curvature for the Retro look, each set in the menu
- **Brightness and colour vision:** a brightness slider for screens without HDR, and colour-blind modes
- **Screenshot key:** F12 saves the picture as you see it, as a PNG beside the game
- Also: the one-click Windows HDR launcher, the water's per-light shadow maps, several users, each game in its own
  folders, the RX 6600 / 6650 XT / 6500 XT fallback

**🟡 In progress**: most are on `main` now and being tested in the game; the rest are being built

- **Mod manager:** your own mods listed in the menu, on and off, their load order and conflicts
- **Hero mode and quiet Navi:** double damage and no recovery hearts; Navi's callouts off
- **Hookshot Launcher:** several builds side by side, stable, release-candidate and nightly channels, saves imported
  and exported, an installer and updates of its own, in Hookshot's 3D look
- **Toggle buttons and Mono:** tap a button to hold it (the shield, aiming), and a Mono sound output
- **Less memory, a faster start:** video memory only where the game uses it; the button prompts ready in about 20 s
  instead of 160
- **A steadier picture:** HUD labels that stay sharp, the Gossip Stones whole with frame generation, no HDR flicker,
  sharper scaling when the picture is larger than the window
- **Intel and AMD fixes:** Intel Arc and Iris, the Radeon RX 6600 family; the mouse cursor hidden in play
- **Steam Deck profile:** settings made for the Deck, on by themselves on a Deck
- **Walk, sprint and mouse look:** a walk key, a sprint button, and the mouse for aiming, locking on and riding
- **Pro Controller and amiibo:** the Switch 2 Pro Controller over USB, and NFC tags from your own files
- **Every screen shape:** the HUD placed right on ultrawide screens, filling the window, any output size, field of view
  up to 300%
- **Straight into play:** skip the title screen into your newest save, and open the menu from the pause screen
- **Hundreds of fixes:** renderer, runtime and build fixes, each checked by tests

**⚪ Coming next**: planned, not started

- **Memory in long sessions:** a soak test on this PC levels off at about 33 GB; next, the same test held to a 16 GB
  PC's memory, where players run out
- **Faster towns and fields:** Castle Town and Hyrule Field, where each frame waits on the processor
- **Jump loop after Gohma:** Link repeating a jump in dialogue above 60 FPS
- **Invisible doors and walls** in a few places of the game
- **Play in VR:** PC VR headsets through OpenXR, with a VR tab in the menu
- **Item wheel:** pick items from a wheel, with instant equip
- **Find my best settings:** the menu measures your PC and picks the settings
- **Photo mode:** a free camera with the HUD hidden (F12 screenshots already work)
- **First-person aim:** bow, slingshot and Hookshot from Link's eyes, with the mouse
- **Small toggles:** auto jump, Young Link on Epona, gear on and off, N64-style controls
- **Randomizer:** items shuffled each run, a new game every time
- **Online co-op:** play the adventure together with a friend
- **AMD on Windows:** crashes on some Radeon cards (needs an AMD tester)
- Later: a signed Builder, Intel cards, cards without mesh shaders

Mods that swap in Nintendo's own models, textures, music or voices are for players to add from their own files
(Hookshot loads them from the `mods` folder, see [Mods](#mods)); the project ships none of them.

</details>

## Quick start

1. Download `HookshotBuilder.exe` (Windows) or the AppImage (Linux) from the
   [latest release](https://github.com/notquiteog/Hookshot/releases/latest).
2. Run it and pick your game copy: a `.nup` file, or the `romfs` and `exefs` folders.
3. Press **Build the game** and wait about 10 to 45 minutes.
4. Press **Play**. The first start prepares the game's shaders; later starts are faster.

You need a graphics card with Vulkan 1.3 and mesh shaders (GeForce RTX 20 or newer, Radeon RX 6000 or newer, Intel
Arc), 16 GB of RAM and about 60 GB free while building. The [full guide](#install-and-play) has every step.

### Hookshot Launcher

The **Hookshot Launcher** does all of the above in one program, and keeps doing it: it installs the builder for each
version (every file checked by its SHA-256), builds the game in a three-step wizard (your game files, the settings, the
build with one progress bar), keeps several versions side by side (Play starts your default), offers each its channel's
updates (stable, release candidate or nightly) and updates itself. It keeps one save folder for every version and imports
saves from Longshot, NX2navi and the emulators, backing up first. Windows (installer or portable) and Linux / Steam Deck
(AppImage). It is a preview: download it from the [`launcher-nightly`](https://github.com/NoobyGains/Hookshot/releases/tag/launcher-nightly)
pre-release (each push to `main` publishes it); [launcher/README.md](launcher/README.md) has the rest and
[docs/launcher.md](docs/launcher.md) its history.

<p align="center">
  <img src="docs/images/launcher/home.png" alt="The Hookshot Launcher's home: the 3D Hookshot turning beside the name and the shield, the default version with Play, and the versions built" width="640">
</p>

## Project status

Experimental. Players have reported on many PCs, from Kokiri Forest to the dungeons: the table says what works and
what does not yet. Open problems are collected in tracking issues, linked below.

This repository is developed and play-tested on a GeForce RTX 5090 and a Ryzen 9 9950X3D (Windows 11, 4K at 240 Hz, HDR); every run, on this PC and on others' hardware, is in [docs/tested-configurations.md](docs/tested-configurations.md).

<details>
<summary><b>The full status table</b></summary>

| What | Status |
|---|---|
| Kokiri Forest: reaching gameplay and walking around | ✅ Works |
| Sound, controller, keyboard and saves | ✅ Works |
| In-game menu, frame generation and upscaling | ✅ Works |
| Flicker (the picture flashing too bright while moving) | ✅ Fixed in v2.0.2 ([#645](https://github.com/NotRexed/Hookshot/pull/645)) |
| Ground fog vanishing when looking down | ✅ Fixed in v2.0.2 ([#638](https://github.com/NotRexed/Hookshot/pull/638)) |
| Models with missing pieces (doors, fences, parts of trees) | ✅ Fixed where tested, more play needed |
| Stutter when entering new areas | ⚠️ Still happens the first time you visit a place. The next visits are smooth |
| Performance | ⚠️ Depends on the PC: some reach a steady 60 fps, others stay below it, more so in Hyrule Field |
| Hyrule Field, Castle Town, Kakariko and the dungeons | ⚠️ Players got there, with open bugs: lighting and shadows ([#1004](https://github.com/NotRexed/Hookshot/issues/1004)), crashes and freezes ([#2507](https://github.com/NotRexed/Hookshot/issues/2507)) |
| Ultrawide and 4:3 | ✅ Works. The Aspect ratio row's default, Monitor's shape, widens the 3D to the screen and keeps the HUD and movies in the middle 16:9 ([#2119](https://github.com/NotRexed/Hookshot/pull/2119)) |
| NVIDIA cards | ✅ Works. The most tested |
| AMD cards | ⚠️ Many tested: reports from the RX 6600, RX 6800 XT, RX 7800 XT, RX 7900 XTX and RX 9070 XT. On Windows, the RX 6600 to RX 6950 XT and their mobile and Pro models (Navi 21, 22 and 23) draw task and mesh shaders through the compute fallback by default: the driver lost the GPU on their own mesh shaders on an RX 6700 XT, an RX 6800 XT and, in one report in Mako, an RX 6600 ([#1747](https://github.com/NotRexed/Hookshot/pull/1747), [#1992](https://github.com/NotRexed/Hookshot/pull/1992), [#2215](https://github.com/NotRexed/Hookshot/pull/2215)); another RX 6600 played 15-20 minutes on them ([Longshot #130](https://git.magicbean.dev/MagicBeanDev/Longshot/issues/130)). The RX 6400 and 6500 XT (Navi 24) take the fallback too, as Ocarina Reborn has them; the rest of Navi 24 (RX 6300, Radeon Pro W6300 to W6500M) keeps its own mesh shaders, as no report has them losing the GPU, and `RX_VK_TASK_MESH_FALLBACK=1` tries the fallback there (`=0` gives any card its own). Driver crashes and device lost are still reported ([#996](https://github.com/NotRexed/Hookshot/issues/996)) |
| Intel cards | ❓ Few reports, many of them black screens or crashes ([#999](https://github.com/NotRexed/Hookshot/issues/999)). On Windows, Intel's shader compiler is entered by one thread, and a shader it faults on is left out instead of closing the game, on later starts too (from [Longshot #252](https://git.magicbean.dev/MagicBeanDev/Longshot/pulls/252), made for an Intel UHD laptop with 4 threads that crashed in `igvk64.dll`): not yet tested on an Intel GPU |
| Pre-rendered movies on a slow CPU | ⚠️ Shown rather than skipped when the decoder is slower than the movie, so the picture can fall behind the sound. With 4 logical processors or fewer the decoder uses 2 threads, leaving the game its own. The first picture can still be black on some PCs |
| Cards without mesh shaders (such as AMD RX 5000 and older) | ❌ Not supported: parts of the picture are missing. Since v2.0.6 a fallback runs the mesh programs as compute shaders on cards with buffer device addresses ([#640](https://github.com/NotRexed/Hookshot/issues/640)); it leaves out the mesh draws that take their count from a buffer |
| Linux | ✅ Works with the AppImage. Tested on several distributions (CachyOS, Fedora, Bazzite, SteamOS) and cards, with open problems on some AMD cards ([#1000](https://github.com/NotRexed/Hookshot/issues/1000)) |

</details>

## Install and play

<details>
<summary><b>The full install guide: what you need, Windows, Linux, updating, where the files go, problems</b></summary>

The game does not come ready-made: Hookshot Builder builds it on your PC from your copy. You do this once. After that
you start the game from its launcher, which also updates it.

### What you need

- **Your copy of the game at the supported version:** program `0400486024DEC000`, update v131072, build `e0f3ccfa`.
  Other versions do not work. A `.nup` file, or the `romfs` and `exefs` folders.
- 64-bit Windows 10 or 11, or 64-bit Linux with glibc 2.35 or newer (Ubuntu 22.04, Debian 12, Fedora, Arch,
  SteamOS ...) and a CPU with AVX2. The Linux AppImage needs AVX2; on Windows, and in a build from source, a CPU
  without it gets a game built for what it has, a little slower.
- A graphics card with Vulkan 1.3 and mesh shaders, with an up-to-date driver: NVIDIA GeForce RTX 20 series or newer,
  AMD Radeon RX 6000 series or newer, or Intel Arc. On Linux, Mesa or NVIDIA's driver. Cards without mesh shaders are
  not supported.
- 8 GB of video memory (VRAM) or more is recommended. Cards with less can use the in-game menu's lower Quality presets.
- 16 GB of RAM or more. A run uses about 10 GB.
- About 60 GB free while building, on an SSD if you can: a hard drive makes the build much slower. You can build on one
  anyway; the builder says so first.
- An internet connection for the download. Nothing else to install: the builder brings its own compiler and tools.

### On Windows

For a portable install on an external SSD, run the downloaded setup with `--portable`; see
[Portable Hookshot Builder](docs/windows-portable-builder.md) for folder, move and repair behavior.

1. Open the [latest release](https://github.com/notquiteog/Hookshot/releases/latest) and download `HookshotBuilder.exe`.
2. Run it. It downloads the rest of Hookshot Builder (about 500 MB), checks it, and opens it.
3. Pick your game. The builder looks for `.nup` files in your Downloads, Desktop and Documents folders and lists them
   under **Found on this PC**. Not listed? Press **Browse…**, drop the file on the window, or choose
   **romfs and exefs folders**. The builder checks that it is the right version.
4. Under **Install the game to**, keep the folder (`Games\Hookshot` in your user folder) or press **Change**. Choose
   the **Game language**.
5. Press **Build the game**. It takes about 10 to 45 minutes, depending on your CPU and memory. You can use your PC in
   the meantime.
6. When it says **Your game is ready**, press **Play**. The **Desktop shortcut** and **Start menu entry** boxes are
   ticked: untick them if you don't want them.

Next time, start the game from the Hookshot shortcut, or `hookshot.exe` in the game folder. That is the launcher: it
has **Play**, and **Update** when a newer release is out.

The first start prepares the game's shaders, which takes a while. Later starts are faster.
A build whose preparation stopped ("the GPU driver stopped responding") leaves `hookshot_prepare_skipped` beside the
game instead, and the game then prepares nothing at a launch, building each shader when first drawn, until that file
is deleted or a build prepares them.

### On Linux

1. Open the [latest release](https://github.com/notquiteog/Hookshot/releases/latest) and download
   `Hookshot-<version>-x86_64.AppImage`. It is Hookshot Builder with everything it needs inside.
2. Allow it to run as a program. In most file managers: right-click it, open **Properties**, and turn on
   "Allow executing file as program" (the words differ between desktops). Or in a terminal:
   `chmod +x Hookshot-*-x86_64.AppImage`.
3. Double-click it. The Hookshot Builder window opens.
4. Under **Game files**, choose **.nup file** or **romfs and exefs**, then press **Browse** to pick them. The builder
   checks the version.
5. Under **Save the game to**, keep `~/Games/Hookshot` or choose another folder. Choose a **Language**.
6. Press **Build**. It takes about 10 to 45 minutes, depending on your CPU and memory.
7. When it says "Your game is ready", press **Play**.

The game is also added to your applications menu as "Hookshot". That entry, and `hookshot` in the game folder, open the
launcher: **Play**, and **Update** when a newer release is out. Keep the AppImage where it is: the launcher uses it to
update.

When the desktop gives the launcher its own systemd service, **Play** waits up to two seconds for the game's
separate scope before closing the window. If that hand-off fails, it cancels that attempt before starting the
game directly, and records the fallback in `hookshot_startup.log` after the game exits. A direct start still
follows the desktop's original service lifetime; this fallback cannot bypass a desktop that stops its children.

The same AppImage also builds and starts the game without opening the window, for a machine you reach over SSH or for a
script: see [Linux, the AppImage from the command line](#build-from-source).

For fast GPU memory imports on Linux, the game user needs read/write access to `/dev/udmabuf` (the kernel's
`udmabuf` module). Without it, Hookshot falls back to host-pointer imports, which can be much slower on AMD/RADV
(NVIDIA's driver refuses these dma-bufs, so on NVIDIA the game uses host-pointer imports, which are not slow there);
permission errors produce a warning on stderr and in `hookshot_log.txt`. With an NVIDIA card on NVIDIA's own driver
you do not need this access and can ignore that warning: the check runs at the start, before the game knows which
GPU it has. Otherwise, check `ls -l /dev/udmabuf` and `id`.
An administrator can add you to the device's owning group, then you must log out and back in. Only use that group
if access to its other devices is intended: `kvm` also grants virtualization access. For an active local desktop
session using systemd-logind, prefer a device-specific rule in `/etc/udev/rules.d/70-hookshot-udmabuf.rules`:
`SUBSYSTEM=="misc", KERNEL=="udmabuf", TAG+="uaccess"` (before `73-seat-late.rules`). This grants access to the active
local user, not SSH or service users. For those, an administrator can instead create a dedicated `udmabuf` group,
add only the game user, and use `SUBSYSTEM=="misc", KERNEL=="udmabuf", GROUP="udmabuf", MODE="0660"` in that file.
Reload with `sudo udevadm control --reload-rules` and apply with
`sudo udevadm trigger --action=add /sys/class/misc/udmabuf`; restart the session/service after a group change.
If the device is absent, the distribution must provide/load the module first (`sudo modprobe udmabuf`).
Do not run the game as root or make the device world-writable.

### Updating

When a new release is out, the launcher says "Update available". Press **Update**: in `hookshot.exe` on Windows, or in
`hookshot` (or the AppImage) on Linux. It downloads only the parts that changed and builds the game again in the same
folder. The build files of the last build are gone by then (see [Where the files go](#where-the-files-go)), so an
update takes about as long as the first build. Your saves and settings are kept. What changed is on the
[Releases page](https://github.com/notquiteog/Hookshot/releases).

<details>
<summary>What an update keeps and replaces, and updating from the command line</summary>

To be safe, copy your saves somewhere first: the `user` folder in the game folder on Windows, or
`~/.local/share/hookshot` on Linux.

| Kept | Replaced |
|---|---|
| Your saves (`user`, or `~/.local/share/hookshot` on Linux) | The game in `bin` and its files |
| `hookshot_options.ini`, the in-game menu's choices and your controls | `image.bin` and the shader list |
| `hookshot_env.txt` | `language.txt`, written again with the game's language |
| `mods` | |

The game files the first build read are kept in the game folder, so an update does not need your `.nup` again.

From a clone: `git pull`, then `python -I nx2/make_game.py --update <game folder>`. The Linux AppImage does the same
with `--update <game folder>`.

</details>

### Latest development build

Want a fix before it is in a release? The
[latest development build](https://github.com/notquiteog/Hookshot/releases/tag/nightly) is made from `main` after every
change, with the same files as a release. It is untested and may break your saves or settings: copy them first (see
above).

- **Windows:** download `HookshotBuilder.exe` from it and start it from a terminal as `HookshotBuilder.exe --tag nightly`
  (without `--tag nightly` it installs the latest release instead).
- **Linux:** download `Hookshot-<version>-x86_64.AppImage` from it and use it as above.

To go back, install the [latest release](https://github.com/notquiteog/Hookshot/releases/latest) the usual way.

### Where the files go

- The build reads your game and never changes it. It writes to the folder you choose and to the builder's own folder:
  `%LOCALAPPDATA%\HookshotBuilder` on Windows, `~/.cache/hookshot-builder` on Linux.
- The romfs is hard-linked instead of copied where the disk allows it.
- The build files (about 4 GB: the translated code and the compiled objects) are deleted once the game is ready. None
  of them are needed to play. To keep them, so that an update compiles only what changed, set the environment variable
  `HOOKSHOT_KEEP_BUILD_FILES=1` for the builder; on Windows, **Free up space** on the "Your game is ready" page then
  deletes them when you want. The build files folder can be moved before a build (**Change**, **Default**).
- Saves: the `user` folder in the game folder on Windows, `~/.local/share/hookshot` on Linux (a `user` folder from an
  earlier Linux build is moved there once). `--user <folder>` puts them somewhere else ([command line
  arguments](#running-the-game-from-the-command-line)).
  To carry on with a save from an emulator (Lichii, Eglantine, Orchid, ...) or NX2navi, or to take yours there, see
  [using a save from an emulator](docs/saves.md).
- To uninstall, delete the game folder, the builder's folder and the shortcuts.

### What Hookshot connects to

Hookshot uploads nothing about you or your PC. It reads no browser data, passwords or session keys. Everything it does on
the network or with other programs:

- **Downloads from GitHub only.** The builder and the updater ask `api.github.com` which release is the latest, and download
  that release's files from this repository's Releases on `github.com` (the setup lists, the build parts, the Linux AppImage
  parts and the shared pipeline list). With **DLSS** ticked in the builder, NVIDIA's DLSS library comes from
  `github.com/NVIDIA/DLSS`. The game checks for a newer release on `api.github.com` at start; set
  `HOOKSHOT_NO_UPDATE_CHECK=1` to turn that off.
- **Your Discord status, through the Discord app on this PC.** While Discord runs, the game shows "Playing Hookshot" with
  the time played. It does this the way every game does: through the Discord app's own local connection, a named pipe on
  Windows and the socket `discord-ipc-0` in `$XDG_RUNTIME_DIR` (or `$TMPDIR`, or `/tmp`) on Linux. What it sends is
  "Ocarina of Time", the Hookshot version, the start time and the icon's name. The Discord app then shows it through
  Discord's servers. Turn it off with **Gameplay → Discord status** in the Insert menu.
- **Files it writes outside the game folder:** the builder's own folder (above), its settings (`~/.config/hookshot` on
  Linux), the saves (above), and shortcuts if you ask for them. **Bug report** (Gameplay tab) only writes a folder in
  `bug-reports` in the game folder, with your home folder and user name taken out of its logs, and **Save my pipeline
  list** only saves a zip in your Downloads folder: you choose whether to attach them anywhere.
- On Linux the game starts through a small script (`play-diagnostics.sh`). It keeps the game's first error messages in
  `hookshot_startup.log` in the game folder, using a private temporary folder there that it removes when the game exits.

Only download Hookshot from this repository's [Releases](https://github.com/notquiteog/Hookshot/releases). Each release
lists its files' checksums in `SHA256SUMS`. A copy from anywhere else may not be ours.

### If something goes wrong

| Problem | What to do |
|---|---|
| Where is the log? | `hookshot_log.txt` in the game folder holds the last run. The four runs before are `hookshot_log.1.txt` (the last) to `.4.txt`. Started from a terminal, the game prints there instead. Every 600 frames it has a `vk: status:` line: the video memory in use of what the driver allows, and DLSS's details while it draws; `vk: over the driver's video-memory allowance` says when the game passed it |
| A place has a wrong texture, or a floor or wall is missing | Look for `hookshot_damaged_files.txt` in the game folder. The build writes it when your game dump is incomplete (about 23.3 GB, a complete one is about 23.8 GB): it lists each damaged game file and the file put in its place. Dump the game again and build from the new dump; the file is then removed |
| Linux Builder Play closed before the game log appeared | After the game exits, check `hookshot_startup.log` in the game folder for up to 64 KiB of startup stderr and its exit status. |
| "Hookshot supports build e0f3ccfa" or "This version isn't supported" | Check that you chose the right game with its update installed |
| The game opens and closes, or the log says "device lost" | Update your graphics driver. On AMD cards there are known crashes ([#708](https://github.com/NotRexed/Hookshot/issues/708), [#614](https://github.com/NotRexed/Hookshot/issues/614)) |
| Parts of the picture are missing, or a message says your card has no mesh shader support | The card or its driver has no mesh shaders. Update the driver; older cards are not supported ([#640](https://github.com/NotRexed/Hookshot/issues/640)) |
| AMD: blocky textures, solid rectangles in the sky or unusually dark courtyard surfaces | Try the [RGBA8 texture workaround](#amd-texture-workaround). It uses more graphics memory |
| Windows: HDR is on, but the game stays SDR | The **HDR** row's help in the menu, and the `vk: HDR:` line in the log, say why. "HDR is off for this display": turn on **Use HDR** for the display the game is on, in Windows' **Settings > System > Display**. "Windows has HDR on, but the graphics driver offers the game no HDR output": Windows' desktop is in HDR but the driver does not offer HDR to Vulkan games; update the graphics driver with a clean install (NVIDIA: run the installer, choose **Custom**, tick **Perform a clean installation**), then restart the PC. A clean install resets the driver's settings, such as the output colour depth. |
| Linux: the game does not start or the picture is broken | The game needs a Vulkan 1.3 driver with mesh shaders. Check with `vulkaninfo \| grep mesh`: it should list `VK_EXT_mesh_shader`. Update Mesa or the NVIDIA driver |
| Steam Deck: the game freezes and closes in Kokiri Forest or the Great Deku Tree (`gfx_0.0.0 timeout` in `journalctl -k`) | `RX_VK_MESH_NOCULL=2c56dc1006942f74` in `hookshot_env.txt` gets past it with every model drawn (the culling pass that runs for seconds is turned off). `RX_VK_SKIP_CODE=2c56dc1006942f74` also gets past it, but the models those draws make go missing (see the [development guide](docs/development.md#switches-for-testing-and-debugging), [#817](https://github.com/NotRexed/Hookshot/issues/817)) |
| "Your antivirus removed part of the build tools" | A false alarm on unsigned programs. Restore the files from Windows Security's Protection history, or add `%LOCALAPPDATA%\HookshotBuilder` to its exclusions, then press **Repair** |
| Stutter the first time you see something | Normal for now: shaders are being prepared. It gets better when you pass through the same place again. You can help remove it for everyone: [send your pipeline list](#send-your-pipeline-list) |
| Windows, NVIDIA: stutter every start in places you have seen, after the shaders were prepared | The driver's shader cache is too small to keep them all (the first start builds about 2 GB of pipelines into it). In the NVIDIA Control Panel, Manage 3D settings, set **Shader Cache Size** to **Unlimited** (or 10 GB). On Linux the game raises the driver's limit itself |
| Windows, Intel: the game closes in the first scene, and the log names `igvk64.dll` | Keep the Debug tab's **Intel shader compiles** row on **One at a time** (the default) and update the graphics driver. |
| The build said "the GPU driver stopped responding", or the log says `the shaders' preparation was skipped at the build` | The game then builds every shader when it is first drawn, and stutters or leaves things out for a long time. Delete `hookshot_prepare_skipped` from the game folder so that the next start prepares them, or build again. |
| A movie stutters, falls behind its sound, or starts on a black picture | On a CPU with 4 logical processors or fewer, the decoder uses 2 threads; `HOS_DAV1D_THREADS=<n>` in `hookshot_env.txt` sets another count. Run once with `HOS_VIDEO_LOG=1` and attach the log: its `video:` lines say how long each picture took to decode and how far the picture was behind the sound. |
| The game is in the wrong language | Change the code in `language.txt` in the game folder. The file lists them all, and an update keeps the one you set there |

If the problem continues, [report it](https://github.com/NotRexed/Hookshot/issues/new/choose) with the version, where
you were in the game, your graphics card, `hookshot_log.txt` and a screenshot or video. Never send game files. The
in-game menu's **Gameplay → Bug report** gathers all of it in one press ([In-game menu](#in-game-menu)).

#### Low FPS or stutter

Walk through the same spot twice after shader preparation finishes. Note whether the slowdown clears on the
second pass or lasts until you restart the game. For a slowdown after an update, compare the same spot and
settings on both versions if you still have the earlier build. Turn off **Frame generation** for both runs so the
FPS reflects game frames, and keep the resolution, upscaler and frame rate cap the same.

Attach the log from the slow run and, if available, the one from the earlier build. Say where the FPS dropped and
keep the lines around the drop that show `presents`, `GPU time`, `waits for shaders or pipelines`, `VRAM:` and
`memory heaps`. Compare total and per-heap memory use with the driver's allowances. The texture cache has a
separate budget on the `VRAM:` line.

If the GPU time stays high, a separate run with `RX_VK_PASS_TIMING=1` in `hookshot_env.txt` reports which GPU
passes take the time every 600 presents. Keep the unprofiled log for the FPS comparison since the timing itself
adds work. Remove the switch after collecting the log. The [development guide](docs/development.md#time-and-profiles)
has more switches.

#### Intel laptops

What [Longshot #252](https://git.magicbean.dev/MagicBeanDev/Longshot/pulls/252) changes was made from the logs of a laptop with
Intel UHD Graphics, a 4-thread CPU, 16 GB and Windows. There the game closed in Intel's driver (`igvk64.dll`) in the
background save of the pipeline cache while other threads built pipelines into the same cache; the game now fetches a
cache's data with no build under way on Intel ([Longshot #190](https://git.magicbean.dev/MagicBeanDev/Longshot/pulls/190)).
The build's shader preparation had stopped, so every run built its shaders in play, and the title ran at about 35 fps.
It has not been tested on an Intel GPU yet. On such a PC:

1. Build with **Prepare shaders now** ticked. If the game folder has a `hookshot_prepare_skipped` file from an earlier
   build, delete it first.
2. Keep the Debug tab's **Intel shader compiles** row on **One at a time** (the default). Side by side builds faster on a
   CPU with many cores, but Intel's driver can crash the game then.
3. A shader the driver faulted on is listed in `hookshot_driver_faults.txt` (beside the game) and left out, with
   its draws, on later starts on the same driver. After a driver update the list starts again; delete the file to try
   them all again sooner.
4. Leave **ASTC as RGBA8** off: it is the [AMD texture workaround](#amd-texture-workaround), and its larger textures
   come out of the memory that integrated graphics share with the rest of the PC.
5. If it still crashes or runs slowly, [report it](https://github.com/NotRexed/Hookshot/issues/new/choose) with
   `hookshot_log.txt` from a run with `HOS_VIDEO_LOG=1` in `hookshot_env.txt`, the build's details, and the FPS on the
   title and in the first scene.

#### Steam Deck

On a Steam Deck (LCD or OLED, found by its processor) the game turns on its Steam Deck profile by itself: the settings
that ran fastest there. With the Quality preset on **Auto (this PC)** it sets Minimum's scaling, and when the profile is
first chosen **Frame generation** 2x and the **VRAM budget** Auto (2.5 GB with the Deck's 16 GB, not Minimum's 2.2 GB
cap); if you change those two afterwards they stay as you set them. Whatever the preset, the renderer runs its commands on
a thread of its own and keeps no graphics pipelines ready before the title, which ran the Deck out of memory.
`RX_VK_STEAM_DECK=0` in `hookshot_env.txt` (or a line `steam_deck=0` in `hookshot_options.ini`) turns it off (Auto then
gives back Minimum's VRAM budget; Frame generation stays as it is), and `=1` turns it on elsewhere.
The log's `vk: Steam Deck profile:` and `Auto (this PC)` lines say what it did.

The largest gain on the Deck is its GPU clock, which the game cannot set itself. In Gaming Mode, open the Quick Access
menu (the **...** button), then **Performance**: turn on **Use per-game profile** and **Manual GPU clock control**, and
set **GPU clock frequency** to 1600 MHz. In Kokiri Forest the game went from about 15 to about 20 frames a second (about
28 to 39 shown with Frame generation 2x), and its slowest frames from about 81 to 46 ms. It draws about 19 W instead of
about 8 W and ran up to 68 °C, so it suits the Deck docked or plugged in.

#### AMD texture workaround

For these AMD texture artifacts, try keeping decoded ASTC textures as RGBA8 instead of re-encoding them to BC3
([#57](https://github.com/NotRexed/Hookshot/issues/57), [#1006](https://github.com/NotRexed/Hookshot/issues/1006)).
Turn on **ASTC as RGBA8** in the menu's Debug tab, under Developer, and restart the game. (`RX_VK_ASTC_RGBA8=1` in
`hookshot_env.txt` does the same, as earlier versions of this readme said; while that line is there the row shows its
value and cannot be changed, so remove the line to choose in the menu.)

This is a workaround for some artifacts, not a general lighting fix. It can substantially increase graphics-memory
use and cause stalls when the card runs out of headroom. To undo it, turn the row off (and remove any `RX_VK_ASTC_RGBA8` line from `hookshot_env.txt`) and restart the game.

`RX_VK_ASTC_BC7=1` keeps those big ASTC textures as BC7 instead of BC3. Both are 8 bits a texel, so the graphics memory
is the same; BC7's mode 6 keeps the colours' gradients and alpha much better, and the textures look cleaner where BC3
shows bands or blocks. Off unless set; `RX_VK_ASTC_RGBA8=1` above still wins when both are set.

</details>

## In-game menu

<details>
<summary><b>Every row of the menu, the controls and what each setting does</b></summary>

By default, press <kbd>Insert</kbd>, <kbd>F1</kbd> or <kbd>Esc</kbd> in game. On a controller, press Home or Select and
Start together; on a DualShock 4 or DualSense, clicking the touchpad does the same as <kbd>F1</kbd>, unless a row of
Controls takes the touchpad as its input. In the game's pause menu, the Menu page has a sixth button, **Recomp Options**,
below Title Screen: A on it opens the same menu (a build made with this button; a controller player need not know the keys).
The same keys close it; with every Menu shortcut, <kbd>Esc</kbd> goes back a page or closes the open menu.
<kbd>F1</kbd> always works. **Controls → Menu shortcut** can leave <kbd>Insert</kbd> free for another overlay (F1 only).
With Insert or F1, or with F1 only, <kbd>Esc</kbd> does not open the menu: it only lets the mouse go. Options saved by
an older version on Insert or F1, the default then, move to Insert, F1 or Esc; F1 only stays.
The menu has six tabs, Graphics, Audio, Gameplay, Controls, Neural and Debug:
<kbd>Q</kbd> and <kbd>E</kbd> (or <kbd>Tab</kbd> and <kbd>Shift</kbd>+<kbd>Tab</kbd>) switch between them, LB and RB on
a controller (or the triggers). <kbd>Up</kbd> and <kbd>Down</kbd> choose a row, <kbd>Left</kbd> and <kbd>Right</kbd>
change it (<kbd>Enter</kbd> changes it too); beside the rows, the help says what the row is and, on a line of its own,
what the value chosen does. On a controller the D-pad chooses and changes, A changes too and opens a page (Motion,
Controls, Mods, the Teleport list, the inventory), and B goes back or closes the menu: A and B are the buttons your layout puts the Switch's A and B
on (with the Nintendo layout, A is the right face button). The mouse is free while the menu is open: click a tab, click a row's name to choose it (its
value stays), click the left or right half of a value to lower or raise it, drag a slider, turn the wheel to scroll the rows (it never changes a value), and right-click to go back. The
button prompts at the bottom show the keys or the controller's buttons, whichever you used last. Your choices are saved
in `hookshot_options.ini` in the game folder.

The menu, the FPS counter and the start-up screen are drawn in the style of the game's own menus. They use the game's
own menu font, read into memory from your game files (the romfs folder the game runs from) the first time one of them is
drawn. It is never copied anywhere, and Hookshot does not include it. Without it, or if it has no Latin letters, they use
Libertinus, which Hookshot includes.

The rows marked "after a restart" below are read when the game starts. The help of such a row says "Takes effect
after a restart" before you change it, and in gold once you have. While one is changed, it is tagged "After
restart", and the help on the Graphics tab lists what waits for a restart when that is more than the selected row; closing the menu then asks whether to restart now, with a list of
what the restart applies (the rows changed, and the mods switched on the Mods page). **Later** keeps the change for the
next start (and is not asked again until you change one of those rows, or a mod); **Restart now** saves your
choices and starts the game again, so progress since your last save is lost.

A row for something this PC cannot use is not shown: NVIDIA Reflex and AMD Anti-Lag 2 without a GPU and driver that
have them, the DLSS model where DLSS does not run. HDR paper white and
HDR peak brightness show only while HDR is on, the HDR tone mapper only with HDR set to Native.

On Windows, HDR needs **Use HDR** on for the display (Settings > System > Display) before the game starts.
[`scripts/windows/launch-hdr.ps1`](scripts/windows/launch-hdr.ps1) does that for one start: copied beside
`hookshot.exe`, it turns Use HDR on for one display, sets the HDR rows, starts the game, and turns Use HDR off again
when the game closes if it was off before (`-List` shows the displays and whether each offers HDR; `-PeakNits`,
`-PaperWhite`, `-Dlaa` and `-FrameGen` set those rows too).

The Graphics tab groups its rows under section titles: Resolution and upscaling, Frame generation and latency, Screen,
HDR, Detail, and GPU and memory (last: the rows to change when something is wrong). The table lists them in that order.

| Tab | Option | Choices | Default |
|---|---|---|---|
| Graphics | Quality preset | Custom, Minimum (4GB), Low (6GB), Balanced (8GB), High (12GB), Ultra (16GB+), Auto (this PC) | Auto (this PC) on a first start; Custom in an options file from before it |
| | Aspect ratio | The shapes your screen's resolutions have, narrowest first (5:4, 4:3, 16:10, 16:9, 21:9, 32:9, ...), your monitor's own marked "(monitor's)", or Window to fill the actual window (after a restart) | Your monitor's |
| | Output resolution | The Aspect ratio's sizes: your screen's resolutions and the common ones (1440p, 4K, 5K at 16:9; 1920x1200, 2560x1600 at 16:10; 3440x1440 at 21:9; ...), and 2048x1152 (the game's own reduced size, 80% of its 2560x1440, marked "(reduced)") at 16:9 (after a restart) | 2560x1440, the game's own picture, or your screen's size where it is smaller (a Steam Deck's 1280x800, a 1080p monitor), at its own shape; Auto (this PC) leaves it as it is |
| | Custom output size | A size of your own, typed as `<width>x<height>` (after a restart) | None |
| | Profile | Docked, Handheld (after a restart) | Docked |
| | Upscaler | Game's own, NVIDIA DLSS, NVIDIA DLAA (only in builds with NVIDIA's DLSS SDK, below; DLSS and DLAA on RTX GPUs), AMD FSR 3.1 (every build, on GPUs it runs on, below), AMD FSR 4, AMD FSR 4 Native AA (only in builds with FSR 4, below), Off (no upscaling) | Game's own |
| | DLSS model | Transformer (K), Transformer 2 (M), Transformer 2 (L), NVIDIA default (shown where DLSS runs; used by DLSS and DLAA) | Transformer (K) |
| | Render resolution | Auto (the game's own dynamic resolution), 100%, 75%, 67%, 50% (each with its size). With DLSS, FSR 3.1 or FSR 4: Auto, Quality (67%), Balanced (58%), Performance (50%), Ultra Performance (33%). With DLAA or FSR 4 Native AA: Native. With Off: Auto, 100%, 75%, 67%, 50%, 33% | Auto |
| | Sharpness | 0 to 100%, in steps of 10 | 0% |
| | Frame generation | Off, Auto, 2x to 8x | Off |
| | Frame generation by | Auto (NVIDIA DLSS Frame Generation where it runs: RTX 40 and newer, with a temporal Upscaler; else the built-in one; with frame generation on, the row shows who makes the frames, as Auto: DLSS FG, and why not DLSS FG when another does), Built-in FG, and, in this fork, AMD FSR 4 and AMD FSR 3.1 (2x only) where they run on this PC (changes at once) | Auto |
| | Frame pacing | Off, On | Off |
| | Game frame rate cap | 60, 90, 120, 144, 165, 240 FPS, Uncapped, 30 FPS (after a restart) | 60 FPS |
| | NVIDIA Reflex | Off, On, On + Boost (shown only on NVIDIA GPUs with `VK_NV_low_latency2`) | Off |
| | AMD Anti-Lag 2 | Off, On (shown only on AMD GPUs with `VK_AMD_anti_lag`) | Off |
| | Fullscreen | Off, On (the same as <kbd>F11</kbd>) | Off |
| | V-Sync | Auto, On, Off | Auto |
| | Window scaling filter | Off, Catmull-Rom, Lanczos | Off |
| | Ultrawide menus | Full width; Centred, blurred sides; Centred, black bars (with the Aspect ratio at the monitor's shape) | Centred, blurred sides |
| | HDR | Off, Expanded, Native (the game's) | Off |
| | HDR paper white | 80 to 400 nits (while HDR is on) | 200 nits |
| | HDR peak brightness | 400 to 4000 nits (while HDR is on) | 1000 nits |
| | HDR contrast | 50% to 200% around mid grey (while HDR is on) | 100% |
| | HDR tone mapper | Vanilla (the game's curve), PsychoV35 (RenoDX's; with HDR set to Native. DLSS/DLAA with their NVIDIA frame-generation inputs, and AMD FSR 4, can be tried with `RX_VK_PSYCHOV35_DLSS=1`; FSR 3.1, TAAU and Upscaler Off still fall back to the game's network) | Vanilla |
| | FXAA | Off, On (on the finished picture, in the Window scaling filter's place; not with HDR set to Native; changes at once) | Off |
| | Bloom | Off, Low, Medium, High (a glow around bright light; not with HDR set to Native; changes at once) | Off |
| | Colour grade | Off, Rich, Vivid, Warm, Cool, Cinematic (not with HDR set to Native; changes at once) | Off |
| | Brightness | 70% to 150% (a gamma curve: the mid-tones lighter or darker, black and white kept; for SDR, with HDR on set HDR paper white instead; changes at once) | 100% |
| | Colour vision | Off, Protanopia, Deuteranopia, Tritanopia (daltonization for colour blindness: the colours it confuses moved to ones that can be told apart; not a simulation; greys unchanged; not with HDR set to Native; changes at once) | Off |
| | Retro look | Off, N64 (the picture at the Nintendo 64's 240 lines, soft, its colours cut to 16 bits with the console's dither), N64 + CRT (that picture on a CRT, set by the five CRT rows below); in the Window scaling filter's, FXAA's and Sharpness's place, the menu left sharp; not with HDR set to Native; changes at once | Off |
| | CRT scanlines | Off, Light, Medium, Strong (the dark between the lines of light; bright parts fill out; with Retro look N64 + CRT) | Medium |
| | CRT mask | Off, Aperture grille, Slot mask, Shadow mask (the screen's red, green and blue on your screen's pixels; with N64 + CRT) | Aperture grille |
| | CRT mask strength | 10% to 100% (the picture keeps its brightness; with N64 + CRT) | 30% |
| | CRT glow | Off, Low, Medium, High (light spreading in the glass around bright parts; with N64 + CRT) | Medium |
| | CRT curvature | Off, Subtle, Strong (a curved screen with darker corners; with N64 + CRT) | Subtle |
| | Texture detail | Auto, Full, Medium, Low | Auto |
| | Field of view | 50% to 300%, in steps of 5; applies immediately during gameplay | 100% (original) |
| | Anisotropic filtering | Game's, 2x, 4x, 8x, 16x | 16x |
| | View distance | Short, Original, Far, Very far, Max (how far trees, bushes and detailed models reach; changes at once) | Original |
| | Grass | Off, Less, Original, More, Dense (changes at once) | Original |
| | Shadow distance | Short, Original, Far, Max (how far scenery and characters cast shadows; changes at once) | Original |
| | GPU device | Auto, or each graphics card by name (after a restart) | Auto |
| | VRAM budget | Auto, 3.6, 4.8, 6, 7.5, 9, 11 GB (2.2 GB only from the Minimum (4GB) preset); a quality preset sets it | Auto |
| Audio | Volume | 0 to 100%, in steps of 5 | 100% |
| | Mute in background | Off, On | Off |
| | Audio output | Auto, Stereo, 5.1, Mono (layout changes after a restart; Mono/Stereo live on stereo output) | Auto |
| Gameplay | FPS counter | Off, FPS, Frame time, Graph, Breakdown, Dev | Off |
| | FPS counter position | Top right, Top left, Bottom right, Bottom left | Top right |
| | Classic counters | Off, On (as on the N64: no count over Link at a pick-up, the rupees always in the bottom left corner once a save is loaded; changes at once) | Off |
| | Speedrun timer | Off, On (real time at the top of the screen, in the middle, paused while the menu is open; off and on again starts it from zero) | Off |
| | Death counter | Off, On (how often Link's hearts ran out since the game started, a fairy's revive not counted; at the top, in the middle) | Off |
| | Hero mode | Off, On (double damage, and no recovery hearts from grass, pots, rocks or enemies; fairies, Pieces of Heart and Heart Containers stay; changes at once) | Off |
| | Navi callouts | Off, On (Off: no "Hey! Listen!" for the hints of the places you enter, and none when you ask her there; story dialogue, Z-targeting and her enemy info stay; from the next place you enter) | On |
| | Menu size | Small, Medium, Large | Medium |
| | Game speed | Per frame, Real time | Real time |
| | Text speed | Normal, 2x, 4x, Instant | Normal |
| | Text size | Original, 110%, 125%, 150%, 175% (dialogue, Navi and signs) | Original |
| | Skip title screen | Off, On (after a restart) | Off |
| | Microphone | Off, Default, or each microphone by name | Default |
| | Game language | The game's 16 languages, each by its own name (after a restart) | The one built with |
| | Menu language | Auto (the game's language), or English, Português (Brasil), Español (Latinoamérica), Español (España), Français, Deutsch, Italiano, Nederlands, Polski, Русский, 日本語, 한국어, 简体中文, 繁體中文 | Auto |
| | Discord status | Off, On ("Playing Hookshot" and the time played in your Discord status, while Discord runs on this PC) | On |
| | Skip opening | Off, On (skips the new-game opening: the story movie and Navi waking Link; later cutscenes and the title screen stay) | Off |
| | Mods | Opens the Mods page: each mod in the `mods` folder on or off, and the order they load in (after a restart; [Mods](#mods)) | |
| | Bug report | Saves a report into a new folder in `bug-reports` (below) | |
| Controls | Controller in background | Off, On | Off |
| | Keyboard | Auto (only without a connected controller), On, Off; applies to gameplay and menu navigation; F1 and the enabled Insert shortcut remain available | Auto |
| | Mouse camera | As the stick, Native, Off | As the stick |
| | Disable camera centering | Off, On | Off |
| | Sprint | Off, On | Off |
| | Mouse sensitivity | 0.10 to 5.00 | 1.00 |
| | Invert mouse vertical | Off, On | Off |
| | Invert camera X | Off, On | Off |
| | Invert camera Y | Off, On | Off |
| | Camera speed | 50% to 400%, in steps of 25 | 100% |
| | Stick dead zone | Default (24%), 5%, 10%, 15%, 20%, 30% | Default (24%) |
| | Auto run | Off, On | Off |
| | Rumble strength | Off, 25% to 150%, in steps of 25 | 100% |
| | Layout preset | Nintendo (Def), Xbox / PC, Swap Face, Switch 2 Pro; Custom once you bind a button yourself (on the Controls page) | Nintendo (Def) |
| | Button prompts | Auto, Switch, Xbox, PlayStation 4, PlayStation 5, Steam Deck (on the Controls page) | Auto |
| | Motion | Opens the Motion page: Motion controls (Off, On; On), Motion sensitivity X (10% to 600%) and Y (10% to 300%; 100%), Invert motion X and Y (Off, On; Off), Motion deadzone (Low, Standard, High; Standard) | |
| | Walk mode | Hold, Toggle | Hold |
| | Walk speed | 15% to 90%, in steps of 5 | 45% |
| | Controls | Opens the Controls page | |
| | Menu shortcut | Insert or F1; F1 only; Insert, F1 or Esc | Insert, F1 or Esc |
| | Controller menu button | None, Home, Back left (GL), Back right (GR) | Home |
| | Compact menu key | Right Shift, Right Ctrl | Right Shift |
| | Screenshot key | Off, F12 (saves the picture as the window shows it, without the menu or the FPS counter, as a PNG in the `screenshots` folder: [Controls](#controls)) | F12 |
| NFC | NFC tag | The tag files of your NFC folder, by their names | The first |
| | Tap tag | Holds the chosen tag to the game's reader | |
| | Remove tag | Takes it off the reader | |
| | Scan tag on controller | Reads a tag you own with a Switch 2 Pro Controller (USB) and saves it in your NFC folder | |
| Debug | Debug tools | Off, On (the tools below it while on) | Off |
| | Player: Damage taken | Half, Normal, Double, Quadruple (live, while Debug tools is on; Half rounds damage up to a quarter heart; Heart protection wins) | Normal |
| | Developer: Descriptor reuse | Off, On (changes at once) | On |
| | Developer: Sampler cache | Off, On (changes at once) | Off |
| | Developer: Robust buffers | Auto, Off, On (after a restart) | Auto |
| | Developer: ASTC as RGBA8 | Off, On (after a restart) | Off |
| | Developer: Intel shader compiles | One at a time, Side by side (after a restart; Intel graphics on Windows only) | One at a time |

- **Quality preset** sets Render resolution, Window scaling filter, Sharpness, Frame pacing, Game speed, Profile
  and the video memory limits for a card with that much memory. It leaves the Upscaler and Frame generation as
  you chose them: with DLSS, FSR 3.1 or FSR 4, the preset's resolution becomes their nearest mode. Changing most other
  rows yourself sets it back to Custom.
- **Auto (this PC)**, which a first start begins on, chooses for the PC it runs on: the memory tier from the card's
  video memory (an integrated GPU, a Steam Deck or a card without mesh shaders at Minimum), DLSS on an NVIDIA RTX card
  or FSR 4 on an AMD RX 9000 where the build has them (else the game's own upscaler), and on a Steam Deck the
  [Steam Deck](#steam-deck) profile. It leaves the Output resolution as it is: on a first start the game's own
  2560x1440, or the screen's size where that is smaller (a Steam Deck's 1280x800, a 1080p monitor), applied from the
  first start with no restart. In the first minute of play it then measures the GPU: while
  frames are missed with the GPU over 90% busy it lowers the Render resolution a step, and while the frame rate cap holds
  with the GPU under half busy it raises it a step, up to the best mode that still upscales (DLSS or FSR Quality, or 100%
  with the game's own; never DLAA or native AA). At most two steps; a PC that holds its cap keeps its picture. It chooses again when the card or the screen changes. `hookshot_log.txt`'s
  `Auto (this PC)` lines say what it chose and why.
- **Menu size** is how large the menu, the FPS counter and the start-up screen are drawn: Medium unless you choose Small
  (a desk) or Large (a TV across the room). It stays the same whether you use a controller or the keyboard and mouse.
- **Field of view** changes the gameplay camera's vertical angle: 100% keeps the game's view, higher shows more of the
  world and lower brings it closer. The game's zoom changes remain relative to your choice.
  Aiming has been tested in the 50% to 150% range, including with ultrawide enabled.
  Cutscenes, the HUD and movies keep their own view. The setting is saved as `field_of_view` in `hookshot_options.ini`.
- **Skip title screen** starts the game with your most recent save: Hookshot presses A through the title screen and its
  file list as soon as the game has a save. Until you have saved once, it leaves the title screen alone, so a new game can
  still be started. It applies after a restart; turn it off to watch the intro and use the title.
- **GPU device** matters on a PC with more than one graphics card (a laptop's integrated and dedicated GPUs, or a
  second card for Lossless Scaling). Auto prefers a dedicated one, and only cards with Vulkan 1.3 are listed.
  `hookshot_log.txt` lists every card as `vk: device <n>`; `RX_VK_DEVICE=<n>` chooses one for a single run and wins
  over the menu.
- **Frame generation** makes extra frames between the game's own. It adds a little input delay, and fast motion can
  show artifacts. The renderer's own interpolation makes the frames; at 2x, AMD FSR 3.1's frame interpolation can make
  it instead with `RX_VK_FSR_FG=1` (below: it moves the HUD with the scene, so it is not the default). **Frame pacing** shows frames at an even interval: less stutter, up to one frame of delay. It paces
  the frames that frame generation shows, so it has no effect while Frame generation is Off.
- **Game frame rate cap** limits the frames the game renders. With a cap of 60 and Frame generation at 2x, the output
  can reach 120 FPS. Choose **Auto** in Frame generation to target the display's refresh rate instead of a fixed multiplier.
  **30 FPS** reduces rendering work for handhelds and slower PCs while keeping real-time game speed. It is the last option
  in the row so existing saved caps keep their meaning. At 30, Game speed follows real time even if Per frame is selected.
  A cap **past 60 is experimental**: the game keeps real time, but some cutscenes and bosses still count frames and can
  misbehave (Gohma running into the wall, the intro's narration running ahead: #1742). 60 is the safe choice.
  Scarecrow's Song keeps the timing of its eight-note recording and playback above 60. Saved songs are not retimed;
  re-record a song after updating if its recorded rhythm was lost.
  **Uncapped** renders as fast as the PC can (the game still keeps real time). A display that waits for its refresh still
  holds the frames to its refresh rate: V-Sync on, or the driver's FIFO mode. `HOS_FPS_MAX=30` or `<61-1000>` sets a cap for one
  run.
- **Bug report** writes a folder `bug-reports/<date>_<time>` in the game folder with what an issue needs: `report.txt`,
  which answers the [game problem form](https://github.com/NotRexed/Hookshot/issues/new?template=1-game-problem.yml)'s
  questions under its own headings (the version, the map you are in, your graphics card and driver, CPU, RAM and
  system, the menu options and the `RX_`/`HOS_` switches you changed) and ends with a link that opens the form with them
  filled in (the switches by name only); `hookshot_log.txt` (this run's log so far) and `hookshot_log.1.txt` (the run
  before's, which has the crash if the game crashed last time); and `picture.png`, the game's picture without the menu.
  Settings whose defaults depend on the display, upscaler, Auto preset or other run-time context are listed after the
  changes, in the same answer, under a **Depends on this PC** line, with their current value and “default depends on this
  PC”. They are not counted as changed settings; the report does not invent a default from a run-time list index. The rows
  a preset sets keep their fixed defaults on Custom while Auto (this PC) has never chosen for the options file; with a
  preset, or once Auto has chosen, they depend on this PC.
  Fixed defaults, including GPU Auto, the system-default microphone and Frame generation by's Auto, still report actual
  changes; the Aspect ratio's default is the monitor's shape, and the Game language's `language.txt`'s.
  Your home folder is written `~` (`%USERPROFILE%` on Windows) and your user name `<user>` in the logs' paths. A switch's
  value is written only when it is a number, a size or on/off, and never for a name with `TOKEN`, `KEY`, `ROOM`,
  `SECRET`, `PASS`, `SERVER` or `USER` in it; other values read `(value left out)`. Nothing else goes in (no saves, no
  game files, not `hookshot_options.ini` or `hookshot_env.txt` themselves), and nothing is sent: open the form, write
  what happened, and drag the folder's files into it (from File Explorer on Windows, a file manager on Linux; on a Steam
  Deck, in Desktop Mode). The row then shows the folder's name. A game that stops before its menu can be used leaves its
  log as `hookshot_log.1.txt`: start it again, or attach that file yourself.
- **The scaling rows**, in the picture's order: **Output resolution** is the size of the game's whole frame, HUD
  included. The **Upscaler** fills it from the 3D: the game's own network, NVIDIA DLSS or DLAA (the 3D at full size,
  edges smoothed), AMD FSR 3.1, or AMD FSR 4 or its Native AA (below). DLSS and DLAA look softer than the game's own: set
  **Sharpness** to around 80% with them. **Off** is no upscaler at all: the game's own network is left out too, and the 3D
  is stretched to the output with a plain linear filter (the fastest choice, below). **DLSS model**
  chooses their network (below). **Render
  resolution** is the 3D's share of the output. The **Window scaling filter** then scales the frame to your window,
  and **Sharpness** sharpens it, by the picture's pixels: when the window is much larger than the picture (the Handheld
  Profile's 1536x864 on a 4K screen), a Sharpness kept from an older version is stronger than it was, so a lower one may
  suit.
  Changing the Upscaler keeps your chosen render scale, including across a restart. An engine without that scale
  temporarily uses and shows its nearest supported size: DLSS Balanced (58%) shows 50% with the game's own, then 58%
  again on returning to DLSS. Changing Render resolution or choosing a Quality preset replaces that saved scale.
- **Window aspect ratio** (opt-in): fills the actual window. Wider than 16:9 shows more at the sides (Hor+);
  narrower or taller shows more above and below (Vert+), keeping the 16:9 horizontal view. Select Window in
  Graphics, Aspect ratio, then restart (`ultrawide=2` in `hookshot_options.ini`; 1 keeps Monitor's shape,
  0 keeps the chosen output shape). Later window resizes update the camera and presentation without a restart;
  the picture size is set by the window's shape at start. Only the Output resolution's height is used.
  A windowed start is normally 1280x720: widening it later stretches the fixed-size picture, so it can look softer
  than Monitor's shape. Start full screen or set `HOS_WINDOW_SIZE` to choose another startup shape.
  Startup and live shapes are clamped to 5:4 through 48:9 (2448x1848 is within this range).
  Narrow windows render more pixels at startup and may run slower.
  The UI keeps its 16:9 proportions in the centre, including after resizing. HUD docking and size controls are not added.
  The existing monitor modes, including their narrow-screen HUD behavior (https://github.com/NotRexed/Hookshot/pull/2015), stay unchanged.
- **Aspect ratio** and **Output resolution:** the menu lists the resolutions your screen offers (its display modes, as
  Windows lists them, DSR's included), with the common sizes of each of those shapes your screen does not list (1440p, 4K
  and 5K at 16:9, 1920x1200 and 2560x1600 at 16:10, 3440x1440 at 21:9, ...), grouped by shape. **Aspect ratio** lists
  the shapes, your monitor's own marked "(monitor's)" (the default: 21:9 on an ultrawide, 16:10 on a 16:10 screen);
  **Output resolution** then lists that shape's sizes, your screen's own marked "(native)". A size larger than your
  screen is drawn at that size and scaled down to the window. The marks are for the monitor the game's window is on, and
  follow it: moved to another monitor, or the desktop's resolution changed while playing, the menu adds that screen's
  sizes. On Linux the screen's size comes from SDL (the primary display). A portrait screen has no shape the game can
  draw, so the row shows Monitor's shape as a value of its own there. Docked only. A shape other than 16:9 widens the cameras (21:9, 32:9) or narrows the
  picture (16:10, 4:3, 5:4) and keeps the HUD and movies in the middle 16:9. At 16:9 on a 5120x1440 (32:9) monitor, the
  game's 16:9 picture is stretched across the 32:9 output, sharp but wide. Options saved by an older version at 16:9,
  the default then, move to Monitor's shape on a screen narrower than 16:9 (16:10 such as the Steam Deck's, or 4:3),
  where 16:9 only adds bars above and below; an ultrawide keeps its 16:9. The output's rows below show the sizes for the
  output you chose. At your screen's own size the HUD and text map pixel for pixel. Above 2560x1440 the game's render
  targets get a bigger GPU pool, so a full-size 3D fits. Where the screen's modes are not known (Linux), the menu offers
  1920x1080, 2560x1440, 3840x2160, 5120x1440 and 5120x2880. For a size the menu does not offer, type it in
  **Custom output size** (Enter or the pad's confirm button to edit and set it, Esc or the back button to cancel).
  On a controller, D-pad Left/Right moves the caret, Up/Down cycles its digit or separator, the right shoulder inserts
  a digit and the left shoulder removes a character. At the end, Up/Down adds a character. The shown Paste button
  still pastes; with a keyboard, Ctrl+V or Shift+Insert does the same. Full-width digits and `ｘ` become ASCII.
  Or set `output_res=<width>x<height>` in `hookshot_options.ini`: each side a multiple of 8, at least 640x360,
  at most 5120x2880's pixels, and between 5:4 and 48:9 in shape. The menu says why it refuses a size; in the file,
  anything else uses the game's reduced 2048x1152. The Output resolution row chooses the typed size from its list when it is
  already there, including sizes found after a monitor change, or offers it as your own choice and selects its shape.
  Typing a 16:9 size keeps Aspect ratio on the monitor's shape when it already follows the monitor.
  The size this run started with stays available until the next start, so returning to the starting shape still
  restores that size even after a custom-size edit.
  A picture wider or narrower than 16:9 is kept to 5120x2160's pixels, so above that a size of another shape is
  not a native frame. A size's own shape sets the camera's, even when the OS reports a single 16:9 primary monitor. For
  three 16:9 monitors, use `5760x1080` or `7680x1440` and a window or logical display
  that spans all three. Both render at full size: 7680x1440 has 5120x2160's pixels, the most a wide picture takes.
  For one run, set `HOS_OUTPUT_RES` to a size, such as `HOS_OUTPUT_RES=3840x2160`.
- **Window scaling filter** matters only when your window's size differs from the Output resolution: for the sharpest
  picture, set the Output resolution to your screen's, and the row shows "Not needed (window = output)". It and
  **Sharpness** also work when Frame generation is Off.
- **Anisotropic filtering** keeps textures sharp on surfaces seen at a slant: the paths and floors ahead of Link. The game
  asks for 1x or 2x, which at a PC's resolutions smears the ground a few metres off; 16x costs little on most cards, and
  Game's is the console's own. `RX_VK_ANISO=<n>` sets it for one run (0: the game's).
- **Upscaler Off** (`dlss=6` in `hookshot_options.ini`) is for slow GPUs and for measuring: no DLSS, no FSR, and not the
  game's own network either, which otherwise runs on every frame (at the game's usual 3/4 share it scales the 3D up and
  smooths its edges; at 100% a pass of the same kind still smooths them). In its place the 3D is stretched to the output
  with a linear filter, and the HUD is drawn over it at the output's size as always. Nothing is kept from frame to frame, so
  there is no ghosting, but no anti-aliasing either: edges are jagged, and below 100% the picture is soft. The Render
  resolution then sets the 3D's size alone (Auto, 100%, 75%, 67%, 50%, 33%): lower is faster. RX_VK_DLSS, RX_VK_FSR4 and
  RX_VK_FSR set for a run go over it, as over the row's other choices.
- **Texture detail with DLSS, FSR 3.1 or FSR 4:** DLSS and DLAA sample the world's textures as NVIDIA's DLSS guide asks:
  at the output's size and one mip step finer (the game's own bias + log2(3D / output) - 1), which DLSS resolves over its
  frames, so they keep the detail of the full-size picture instead of the 3D's smaller size. FSR 3.1 and FSR 4 sample them
  one finer mip step for each halving of the 3D below 75% (the game already does so for its own 75%).
  `RX_VK_UPSCALE_LOD_BIAS=0` turns it off; `RX_VK_DLSS_LOD_OFFSET=<steps>` sets DLSS's extra step for a run (-1 by default,
  0 for none, down to -3).
- **NVIDIA Reflex** Off is the game as without it. `RX_VK_REFLEX_LOG=1` logs the driver's latency timings every 300
  frames while it is on.
- **AMD Anti-Lag 2** Off is the game as without it. It works with Frame generation too: each game frame's present
  stage is given when that frame itself is shown, not at the made frames before it.
- **Profile** runs the game as the console docked (at the Output resolution) or Handheld (1536x864): lighter on the GPU.
- **Mesh shaders** (how the game's mesh programs, much of the scenery, run) is no longer a menu row: changing it made
  the next start translate every shader again. The game uses the GPU's own mesh shaders where it has them, and the
  compute path where it has not and on Linux AMD cards (issue 2245). For troubleshooting, `RX_VK_MESH_SHADERS=compute`
  in `hookshot_env.txt` uses the compute path on every GPU (try it if your card crashes or leaves objects out; usually a
  little slower), and `RX_VK_MESH_SHADERS=native` the GPU's own for every draw. A `mesh_shaders=` line left in
  `hookshot_options.ini` is no longer read.
- **Ultrawide menus:** with the Aspect ratio at the monitor's shape, the pause, item and map menus stay in the middle
  16:9, with what the game draws beside them out of focus, or black; Full width stretches them over the whole screen,
  as before. Loading screens and pre-rendered movies get the same sides. It changes at once.
- **V-Sync:** Auto is mailbox where the driver has it (no tearing, no wait for the display); otherwise On, or on Windows
  Off. On waits for each refresh (FIFO): no tearing, at most the display's rate. Off shows each frame at once and can
  tear (where the driver cannot, it is Auto). It changes at once. `RX_VK_FIFO=1` (On) or `RX_VK_IMMEDIATE=1` (Off) chooses
  for one run.
- **Robust buffers** (Debug tab, Developer): a read past a buffer's end is dropped instead of stopping the GPU. Auto is
  on, on every card; Off can be faster on some NVIDIA cards.
- **ASTC as RGBA8** (Debug tab, Developer): the AMD texture workaround below.
- **Intel shader compiles** (Debug tab, Developer; Intel graphics on Windows only): One at a time, the default, lets one
  thread at a time into Intel's shader compiler; Side by side is faster on many cores but can crash in the driver. See
  [Intel laptops](#intel-laptops). It applies after a restart.
- **Game speed:** with Per frame, the game runs slower whenever it is below 60 fps. Real time keeps it at normal speed
  down to 15 fps.
- **FPS counter** shows in a corner (**FPS counter position**; at the top right while the menu is open), at one of
  five levels. **FPS** is the number alone (an options file's old On); with frame generation on, it also shows the
  game's own rate and who makes the frames: `Base 60, DLSS FG` (NVIDIA DLSS Frame Generation), `FSR 3.1 FG` or `Built-in FG`. **Frame time** adds the game's frame time and its 1% low (the rate of the slowest 1% of frames over
  the last 10 seconds). From this level on, the number and the frame time are green at the Game frame rate cap's rate,
  amber under it and red under two thirds of it. (The cap's rate is the display's refresh instead with V-Sync On when
  that is slower; with Uncapped and V-Sync not On there is no line, and the colours are against 60.) **Graph** adds
  the frame times of the last 4 seconds (each point the slowest frame of its span, so no stutter is missed), with a
  dashed line at the Game frame rate cap's frame time and a red mark over frames that took more than twice it; its
  scale follows the usual frame, so a spike is drawn at the top rather than flattening the rest. **Breakdown** adds
  where the frame's time went on the game's presenting thread, as a bar and in numbers: the game's own code (Game),
  recording and submitting the GPU's work (Renderer), waiting for the GPU (GPU wait), and waiting for the frame's turn
  (Pacing: the frame rate cap, vsync, Reflex); then the GPU's own time per frame, and the shaders built and draws left
  out in the last 4 seconds (red marks on the graph where they happened, the usual cause of a stutter). **Dev** adds the
  renderer's own numbers, for debugging and bug reports: video memory used of what the driver allows (red past it), the
  textures held and their memory, draws, dispatches and render passes a frame, draws skipped a frame (red when any),
  texture uploads a second and the pipelines built since the start.
- **Volume** scales the game's whole sound, on top of the game's own sound settings and Windows' volume. Its steps
  follow a curve so they sound about even: 50% is a quarter of the level (-12 dB). **Mute in background** silences the
  game while another window has the focus; an overlay such as Steam's or Discord's does not count as another window
  while the game was in front.
- **Audio output** is the speakers the game mixes its sound for. Auto is 5.1 when your default output device has 5.1
  or more speakers, else stereo; Stereo or 5.1 chooses one whatever the device has (5.1 on stereo speakers is mixed
  down). Auto counts the speakers Windows names, not the channels: an audio interface whose outputs are not set up as
  surround speakers (a Focusrite Scarlett's 8 outputs, for one) is stereo, so voices and the ocarina do not go to an
  output with nothing connected. Mono averages the stereo channels into both ears, for one-sided hearing or one earbud.
  Mono/Stereo changes apply live while output is stereo; changing the channel layout (from or to 5.1) needs a restart.
  Auto never applies the mono average. Saved `audio_output` values remain 0 Auto, 1 Stereo, 2 5.1; Mono is 3.
  For one run, `HOS_AUDIO_CHANNELS=2` or `6` chooses the channel layout over the menu (6 leaves Mono inactive).
- **Microphone** is what the ocarina hears when the game's own microphone option is on (an instrument, or humming).
  Default follows Windows' default recording device; the list shows each microphone by name, and a change applies at
  once. A chosen microphone that is unplugged stays chosen (shown as not connected): Default stands in until it is
  back. On Linux (SDL2) two microphones with the same name cannot be told apart: the first is used. Windows must allow desktop apps to use the microphone
  (Settings, Privacy & security, Microphone). `HOS_MIC_LOG=1` logs what the game reads, a line a second.
- **Game language** is the game's own text, `language.txt` in the game folder: the row writes it once you leave the row,
  and the game reads it at its next start (`HOS_LANGUAGE`, when set, wins over the file, as for the game). Where the
  folder cannot be written the row goes back to the file's language. **Menu language** is this menu's: Auto follows the
  language the game runs in until the restart (English (UK) and French (Canada) take English and French). The
  translations are machine-made and want checking by speakers of each language: each is
  one line in `gpu/vk/menu_i18n.h`. Place and item names stay English for now. Japanese, Chinese and Korean letters come
  from the game's own fonts for them, with Windows' (Yu Gothic, Microsoft YaHei, Microsoft JhengHei, Malgun Gothic) or
  Linux's Noto CJK where a game font lacks one.
- **Discord status** shows "Playing Hookshot" and the time played in your Discord status. It is on by default and does
  nothing unless a Discord client is running on this PC; with the row Off nothing is sent to it.
- **Controller in background:** On keeps the controller working while another window has the focus. The keyboard and
  mouse still need the game's window.
- **Mouse camera:** Native turns the camera with the mouse one to one, as in a PC game: the camera that follows Link,
  and also the aim (bow, slingshot, hookshot, first-person view), the aim while locked on, lock-on's manual turn, riding
  Epona and the event and talk cameras you can turn. The aim starts at the pitch the view had, not level. As the stick
  uses the mouse in place of the right stick. The <kbd>-</kbd> and <kbd>=</kbd> keys change the sensitivity in game too.
  When another camera takes over, Native leaves it alone; on returning, mouse look starts from the game's current
  pitch and yaw rather than restoring the old view. Off leaves the mouse out of play: a click in the window doesn't
  capture it, so it neither turns the camera nor presses buttons. Play with a controller or the keyboard.
- **Disable camera centering:** On stops the game gradually turning the camera toward your movement, so it does not fight
  native mouse look. With Mouse camera on Native, it also keeps the aim's direction when you stop aiming instead of
  swinging the camera back behind Link. Off keeps the game's standard behavior. Changes apply immediately with either
  Mouse camera mode.
  Manual controls, explicit recentering and scripted camera headings still work; automatic pitch adjustment is unchanged.
- **Sprint:** On lets Link run with <kbd>Shift</kbd> held or the left stick pressed once while you move (see **Sprint**
  under Controls). Turning it on moves Shift from B to Sprint (B goes to <kbd>V</kbd>) and the left stick's press from LS
  to Sprint; turning it off puts them back.
- **Camera speed** is how fast the right stick turns the camera, in percent of the game's own speed. The camera keys
  follow it, and so does the mouse with Mouse camera on As the stick; Native mouse look has its own sensitivity. The
  game's own camera speed option still picks the speed this multiplies.
- **Stick dead zone:** how far a stick moves from center in any direction before it counts. Default is about 24%. Use
  a lower value for a precise stick or a higher one for a stick that drifts. The game also applies its own dead zone.
- **Auto run:** the sprint goes on after the run button (A) is let go. Hold A for 0.4 s while moving (the roll, then
  the sprint, as usual), let go, and A stays held for the game while the stick stays pushed; a short press (a roll on
  its own) is not kept. Letting go of the stick or pressing A again stops it (a long hold keeps it again). Only while
  Link is yours to move: an event (a talk, a cutscene), the pause menu, the map, the Insert menu and the ocarina's notes
  end it, so A never picks an entry, skips text or plays a note there.
- **Rumble strength** scales the controller's rumble: 100% is the game's own, Off turns it off. The game's HD rumble
  goes to a controller's heavy and light motors by its frequency.
- **Motion controls** (Controls tab, Motion page): the controller's gyroscope aims where the game uses motion, as on the Switch. It works with
  Switch Pro controllers and pads in Switch mode, DualSense and DualShock 4 (through SDL). Its row
  says whether the connected pad has a gyroscope; Off leaves the game seeing a pad lying still. **Motion sensitivity X/Y**
  scale the left-right and up-down aim (100% is the console's), **Invert motion X/Y** turn either direction around. The game gets the motion
  state as a Switch (and Eden) builds it, so how you hold the pad when motion starts does not matter. Motion follows the pad used
  last. The gyroscope's drift is learned while the pad rests on a table, so set it down for a second if the aim
  creeps. `HOS_MOTION_DEBUG=1` (in `hookshot_env.txt`) logs what the game gets twice a second.
- **Layout preset:** Nintendo has A on the right face button, Xbox / PC and Swap Face put A on the bottom one. Changing
  a button yourself sets it to Custom.
- **Button prompts** (on the Controls page): the button icons in the game's texts, hints and menus. Auto shows the first
  controller's; with no controller connected, the keyboard's. Keyboard shows the key or mouse button your controls put each
  action on (the first of its two), and WASD and the mouse for the sticks; the ocarina's notes and the pause menu's
  controller keep the Switch's buttons.
- **Save my pipeline list** (Debug tab, under Developer): see [Send your pipeline list](#send-your-pipeline-list).
- **Walk mode** and **Walk speed:** on the keyboard the movement keys push the stick all the way, so Link runs. While the
  Walk key is held (<kbd>Caps Lock</kbd> unless you change it on the Controls page), they tilt it only Walk speed of the
  way, and he walks; with Walk mode on Toggle, one press walks and the next runs again. 15% is his slowest walk, 45% to
  50% his fastest; from 55% up he jogs, then runs. Controllers, the mouse and the camera keys are not changed. Caps Lock
  still switches capitals on and off in other programs at each press: bind another key if that bothers you.
  Walk mode is separate from the Controls page's Toggle column, which holds Switch buttons such as ZL, not Walk.
  They can be used together without toggling twice. In Toggle mode, walking stays selected across Insert and focus
  changes, but a Walk key held when play resumes must be released before a fresh press changes that selection.

### Controls

Use a controller, or the keyboard and mouse. On the keyboard, <kbd>W</kbd> <kbd>A</kbd> <kbd>S</kbd> <kbd>D</kbd> move
(hold <kbd>Caps Lock</kbd> to walk) and the arrow keys (or <kbd>I</kbd> <kbd>J</kbd> <kbd>K</kbd> <kbd>L</kbd>) turn the
camera.
With the default keyboard bindings, press <kbd>E</kbd> to select **New Game** on the title screen.

**Sprint** (off by default: the Controls tab's **Sprint** row): hold <kbd>Shift</kbd> while you move and Link runs. On a
controller, press the left stick in once while you move: Link keeps running until you stop, then press it again. Sprint
holds A, the game's own run, only while the left stick (or the movement keys) is pushed, and the game never sees that A
as a press: Link runs at once, without rolling, and runs past people, signs and pots without talking, reading or picking
up. Your own A still works while sprinting: Sprint lets go of A for a moment as yours goes down, so a tap rolls (or
talks, opens, picks up) as it does without Sprint. While the ocarina waits for a note, Sprint holds nothing (A is a note
there), and the left stick's toggle ends.
(`HOS_SPRINT_STILL_MS=<ms>` in `hookshot_env.txt` starts a sprint with the stick let go for that long instead, the older
way round the roll, for a game without the patch.) Turning the row on changes your controls: Shift moves from B to Sprint (B
goes to <kbd>V</kbd>, when no control has V) and the left stick's press from LS to Sprint. Turning it off puts them
back. Controls you rebound yourself, and keys or buttons you gave Sprint, are left alone. Sprint has its own row on the
Controls page.

**Screenshots:** press <kbd>F12</kbd> to save the picture as the window shows it: at its size in the window, with the
Graphics tab's looks in it (Retro look, Colour grade, Bloom, FXAA, Sharpness, the scaling filter) and without the menu, the
FPS counter or the other overlays. It goes into the `screenshots` folder of the game folder as
`Hookshot <date> <time>.png`, and "Screenshot saved" shows for two seconds. The PNG is not compressed (about 25 MB at
4K). With HDR set to Native, the game's HDR picture is tone mapped to SDR for it (its paper white as the white).
**Controls → Screenshot key** turns the key off; F12 cannot be bound to a control.

**Mouse in the game's menus (Windows):** the title screen and its file list, the pause menu, the Key Items, Threads of
Time and Map pages, the options and the save dialogs free the mouse while they are shown. Point at an entry to select
it, left-click to choose it (A) and right-click to go back (B); the tabs, the L and R signs and the Back prompt can be
clicked too. The wheel turns the pause menu's pages and scrolls lists; on the map it changes floors and zooms. Drag
with the left button to pan the map and the tapestry or turn a stone on Key Items. The cursor stays hidden while you
play on a controller or the keyboard, until the mouse moves.

**Rumble:** a Nintendo Switch Pro Controller or Joy-Con plays the game's HD rumble as the Switch does, each side and
both frequency bands as the game asks, with SDL3 (the Windows game brings it; on Linux the system's SDL3, where it has
one). Other controllers, Switch 2 controllers, a pair of Joy-Cons used as one controller, and SDL2's own library get
the game's rumble on their two motors. The menu's Rumble strength scales it too. `HOS_HD_RUMBLE=0` sends the Switch
controllers the motor rumble too. On Linux, SDL talks to the Switch controller itself through its hidraw device, which
needs read and write access for your user; Steam's udev rules (the `steam-devices` package on most distributions) give
it. Without them the kernel's hid-nintendo driver runs the controller, and it gets the motor rumble. HD rumble goes to
anything SDL reports as a Switch Pro Controller or Joy-Con, and that includes third-party controllers in Switch mode
(8BitDo, GameSir and others; SDL gives them Nintendo's ids). Some of them may turn it into weak rumble or none: set
`HOS_HD_RUMBLE=0` to give them the plain motor rumble.

**NFC tags:** where the game asks for a figure's NFC tag, the Insert menu's **NFC** tab gives it one. The tags are files
in a folder of yours, dumps of tags you own: `.bin` (an NTAG215's 540 bytes; 532 and 572 byte ones too) or a Flipper
Zero's `.nfc`. The folder is `%LOCALAPPDATA%\Hookshot\nfc` on Windows and `~/.local/share/hookshot/nfc` on Linux
(`HOOKSHOT_NFC_DIR` names another); copy them in yourself.
Choose one in the **NFC tag** row and press **Tap tag** while the game waits for one (or before: it stays at the reader
until the game reads it). With a Nintendo Switch 2 Pro Controller plugged in over USB (Windows), a real tag held on the
controller is read too, and **Scan tag on controller** saves one into the folder. Only a tag's ID and its figure's model
are read from a file; what a game writes to a tag is kept beside your saves instead (`user/nfc`), and no tag, real or
file, is ever written. [docs/nfc.md](docs/nfc.md) has the details.

**The Nintendo Switch 2 Pro Controller over USB (Windows):** Windows has no driver a game can use for it, so the game
reads it itself: plugged in with its cable, it is a controller with its motion sensor and rumble like any other, with no
bridge program. Pick **Switch 2 Pro** as the Layout preset (Controls page) for its own buttons and the Switch's icons;
its Home button opens this menu (**Controller menu button**, which can also be GL or GR, or none). Only one program can
have the controller: close Steam (it takes it for Steam Input) and any bridge such as Switch2Connect first, or the log
says another program has it. A controller that stops taking rumble (it happens; the log says so) plays its own buzz and
click instead until it is unplugged and plugged in again. Not over Bluetooth, where the controller speaks a pairing of
Nintendo's own. `HOS_SWITCH2=0` leaves the controller alone.

To change which gamepad button or key presses a Switch button or sprints, or which keys move, walk and turn the camera, open the
Controls tab's Controls page. Choose a row and a column (Input 1 or 2 for the gamepad, Key 1 or 2 for the keyboard: each
control takes two of each), press <kbd>Enter</kbd> (or the bottom face button), then the new button or key. <kbd>Esc</kbd> cancels, <kbd>Delete</kbd> clears it, and Reset to defaults
puts them all back. A gamepad button taken from another Switch button swaps with it. The page saves them in
`hookshot_options.ini`.

**Toggle:** on the Controls page, set a Switch button's Toggle column to On to hold it with one press and release it
with the next. Both gamepad inputs, bound keys and mouse buttons share the latch. Every Toggle starts Off.
Plus, Minus, stick directions, Walk and ocarina note rows have no Toggle. Opening Insert, pressing Plus or Minus,
losing focus, rebinding or Reset to defaults releases latched buttons. With Controller in background On, a new
press can latch again behind another window. On Linux, any menu screen receiving pane focus also clears the latch,
not only the pause page. Insert always releases it. There is no separate on-screen latch indicator.

**Ocarina notes:** the page gains five rows, `Ocarina note (L)`, `(R)`, `(A)`, `(Y)`, `(X)`, unset by default: the game's own
buttons play until you bind a note to a key or gamepad input of your own, and a bound note then answers only that input while
the game waits for it. A dialogue or cutscene that takes the buttons ends the wait, and a song lesson keeps the game's own too.

<details>
<summary>Writing the controls in hookshot_options.ini yourself</summary>

```ini
pad_a=0
key_a=69,13
toggle_a=0
```

`pad_<button>` is a gamepad input by position: 0 bottom face button, 1 right, 2 left, 3 top, 4 Select or Back, 5 Home,
6 Start, 7 and 8 the stick presses, 9 and 10 the shoulder buttons, 11 to 14 the D-pad (up, down, left, right), 15 and
16 the triggers, -1 none. `key_<button>` is one or two
[Windows key codes](https://learn.microsoft.com/windows/win32/inputdev/virtual-key-codes) in decimal (69 is
<kbd>E</kbd>, 13 <kbd>Enter</kbd>), 0 none; the mouse's buttons are 1 (left), 2 (right), 4 (middle), 5 and 6 (side
buttons), and count while the mouse is captured. The buttons are `a` `b` `x` `y` `l` `r` `zl` `zr` `plus` `minus` `ls`
`rs` `left` `up` `right` `down`, for keys only the left stick's and the camera's directions and walking: `move_up`
`move_down` `move_left` `move_right` `cam_up` `cam_down` `cam_left` `cam_right` `walk`, and the ocarina's five notes,
which also take a `pad_` line: `note_l` `note_r` `note_a` `note_y` `note_x`; `sprint` takes both a `pad_` and a
`key_` line. A button the file leaves out keeps its default. `toggle_<button>=0|1` sets that button's Toggle (0 Off,
the default; 1 On). It accepts the Switch buttons above except `plus` and `minus`; stick directions, Walk and note
rows do not accept it. Other values mean Off.
The file saves enabled flags, not held state; a restart starts with no button latched.

</details>


### What this fork adds

#### Upscaling and frame generation

**The upscalers are upstream's**, all of them: the Graphics tab's **Upscaler** row (the game's own, NVIDIA DLSS and DLAA,
AMD FSR 3.1, AMD FSR 4 and its Native AA) and **NVIDIA DLSS Frame Generation** on the **Frame generation by** row's Auto
are the code upstream ships and tests, described further down this page. This fork used to carry its own FSR 4 upscale
and its own DLSS frame generation; both are gone in favour of upstream's, which were measured in the game on the hardware
they are for.

What the fork adds on top:

- **AMD's frame generation on the Frame generation by row.** Beside upstream's **Auto** (NVIDIA DLSS Frame Generation
  where it runs, else the built-in one) and **Built-in**, the row shows **AMD FSR 4** where AMD's runtime is beside the
  game (Windows: `amd_fidelityfx_loader_vk.dll` and `amd_fidelityfx_framegeneration_vk.dll`, from AMD's FSR SDK; another
  copy can be named with `RX_VK_FFX_DIR`) and **AMD FSR 3.1** on any GPU its frame interpolation runs on. Both are yours to
  choose and neither is ever Auto's: they are given the finished picture with the HUD in it, and can smear the HUD (upstream
  measured that with FSR 3.1's and keeps it behind `RX_VK_FSR_FG=1`). FSR 3.1 makes the frame halfway between two of the
  game's and no other, so it makes 2x sets only; FSR 4 makes one frame a set unless `RX_VK_FFX_FG_MAX=<1-4>` says more. A
  set a method does not make whole, or a frame it refuses, is the built-in one's: a frame is never left out.
  `RX_VK_FG_METHOD=auto|builtin|fsr4|fsr3` picks a value for one run.
- **DLSS 5 neural rendering** (the Neural tab, below).
- **A release that carries the renderer CI built** (`tools\prebuilt\hookshot_vk.dll`), with DLSS, DLSS 5 neural rendering
  and FSR 4 compiled in. The Builder installs that one rather than compiling its own: your PC has none of NVIDIA's SDKs,
  and a renderer compiled there would leave those out. `HOOKSHOT_VK_LOCAL=1` asks for the local compile anyway. The Linux
  AppImage carries its renderer the same way, with DLSS in it. NVIDIA's runtimes are NVIDIA's to ship and are never in a
  release: they come from NVIDIA's DLSS SDK (`github.com/NVIDIA/DLSS`, `lib/Windows_x86_64/rel/` or
  `lib/Linux_x86_64/rel/`) or a game that ships them, and go in the game folder's `ngx` folder (`nvngx_dlss.dll` and, for
  frame generation, `nvngx_dlssg.dll`; on Linux `libnvidia-ngx-dlss.so.*` and `libnvidia-ngx-dlssg.so.*`).

#### DLSS 5 neural rendering

The **Neural** tab is NVIDIA's DLSS 5 neural rendering: a model that goes over the finished frame and
rebuilds detail, tone and structure in it. It is not an upscaler and not ray reconstruction -- it
takes the picture, not the scene -- so it works on this game, and it stacks with whatever the Upscaler
and Frame generation are set to. It runs once for each of the game's frames, on the part of the frame
that is shown, before frame generation: the made frames are made from its picture. All of its rows take
effect on the next frame.

| Row | What it does |
|---|---|
| Neural rendering | The switch. Left out while HDR is Native (the model takes an SDR picture; HDR Expanded is made from its result) |
| Backend | What runs the model: Auto, Streamline, NGX direct or Open (below) |
| Model | How much work the model does per frame: Performance, Balanced, Quality (its default), DLAA |
| Style | The look it aims for: Default, Natural, Cinematic |
| Preset | Which trained network it uses: Default, or presets A to G |
| Passes | How many times the model goes over each frame, 1 to 10, each pass on the picture of the one before: a stronger effect, at the model's whole cost (and video memory) again for every pass. Passes after the first leave Local tone out. NVIDIA's model only |
| Resolution scale | The size the model works at, 50% to 100% of the picture's width and height. Below 100% it is given a smaller copy and its detail is added back at full size, so the picture stays as sharp as the game drew it: the cheapest way to more frames with the model on. Any backend |
| Intensity | How much of the model's result is mixed into the frame |
| Local tone, Local structure, Global tone | How far the model may move brightness and colour in a small area, how much fine detail it adds, and how far it may move the whole frame's tone |
| Skin structure, Auto mask | Detail on characters' skin, and letting the model find the characters itself |

These are the settings the RenoDX DLSS add-on offers for the same model (its style, pass count, processing scale,
intensity, tone, structure, skin structure and character mask), under the names the model's own options have.

**Three ways to the same network** (the **Backend** row, saved as `nr_backend`;
`RX_VK_DLSS_NR_BACKEND=auto|streamline|ngx|open` over it for one run): **Streamline**, NVIDIA's plugin and the files in the
table below; **NGX direct**, which asks NVIDIA's NGX for the feature itself, through the same NGX session DLSS uses, and
needs only `nvngx_dlssnr.dll`; or **Open (OpenDLSS-NR)**, below, which runs the network on Vulkan without NVIDIA's runtime.
**Auto** takes Streamline where it is attached and accepts the GPU, then NGX direct where it can run, then Open where a model
folder is in place. The other rows apply to whichever runs.

**Open (OpenDLSS-NR)** is [OpenDLSS-NR](https://github.com/maanHimself/OpenDLSS-NR) (MIT), a Vulkan implementation of the
DLSS 5 NR network, built into the renderer on Windows and Linux alike: on Linux it is the way to the feature today. It
needs an NVIDIA RTX 40 or 50 card for now (`VK_NV_cooperative_matrix2` and `VK_EXT_shader_float8`; the log names anything
missing), and **a model folder you supply**: the network's weights, in OpenDLSS-NR's layout (`manifest.json` and its stage
files), in a folder called `nr-model` in the game folder (or wherever `RX_VK_OPENNR_MODEL` points). **Hookshot includes no
weights and no way to get them**; without a folder the Neural tab says so. Put the folder in place before starting the
game: the GPU is set up for the network at the start. Its log lines start `vk: open NR`;
[docs/neural-rendering.md](docs/neural-rendering.md) says what was measured (the kernels, against the network's own CPU
reference, on synthetic weights) and what was not (image quality with real weights).

**NGX direct** looks for `nvngx_dlssnr.dll` where NGX looks for DLSS's own runtime: the folder `RX_VK_DLSS_DIR` names, then
the **`ngx` folder in the game folder**, then `%LOCALAPPDATA%\Hookshot\ngx`, then the game folder itself. On Linux NGX
looks in the same places (`$XDG_DATA_HOME/hookshot/ngx` or `~/.local/share/hookshot/ngx` third) for
`libnvidia-ngx-dlssnr.so`, which **NVIDIA has not shipped yet**: the Linux NGX core knows the feature, but NVIDIA's SDK has Linux libraries only for DLSS, Ray
Reconstruction and Frame Generation. Until it does, the Neural tab and the log say so, and on Linux the way to the
feature is the Windows build under Proton. NGX direct's log lines start `vk: DLSS 5 neural rendering (NGX direct)`; when
NGX refuses it on Windows they name the GPU, the `nvngx_dlssnr.dll` found, whether it is signed, and the override, as the
Streamline path's do.

**Streamline is Windows x64 only**: it ships as DLLs.

**RTX 50 with NVIDIA's own model; RTX 20, 30 and 40 with a patched one.** NVIDIA's `nvngx_dlssnr.dll` runs on RTX 50
(Blackwell) only: on an older card NGX refuses it (`0xbad00001`) and the Neural tab says so. Community builds of the same
file recompile its model for Turing, Ampere and Ada -- [dlssnr-patcher](https://github.com/dev-camo/dlssnr-patcher)
patches your own copy, and [openNR](https://github.com/clshortfuse/openNR)'s 310.9.16 compatibility build (an FP16 one,
reported much faster on RTX 30 and 40) is reconstructed from it. Hookshot loads whichever `nvngx_dlssnr.dll` is there.
Two things to know:

- A patched file has **no NVIDIA signature**, and NVIDIA's NGX loads an unsigned feature only with its signature override
  on: the DWORD `EnableSignatureOverride` = `1` under `HKEY_LOCAL_MACHINE\SOFTWARE\NVIDIA Corporation\Global\NGXCore`.
  Hookshot reads it, for the log, and never sets it: that is your choice to make. It applies to every program on the
  PC, so turn it back off when you are done, and keep patched DLLs away from games with anti-cheat.
- It costs more on older cards: about 1.5 times an RTX 5070 Ti's GPU time on an RTX 4070 SUPER, by one report.

When Streamline refuses the feature, the log's `vk: DLSS 5 neural rendering is not supported here` line names the GPU, whether
the `nvngx_dlssnr.dll` there is NVIDIA's or a patched one, and whether the override is set, and the line after it says
what is missing.

For Streamline, these files go beside the game, or in a `streamline` folder beside it, or wherever
`RX_VK_STREAMLINE_DIR` points. They are NVIDIA's to ship; Hookshot builds against Streamline's
MIT-licensed headers only and loads nothing it has not checked NVIDIA's signature on:

| file | what it is |
|---|---|
| `sl.interposer.dll` | Streamline's loader |
| `sl.common.dll`, `sl.pcl.dll` | the interposer needs both, whichever feature loads on top |
| `sl.dlss_nr.dll` | the neural rendering plugin |
| `nvngx_dlssnr.dll` | the model -- it must sit in the same folder as `sl.dlss_nr.dll` |

Keep the three `sl.*` files from one Streamline release: mixing versions is not a supported
combination. Streamline **2.14.1 or newer** -- older releases do not have the feature at all.
[docs/neural-rendering.md](docs/neural-rendering.md) has the whole picture, including what is
measured and what is not.

</details>

## Mods

<details>
<summary><b>Where mods go and how they load</b></summary>

Put mods in a `mods` folder in the game folder, beside `hookshot.exe` (or point `HOS_MODS` at another folder), in the
layout emulators use: `mods/<name>/romfs/...` holds files that replace or add to the game's own. Deeper layouts such as
`mods/contents/<title id>/<name>/romfs` work too. Hookshot reads the folder as the game starts.

**Turning mods on and off: Gameplay → Mods.** The menu's Mods page lists every mod it found, in load order, each with its
number of files and Off or On. <kbd>Up</kbd> and <kbd>Down</kbd> choose a mod; <kbd>Left</kbd>, <kbd>Right</kbd> or
<kbd>Enter</kbd> turn it on or off; <kbd>Q</kbd> and <kbd>E</kbd> (or <kbd>Tab</kbd>, LB and RB on a controller) move it
up or down the order. With the mouse, click Off or On, or the arrows beside the chosen mod. When two mods have the same
file, the one lower in the list wins it: a mod's line names the mod on that shares files with it and which of the two
wins, and the help beside the list names every one. Changes apply after a restart (closing the menu asks, as for the
other settings that need one: its question lists each mod switched, with On or Off, and the order when it changed, and the
menu's "Restart needed" line names one switched mod and counts more, "2 mods"). Your folders are never renamed: the page keeps its choice in `mods/hookshot-mods.ini`, a
text file you can also edit, with the game closed:

```ini
; Hookshot's mod list. The Insert menu's Mods page (Gameplay, Mods) writes it; edit it with the game closed.
HD Textures = on
Classic Voice = off
contents/0100000000000000/Retro Models = on
```

A line a mod: its folder in the `mods` folder (`/` between folders, in any case), then `= on` or `= off` (a name alone
is on); lines starting with `;` are comments. The lines are the load order, the first loading first. Mods the file does
not name load after them, on, in name order; with no file at all that is every mod, so the one whose path in `mods`
sorts last (ignoring case) wins (name them `01-...`, `02-...` to set the order without the file). A folder whose name
starts with `-` or `_` is off whatever the file says, and so are the mods in it: the page lists them greyed; rename the
folder to manage them there.
A line for a folder that is not there is kept, for when it is back.

Only RomFS mods are loaded. `exefs` patches (`.pchtxt`, `.ips`) are left out: Hookshot compiles the game's code ahead
of time, so patching its instructions would need a rebuild. The log (`hookshot_log.txt`) has a line for each mod as the
game starts (`mods: #1 HD Textures: on, 1234 RomFS files`), one for each two mods on that have files in common and which
of them loads, and names the files read from the mods.

A mod file larger than the game's own does not load unless the resource size table allows for it:
`System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs` gives each file the memory the game sets
aside for it (by the CRC32 of its path without `.zs`; for a texture, its decompressed size + 280). Past that, the game
goes on without the mod's file, or a loading screen waits for good. A mod that makes files bigger (HD
textures, longer parameter files) ships the table with its entries grown. Since only one mod's table is used, mods that
each grow files need one table with all their entries, in the mod that loads last. Hookshot merges the button prompts'
entries into that table (each file gets the larger of the two), so your controller's icons stay in texts; the log says
`(with the button prompts' sizes merged in)` after the table's line. A table it cannot read that way (not the game's
format, or a zstd frame that does not give its size) is used as it is, with the Switch's icons.
If a mod includes tables for several game versions, the prompts use the table name from the game's own RomFS,
not the first table found in the mod. Other versions' tables do not change the prompts' font or its size entries.

For authors: the [existing file contract and game-free example](docs/mods.md) cover discovery, conflicting files,
disabling and what this loader does not provide. The example contains only invented text, not a seed or game data.

</details>

## Build from source

<details>
<summary><b>Building it yourself, and running the game from the command line</b></summary>

For developers, and for players who prefer the command line. The builder windows run the same script,
`nx2/make_game.py`. [CONTRIBUTING.md](CONTRIBUTING.md) has more.

<details>
<summary>Windows, from the command line</summary>

```powershell
python -I nx2/make_game.py --nup "C:\path\your-game.nup" --out "C:\Games\Hookshot" --language en-US
python -I nx2/make_game.py --romfs "C:\path\romfs" --exefs "C:\path\exefs" --out "C:\Games\Hookshot" --language en-US
```

Add `--check` with your `.nup` or `--exefs` to only check the game's version. It builds nothing.
Add `--log "C:\path\build.log"` to also save the build's output to a file (UTF-8, replaced if it exists); it works
with `--check` and `--update` too, and on Linux.
`HOOKSHOT_JOBS=<n>` (or `--jobs <n>`) limits how many files compile at once.
`HOOKSHOT_MEM_LIMIT_GB=<n>` lets the compilers take that many GB together, whatever is free now; up to 4 always run.

You need:

- Python 3 from python.org (the Microsoft Store's Python installs packages where `python -I` does not look), with
  `pip install -r requirements.txt` (core tools plus the button-prompt packages).
- [llvm-mingw](https://github.com/mstorsjo/llvm-mingw) (the `ucrt-x86_64` build), unpacked as `llvm-mingw` in the
  clone or with `HOOKSHOT_MINGW` set to its folder. Without it the build uses the clang from
  [emsdk](https://github.com/emscripten-core/emsdk) at `C:\emsdk` with Visual Studio's C++ tools and the Windows SDK
  (`HOOKSHOT_MSVC=1` forces that route).
- What the builder's `tools` folder carries and a clone does not. Run `HookshotBuilder.exe` once: the folder is
  `%LOCALAPPDATA%\HookshotBuilder\versions\<version>\HookshotBuilder\tools`. The builder sets the variables itself;
  from the command line, set them before you run `make_game.py`:
  - `tools\cpm`: the Vulkan headers and FFmpeg. Set `RX_CPM` to this folder. Without it (and without system
    Vulkan / SPIR-V / VMA headers or `HOOKSHOT_*_HEADERS`), the standalone build stops instead of shipping a
    game with no renderer.
  - `tools\wgpu-native`: set `WGPU_NATIVE` to this folder.
  - `tools\third_party`: the prebuilt files a clone lacks (`a64emit`, `lld-link`, `zbic` and SDL2). Copy its `.dll`,
    `.exe`, `.lib` and `.sha1` files to the same places under `third_party\`.
  - `tools\work`: copy it to `work\`. It holds the hot-function list, the link order, the profile and the icon;
    without them the game builds but runs slower.
- Visual Studio 2022 with .NET 8, only if you want to change the builder itself.

</details>

<details>
<summary>Linux, the AppImage from the command line</summary>

```sh
./Hookshot-<version>-x86_64.AppImage --cli --nup ~/your-game.nup --out ~/Games/Hookshot   # make_game.py's options
./Hookshot-<version>-x86_64.AppImage --play                    # the game the builder built last, without the window
./Hookshot-<version>-x86_64.AppImage --play ~/Games/Hookshot   # the game in that folder
./Hookshot-<version>-x86_64.AppImage --update ~/Games/Hookshot # the new release, and that folder built again
```

`HOOKSHOT_JOBS=<n>` (or `--jobs <n>` with `--cli`) limits how many files compile at once.
`HOOKSHOT_MEM_LIMIT_GB=<n>` lets the compilers take that many GB together, whatever is free now. Linux stops a compiler
that does not fit; it is then compiled again alone at the end.

In a game folder, `hookshot` is the launcher and the game itself is `bin/hookshot`. The builder's settings are in
`~/.config/hookshot/builder.ini`.

</details>

<details>
<summary>Linux, without the AppImage</summary>

You need `clang` and `lld` (LLVM 23 or newer reads the play profile; an older one builds without it), Python 3 with
`pip install -r requirements.txt`, FFmpeg's development files (with dav1d, for the movies) and SDL3 (SDL2 works too).
Then run `python -I nx2/make_game.py ...` as on Windows. Vulkan / SPIR-V / VMA headers come from the distro, from
`HOOKSHOT_*_HEADERS`, or from a CPM cache via `RX_CPM`.

`scripts/linux/deps.sh` fetches and builds all of these into `build-linux/deps`, and `scripts/linux/appimage.sh` makes
the AppImage from them. A folder built from a source checkout has no launcher: `hookshot` there is the game.

</details>

<details>
<summary>The Windows game, built on Linux</summary>

Unpack llvm-mingw's Linux build (`ucrt-ubuntu-22.04-x86_64`), then run `make_game.py` with `RX_TARGET=windows` and
`HOOKSHOT_MINGW` set to its folder. The objects go to `~/.cache/hookshot-builder-windows`, apart from the Linux game's.
The game folder runs under Proton or on Windows.

</details>

### Running the game from the command line

The built game is `bin\hookshot.exe` on Windows and `bin/hookshot` in a packaged Linux game folder. A build from a
source checkout has `hookshot.exe` or `hookshot` in its build folder, with no launcher beside it. The `hookshot.exe`
or `hookshot` launcher in the game folder does not pass these arguments to the game, so start the game directly to
use them.

| Argument | What it does |
|---|---|
| `image.bin` | The game image to run. Without it the game uses the `image.bin`, `romfs` and `user` in its folder |
| `--romfs <folder>` | The extracted RomFS folder |
| `--user <folder>` | Where the game keeps per-user data: saves, caches and temp files (and `mouse_sens.txt` when `HOS_MOUSE_SENS` is set; the menu keeps the sensitivity otherwise). Default: `user` in the game folder on Windows, `~/.local/share/hookshot` on Linux; with an explicit image path, `user` in the current folder |
| `--trace` | Log every Horizon OS call (the same as `HOS_TRACE=1`) |
| `--prepare-shaders` | Prepare the shaders as the first start does, then exit without starting the game (no build step runs it) |

For example, keep saves somewhere else:

```powershell
cd "C:\Games\Hookshot"
.\bin\hookshot.exe --user "D:\Hookshot data"
```

```sh
cd ~/Games/Hookshot
./bin/hookshot --user "$HOME/hookshot-data"
```

`hookshot_env.txt` and the other test switches are documented below.

<details>
<summary>AMD FSR 3.1 (every build)</summary>

**AMD FSR 3.1** in the Graphics tab's **Upscaler** row (`dlss=3` in `hookshot_options.ini`; `RX_VK_FSR=1` for one run,
`RX_VK_FSR=0` never) upscales in place of the game's own network, and with **Frame generation** at 2x its frame
interpolation can make the frame in between with `RX_VK_FSR_FG=1` (opt-in: the game draws its HUD into the same picture
and FSR 3.1 has no HUD-less colour to keep it still, so the HUD smears; by default the renderer's own makes it). Both are AMD's FidelityFX
SDK 1.1.4 shaders (`third_party/fidelityfx-sdk`, MIT), compiled into the renderer: no AMD runtime or DLL is needed, and
the row offers FSR 3.1 on any Vulkan 1.3 GPU with push descriptors, extended storage image formats and storage writes
without a format (`vk: fsr3: ... can run on this GPU` in the log). It upscales on the same inputs as DLSS and FSR 4: the
scene's colour, its depth, motion from the camera with the skinned characters' own drawn over it (Link, his shield and
the people around him keep their outline while they move), and the same camera jitter (`RX_VK_FSR_JITTER=0` turns it
off). Things that move by themselves and are not skinned (Navi's body, props) can still trail. `RX_VK_FSR3_CHAIN=0` gives
it the camera's motion alone, as before. With HDR on **Native**, it takes the game's HDR colour as linear light, so
highlights above the paper white are kept (`RX_VK_FSR3_HDR=0`: cut at the paper white, as before; with
`RX_VK_FSR3_CHAIN=0` they are cut too).

</details>

<details>
<summary>NVIDIA DLSS (optional, NVIDIA's SDK under NVIDIA's license)</summary>

A game built with NVIDIA's DLSS SDK offers **NVIDIA DLSS** and **NVIDIA DLAA** in the Graphics tab's **Upscaler** row on
NVIDIA RTX cards (`dlss=` in `hookshot_options.ini`, `RX_VK_DLSS=0/1/2` for one run): DLSS Super Resolution in place of
the game's own upscaler, with camera jitter (**NVIDIA Reflex** needs no SDK and is in
every build). NVIDIA's files are NVIDIA's, under its own license, the
[NVIDIA RTX SDKs license](https://github.com/NVIDIA/DLSS/blob/9981c6350dc58c0ce21f024fd65e31e851c31689/LICENSE.txt).
Hookshot never includes or redistributes them: each build downloads them for itself, and only after you accept that
license. Never share a game folder built with them, and do not post builds made with them.

- **Windows, the Hookshot Builder:** tick **NVIDIA DLSS (downloads NVIDIA's SDK under NVIDIA's license)** before you
  build. It is off by default and shows NVIDIA's license when you tick it. The build downloads the SDK into
  `%LOCALAPPDATA%\HookshotBuilder\ngx-sdk` and puts DLSS's runtime, `nvngx_dlss.dll`, and DLSS Frame Generation's,
  `nvngx_dlssg.dll`, in the game folder's `ngx` folder.
- **Windows, the command line:** `python -I scripts/ngx_sdk.py --platform windows <sdk folder>` asks you to accept
  NVIDIA's license (or pass `--accept-nvidia-license`) and fetches the headers, `nvsdk_ngx_s.lib`, `nvngx_dlss.dll` and
  `nvngx_dlssg.dll`, each checked against its SHA-256. Then build with `HOOKSHOT_NGX_SDK=<sdk folder>`: `make_game.py`
  copies both runtimes into `<game folder>\ngx`. NGX is also pointed at `%LOCALAPPDATA%\Hookshot\ngx`, and at
  `RX_VK_DLSS_DIR` when it is set, and uses the newest of each it finds across them (to try a given one, make sure no
  other folder has a newer one). Without `nvngx_dlssg.dll` there, frame generation takes the driver's own copy, which
  may be older: one that makes 1 frame at most, or refuses every set. Never copy NGX's core, `_nvngx.dll`, beside
  the game: it comes with NVIDIA's driver.
- **Linux, the Hookshot Builder (the AppImage):** the same tick as on Windows, and nothing else to do: no variable is
  passed to the AppImage and no file is copied by hand. The build downloads the SDK into the builder's cache folder,
  `$XDG_CACHE_HOME/hookshot-builder/ngx-sdk` (`~/.cache/hookshot-builder/ngx-sdk`), builds the game with it and puts
  DLSS's runtime, `libnvidia-ngx-dlss.so.<version>`, and frame generation's, `libnvidia-ngx-dlssg.so.<version>`, in
  the game folder's `ngx` folder. The builder's settings
  (`~/.config/hookshot/builder.ini`) remember that you accepted NVIDIA's license, so an update keeps DLSS even after the
  cache was emptied: it downloads the SDK again.
- **Linux, a build from source:** `scripts/linux/ngx-sdk.sh <sdk folder>` (it runs `scripts/ngx_sdk.py --platform
  linux`) asks you to accept NVIDIA's license and fetches `libnvsdk_ngx.a` for the build,
  `libnvidia-ngx-dlss.so.<version>`, DLSS's runtime, and `libnvidia-ngx-dlssg.so.<version>`, frame generation's. Then
  run the build with `HOOKSHOT_NGX_SDK=<sdk folder>` set: `make_game.py` puts both runtimes in the game folder's `ngx`
  folder. NGX's core comes with NVIDIA's Linux driver.
- **Linux, a game folder with other than plain English letters in its path:** NVIDIA's NGX on Linux loads DLSS's
  runtimes only from a folder whose whole path is ASCII. A game in `~/Games/Zelda` needs nothing more. A game in a
  folder such as `~/Games/Zelda-Café` (the `é` is not ASCII) cannot use the runtimes in its own `ngx` folder, and the
  log and the Insert menu say so: copy `libnvidia-ngx-dlss.so.*` and `libnvidia-ngx-dlssg.so.*` from there into
  `$XDG_DATA_HOME/hookshot/ngx`
  (`~/.local/share/hookshot/ngx`), which the game also looks in, or into any other folder with an ASCII path and name
  that folder in `RX_VK_DLSS_DIR`.

The **DLSS model** row chooses DLSS's network, by NVIDIA's preset letter, for every mode: **Transformer (K)**, the
transformer model and the one tested most here (the default); **Transformer 2 (M)**, NVIDIA's second-generation
transformer as it picks it for Performance; **Transformer 2 (L)**, the same generation as tuned for Ultra Performance;
**NVIDIA default**, which lets DLSS's runtime pick for each mode, so it can change with a runtime update. The runtime
the SDK comes with (310.9.16) has all of them. A change applies at once, without a restart (`dlss_model=` in
`hookshot_options.ini`, 0 to 3 in that order). `RX_VK_DLSS_PRESET=<letter>` (or `0` for NVIDIA's default) chooses
the preset for one run and wins over the row; the log's `vk: NVIDIA DLSS: ... preset <letter>` line says which one was
asked for, and with `RX_VK_DLSS_LOG=1` NGX's own `Using App hint Preset <letter>` lines say which it took.

**8 GB cards:** DLAA draws the 3D at full size, and DLSS and DLAA add images of their own beside the game's. In busy
areas that can pass what the driver allows the game, and the game then stutters: Quality or Balanced is safer there.
The log's `vk: status:` line every 600 frames shows the video memory in use of the allowance, with DLSS's details
(its images' size, the jitter and the actor motion) appended while it draws, and a `vk: over the driver's
video-memory allowance` line says when the game passed it.

The game's log says whether DLSS started, and why not when it did not (`vk: NVIDIA DLSS:` lines in `hookshot_log.txt`).
NGX starts on demand: when the Insert menu first opens (to know whether the Upscaler can offer DLSS) or at the first
gameplay upscale with DLSS chosen, so on the title screen the log has no NGX lines yet.
With `RX_VK_DLSS_LOG=1` NGX's own lines go there too (`ngx:`). Some of them look like errors but are not:
`failed to load NGXCore: 126` (twice) is NVIDIA's library looking for `_nvngx.dll` and `nvngx.dll` beside the game, which
are not there on purpose, before it loads the driver's; `Feature ... failed to load from cache` is NGX finding no model
of its own downloads (`C:\ProgramData\NVIDIA\NGX\models`) before it uses the game folder's `nvngx_dlss.dll`.

</details>

<details>
<summary>AMD FSR 4 (optional, AMD's DLLs not included)</summary>

A game built with FSR 4 offers **AMD FSR 4** and **AMD FSR 4 Native AA** in the Graphics tab's **Upscaler** row: AMD's
machine-learned temporal upscaler in place of the game's own, on the same inputs as DLSS (the scene's colour and depth, the
camera's and the characters' motion, and the camera jitter). Native AA draws the 3D at full size and smooths its edges.
With HDR on **Native**, it takes the game's HDR colour as linear light, so highlights above the paper white are kept
(`RX_VK_FSR4_HDR=0`: cut at the paper white, as before).
Unlike FSR 3.1 (above), it runs AMD's own DLLs, so it needs them beside the game. Choose it in the menu (`dlss=4` or `5`
in `hookshot_options.ini`, `RX_VK_FSR4=1` or `2` for one run, `RX_VK_FSR4=0` to leave it out).

- **Windows, the Hookshot Builder:** tick **AMD FSR 4** before you build. It shows AMD's license first and stays ticked
  only if you accept; the build then fetches AMD's DLLs for you (below), into the builder's `ffx-sdk` folder and the
  game folder.
- **The command line:** `make_game.py --fsr` (or `HOOKSHOT_FSR=1` for `nx2/build.py`). Rebuilding a folder built with
  it (`--update`) keeps it; `--no-fsr` takes it out.
- **AMD's files:** Hookshot includes only AMD's MIT-licensed API headers (`third_party/fidelityfx`). Put
  `amd_fidelityfx_loader_vk.dll` and `amd_fidelityfx_upscaler_vk.dll` from the
  [FidelityFX SDK](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK) 2.4 release (`Kits/FidelityFX/signedbin`)
  beside the game's exe (`bin\hookshot.exe`) or in the game folder. (`RX_VK_FSR_DIR` names another folder, for testing:
  set it in the environment or a `HOS_ENV_FILE` file; `hookshot_env.txt` takes no paths.) Without them the Upscaler row
  says so and offers the rest. On Linux, a Vulkan FSR 4 library (`amd_fidelityfx_upscaler_vk.so`, such as fsr4-vk's)
  takes their place.
- **Or fetched for you (Windows):** `make_game.py --fsr --fetch-fsr-runtime --accept-amd-license` downloads those two
  DLLs and AMD's license from AMD's FidelityFX SDK repository at the v2.4.0 tag, checks each against its SHA-256, and
  puts them in the game folder (`HOOKSHOT_FFX_SDK=<folder>` keeps them between builds, default `work/ffx-sdk`).
  `python -I scripts/ffx_sdk.py --accept-amd-license --game <game folder>` does the same for a game built already.
  Without `--accept-amd-license` nothing is downloaded (the script asks when run by hand), as with NVIDIA's license for
  DLSS. AMD DLLs already in the game folder that are not v2.4.0's (a newer SDK put there by hand) are left alone, and
  the build says so. They are AMD's, under
  [AMD's FSR SDK license](https://github.com/GPUOpen-LibrariesAndSDKs/FidelityFX-SDK/blob/7539ae8b6568ad29ed78a753404351daf3b5cca7/Kits/FidelityFX/docs/license.md)
  (`LICENSE-AMD-FSR-SDK.md` beside them). On Linux the flag does nothing but say so.

The log's `vk: AMD FSR 4:` lines say which of AMD's upscalers it found for the card and which it uses (the newest FSR 4;
never an older FSR in its place), and why not when it did not start. Tested on an RX 6700 XT (RDNA 2).

</details>

<details>
<summary>Switches for testing (hookshot_env.txt)</summary>

Switches to test (`RX_VK_NOOPT=1` and the others) go in `hookshot_env.txt` in the game folder, one `NAME=VALUE` a
line, on Windows and Linux. The running game reads it, not the builder. A test run can name another file with
`HOS_ENV_FILE=<path>`; the game then reads that one instead and leaves `hookshot_env.txt` alone.
`hookshot_env.txt` sets only the game's own switches (names that start with `RX_`, `HOS_`, `HOOKSHOT_`, `EDEN_`,
`NVN_` or `SDL_`, but not SDL's library names such as `SDL_VULKAN_LIBRARY`), and no value that is a path except
`RX_VK_DLSS_DIR`'s (a folder on this PC, not a network share), and no value at all for the switches that name a file
or folder (`HOS_AUDIO_DUMP`, `RX_VK_SHOTS` and the like) or press buttons on a timer (`HOS_INPUT_SCRIPT`,
`RX_VK_MENU_SCRIPT`); other lines are left out, and the log says so. Switches that need a path, or other variables, go
in a file named by `HOS_ENV_FILE`.
A switch set in the environment the game is started with (a shell's `HOS_FULLSCREEN=0 ./hookshot`, a launcher's own)
goes over the same name in the file, and the log says so; within the file, a later line replaces an earlier one. A
switch that stands in for a menu row (`RX_VK_PACE`, `RX_VK_UPSCALE`, `RX_VK_FRAMEGEN_MULT`, `HOS_REALTIME_STEP`,
`HOS_DYNRES`, `HOS_OUTPUT_RES`) applies to that run only: `hookshot_options.ini` keeps the value chosen in the menu.

To enable the debug tools, turn **Debug tools** on in the menu's Debug tab (or add `HOS_OOT_CHEATS=1` to
`hookshot_env.txt` in the game folder). The tools then show below it on the same tab. **Damage taken** is in the
**Player** group beside **Heart protection**: Half, Normal (the default), Double or Quadruple (`damage_taken=0/1/2/3`
in `hookshot_options.ini`). It applies only while Debug tools is on: off, Link takes Normal damage, and the saved
choice returns when the tools do. Heart protection takes priority while enabled. Half scales the full hit before life
is clamped to zero: with two quarter hearts left, a four-quarter hit still kills. The tab's Developer section, always
shown, has the Descriptor reuse, Sampler cache, Robust buffers and ASTC as RGBA8 rows, and on Intel graphics on
Windows the Intel shader compiles row.

A save whose minimap stopped showing after a Teleport on an earlier build (the area left had hidden it, and the flag
stayed set in the save) is mended by the Teleport itself: teleport to an outdoor area, wait until you can move, then
save from the game's System menu. The minimap then stays after a restart.

`RX_VK_UI_GAME_FONT=0` draws the menu with the included font (Libertinus) even when the game's files have the game's own
menu font. `RX_VK_UI_PROMPTS=pad` (or `keys`) shows the controller's (or the keyboard's) prompts whatever was used last,
for screenshots.

For a first run on a 4 GB card such as a GTX 1650, `RX_VK_LOW_SPEC=1` starts with the Minimum (4GB) preset, with
frame generation and upscaling off. It applies only when there is no `hookshot_options.ini` yet; after that, change
the settings in the in-game menu.

On **Minimum (4GB)**, when the driver reports a nonzero VRAM budget of at most 4.5 GiB, or the GPU is integrated
and the PC has 16 GB of RAM or less (its "VRAM" is that RAM, whatever budget the driver reports), sampled ASTC textures
use a 1024 dimension limit and an 8 MiB decoded-size threshold for leaving out their top mip levels. This lowers texture
detail to reduce the working set. Other presets and larger or unknown budgets keep the 2048 / 64 MiB defaults;
uncompressed render targets, depth images and the separate `RX_VK_TEX_MAX_MB` allocation limit keep their handling.
The driver budget is sampled at the first texture creation and kept for the session. It is a heuristic, not a physical
VRAM measurement: other applications can lower the budget even on a larger card.

`RX_VK_LOW_VRAM_MIPS=0` (also `off`, `false` or `no`) disables the automatic rule. `RX_VK_TEX_MAX_DIM` overrides only
the dimension limit, so setting it to 2048 still leaves the automatic 8 MiB threshold active on Minimum with a small
budget. `RX_VK_TEX_SKIP_MB` overrides that threshold using its existing parsing. For a more aggressive experiment,
use `RX_VK_TEX_MAX_DIM=512 RX_VK_TEX_SKIP_MB=2`. Changes to these environment switches take effect after a restart.

`RX_VK_MOVIE_UPSCALE=linear` replaces the movies' neural upscale with the plain linear one. The default, `auto`, keeps
the networks and falls back only when a movie frame takes the GPU more than 40 ms. That is on NVIDIA cards: on other
cards, or where the GPU cannot multiply the networks' matrices itself, the movies always get the linear upscale. It does
not change the gameplay upscaler, and movies can look softer. `RX_VK_NETWORK_KEEP=all` takes precedence and keeps the
movie networks.

A movie whose pictures take longer to decode than the time between them is shown, rather than skipped until the sound
has moved on: on a slow CPU the opening used to drop most of its pictures. How fast the decoder is counts from its recent
pictures, so a slow first picture does not stop a decoder that keeps up from catching up later, and catching up takes at
most one picture's time in a frame. With a decoder slower than the movie, the picture can fall behind the sound.
`HOS_VIDEO_NO_CATCHUP=1` skips nothing. Each picture is waited for for about a tenth of a second
(`HOS_VIDEO_ACQUIRE_TRIES=1`: a count of sleeps instead of the clock). After a movie stops or is flushed, and nothing new
has been submitted, there is no wait. The first picture can still be black on some PCs; why is not known yet.

A PC with 4 logical processors or fewer decodes the movies on 2 threads rather than one per processor, so the decoder
leaves the game's own threads their time. A 4-thread laptop with Intel UHD Graphics showed the title and the opening
movie at about 35 fps of 60, with the game's thread waiting 14 to 24 ms on most frames; that report was not run again
with this change. `HOS_DAV1D_THREADS=<n>` sets the count on any PC.

On Windows, Intel's compiler (UHD and Arc) is entered by one thread. A fault inside it leaves that shader out instead
of closing the game, and the program is written to `hookshot_driver_faults.txt` so that later starts on the same
driver leave it out too (delete the file to try again). This covers the game's shaders and the renderer's own (texture
decoding, upscaling, frame generation). A draw that only asks whether its pipeline is ready never waits behind another
thread's compile: while one is compiling, the answer is "not yet", even for a pipeline already in a cache, and the
draw is left out until a worker has made it (the log's `vk: asked cold: Intel's gate busy` lines count these). The
renderer's own pipelines made at their first use (the movie's upscale, the texture decoders, a masked clear, the
write-back and late-page fixes) do wait for a compile under way. Whether the driver keeps working after a caught fault
has not been tested. The first scene can still pause while shaders compile, especially when they were not prepared at
the build. If a build's preparation stopped ("the GPU driver stopped responding"), the game leaves a
`hookshot_prepare_skipped` file beside it and every start after that builds shaders only when first drawn.
Build again with **Prepare shaders now** ticked, or delete that file, to prepare them with this fix.
The Debug tab's **Intel shader compiles** row (Developer section, shown on Intel graphics on Windows) chooses: **One at
a time**, the default and the safe choice on a CPU with 4 cores or fewer, or **Side by side**, faster builds on a CPU
with many cores, but Intel's driver can crash the game while building them. It applies after a restart.
`RX_VK_NO_INTEL_SERIAL=1` is Side by side for a run, whatever the row says. NVIDIA, AMD, and Intel on other systems are
unchanged.

`RX_VK_SKIP_CODE=<prefix,...>` leaves out the draws of every program with a stage whose native code key starts with one
of the prefixes (the keys the log prints after "its code:"). On a Steam Deck, `RX_VK_SKIP_CODE=2c56dc1006942f74`
avoids a GPU hang in Kokiri Forest and the Great Deku Tree: the GPU runs for seconds in the programs that share that
task shader (a culling pass) until the kernel resets it ([#817](https://github.com/NotRexed/Hookshot/issues/817)).
It is a workaround, not a fix: those are task + mesh programs, so the geometry they draw goes with them, and key models
are missing while it is set. Off unless set.

The switches for scripted test runs, screenshots, frame dumps and profiles are in the
[development guide](docs/development.md#switches-for-testing-and-debugging).

`RX_VK_WB_MAX_KB=<KB>` (off by default; 1024 is the tested value) is the size from which a written GPU binding may go
without most of its write-back. OoT
writes tens of MB of culling lists and per-frame buffers through the GPU that the CPU never reads, and copying them back
sat on every submit's memory sync: in Hyrule Field on a 10 GB RTX 3080, about 66 MB and 4.4 ms a submit, holding the
scene at 45-48 fps. The CPU does read and write parts of some large ones, so a binding over the size is written back
whole for the first `RX_VK_WB_PROBATION` submissions that write it (default 8), and after that only the ranges the CPU
read or wrote meanwhile, and its first and last page when it shares them, are written back (`gpu/vk/wb_learn.h`). The
trade-off: a range the CPU first touches only after that (read more rarely than every 8 frames) gets the stale copy
once, and is written back from then on; the log names each one (`in a binding whose write-back was left out`).
Unset or `0`, every written binding is copied back whole. It is off by default because, measured so far (an RTX 3060 Ti
on Windows, an RX 580 on Linux with its mirror forced on), it copies back ~50 MB a frame less at the same frame rate:
results from laptops and other slow PCIe links are wanted. `RX_VK_LOG_WB_SKIPS=1` lists the bindings left out every
600 submits.

`RX_VK_PROGRAM_CACHE_ZSTD=1` keeps the translated shader programs in `hookshot_programs.zst.bin`, each record
compressed with zstd and unpacked when it is read. The uncompressed cache is about 6.9 GB; in the reference cache
(46,587 programs) zstd's level 3 made it 1.83 GB (3.75x). It is a file of its own: an existing
`hookshot_programs.bin` is left alone, and the first run translates the programs into the compressed cache.

</details>

</details>

## How it works

1. `nx2/lift.py` translates the game's ARM64 code to C.
2. `nx2/build.py` compiles that C together with `host/`, which plays the part of the console's system.
3. `host/nvn_native.c` records the game's NVN2 graphics calls, and `gpu/vk/` replays them on Vulkan.
4. Switch 2 Ampere shaders are lowered to Maxwell (`lower_to_maxwell.h`) and translated to SPIR-V by Eden's shader
   recompiler.

More detail is in the [development guide](docs/development.md) and the [design notes](docs/design.md).

## Want to help?

Testing on other graphics cards and reporting the result already helps a lot, and so does playing further into the
game than anyone has yet.

<details>
<summary><b>Send your pipeline list, and other ways to help</b></summary>

### Send your pipeline list

The first time the game meets a pipeline it builds it on the spot, which stutters. Releases build a list of known
pipelines before the title, and every player's play adds to it. To send yours:

1. In the game, open the menu (Insert or F1), go to the **Debug** tab and choose **Save my pipeline list** (under Developer). Or, in
   Hookshot Builder's launcher page for the game folder, press **Save my pipeline list**.
2. It saves `hookshot-pipelines-<date>.zip` in your Downloads folder, copies a filled-in report to the clipboard and
   opens the [Submit your pipelines](https://github.com/NotRexed/Hookshot/issues/2034) issue in your browser.
3. Attach the zip to a comment there, paste the report and fill in where you played.

The zip holds only `hookshot_pipeline_states.bin` (shader hashes, formats and draw state, and the hashes of the compute
programs your play ran, so that a release can keep those ready too: no game code, game data or personal info) and the
report (the version, OS, GPU and driver, output and render resolution, upscaler, frame
generation, HDR and the mods the game loaded). Nothing is uploaded for you. If the list is missing or damaged, it says
so and saves nothing. In a run without a window (`HOS_HEADLESS`) the menu saves the zip but opens nothing.

Bigger ways to help:

- **Linux testing.** The Linux build (`host/posix`) has been tested on several distributions and cards: reports from
  others still help.
- **Fixes in your own fork.** Fork the project, fix what you find and send the change back. Keep game files, keys and
  anything generated from your game out of it.

[CONTRIBUTING.md](CONTRIBUTING.md) has the setup, the test commands, the code conventions and what a good pull request
looks like.

</details>

## Related projects

- **[Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot)**: another build of the same engine, by the Magic Bean
  team, with its own [Longshot Launcher](https://git.magicbean.dev/MagicBeanDev/LongshotLauncher).
- **[oot-mod](https://github.com/craftycorvid/oot-mod)** by craftycorvid: ultrawide (21:9, 32:9) and 16:10 patches for
  playing the remake on an emulator. Hookshot has the same built in: the Aspect ratio row widens the view and keeps the
  HUD and movies in the middle 16:9.

## Credits

<details>
<summary><b>Everyone whose work Hookshot stands on</b></summary>

Hookshot exists thanks to the work of many people:

- **NotRexed**: Hookshot, BlueShell (Mario Kart World), Skybound (Tears of the Kingdom) and the a64-kit tools.
- **[Eden](https://git.eden-emu.dev/eden-emu/eden)** and **Eglantine**: the shader recompiler and Switch 2 shader work.
- **suyu**: the graphics decoders and the AArch64 translator.
- **[seedds/nxnative](https://github.com/seedds/nxnative)**: reference for how task and mesh shaders work.
- **[EvilBoyce / evilmfkr](https://github.com/evilmfkr/Hookshot)** (EvilOOT): the GPU culling that brings back Kokiri's foliage
  (trees, ferns, grass, falling leaves, fireflies), the ambient light probes, the pond's water, the game's own fog, the freeze
  after Load (Horizon's mutex handoff) and the exposure flicker fix.
- **[zortos293/Lichii](https://github.com/zortos293/Lichii)**: reference for Ampere shader lowering, and its compare-exchange retry fix.
- **[mstorsjo/llvm-mingw](https://github.com/mstorsjo/llvm-mingw)**: the bundled Windows compiler (no Visual Studio needed).
- **NVIDIA DLSS**: builds made with NVIDIA's DLSS SDK (optional, downloaded by each build, never bundled) use NVIDIA DLSS
  Super Resolution, NVIDIA's technology. NVIDIA and DLSS are trademarks of NVIDIA Corporation.
- **[openNR](https://github.com/clshortfuse/openNR)** (MIT, Carlos Lopez): the NGX parameter names DLSS 5 neural rendering's
  NGX direct backend drives feature 18 with, and the layout of its Streamline options.
- **AMD FSR 3.1 and FSR 4**: every build has AMD FidelityFX Super Resolution 3.1, built from AMD's MIT-licensed FidelityFX
  SDK shaders; builds made with FSR 4 (optional; AMD's DLLs are never bundled) use AMD FidelityFX Super Resolution 4
  through AMD's MIT-licensed FSR API headers. Both are AMD's technology. AMD, Radeon and FidelityFX are trademarks of Advanced Micro
  Devices, Inc.
- **[kinnay/zbic](https://github.com/kinnay/zbic)**, **Opus** and **SDL**: decompression, audio and controllers.
- **[sostenesfreitas/ocarina-recomp](https://github.com/sostenesfreitas/ocarina-recomp)**: this README's layout, and its notes
  confirmed the mesh stage's control section.
- **[MythosOfs/Orchid](https://github.com/MythosOfs/Orchid)**: the fog and exposure workaround Ocarina of Time used before
  its fog and lighting were fixed.
- **[Ocarina Reborn](https://github.com/misterrageguy-cyber/OoT2026-PC-Recomp)** (misterrageguy-cyber): the View distance,
  Grass and Shadow distance rows, FXAA, Bloom, the Colour grade, Classic counters, the Speedrun timer and the
  Death counter.
- **hotoni** (the Graphics-Menu mod): where the game keeps its view, grass and shadow distances.
- **[angrylion-rdp-plus](https://github.com/ata4/angrylion-rdp-plus)**: the Nintendo 64's colour dither (its magic square),
  which the Retro look uses.
- **Machado, Oliveira and Fernandes** ([A Physiologically-based Model for Simulation of Color Vision
  Deficiency](https://www.inf.ufrgs.br/~oliveira/pubs_files/CVD_Simulation/CVD_Simulation.html), IEEE TVCG 2009) and
  **Fidaner, Lin and Ozguven** (Analysis of Color Blindness, Stanford 2005): the Colour vision row's model and its daltonization.
- **Timothy Lottes**: his public-domain CRT shader
  ([crt-lottes](https://github.com/libretro/glsl-shaders/blob/master/crt/shaders/crt-lottes.glsl)), the model of the Retro
  look's N64 + CRT: its scanline beams, horizontal softness, glow, masks and curvature.
- **Mesa (NAK)**: the reference for Ampere's instruction encoding.
- Everyone who sent fixes: SkippySteve (Linux and the AppImage, and many more), monsterlag, klimovich008, hckrman101 (NVIDIA
  DLSS, DLAA and Reflex, the exposure flicker and fog fixes, build speed, CI), madebyjordan (AMD FSR 4.1), N3oTraX (FSR 4 on
  Linux), shayderrr, gab9281, Wpaif, nicholasgower, ZurielAtr, Joey-Magnus, Zorkats,
  d3zessete, chrispository, vzeol, leonidasmark, Segmentree, ShyVortex, hiKareeem, i900gaming and YakuzaFanA (each
  light's own shadow map in the water's light loop), among others.

</details>

## License

Hookshot is free software under the [GNU General Public License, version 3 or later](LICENSE) (GPL-3.0-or-later).
It includes code from Eden and suyu, which are under the GPL too. Third-party parts under other licenses that
work with the GPL (Sirit, the Vulkan Memory Allocator, SDL, Opus, Dear ImGui, zstd, the Libertinus fonts, zbic and the
a64-kit tools) keep their own notices in their folders.

Hookshot is an unofficial fan project, not affiliated with or endorsed by Nintendo. The Legend of Zelda and Ocarina of
Time are trademarks of Nintendo.
