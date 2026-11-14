# Hookshot brand

## The mark

The tool in the name, as an object of its own: a blue barrel with chain wound around it, a four-sided steel spearhead
at the front and a bracket handle with a leather grip and a gold cap at the back. The shape follows the Hookshot the
project's first logo (`assets/hookshot.png`) shows; the picture itself is a new render, not artwork from the game.

`emblem.png` was rendered locally on 2026-11-14 with **Z-Image-Turbo** (Apache 2.0) in ComfyUI on an RTX 5090: 8 steps,
`res_multistep` sampler, cfg 1, 1024×1024, seed `502`. Prompt:

> A premium brand emblem of a fantasy grappling device: a short thick cobalt-blue cylinder barrel with a steel chain
> wound tightly around its middle in three rows, a large four-sided silver pyramid spearhead tip mounted on the front
> of the cylinder, and at the back an angular grey metal handle frame shaped like an open bracket holding a grip
> wrapped in brown leather with gold end caps, made of polished black obsidian glass and brushed steel with
> razor-sharp bevelled facets, edges glowing with neon light in sapphire blue, cyan and warm gold, the whole device
> pointing diagonally up to the right, floating centered on a pure black background, faint reflection on a glossy
> black floor below, premium 3D render, cinematic rim lighting, single object, no text, no letters, no logos

Twelve candidates were compared on two contact sheets. The first six were abstract (a grapple through a slab of glass,
a tip with a chain, a chain around a gem) and did not read as the Hookshot. Of the second six, seed 502 has every part
in the right place: barrel, chain, spearhead, bracket handle and grip.

## Derived files

| File | Size | Built by | Use |
|---|---|---|---|
| `hero.png` | 1600×600, rounded corners | `python scripts/make_hero.py` | The still banner |
| `hero.webp` | 1200×450, 35 frames, animated WebP | `python scripts/make_hero_anim.py` | The README header: a band of light crosses the banner, then rests |
| `social-preview.png` | 1280×640 | `python scripts/make_hero.py` | GitHub's social preview (uploaded by hand in Settings) |
| `icon.png` | 512×512, rounded square | `python scripts/make_hero.py` | Listings and avatars |

Both scripts need only Pillow, and rebuild every file from `emblem.png`.

## Type and colour

- Wordmark: **Unbounded** ExtraBold (SIL Open Font License), white to blue `#3b82f6` to cyan `#22d3ee` to gold
  `#fbbf24`, the emblem's own colours, over a soft blue glow.
- Tagline and labels: **JetBrains Mono** (SIL OFL).
- Background `#06070b`; text `#f8fafc`, muted `#cbd5e1`.
- Both fonts are vendored in `fonts/` as static instances, with their licence files.

The layout and the scripts follow [NoobyGains/usage-pulse](https://github.com/NoobyGains/usage-pulse)'s.
