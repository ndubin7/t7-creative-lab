"""HCN daily report: per-source funnel + rule-based actions (report section of the research plan).
Inputs (one row per MGID source/widget for the period):
  mgid:  widget, campaign, spend, clicks, viewable_imps, offer_redirect (MGID goal), owner_yes (MGID goal)
  ga4:   widget, page_views, owner_yes, zip_submit, offer_redirect, no_click_id_hits, zip3_mismatch
  leads: widget, offer, payout, accepted (from postback sheet / network report)
Rules (research report + launch package):
  - Bot flag: clicks > viewable impressions, or <50% of clicks render a page view
  - Proxy block: spend >= $15 and 0 offer_redirect
  - Lead block: spend >= 2x payout and 0 accepted leads
  - Scale: cost per accepted lead < 70% of payout (2 days) -> double / x1.5-2 multiplier
  - Tracking alert: >2% of hits without a click id
"""
from collections import defaultdict
def build(mgid, ga4, leads, payout_by_campaign):
    G={r['widget']:r for r in ga4}; L=defaultdict(lambda:{'leads':0,'rev':0.0})
    for r in leads: L[r['widget']]['leads']+=r['accepted']; L[r['widget']]['rev']+=r['accepted']*r['payout']
    rows=[]; actions=[]; tot=defaultdict(float)
    for m in mgid:
        w=m['widget']; g=G.get(w,{}); l=L[w]; pay=payout_by_campaign.get(m['campaign'],12.0)
        pv=g.get('page_views',0); cpl=(m['spend']/l['leads']) if l['leads'] else None
        r=dict(widget=w,campaign=m['campaign'],spend=m['spend'],clicks=m['clicks'],
               render=pv/m['clicks'] if m['clicks'] else 0, redirects=m.get('offer_redirect',0),
               leads=l['leads'],rev=l['rev'],profit=l['rev']-m['spend'],cpl=cpl)
        rows.append(r)
        for k in ('spend','clicks','leads','rev'): tot[k]+=r[k]
        tot['redirects']+=r['redirects']; tot['pv']+=pv; tot['noclick']+=g.get('no_click_id_hits',0)
        if m['clicks']>m.get('viewable_imps',10**9) or (m['clicks']>=30 and r['render']<0.5):
            actions.append(f"BLOCK {w}: likely bots (clicks {m['clicks']}, viewable {m.get('viewable_imps','?')}, page render {r['render']:.0%})")
        elif m['spend']>=15 and r['redirects']==0:
            actions.append(f"BLOCK {w}: ${m['spend']:.2f} spent, 0 offer click-throughs")
        elif m['spend']>=2*pay and l['leads']==0:
            actions.append(f"BLOCK {w}: ${m['spend']:.2f} spent (>= 2x ${pay:.2f} payout), 0 accepted leads")
        elif cpl is not None and cpl<0.7*pay:
            actions.append(f"SCALE {w}: cost per lead ${cpl:.2f} < 70% of ${pay:.2f} (raise multiplier x1.5-2 if it holds 2 days)")
        if g.get('zip3_mismatch',0)>=3: actions.append(f"CHECK {w}: {g['zip3_mismatch']} ZIPs outside the region MGID reports (possible bots)")
    if tot['pv'] and tot['noclick']/tot['pv']>0.02: actions.append(f"TRACKING ALERT: {tot['noclick']/tot['pv']:.1%} of page hits had no click id (>2%)")
    return rows,actions,tot
def render(rows,actions,tot):
    out=['| Source | Campaign | Spend | Clicks | Page render | Offer clicks | Leads | Revenue | Profit | Cost/lead |','|---|---|---|---|---|---|---|---|---|---|']
    for r in sorted(rows,key=lambda r:-r['spend']):
        out.append(f"| {r['widget']} | {r['campaign']} | ${r['spend']:.2f} | {r['clicks']} | {r['render']:.0%} | {r['redirects']} | {r['leads']} | ${r['rev']:.2f} | ${r['profit']:.2f} | {'$%.2f'%r['cpl'] if r['cpl'] else '-'} |")
    out.append(f"| **Total** | | **${tot['spend']:.2f}** | **{int(tot['clicks'])}** | | **{int(tot['redirects'])}** | **{int(tot['leads'])}** | **${tot['rev']:.2f}** | **${tot['rev']-tot['spend']:.2f}** | |")
    out.append('\n**Proposed actions (Nate approves):**'); out+= [f'- {a}' for a in actions] or ['- None']
    return '\n'.join(out)
if __name__=='__main__':
    mgid=[dict(widget='W1',campaign='HS-C',spend=16.2,clicks=135,viewable_imps=9000,offer_redirect=0),
          dict(widget='W2',campaign='HS-C',spend=9.0,clicks=140,viewable_imps=120,offer_redirect=4),
          dict(widget='W3',campaign='HS-C',spend=80.0,clicks=660,viewable_imps=40000,offer_redirect=40),
          dict(widget='W4',campaign='HS-D',spend=30.0,clicks=420,viewable_imps=30000,offer_redirect=25)]
    ga4=[dict(widget='W1',page_views=120),dict(widget='W2',page_views=30),dict(widget='W3',page_views=600,zip3_mismatch=4),
         dict(widget='W4',page_views=400,no_click_id_hits=30)]
    leads=[dict(widget='W4',offer='nan_gutters',payout=37.5,accepted=2)]
    r,a,t=build(mgid,ga4,leads,{'HS-C':37.5,'HS-D':37.5}); print(render(r,a,t))
