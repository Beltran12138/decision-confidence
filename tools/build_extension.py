"""Build the Chrome extension: copy the wallet check's hl.js in, draw the icons, zip it.

Usage:
    python tools/build_extension.py        # writes dist/evidence-deflator-extension-<version>.zip

extension/hl.js is a copy of docs/assets/hl.js (the scoring the site and the parity test use),
so the extension and the site cannot drift apart. Icons are the site's mark: three bars under a
red bar line.
"""
import json
import os
import shutil
import zipfile

from PIL import Image, ImageDraw

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
EXT = os.path.join(ROOT, "extension")


def icon(size):
    s = size / 24
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=max(1, round(4 * s)), fill=(21, 23, 28, 255))
    d.rectangle([3 * s, 4 * s, 21 * s, 6 * s], fill=(230, 106, 75, 255))
    for x, y in ((4.5, 13), (9.5, 9.5), (14.5, 15)):
        d.rectangle([x * s, y * s, (x + 3) * s, 20 * s], fill=(250, 249, 246, 255))
    return im


def main():
    shutil.copyfile(os.path.join(ROOT, "docs", "assets", "hl.js"), os.path.join(EXT, "hl.js"))
    os.makedirs(os.path.join(EXT, "icons"), exist_ok=True)
    for n in (16, 48, 128):
        icon(n).save(os.path.join(EXT, "icons", f"{n}.png"))
    version = json.load(open(os.path.join(EXT, "manifest.json"), encoding="utf-8"))["version"]
    os.makedirs(os.path.join(ROOT, "dist"), exist_ok=True)
    out = os.path.join(ROOT, "dist", f"evidence-deflator-extension-{version}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirs, files in os.walk(EXT):
            dirs[:] = [d for d in dirs if d != "store"]  # listing images and text are not part of the package
            for f in sorted(files):
                p = os.path.join(dirpath, f)
                z.write(p, os.path.relpath(p, EXT))
    print(out, os.path.getsize(out))


if __name__ == "__main__":
    main()
