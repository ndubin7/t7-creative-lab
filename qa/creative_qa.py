"""Creative pre-flight check: run on every headline and on-image text BEFORE upload.
Usage: check(text, kind='headline'|'overlay', offer=None) -> list of problems (empty = pass)."""
import re
BANNED = ['free','government','grant','stimulus','rebate','program','guaranteed','limited time','new ',' new','tax credit']
PCB_REQUIRED = ['quote','cost','price','savings','budget','affordable']  # need >=2 for 86832, 74830, 1000767-style rules
QUESTION_STARTS = ('do ','does ','did ','is ','are ','was ','were ','can ','could ','should ','will ','would ',
                   'have ','has ','tired of','still ','own a','what ','how ','why ','where ','which ','who ','when ')
def check(text, kind='headline', offer=None):
    p=[]; t=text.strip(); low=t.lower()
    for b in BANNED:
        if b in f' {low} ': p.append(f'banned word: "{b.strip()}"')
    if re.search(r'\$\s?\d|\d+\s?%', t): p.append('number/savings claim: needs advertiser substantiation')
    if '—' in t or '–' in t: p.append('em/en dash: not allowed')
    if '  ' in t: p.append('double space')
    if kind=='headline' and len(t)>60: p.append(f'headline {len(t)} chars (>60)')
    lines=[l.strip() for l in t.split('/')] if kind=='overlay' else [t]
    if kind=='overlay':
        for i,l in enumerate(lines,1):
            if not 1<=len(l.split())<=6: p.append(f'line {i}: {len(l.split())} words (1-6)')
        if not re.search(r'[.?!]$', lines[-1]): p.append('last line: missing end punctuation')
        if lines[0][:1].islower(): p.append('first line should start uppercase (sentence case)')
    joined=' '.join(lines)
    # check each SENTENCE (lines can wrap mid-sentence)
    for sent in re.findall(r'[^.?!]+[.?!]?', joined):
        st=sent.strip(); sl=st.lower()+' '
        if not st: continue
        if sl.startswith(QUESTION_STARTS) and not st.endswith('?'):
            p.append(f'"{st}" reads as a question but does not end with "?"')
        if len(st.rstrip('.?!').split())<=3 and st.endswith('.') and not sl.startswith(('see ','compare ','get ','find ','check ','learn ','read ','start ')):
            p.append(f'REVIEW "{st}": short fragment ending in "." - should it be a question?')
    if offer in ('86832','74830','1000767'):
        n=sum(1 for w in PCB_REQUIRED if w in low)
        if n<2: p.append(f'PerformCB {offer}: needs >=2 of {PCB_REQUIRED}, has {n}')
    return p

if __name__=='__main__':
    tests=[('Tired of stepping / over the tub.','overlay',None),
           ('Tired of stepping / over the tub?','overlay',None),
           ('Old windows. / See local prices.','overlay',None),
           ('Old windows? / See local prices.','overlay',None),
           ('Still Climbing a Ladder to Clean Your Gutters?','headline',None),
           ('Clogged Gutters? Compare Local Quotes','headline',None),
           ('See Gutter Guard Prices in Your Area','headline',None),
           ('Tub-to-Shower Conversion Cost: Compare Local Quotes','headline','74830'),
           ('Fogged Window Panes? Compare Replacement Costs and Quotes','headline','86832'),
           ('Homeowners: Compare Window Prices and Quotes Near You','headline','86832'),
           ('Walk-In Shower Cost in Your Area: Compare Quotes','headline','74830'),
           ('Window Replacement Cost: Compare Local Quotes','headline','86832'),
           ('See Window Prices in Your Area and Compare Quotes','headline','86832'),
           ('Bathroom Remodel on a Budget? Compare Local Prices','headline','74830')]
    for t,k,o in tests:
        r=check(t,k,o); print(('PASS ' if not r else 'FAIL ')+f'[{k}{"/"+o if o else ""}] {t}' + ('' if not r else '\n      -> '+'; '.join(r)))
