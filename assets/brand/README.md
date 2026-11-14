# Hookshot brand

## The mark

Two objects from the game the project runs, turning either side of the name: the Hookshot on the left, the Hyrule
shield on the right. They are renders of fan-made 3D models, lit in one black studio with blue, cyan and gold rim
lights; nothing is taken from the game's own files.

| Object | Model | Credit |
|---|---|---|
| Hookshot | `Hookshot_DTStheTDS.blend`, from the download `hookshot-ocarina-of-time.zip` | DTStheTDS (the name in the file) |
| Hyrule shield | `Oot_HyruleShield.fbx` with its textures, from the download `zelda-ocarina-of-time-hyrule-shield.zip` | Author to be added |

The models are not in this repository: only the pictures rendered from them are. **To do:** add each model's page and
licence here (neither download carried a licence file). The Hookshot, the shield and its crest are Nintendo's designs;
this is fan art for an unofficial project.

Rendered on 2026-11-14 in Blender 4.5 (Cycles, OptiX, RTX 5090), 96 samples, 600×600, 40 frames each:

    blender -b --disable-autoexec -P scripts/render_emblem.py -- Hookshot_DTStheTDS.blend FRAMES hookshot 40 96 600
    blender -b --disable-autoexec -P scripts/render_emblem.py -- Oot_HyruleShield.fbx FRAMES shield 40 96 600
    python scripts/make_hero.py --frames FRAMES

## Files

| File | Size | Use |
|---|---|---|
| `emblem_hookshot.png`, `emblem_shield.png` | 600×600 | The first frame of each turn: what the still banner is built from |
| `hero.webp` | 1200×450, 40 frames, animated WebP | The README header: both objects turn once, and loop |
| `hero.png` | 1600×600, rounded corners | The still banner |
| `social-preview.png` | 1280×640 | GitHub's social preview (uploaded by hand in Settings) |
| `icon.png` | 512×512, rounded square | Listings and avatars |
| `roadmap.png` | 1600×638 | The README's roadmap (`python scripts/make_roadmap.py`) |

`python scripts/make_hero.py` rebuilds the stills from the two emblem pictures; the animation needs the rendered
frames, which are not kept here. Both scripts need only Pillow.

## Type and colour

- Wordmark: **Unbounded** ExtraBold (SIL Open Font License), white to blue `#3b82f6` to cyan `#22d3ee` to gold
  `#fbbf24`, the objects' own colours, over a soft blue glow.
- Tagline and labels: **JetBrains Mono** (SIL OFL).
- Background `#06070b`; text `#f8fafc`, muted `#cbd5e1`.
- Both fonts are vendored in `fonts/` as static instances, with their licence files.

The layout and the scripts follow [NoobyGains/usage-pulse](https://github.com/NoobyGains/usage-pulse)'s.
