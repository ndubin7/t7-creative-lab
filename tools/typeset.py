"""Team7 creative typesetter.
Reads jobs/<id>/plate.* + spec.json, writes final_1080.png, final_2048.png, checks.jpg, report.json.
spec: {"lines": ["..."], "zone": {"x0":0.475,"x1":0.955,"cy":0.46}, "align":"left",
       "max_block_h":0.30, "color":[248,244,236], "callback_url": "..."}
"""
import json, sys, glob, os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FONT = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'Inter.ttf')
SAFE_TOP, SAFE_BOT = 0.25, 0.75          # inside the 16:9 crop band with margin
MIN_FONT_PCT = 5.0                          # below this a headline dies at feed size

def font(sz):
    f = ImageFont.truetype(FONT, sz); f.set_variation_by_name('ExtraBold'); return f

def typeset(job):
    spec = json.load(open(os.path.join(job, 'spec.json')))
    plate = [p for p in glob.glob(os.path.join(job, 'plate.*'))][0]
    im = Image.open(plate).convert('RGB')
    if im.size[0] != im.size[1]:
        s = min(im.size); l = (im.size[0]-s)//2; t = (im.size[1]-s)//2; im = im.crop((l, t, l+s, t+s))
    im = im.resize((2048, 2048), Image.LANCZOS); W = H = 2048
    lines = [l for l in spec['lines'] if l.strip()]
    z = spec.get('zone', {}); x0 = int(z.get('x0', .08)*W); x1 = int(z.get('x1', .92)*W); cy = z.get('cy', .5)
    maxw = x1-x0; maxh = spec.get('max_block_h', .30)*H; align = spec.get('align', 'left')
    sz = 30
    while True:
        f = font(sz+2); lh = (sz+2)*1.15
        if max(f.getlength(l) for l in lines) > maxw or lh*len(lines) > maxh: break
        sz += 2
    f = font(sz); lh = int(sz*1.15); bh = lh*len(lines)
    y0 = int(cy*H - bh/2)
    y0 = max(int(SAFE_TOP*H), min(y0, int(SAFE_BOT*H)-bh))   # clamp into crop-safe band
    color = tuple(spec.get('color', [248, 244, 236]))
    pos = []
    for i, l in enumerate(lines):
        w = f.getlength(l)
        x = x0 if align == 'left' else (x0+(maxw-w)/2 if align == 'center' else x1-w)
        pos.append((int(x), y0+i*lh, l))
    shadow = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(shadow)
    for x, y, l in pos: d.text((x+5, y+6), l, font=f, fill=(0, 0, 0, 160))
    out = Image.alpha_composite(im.convert('RGBA'), shadow.filter(ImageFilter.GaussianBlur(9)))
    d = ImageDraw.Draw(out)
    for x, y, l in pos: d.text((x, y), l, font=f, fill=color+(255,))
    out = out.convert('RGB')
    out.save(os.path.join(job, 'final_2048.png'))
    out.resize((1080, 1080), Image.LANCZOS).save(os.path.join(job, 'final_1080.png'))
    # check sheet: feed thumbnail + MGID crops (full width, height trimmed)
    parts = [out.resize((300, 300), Image.LANCZOS)]
    for r in (16/9, 3/2):
        ch = int(W/r); t = (H-ch)//2; parts.append(out.crop((0, t, W, t+ch)).resize((600, int(600/r)), Image.LANCZOS))
    a, b, c = parts; sheet = Image.new('RGB', (920, b.size[1]+c.size[1]+20), 'white')
    sheet.paste(a, (0, 0)); sheet.paste(b, (320, 0)); sheet.paste(c, (320, b.size[1]+20))
    sheet.save(os.path.join(job, 'checks.jpg'), quality=88)
    fpct = sz/H*100; top = y0/H; bot = (y0+bh)/H
    report = {"font_pct_of_height": round(fpct, 2), "text_top": round(top, 3), "text_bottom": round(bot, 3),
              "lines": lines, "pass_min_font": fpct >= MIN_FONT_PCT,
              "pass_crop_band": top >= SAFE_TOP-0.001 and bot <= SAFE_BOT+0.001}
    report["pass"] = report["pass_min_font"] and report["pass_crop_band"]
    json.dump(report, open(os.path.join(job, 'report.json'), 'w'), indent=1)
    return spec, report

if __name__ == '__main__':
    for job in sys.argv[1:]:
        print(job, typeset(job)[1])
