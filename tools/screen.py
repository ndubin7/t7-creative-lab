"""Find a blank phone screen in a plate and typeset in-scene text onto it with perspective."""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from collections import deque

def _font(path, sz, var='ExtraBold'):
    f = ImageFont.truetype(path, sz); f.set_variation_by_name(var); return f

def find_screen(im, thresh=205, min_frac=0.03):
    g = np.array(im.convert('L').resize((256, 256)))
    m = g > thresh; seen = np.zeros_like(m); best = []
    for y in range(256):
        for x in range(256):
            if m[y, x] and not seen[y, x]:
                q = deque([(y, x)]); seen[y, x] = 1; comp = []
                while q:
                    cy, cx = q.popleft(); comp.append((cy, cx))
                    for ny, nx in ((cy+1, cx), (cy-1, cx), (cy, cx+1), (cy, cx-1)):
                        if 0 <= ny < 256 and 0 <= nx < 256 and m[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = 1; q.append((ny, nx))
                if len(comp) > len(best): best = comp
    if len(best) < min_frac*256*256: return None, len(best)/65536
    ys = np.array([p[0] for p in best]); xs = np.array([p[1] for p in best]); s = xs+ys; d = xs-ys
    k = im.size[0]/256
    tl = (xs[s.argmin()]*k, ys[s.argmin()]*k); br = (xs[s.argmax()]*k, ys[s.argmax()]*k)
    tr = (xs[d.argmax()]*k, ys[d.argmax()]*k); bl = (xs[d.argmin()]*k, ys[d.argmin()]*k)
    return [tl, tr, br, bl], len(best)/65536

def _coeffs(dst, src):
    A = []; B = []
    for (x, y), (u, v) in zip(dst, src):
        A += [[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]]; B += [u, v]
    return np.linalg.solve(np.array(A, float), np.array(B, float)).tolist()

def _wrap(draw, text, f, maxw):
    words = text.split(); lines = []; cur = ''
    for w in words:
        t = (cur+' '+w).strip()
        if draw.textlength(t, font=f) <= maxw: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def render_screen(im, corners, spec, fontpath):
    tl, tr, br, bl = corners
    w = ((tr[0]-tl[0])**2+(tr[1]-tl[1])**2)**.5; h = ((bl[0]-tl[0])**2+(bl[1]-tl[1])**2)**.5
    CW = 900; CH = int(CW*h/max(w, 1))
    cv = Image.new('RGBA', (CW, CH), (0, 0, 0, 0)); d = ImageDraw.Draw(cv)
    pad = int(CW*0.08); inner = CW-2*pad; text = spec.get('text', '').strip(); rows = [r for r in spec.get('rows', []) if r.strip()][:2]
    ink = (22, 24, 28, 255); grey = (150, 155, 162, 255); pill = (236, 238, 242, 255)
    if spec.get('type') == 'search':
        pad = int(CW*0.05); pin = int(CW*0.05); tw = CW-2*pad-2*pin
        sz = 240
        while sz > 40:
            f = _font(fontpath, sz); lines = _wrap(d, text, f, tw)
            if len(lines) <= 4 and all(d.textlength(l, font=f) <= tw for l in lines): break
            sz -= 4
        lab = _font(fontpath, int(CW*0.05), 'SemiBold'); top = int(CH*0.07)
        r = int(CW*0.022); cx = pad+pin+r; cy = top+int(CW*0.03)
        d.ellipse((cx-r, cy-r, cx+r, cy+r), outline=grey, width=6); d.line((cx+r*0.7, cy+r*0.7, cx+r*1.6, cy+r*1.6), fill=grey, width=7)
        d.text((cx+int(r*2.4), cy-int(CW*0.03)), "Search", font=lab, fill=grey)
        top += int(CW*0.10); lh = int(sz*1.08); ph = lh*len(lines)+2*pin
        d.rounded_rectangle((pad, top, CW-pad, top+ph), radius=int(CW*0.05), fill=pill)
        for i, l in enumerate(lines): d.text((pad+pin, top+pin+i*lh-int(sz*0.08)), l, font=f, fill=ink)
        fr = _font(fontpath, max(34, int(sz*0.42)), 'Medium'); y = top+ph+int(CW*0.06)
        for rw in rows:
            d.text((pad+pin, y), rw, font=fr, fill=grey); y += int(sz*0.62)
    else:  # article
        sz = 140
        while sz > 40:
            f = _font(fontpath, sz); lines = _wrap(d, text, f, inner)
            if len(lines) <= 4: break
            sz -= 4
        lh = int(sz*1.1); y = int(CH*0.09)
        for l in lines: d.text((pad, y), l, font=f, fill=ink); y += lh
        y += int(CW*0.05); d.rounded_rectangle((pad, y, CW-pad, y+int(CW*0.45)), radius=18, fill=(205, 208, 214, 255)); y += int(CW*0.55)
        for i in range(4): d.rounded_rectangle((pad, y, CW-pad-(i % 2)*120, y+26), radius=13, fill=(215, 218, 223, 255)); y += 60
    src = [(0, 0), (CW, 0), (CW, CH), (0, CH)]
    warped = cv.transform(im.size, Image.PERSPECTIVE, _coeffs(corners, src), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))
    out = Image.alpha_composite(im.convert('RGBA'), warped).convert('RGB')
    return out, sz/CH*(h/im.size[1])*100   # query font as percent of full image height
