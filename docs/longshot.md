# Fixes from Longshot

[Longshot](https://git.magicbean.dev/MagicBeanDev/Longshot) is the magicbean.dev team's continuation of upstream
Hookshot (GPL-3.0, like this tree). It forked from upstream at `4dd972a8` (upstream #2888, 2026-11-12). Its fixes are
taken here as cherry-picks (`git cherry-pick -x`), each with its Longshot PR number and author. Its history is not merged:
release-please reads every commit a merge brings in, so a merge would put Longshot's rename, its Forgejo tooling and its
`feat(release)!:` in this changelog and version.

**Taken through:** Longshot `main` at `5e072fc8` (2026-11-14), but for #321 (below). The next pull starts at:

```bash
git fetch longshot
git log --reverse --oneline 5e072fc8..longshot/main
```

When a pull is done, the hash above moves to the new tip, in the same pull request.

## Adapting a pick

Longshot renamed the project, so its later commits carry its names. A pick turns them back:

- comment tags `(longshot)` and `(longshot: ...)` become `(hookshot)` and `(hookshot: ...)`;
- file names `longshot_*` (`longshot_env.h`, `longshot_options.ini`, `longshot_load_start.txt`, ...) become `hookshot_*`;
- environment names `LONGSHOT_*` become `HOOKSHOT_*`;
- "Longshot" in a message to the player becomes "Hookshot".

Watch for option ids too: two trees can number a new row alike (Longshot's Damage taken is 55; here it is 56, after Auto
run). `tests/test_option_ids.py` catches it.

## 514591a3 to 5e072fc8

Taken (Longshot PR): #34, #58, #59, #103, #136, #137, #162, #189, #190, #191, #216, #219, #237, #238, #245, #248, #250,
#252, #255 (its `nx2/test_nup_paths.py` only), #269, #277, #281, #307, #323, #324, #325 (its measured rows: the fix is
upstream #3004 here), #329, #357, #358, #369, #400, and #292 (after #172, below). Where a pick met this tree's own work, its commit's
"Hookshot port:" line says how they were joined; the main ones:

- #137 (hold-to-toggle): the Toggle column comes after this tree's two key columns; `HOS_OPT_HOLD_TOGGLE` is 54, as in
  Longshot.
- #136 (Mono on Audio output): `HOS_OPT_AUDIO_OUTPUT` is 63 here (Longshot's 57 is View distance in this tree).
- #219 (Navi 23): this tree keeps Navi 24's `0x743f` (RX 6400, 6500 XT) in the fallback's default, from Ocarina Reborn;
  Longshot holds all of Navi 24 out.
- #248 (the late pages' fix): this tree's mirror-sync pass (upstream #3023) keeps the write-back shadow following the
  sync too.
- #292 and #172 (below) change the first start's Output resolution: 2560x1440, or a smaller screen's own size, and
  Auto (this PC) no longer chooses it (upstream #2566's choice by tier is gone, as on NotRexed's Hookshot).
- New runs Longshot keeps as `docs/tested/*.md` files (#96, which is not taken: this tree keeps one table) are rows of
  [tested configurations](tested-configurations.md), unchanged.

Already here: #156 (= upstream #2708), and #59, #189 and #325 in an earlier form (upstream #2992, #3000, #3004; the
picks bring Longshot's later revisions, or only the rows).

Not taken yet:

| Longshot | What | Why not yet |
|---|---|---|
| #321 | The shader caches and button prompts in the game folder's `cache`, the logs in its `logs` | Moves files players and this tree's scripts read beside the game (`hookshot_log.txt` above all): needs every reader here (75 files) and the owner's go-ahead, in a pull request of its own |
| #151 | The setup copies the Builder from a zip deeper than MAX_PATH | This tree's setup does not copy a Builder from its zip (Longshot #171, #181) |

Left out on purpose: #96 (its process: run files and a frozen table, with its website), #273 (the stale keys it removes
are this tree's current text), #120 and #80 (Longshot's forge and third-party check scripts).

## Up to 514591a3

Taken (Longshot PR): #7, #8, #39, #54, #55, #78, #94, #108, #110, #138, #176, #177, #178, #187, #202, #233, #247,
#265, #266. Also, in a pull request of their own because each needs its own measurement: #41, #197, #198, #260.

Already here from upstream, under other hashes: #49 (= upstream #2929), #77 (= #2972), #131 (= #3038), #147 (= #2732),
#4 (`third_party/zbic` is carried whole), #63 (`host/rx_backend.c` already steps over 256 clear marks at a time), #174
(this tree compiles the Linux back end itself, and the AppImage carries `third_party/fidelityfx`).

Taken since, from this list: #15 (the segment heap), #159 (the fog and exposure docs), #172 (a new install's Output
resolution, and Auto no longer choosing it) and #234 (quick pipelines, off by default as in Longshot).

Not taken yet:

| Longshot | What | Why not yet |
|---|---|---|
| #107 | OoT's clustered lights sample their own shadow maps (Lichii's descriptor arrays) | This tree has its own implementation of the same mechanism (upstream #3047, `ac77296e`: `HandleOp::Index`, `RX_VK_HANDLE_TABLE`), for the water's squares (#2509). The two rewrite the same texture pass; whether ours also clears #52's blocks (Zora's Domain ice, the snow) is to be seen in the game first |
| #158, #164, #167 | Compile shaders All / Most / None | In the Builders, which differ here |

Left out on purpose: the rename (`e2a4d453`), Discord as Longshot's (#10, #194), its README, website and docs (#9,
#11, #104, #114, #168, #192, #193, #210, #214, #257, #258, #274), its nightly version display (#170), its Forgejo forge
tools, templates, CI and releases (#3, #5, #6, #13, #18, #21, #48, #72, #76, #79, #99, #105, #106, #113, #115, #116,
#117, #121, #126, #128, #129, #132, #133, #135, #140, #143, #146, #148, #149, #154, #160, #166, #254), the removal of
builders this tree still ships (#161, #163, #171, #175, #179, #181), and importing Hookshot saves into Longshot (#20).
