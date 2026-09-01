#!/usr/bin/env python3
"""Misspelling battery for editions 65-79 (owner leniency pass, 1 Sep 2026).
For every scheduled answer: lone distinctive words, prefix-dropped forms and
scripted misspellings must be accepted; prints every gap for variant curation."""
import json, re, sys, os
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests"))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright
from helpers import server, page_on, manifest

GENERIC={'hms','uss','rms','ss','mount','mt','cape','lake','the','of','a','an'}
def items_of(p):
    d=json.load(open(p))
    return d.get('items') or d.get('figures') if isinstance(d,dict) else d
POOLS={'who':items_of('data/reveal-who.json'),'what':items_of('data/reveal-what.json'),'map':items_of('data/figures.json')}
BYID={g:{i['id']:i for i in POOLS[g]} for g in POOLS}
eds=manifest()['editions']
sched={'who':[], 'what':[], 'map':[]}
for n in range(65,80):
    for g in sched:
        for i in eds[str(n)][g]:
            if i not in sched[g]: sched[g].append(i)

def mutations(name):
    n=re.sub(r"[^a-zA-Z\s]","",name).strip()
    out=set()
    low=n.lower()
    # drop one h (non-initial)
    i=low.find('h',1)
    if i>0: out.add(low[:i]+low[i+1:])
    # double a consonant mid-word
    m=re.search(r'[bcdfglmnprst]',low[2:])
    if m: j=m.start()+2; out.add(low[:j]+low[j]+low[j:])
    # y->i and i->y
    if 'y' in low: out.add(low.replace('y','i',1))
    # c->k
    if 'c' in low[1:]: j=low.find('c',1); out.add(low[:j]+'k'+low[j+1:])
    # drop a doubled letter
    m=re.search(r'(.)\1',low)
    if m: out.add(low[:m.start()]+low[m.start()+1:])
    # drop one vowel mid-word (only for longer names)
    if len(low)>=8:
        m=re.search(r'[aeiou]',low[3:])
        if m: j=m.start()+3; out.add(low[:j]+low[j+1:])
    return {o for o in out if o!=low and len(o)>=4}

cases=[]
for g,ids in sched.items():
    for iid in ids:
        it=BYID[g][iid]
        name=it['name']
        toks=[t for t in re.sub(r"[^a-zA-Z\s']"," ",name).split() if t]
        low=[t.lower() for t in toks]
        # lone words (len>=5, not generic-ish)
        if len(toks)>1:
            for t in toks:
                tl=t.lower().strip("'")
                if len(tl)>=5 and tl not in GENERIC:
                    cases.append({'g':t,'id':iid,'pool':g,'kind':'lone:'+tl})
            # prefix-dropped
            if low[0] in GENERIC:
                cases.append({'g':' '.join(toks[1:]),'id':iid,'pool':g,'kind':'noprefix'})
        for mu in mutations(name):
            cases.append({'g':mu,'id':iid,'pool':g,'kind':'misspell:'+mu})

payload=[{'g':c['g'],'item':BYID[c['pool']][c['id']],'pool':c['pool']} for c in cases]
res=[]
with sync_playwright() as pw:
    with server() as base:
        with page_on(pw, "chromium") as (pg, errors):
            pg.goto(base + "/index.html?test=1")
            pg.wait_for_function("window.__CHRONICLE_TEST__ && __CHRONICLE_TEST__.data.figures && __CHRONICLE_TEST__.data.reveal")
            for k in range(0,len(payload),400):
                res+=pg.evaluate("(a)=>a.cases.map((c)=>window.__CHRONICLE_TEST__.isMatch(c.g,c.item,c.pool))",{'cases':payload[k:k+400]})
fails=[c for c,r in zip(cases,res) if not r]
print(f"battery: {len(cases)} guesses, {len(cases)-len(fails)} accepted, {len(fails)} gaps")
for c in fails: print(f"  GAP {c['pool']}/{c['id']}: '{c['g']}' ({c['kind']})")
