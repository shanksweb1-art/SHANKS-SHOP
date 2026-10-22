#!/usr/bin/env python3
"""Generate the web icon (favicon / apple-touch / PWA) from a source image.

Usage:
    python make_favicon.py [source.png]

Default source: icon-source.png next to this script, falling back to
C:/Users/Danzona Medicals/Downloads/shoping cart.png
"""
import base64
import io
import os
import re
import sys

from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SOURCE = os.path.join(BASE, 'icon-source.png')
FALLBACK_SOURCE = r'C:\Users\Danzona Medicals\Downloads\shoping cart.png'

ICO_SIZES = [16, 32, 48, 64, 128, 256]
PNG_SIZE = 512
APPLE_SIZE = 180
BRAND_SIZE = 192

ICON_LINK = '<link rel="icon" href="favicon.svg" type="image/svg+xml">'
HEAD_BLOCK = (
    '{i}<link rel="icon" href="favicon.ico" sizes="32x32">\n'
    '{i}<link rel="icon" href="favicon.png" type="image/png" sizes="512x512">\n'
    '{i}<link rel="icon" href="favicon.svg" type="image/svg+xml">\n'
    '{i}<link rel="apple-touch-icon" href="apple-touch-icon.png">'
)

ICON_LINE_RE = re.compile(
    r'^[ \t]*<link rel="(?:icon|apple-touch-icon)"[^>]*>[ \t]*\r?\n',
    re.MULTILINE,
)
TITLE_RE = re.compile(r'^(?P<indent>[ \t]*)<title>.*?</title>[ \t]*\r?\n', re.MULTILINE)


def find_source(argv):
    if len(argv) > 1:
        return argv[1]
    for candidate in (DEFAULT_SOURCE, FALLBACK_SOURCE):
        if os.path.isfile(candidate):
            return candidate
    return None


def square(img, size):
    img = img.convert('RGBA')
    w, h = img.size
    if w != h:
        side = min(w, h)
        img = img.crop(((w - side) // 2, (h - side) // 2,
                        (w - side) // 2 + side, (h - side) // 2 + side))
    return img.resize((size, size), Image.LANCZOS)


def build_svg(img, size=PNG_SIZE):
    buf = io.BytesIO()
    square(img, size).save(buf, format='PNG', optimize=True)
    data = base64.b64encode(buf.getvalue()).decode('ascii')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {size} {size}" width="{size}" height="{size}">\n'
        f'  <image width="{size}" height="{size}" xlink:href="data:image/png;base64,{data}"/>\n'
        '</svg>\n'
    )


def update_html(base):
    changed = 0
    for name in sorted(os.listdir(base)):
        if not name.lower().endswith('.html'):
            continue
        path = os.path.join(base, name)
        with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
        if 'rel="icon"' not in content and 'rel="apple-touch-icon"' not in content:
            continue

        content = ICON_LINE_RE.sub('', content)

        title = TITLE_RE.search(content)
        if title:
            indent = title.group('indent')
            block = HEAD_BLOCK.format(i=indent) + '\n'
            content = content[:title.end()] + block + content[title.end():]
        else:
            head = re.search(r'<head[^>]*>', content, re.IGNORECASE)
            if not head:
                continue
            block = '\n' + HEAD_BLOCK.format(i='') + '\n'
            content = content[:head.end()] + block + content[head.end():]

        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        changed += 1
    return changed


def main():
    source = find_source(sys.argv)
    if not source:
        print('Source image not found. Place it at icon-source.png or pass a path.')
        return 1

    img = Image.open(source)
    print(f'Source: {source} ({img.size[0]}x{img.size[1]} {img.mode})')

    favicon_png = os.path.join(BASE, 'favicon.png')
    square(img, PNG_SIZE).save(favicon_png, format='PNG', optimize=True)

    apple = os.path.join(BASE, 'apple-touch-icon.png')
    square(img, APPLE_SIZE).save(apple, format='PNG', optimize=True)

    brand = os.path.join(BASE, 'brand-logo.png')
    square(img, BRAND_SIZE).save(brand, format='PNG', optimize=True)

    ico_path = os.path.join(BASE, 'favicon.ico')
    square(img, 256).save(ico_path, format='ICO', sizes=[(s, s) for s in ICO_SIZES])

    svg_path = os.path.join(BASE, 'favicon.svg')
    if os.path.isfile(svg_path) and not os.path.isfile(svg_path + '.bak'):
        with open(svg_path, 'r', encoding='utf-8') as fh:
            original = fh.read()
        if '<image' not in original:
            with open(svg_path + '.bak', 'w', encoding='utf-8') as fh:
                fh.write(original)
    with open(svg_path, 'w', encoding='utf-8') as fh:
        fh.write(build_svg(img))

    changed = update_html(BASE)
    print('Generated: favicon.ico, favicon.png, apple-touch-icon.png, favicon.svg, brand-logo.png')
    print(f'Updated icon links in {changed} HTML files')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
