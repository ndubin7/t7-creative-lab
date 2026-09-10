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
    # allow breaks after hyphens so compound words like weight-loss do not cap the font size
    words = text.replace('-', '- ').split(); words = [w if w.endswith('-') else w+' ' for w in words]
    lines = []; cur = ''
    for w in words:
        t = cur+w
        if draw.textlength(t.strip(), font=f) <= maxw: cur = t
        else: lines.append(cur.strip()); cur = w
    if cur.strip(): lines.append(cur.strip())
    return lines

def _wrap_old(draw, text, f, maxw):
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
    elif spec.get('type') == 'article':  # the headline is the hook, so it gets the biggest size that fits 5 lines
        pad = int(CW*0.06); inner = CW-2*pad
        sz = 260
        while sz > 40:
            f = _font(fontpath, sz); lines = _wrap(d, text, f, inner)
            if len(lines) <= 5 and all(d.textlength(l, font=f) <= inner for l in lines): break
            sz -= 4
        lh = int(sz*1.1)
        # Clean story-card layout: small section label, big headline, thin rule, read time.
        # No placeholder images or fake body bars. The block is centred on the part of the
        # screen that survives MGID's 16:9 crop, so the headline is never sliced.
        tl, tr, br, bl = corners; top_img = (tl[1]+tr[1])/2; bot_img = (bl[1]+br[1])/2; Himg = im.size[1]
        def to_c(yimg): return (yimg-top_img)/max(1, bot_img-top_img)*CH
        vis_top = max(to_c(0.25*Himg), CH*0.06); vis_bot = min(to_c(0.75*Himg), CH*0.94)
        ks = max(28, int(sz*0.32)); kf = _font(fontpath, ks); mf = _font(fontpath, ks)
        accent = (31, 111, 120, 255); grey = (120, 126, 136, 255)
        block = ks*1.9 + lh*len(lines) + ks*0.8 + 4 + ks*0.8 + ks
        y = int(max(vis_top, (vis_top+vis_bot)/2 - block/2))
        d.text((pad, y), "Health", font=kf, fill=accent); y += int(ks*1.9)
        for l in lines: d.text((pad, y), l, font=f, fill=ink); y += lh
        y += int(ks*0.8); d.line((pad, y, pad+int(inner*0.35), y), fill=(200, 204, 210, 255), width=4)
        y += int(ks*0.8); d.text((pad, y), "5 min read", font=mf, fill=grey)
    elif spec.get('type') in ('message', 'notification'):
        tl, tr, br, bl = corners; top_img = (tl[1]+tr[1])/2; bot_img = (bl[1]+br[1])/2; Himg = im.size[1]
        def to_c(yimg): return (yimg-top_img)/max(1, bot_img-top_img)*CH
        vis_top = max(to_c(0.25*Himg), CH*0.06); vis_bot = min(to_c(0.75*Himg), CH*0.94)
        if spec['type'] == 'message':
            # iMessage-style received bubble: the message is the hook, so it gets the biggest size that fits
            pad = int(CW*0.05); bin_ = int(CW*0.05); maxb = int(CW*0.86)-2*bin_
            sz = 220
            while sz > 40:
                f = _font(fontpath, sz, 'SemiBold'); lines = _wrap(d, text, f, maxb)
                if len(lines) <= 5 and all(d.textlength(l, font=f) <= maxb for l in lines): break
                sz -= 4
            lh = int(sz*1.12); bw = int(max(d.textlength(l, font=f) for l in lines))+2*bin_; bh = lh*len(lines)+2*bin_-int(sz*0.12)
            ts = max(28, int(sz*0.3)); tf = _font(fontpath, ts, 'Medium')
            block = ts*2.2 + bh + (int(sz*0.9)+2*bin_ if rows else 0)
            y = int(max(vis_top, (vis_top+vis_bot)/2 - block/2))
            stamp = "Today 10:42 PM"; d.text(((CW-d.textlength(stamp, font=tf))/2, y), stamp, font=tf, fill=grey); y += int(ts*2.2)
            d.rounded_rectangle((pad, y, pad+bw, y+bh), radius=int(min(bh/2, CW*0.07)), fill=(233, 233, 235, 255))
            for i, l in enumerate(lines): d.text((pad+bin_, y+bin_+i*lh-int(sz*0.1)), l, font=f, fill=ink)
            y += bh+int(CW*0.03)
            if rows:
                s2 = int(sz*0.75)
                while s2 > 30 and d.textlength(rows[0], font=_font(fontpath, s2, 'SemiBold')) > maxb: s2 -= 2
                f2 = _font(fontpath, s2, 'SemiBold'); w2 = int(d.textlength(rows[0], font=f2))+2*bin_; h2 = int(s2*1.1)+2*bin_
                d.rounded_rectangle((pad, y, pad+min(w2, CW-2*pad), y+h2), radius=int(h2/2), fill=(233, 233, 235, 255))
                d.text((pad+bin_, y+bin_-int(s2*0.1)), rows[0], font=f2, fill=ink)
        else:
            # lock screen: dark wallpaper, clock, one notification card carrying the headline
            for yy in range(CH):
                t = yy/max(1, CH); d.line((0, yy, CW, yy), fill=(int(18+12*t), int(40+18*t), int(46+20*t), 255))
            pad = int(CW*0.035); cin = int(CW*0.045); tw = CW-2*pad-2*cin
            sz = 240
            while sz > 40:
                f = _font(fontpath, sz, 'Bold'); lines = _wrap(d, text, f, tw)
                if len(lines) <= 5 and all(d.textlength(l, font=f) <= tw for l in lines): break
                sz -= 4
            lh = int(sz*1.1); ls = max(30, int(sz*0.34)); lf = _font(fontpath, ls, 'SemiBold')
            ch = int(ls*1.9)+lh*len(lines)+2*cin; ck = _font(fontpath, int(CW*0.15), 'Light'); ckh = int(CW*0.2)
            block = ckh+int(CW*0.06)+ch
            y = int(max(vis_top, (vis_top+vis_bot)/2 - block/2))
            clock = "10:42"; d.text(((CW-d.textlength(clock, font=ck))/2, y), clock, font=ck, fill=(245, 245, 247, 255)); y += ckh+int(CW*0.06)
            d.rounded_rectangle((pad, y, CW-pad, y+ch), radius=int(CW*0.06), fill=(244, 244, 246, 240))
            d.text((pad+cin, y+cin), "NEWS  \u00b7  now", font=lf, fill=grey)
            for i, l in enumerate(lines): d.text((pad+cin, y+cin+int(ls*1.9)+i*lh-int(sz*0.08)), l, font=f, fill=ink)
    if spec.get('type') == 'notification':
        cx0 = sum(p[0] for p in corners)/4; cy0 = sum(p[1] for p in corners)/4
        corners = [(cx0+(x-cx0)*1.075, cy0+(y-cy0)*1.03) for x, y in corners]
    src = [(0, 0), (CW, 0), (CW, CH), (0, CH)]
    warped = cv.transform(im.size, Image.PERSPECTIVE, _coeffs(corners, src), Image.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))
    base = im.convert('RGBA')
    if spec.get('type') == 'notification':
        # repaint leftover bright screen edge pixels (dimmer than the detector threshold) in wallpaper colour
        xs = [p[0] for p in corners]; ys = [p[1] for p in corners]
        box = (int(max(0, min(xs)-0.04*im.size[0])), int(max(0, min(ys)-0.02*im.size[1])), int(min(im.size[0], max(xs)+0.04*im.size[0])), int(min(im.size[1], max(ys)+0.02*im.size[1])))
        reg = np.array(base.crop(box)); rgb = reg[..., :3].astype(int); lum = rgb.mean(axis=2)
        sat = rgb.max(axis=2)-rgb.min(axis=2)
        cx0 = sum(p[0] for p in corners)/4; cy0 = sum(p[1] for p in corners)/4
        poly = [(cx0+(x-cx0)*1.06-box[0], cy0+(y-cy0)*1.03-box[1]) for x, y in corners]
        pm = Image.new('L', (box[2]-box[0], box[3]-box[1]), 0); ImageDraw.Draw(pm).polygon(poly, fill=255)
        m = (lum > 120) & (sat < 40) & (np.array(pm) > 0)   # neutral white screen glow only, never warm skin
        reg[m] = (24, 50, 58, 255); base.paste(Image.fromarray(reg), box[:2])
    out = Image.alpha_composite(base, warped).convert('RGB')
    return out, sz/CH*(h/im.size[1])*100   # query font as percent of full image height
