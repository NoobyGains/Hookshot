# NFC tags

The game reads figures' NFC tags through the console's `nn::nfp` library. Hookshot gives it that library on tags of the
player's own: files in a folder, and, with a Nintendo Switch 2 Pro Controller over USB, real tags on the controller.
`host/nn_nfp.c` is all of it; the Insert menu's NFC tab (`gpu/vk/vk_menu.cpp`) is its front.

**No tag dump is ever committed, uploaded or put in an issue.** A tag's dump is the player's own copy of something they
own, like the game. The checks build pretended tags in code.

## The folder

| | |
|---|---|
| Windows | `%LOCALAPPDATA%\Hookshot\nfc` |
| Linux | `$XDG_DATA_HOME/hookshot/nfc` (`~/.local/share/hookshot/nfc`) |
| Either | `HOOKSHOT_NFC_DIR=<folder>` instead |

Every build of the game shares it. One file a tag, directly in the folder; its name without the
ending is the tag's name in the menu, in the order of the names (letters' case aside). At most 256 are listed: the first 256 by name. A file
whose name starts with `key_` is left out.

| File | What it is |
|---|---|
| `.bin` | The tag's bytes as they are on it: 540 (an NTAG215's 135 pages), or 532 or 572 as some tools write them |
| `.nfc` | A Flipper Zero NFC file: text, a `Page N: xx xx xx xx` line a page, 130 pages at least |

A file is a figure's tag when its capability container says NTAG215 (`F1 10 FF EE` at 0x0C) and its model ends in `02`
(0x5B). The tag's ID (bytes 0 to 2 and 4 to 7) and the figure's model (0x54 to 0x5B) are plain on a tag and are all that
is read. The rest of a real tag (its owner, its counters, the games' application areas) is encrypted with keys Hookshot
does not have and does not need: a tag is never written back, so what a game keeps on it is kept in a file of Hookshot's
own instead, `user/nfc/<the tag's ID>.area` beside the saves, and a tag is always shown as registered.

## In the game

The game asks for a tag (`StartDetection`), polls the reader (`GetDeviceState`) until one is found, mounts and reads it,
and stops. The NFC tab's **NFC tag** row chooses a file, **Tap tag** holds it to the reader (it stays there until the
game has read it, so it can be tapped ahead), **Remove tag** takes it away. The row's help says what the reader is doing.

## The Switch 2 Pro Controller's reader (Windows, USB)

With that controller plugged in (`host/pad_switch2.c`), its own reader is used as well: while the game waits and no file
is held to the reader, a real tag on the controller is read and, when it is a figure's, given to the game. **Scan tag on
controller** reads one into the folder as `Scanned <its ID>.bin`. The reader's commands are in a comment in
`host/nn_nfp.c`, as the controller answered them (the community's notes name them without their answers). A tag is read
with the figure tags' password first and without it when that is refused (a plain NTAG215). Nothing is written to a tag.

`HOS_NFP_SEARCH=1` makes the reader look for a tag from the start, to check it without the game's NFC screen;
`HOS_NFP_TRACE=1` logs the application area's calls.
