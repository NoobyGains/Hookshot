# Hookshot brand

## The mark

A grapple: a spear tip, a length of chain lit emerald to gold, and a hook, set into a slab of black obsidian glass with
sharp facets. It is the tool in the name, rendered rather than drawn. It shows nothing from the game.

`emblem.png` was rendered locally on 2026-11-14 with **Z-Image-Turbo** (Apache 2.0) in ComfyUI on an RTX 5090: 8 steps,
`res_multistep` sampler, cfg 1, 1024×1024, seed `411`. Prompt:

> A premium brand emblem: a grappling hook with a spear-shaped tip and a short length of chain, the chain made of
> glowing neon light, emerald green fading to cyan and warm gold, shooting diagonally through a thick slab of black
> obsidian glass, carved from black obsidian glass with razor-sharp bevelled facets, light leaking through the edges,
> floating centered on a pure black background, faint reflection on a glossy black floor below, premium 3D render,
> cinematic rim lighting, no text, no letters, no logos

Six candidates were rendered and compared on a contact sheet: two of the grapple through a slab, two of a tip with a
chain behind it, two of a chain around a gem. Seed 411 is the only one that reads as tip, chain and hook at once.

## Derived files

| File | Size | Built by | Use |
|---|---|---|---|
| `hero.png` | 1600×600, rounded corners | `python scripts/make_hero.py` | The still banner |
| `hero.gif` | 800×300, 35 frames | `python scripts/make_hero_gif.py` | The README header: a band of light crosses the banner, then rests |
| `social-preview.png` | 1280×640 | `python scripts/make_hero.py` | GitHub's social preview (uploaded by hand in Settings) |
| `icon.png` | 512×512, rounded square | `python scripts/make_hero.py` | Listings and avatars |

Both scripts need only Pillow, and rebuild every file from `emblem.png`.

## Type and colour

- Wordmark: **Unbounded** ExtraBold (SIL Open Font License), white to emerald `#34d399` to cyan `#22d3ee` to gold
  `#fbbf24`, the emblem's own colours, over a soft green glow.
- Tagline and labels: **JetBrains Mono** (SIL OFL).
- Background `#06070b`; text `#f8fafc`, muted `#cbd5e1`.
- Both fonts are vendored in `fonts/` as static instances, with their licence files.

The layout and the scripts follow [NoobyGains/usage-pulse](https://github.com/NoobyGains/usage-pulse)'s.
