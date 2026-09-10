"""Team7 creative typesetter.
Reads jobs/<id>/plate.* + spec.json, writes final_1080.png, final_2048.png, checks.jpg, report.json.
spec: {"lines": ["..."], "zone": {"x0":0.475,"x1":0.955,"cy":0.46}, "align":"left",
       "max_block_h":0.30, "color":[248,244,236], "callback_url": "..."}
"""
import json, sys, glob, os
sys.path.insert(0, os.path.dirname(__file__))
from screen import find_screen, render_screen
from PIL import Image, ImageDraw, ImageFont, ImageFilter
FONT = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'Inter.ttf')
SAFE_TOP, SAFE_BOT = 0.25, 0.75          # inside the 16:9 crop band with margin
MIN_FONT_PCT = 4.2                          # below this a headline dies at feed size

def font(sz):
    f = ImageFont.truetype(FONT, sz); f.set_variation_by_name('ExtraBold'); return f

def typeset(job):
    spec = json.load(open(os.path.join(job, 'spec.json')))
    plate = [p for p in glob.glob(os.path.join(job, 'plate.*'))][0]
    im = Image.open(plate).convert('RGB')
    if im.size[0] != im.size[1]:
        s = min(im.size); l = (im.size[0]-s)//2; t = (im.size[1]-s)//2; im = im.crop((l, t, l+s, t+s))
    im = im.resize((2048, 2048), Image.LANCZOS); W = H = 2048
    screen_info = {"requested": False}
    sc = spec.get('screen') or {}
    if not sc and spec.get('parent'):   # edits inherit the parent's in-screen text
        pp = os.path.join(os.path.dirname(job.rstrip('/')), spec['parent'], 'spec.json')
        if os.path.exists(pp): sc = json.load(open(pp)).get('screen') or {}
    if sc.get('type') in ('search', 'article') and sc.get('text', '').strip():
        corners, frac = find_screen(im)
        screen_info = {"requested": True, "found": corners is not None, "area_frac": round(float(frac), 3)}
        if corners:
            im, fpct_s = render_screen(im, corners, sc, FONT); screen_info["text_pct_of_height"] = round(float(fpct_s), 2)
    lines = [l for l in spec['lines'] if l.strip()]
    z = spec.get('zone', {}); x0 = int(z.get('x0', .08)*W); x1 = int(z.get('x1', .92)*W); cy = z.get('cy', .5)
    maxw = x1-x0; maxh = spec.get('max_block_h', .30)*H; align = spec.get('align', 'left')
    sz = 30
    while True:
        f = font(sz+2); lh = (sz+2)*1.15
        if max(f.getlength(l) for l in lines) > maxw or lh*len(lines) > maxh: break
        sz += 2
    # collision guard: off-white text needs a dark background. Push the block right
    # (or left for right-aligned zones) until no bright subject pixels sit under it.
    lum = im.convert('L'); edges = lum.filter(ImageFilter.GaussianBlur(3)).filter(ImageFilter.FIND_EDGES)
    def layout(x0, sz):
        f = font(sz); lh = int(sz*1.15); bh = lh*len(lines)
        y0 = int(cy*H - bh/2); y0 = max(int(SAFE_TOP*H), min(y0, int(SAFE_BOT*H)-bh))
        return f, lh, bh, y0
    def fits(x0, sz):
        f = font(sz); return max(f.getlength(l) for l in lines) <= x1-x0 and sz*1.15*len(lines) <= maxh
    def collides(x0, sz):
        f, lh, bh, y0 = layout(x0, sz); w = int(max(f.getlength(l) for l in lines))
        pad = int(0.05*W); box = (max(0, x0-pad), max(0, y0-pad), min(W, x0+w+pad), min(H, y0+bh+pad))
        hist = lum.crop(box).histogram(); total = sum(hist); bright = sum(hist[165:])
        strip = (max(0, x0-pad), box[1], x0, box[3]) if align != 'right' else (x0+w, box[1], min(W, x0+w+pad), box[3])
        eh = edges.crop(strip).histogram(); st = max(1, sum(eh)); sharp = sum(eh[20:])
        return bright/total > 0.004 or sharp/st > 0.0003
    # Try the requested height first, then nearby heights inside the crop band, and keep
    # whichever placement allows the biggest collision-free text (vertical move beats shrinking).
    X0, SZ, CY = x0, sz, cy; best = None
    for dy in (0, .05, -.05, .10, -.10, .15, -.15):
        cy = CY+dy
        if cy < SAFE_TOP+.06 or cy > SAFE_BOT-.06: continue
        x0, sz, moved = X0, SZ, 0
        while collides(x0, sz) and x0 < x1-int(0.2*W):
            x0 += int(0.01*W); moved += 1
            while not fits(x0, sz) and sz > 30: sz -= 2
        ok = not collides(x0, sz)
        score = (ok, sz, -abs(dy))
        if best is None or score > best[0]: best = (score, x0, sz, cy, moved)
    _, x0, sz, cy, moved = best
    # If the strategist's zone is too narrow for readable type, widen it toward the open side,
    # one percent at a time, only while an 8%-of-width gap beyond the text stays empty and dark.
    widened = 0
    def gap_clear(xr, sz):
        f, lh, bh, y0 = layout(x0, sz); pad = int(0.03*H)
        box = (xr, max(0, y0-pad), min(W, xr+int(0.08*W)), min(H, y0+bh+pad))
        if box[2]-box[0] < int(0.08*W): return False
        hist = lum.crop(box).histogram(); bright = sum(hist[140:])/max(1, sum(hist))
        eh = edges.crop(box).histogram(); sharp = sum(eh[20:])/max(1, sum(eh))
        return bright < 0.004 and sharp < 0.0003
    if align == 'left':
        while sz/H*100 < MIN_FONT_PCT and widened < 12:
            f0 = font(sz); textr = x0+int(max(f0.getlength(l) for l in lines))
            if not gap_clear(textr+int(0.01*W), sz+2): break
            x1 += int(0.01*W); widened += 1
            while fits(x0, sz+2) and not collides(x0, sz+2): sz += 2
    f, lh, bh, y0 = layout(x0, sz); maxw = x1-x0
    collision = collides(x0, sz)
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
              "pass_crop_band": top >= SAFE_TOP-0.001 and bot <= SAFE_BOT+0.001,
              "shifted_pct": moved, "final_cy": round(cy, 3), "widened_pct": widened, "pass_no_collision": not collision}
    report["screen"] = screen_info
    report["pass_screen"] = bool((not screen_info["requested"]) or (screen_info.get("found") and screen_info.get("text_pct_of_height", 0) >= 2.5))
    report["pass"] = report["pass_min_font"] and report["pass_crop_band"] and report["pass_no_collision"] and report["pass_screen"]
    json.dump(report, open(os.path.join(job, 'report.json'), 'w'), indent=1)
    return spec, report

if __name__ == '__main__':
    for job in sys.argv[1:]:
        print(job, typeset(job)[1])
