"""The Teleport page's picture files (gpu/vk/vk_menu.cpp read_picture_file, write_picture_file): one file a map in the game
folder's teleport_pictures folder, 'FTP2', width, height, then the RGB. Compiled with a made-up image (no game data is in
this check): the round trip keeps every pixel (alpha comes back opaque), a file that is cut short, has another magic or a size
the picture worker must not allocate is left out, a missing file is no picture, a write replaces the old file and leaves no
.tmp beside it, a folder that cannot be made is a failed write.

python -I -B tests/test_teleport_picture_files.py [--cxx g++] [--source path/to/vk_menu.cpp]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # (tests/srccut.py: python -I leaves this folder off the path)
from srccut import between, block  # noqa: E402

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cxx", default="g++")
    p.add_argument("--source", type=Path, default=ROOT / "gpu/vk/vk_menu.cpp")
    a = p.parse_args()
    menu = a.source.read_text(encoding="utf-8")
    picture = block(menu, "struct TeleportPicture {") + ";\n"
    magic = between(menu, "constexpr char kPictureMagic[4]", "\nbool read_picture_file(")
    reader = block(menu, "bool read_picture_file(const std::string& path, TeleportPicture& p)")
    writer = block(menu, "bool write_picture_file(const std::string& path, const TeleportPicture& p)")
    source = r'''#define _CRT_SECURE_NO_WARNINGS   // (fopen, as the menu's own translation unit has it)
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <string>
#include <system_error>
#include <vector>
static int logged = 0;
void logf(const char*, ...) { logged++; }   // (what the menu logs for a file it leaves out)
''' + picture + magic + "\n" + reader + "\n" + writer + r'''
namespace fs = std::filesystem;
static TeleportPicture made_up(uint32_t w, uint32_t h) {   // (a gradient that differs at every pixel and channel; alpha not 255)
    TeleportPicture p;
    p.w = w, p.h = h, p.rgba.resize((size_t)w * h * 4);
    for (size_t i = 0; i < (size_t)w * h; i++)
        p.rgba[i * 4] = (unsigned char)(i * 7), p.rgba[i * 4 + 1] = (unsigned char)(i * 13 + 1), p.rgba[i * 4 + 2] = (unsigned char)(i * 29 + 2),
        p.rgba[i * 4 + 3] = 17;
    return p;
}
static void put(const std::string& path, const std::vector<unsigned char>& bytes) {
    FILE* f = fopen(path.c_str(), "wb");
    assert(f);
    fwrite(bytes.data(), 1, bytes.size(), f);
    fclose(f);
}
static std::vector<unsigned char> get(const std::string& path) {
    FILE* f = fopen(path.c_str(), "rb");
    assert(f);
    std::vector<unsigned char> b;
    int c;
    while ((c = fgetc(f)) != EOF) b.push_back((unsigned char)c);
    fclose(f);
    return b;
}
static std::vector<unsigned char> header(const char* magic, uint32_t w, uint32_t h) {
    std::vector<unsigned char> b(magic, magic + 4);
    for (uint32_t v : {w, h})
        for (int i = 0; i < 4; i++) b.push_back((unsigned char)(v >> (8 * i)));
    return b;
}
int main(int argc, char** argv) {
    assert(argc == 2);
    const std::string dir = std::string(argv[1]) + "/teleport_pictures/nested";   // (a folder that does not exist yet)
    const std::string file = dir + "/Market_Child.bin";

    // the round trip, a made-up 480x270
    const TeleportPicture src = made_up(480, 270);
    assert(write_picture_file(file, src));
    assert(fs::file_size(file) == 4 + 8 + 480u * 270 * 3);   // ('FTP2', w, h, RGB: no alpha stored)
    assert(!fs::exists(file + ".tmp"));
    {   // (the bytes as written: the header, then each pixel's RGB)
        const std::vector<unsigned char> on_disk = get(file), head = header("FTP2", 480, 270);
        assert(std::equal(head.begin(), head.end(), on_disk.begin()));
        for (size_t i = 0; i < (size_t)480 * 270; i++)
            assert(on_disk[12 + i * 3] == src.rgba[i * 4] && on_disk[12 + i * 3 + 1] == src.rgba[i * 4 + 1] && on_disk[12 + i * 3 + 2] == src.rgba[i * 4 + 2]);
    }
    TeleportPicture back;
    assert(read_picture_file(file, back));
    assert(back.w == 480 && back.h == 270 && back.rgba.size() == src.rgba.size());
    for (size_t i = 0; i < (size_t)480 * 270; i++) {
        assert(back.rgba[i * 4] == src.rgba[i * 4] && back.rgba[i * 4 + 1] == src.rgba[i * 4 + 1] && back.rgba[i * 4 + 2] == src.rgba[i * 4 + 2]);
        assert(back.rgba[i * 4 + 3] == 255);   // (a picture is opaque)
    }

    // writing again replaces the file, and no .tmp stays
    const TeleportPicture other = made_up(4, 2);
    assert(write_picture_file(file, other));
    assert(!fs::exists(file + ".tmp"));
    TeleportPicture second;
    assert(read_picture_file(file, second) && second.w == 4 && second.h == 2);

    // not pictures: left out, one line logged each (and the output not touched)
    const std::string bad = dir + "/bad.bin";
    auto rejects = [&](const std::vector<unsigned char>& bytes) {
        put(bad, bytes);
        TeleportPicture p;
        const int log = logged;
        const bool ok = read_picture_file(bad, p);
        assert(logged == log + 1 && p.rgba.empty());
        return !ok;
    };
    std::vector<unsigned char> good = header("FTP2", 4, 2);
    good.resize(good.size() + 4 * 2 * 3, 9);
    {   // (the control: this one reads)
        put(bad, good);
        TeleportPicture p;
        assert(read_picture_file(bad, p) && p.w == 4 && p.h == 2 && p.rgba[3] == 255);
    }
    { auto old = header("FTP1", 4, 2); old.resize(old.size() + 4 * 2 * 3, 9); assert(rejects(old)); }   // (another magic, a whole body)
    assert(rejects(std::vector<unsigned char>{'F', 'T'}));                        // (cut inside the magic)
    assert(rejects(header("FTP2", 4, 2)));                                        // (no pixels)
    { auto cut = good; cut.pop_back(); assert(rejects(cut)); }                    // (one byte short)
    { auto h0 = header("FTP2", 0, 2); h0.resize(h0.size() + 6); assert(rejects(h0)); }   // (no width)
    { auto big = header("FTP2", 2049, 1); big.resize(big.size() + 2049 * 3); assert(rejects(big)); }   // (past what the worker takes)
    { auto huge = header("FTP2", 0xffffffffu, 0xffffffffu); assert(rejects(huge)); }      // (a size that would not be allocated)

    // a missing file, an empty path
    TeleportPicture none;
    const int log = logged;
    assert(!read_picture_file(dir + "/nothing.bin", none) && !read_picture_file("", none));
    assert(logged == log);   // (a map with no picture yet is the normal case: not logged)

    // a folder that cannot be made (a file is where it should go): the write fails, nothing is left
    const std::string blocker = std::string(argv[1]) + "/blocker";
    put(blocker, {1});
    assert(!write_picture_file(blocker + "/Market_Child.bin", src));
    assert(!write_picture_file("", src));
    std::puts("PASS");
}
'''
    with tempfile.TemporaryDirectory(prefix="tp-pictures-") as tmp:
        cpp = Path(tmp) / "pictures.cpp"
        exe = Path(tmp) / "pictures.exe"
        work = Path(tmp) / "work"
        work.mkdir()
        cpp.write_text(source, encoding="utf-8")
        subprocess.run([a.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe), str(work)], check=True)
    print("PASS: the Teleport picture files round-trip, a bad file is left out, a write replaces and leaves no .tmp")


if __name__ == "__main__":
    main()
