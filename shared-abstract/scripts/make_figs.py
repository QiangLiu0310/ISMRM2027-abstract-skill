#!/usr/bin/env python3
"""Make web copies of the abstract's figures for the shared page.

Usage: python3 make_figs.py out_dir src1.png src2.pdf ...   (sources in figure order)

Writes out_dir/fig/fig1.jpg, fig2.jpg, ... : flattened onto white, at most 2000 px wide,
JPEG quality 88. A PDF/EPS source is rasterized from its first page (needs pdftoppm or
macOS sips). Uses Pillow when installed, otherwise macOS sips.
"""
import os, shutil, subprocess, sys, tempfile

MAX_W, QUALITY = 2000, 88


def rasterize(src, tmp):
    ext = os.path.splitext(src)[1].lower()
    if ext not in (".pdf", ".eps"):
        return src
    out = os.path.join(tmp, "page")
    if shutil.which("pdftoppm"):
        subprocess.run(["pdftoppm", "-png", "-r", "300", "-singlefile", src, out], check=True)
        return out + ".png"
    subprocess.run(["sips", "-s", "format", "png", src, "--out", out + ".png"], check=True, capture_output=True)
    return out + ".png"


def convert(src, dst):
    try:
        from PIL import Image
    except ImportError:
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(QUALITY),
                        "--resampleWidth", str(MAX_W), src, "--out", dst], check=True, capture_output=True)
        return
    im = Image.open(src)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    if im.width > MAX_W:
        im = im.resize((MAX_W, round(im.height * MAX_W / im.width)), Image.LANCZOS)
    im.save(dst, "JPEG", quality=QUALITY, optimize=True)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    out_dir, srcs = sys.argv[1], sys.argv[2:]
    os.makedirs(os.path.join(out_dir, "fig"), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for n, src in enumerate(srcs, 1):
            dst = os.path.join(out_dir, "fig", "fig%d.jpg" % n)
            convert(rasterize(src, tmp), dst)
            print("%s <- %s (%d KB)" % (dst, src, os.path.getsize(dst) // 1024))


if __name__ == "__main__":
    main()
