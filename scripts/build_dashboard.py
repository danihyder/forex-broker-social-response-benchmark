#!/usr/bin/env python3
"""
build_dashboard.py — generate the self-contained interactive benchmark dashboard.

Output: dashboard/index.html (no external dependencies, CSP-safe, theme-aware).
Charts are hand-rolled SVG + vanilla JS so the file runs anywhere and publishes
as an Artifact. All panels except bigrams recompute live from filters.
"""
import csv, json, re, pathlib
from collections import Counter, defaultdict

BASE = pathlib.Path(__file__).resolve().parent.parent
CSV = BASE / "data" / "broker_reviews_clean.csv"
PHRASES = BASE / "data" / "complaint_phrases.json"
OUT = BASE / "dashboard" / "index.html"

STOP = set(("the a an and or but to of in on for is are was were i my me we our you your it its this "
            "that with at as be have has had not no so if then just get got can cant will would they "
            "them he she from about all out up down over more most very much too also only into been "
            "their when because after now like did do does am".split()))
BRAND_TOKENS = {"exness", "etoro", "xm", "plus", "plus500"}

BRANDS = ["Exness", "XM", "eToro", "Plus500"]
FEATURES = ["withdrawal", "deposit", "verification_kyc", "payments", "platform_execution",
            "account_access", "support", "bonus", "scam_fraud", "fees", "other"]
FEATURE_LABEL = {
    "withdrawal": "Withdrawals", "deposit": "Deposits", "verification_kyc": "Verification / KYC",
    "payments": "Payment rails", "platform_execution": "Platform / execution",
    "account_access": "Account access", "support": "Support responsiveness",
    "bonus": "Bonus / promo", "scam_fraud": "Scam / fraud claims", "fees": "Fees / charges",
    "other": "Other / uncategorised"}
REPLY_TYPES = ["none", "substantive", "redirect", "regulator"]


def build():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    months = sorted({r["month"] for r in rows if r["month"]})
    midx = {m: i for i, m in enumerate(months)}
    bidx = {b: i for i, b in enumerate(BRANDS)}

    data_rows = []
    for r in rows:
        feats = r["features"].split("|")
        bits = 0
        for i, f in enumerate(FEATURES):
            if f in feats:
                bits |= (1 << i)
        rh = r["response_hours"]
        rh = float(rh) if rh not in ("", "None") else -1
        rt = r["reply_type"] if r["reply_type"] in REPLY_TYPES else "none"
        data_rows.append([
            bidx[r["brand"]], int(r["rating"]),
            midx.get(r["month"], -1),
            1 if r["is_organic"] == "1" else 0,
            1 if r["replied"] == "1" else 0,
            round(rh, 1),
            REPLY_TYPES.index(rt),
            1 if r["is_template"] == "1" else 0,
            int(r["word_count"]) if r["word_count"] else 0,
            int(r["exclaim"]) if r["exclaim"] else 0,
            bits,
            r["country"] or "",
        ])

    # Complaint phrases are precomputed from the untruncated review text by
    # prepare_dataset.py, so the dashboard does not depend on full text in the CSV.
    if PHRASES.exists():
        bigrams_out = json.load(open(PHRASES, encoding="utf-8"))
    else:
        bigrams = defaultdict(Counter)
        for r in rows:
            if int(r["rating"]) <= 2:
                toks = [w for w in re.findall(r"[a-z']{3,}", (r["title"] + " " + r.get("text", "")).lower())
                        if w not in STOP and w not in BRAND_TOKENS]
                for i in range(len(toks) - 1):
                    bigrams[r["brand"]][toks[i] + " " + toks[i + 1]] += 1
        bigrams_out = {b: bigrams[b].most_common(25) for b in BRANDS if b in bigrams}

    data = {
        "brands": BRANDS,
        "features": FEATURES, "featureLabel": FEATURE_LABEL,
        "replyTypes": REPLY_TYPES, "months": months,
        "rows": data_rows,
        "bigrams": bigrams_out,
        "meta": {"total": len(data_rows),
                 "collected": "2026-07-23",
                 "perBrand": {b: sum(1 for x in data_rows if x[0] == bidx[b]) for b in BRANDS}},
    }
    html = TEMPLATE.replace("/*__DATA__*/", "const DATA = " + json.dumps(data, separators=(",", ":")) + ";")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print("wrote", OUT, "| rows:", len(data_rows), "| months:", len(months), "| size KB:", round(OUT.stat().st_size/1024))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Forex Brokers Social Response Benchmark</title>
<style>
:root{
  --bg:#f6f7f9; --panel:#ffffff; --fg:#1c2430; --muted:#5b6675; --line:#e4e8ee;
  --chip:#eef1f5; --chipOn:#1c2430; --chipOnFg:#fff; --accent:#3363c0;
  --exness:#e8833f; --xm:#d24b4b; --etoro:#4f9d63; --plus500:#4b7fc4;
  --heat0:#eef3fb; --heat1:#123a7a;
}
@media (prefers-color-scheme:dark){
  :root{--bg:#11151b; --panel:#1a202a; --fg:#e6ebf2; --muted:#9aa7b8; --line:#2b3543;
        --chip:#26303d; --chipOn:#e6ebf2; --chipOnFg:#11151b; --accent:#6fa0ff;
        --heat0:#1b2431; --heat1:#7fb0ff;}
}
:root[data-theme="light"]{--bg:#f6f7f9;--panel:#fff;--fg:#1c2430;--muted:#5b6675;--line:#e4e8ee;--chip:#eef1f5;--chipOn:#1c2430;--chipOnFg:#fff;--heat0:#eef3fb;--heat1:#123a7a;}
:root[data-theme="dark"]{--bg:#11151b;--panel:#1a202a;--fg:#e6ebf2;--muted:#9aa7b8;--line:#2b3543;--chip:#26303d;--chipOn:#e6ebf2;--chipOnFg:#11151b;--heat0:#1b2431;--heat1:#7fb0ff;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1180px;margin:0 auto;padding:20px 16px 60px}
h1{font-size:22px;margin:0 0 4px}
.sub{color:var(--muted);font-size:13px;margin:0 0 10px}
.lead{color:var(--fg);font-size:14px;line-height:1.6;margin:0 0 6px;max-width:900px}
.legend{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 4px}
.blab{display:inline-flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:3px 10px}
.dot{width:10px;height:10px;border-radius:50%}
.filters{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin-bottom:16px}
.frow{display:flex;flex-wrap:wrap;gap:14px;align-items:flex-end}
.fg{display:flex;flex-direction:column;gap:5px}
.fg .lab{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{cursor:pointer;user-select:none;font-size:12.5px;padding:4px 11px;border-radius:20px;background:var(--chip);color:var(--fg);border:1px solid transparent}
.chip.on{background:var(--chipOn);color:var(--chipOnFg)}
.chip.brand.on{color:#fff}
select,input[type=range]{font:inherit;color:var(--fg)}
select{background:var(--chip);border:1px solid var(--line);border-radius:8px;padding:5px 8px}
.range{display:flex;align-items:center;gap:6px}
.range input{width:120px}
button.reset{cursor:pointer;background:transparent;color:var(--accent);border:1px solid var(--line);border-radius:8px;padding:6px 12px;font:inherit}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:16px}
.kpi{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 30px 12px 14px}
.kpi .v{font-size:24px;font-weight:650;letter-spacing:-.01em}
.kpi .k{font-size:12px;color:var(--muted);margin-top:2px}
.kpi .info{position:absolute;top:9px;right:10px;width:16px;height:16px;border-radius:50%;background:var(--chip);color:var(--muted);font-size:11px;font-weight:600;display:flex;align-items:center;justify-content:center;cursor:help;user-select:none}
.kpi .info:hover{background:var(--accent);color:#fff}
.kpi .info .tip{visibility:hidden;opacity:0;position:absolute;top:22px;right:-4px;width:210px;background:var(--fg);color:var(--bg);font-size:11.5px;font-weight:400;line-height:1.45;text-align:left;padding:8px 10px;border-radius:8px;z-index:20;box-shadow:0 4px 14px rgba(0,0,0,.25);transition:opacity .12s;pointer-events:none}
.kpi .info:hover .tip{visibility:visible;opacity:1}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}
@media(max-width:820px){.grid{grid-template-columns:1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.card.full{grid-column:1/-1}
.card h3{margin:0 0 2px;font-size:15px}
.card .cap{color:var(--muted);font-size:12px;margin:0 0 10px}
svg{width:100%;height:auto;display:block;color:var(--fg)}
.axis{stroke:var(--line)}
.tick{fill:var(--muted);font-size:10px}
.blab2{fill:var(--fg);font-size:11px}
.val{fill:var(--fg);font-size:10px}
.empty{color:var(--muted);font-size:13px;padding:20px;text-align:center}
.subsel{display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap}
.cards{display:grid;grid-template-columns:1fr 1fr;gap:10px}
@media(max-width:820px){.cards{grid-template-columns:1fr}}
.ex{border:1px solid var(--line);border-radius:10px;padding:10px 12px;font-size:12.5px}
.ex .top{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px}
.ex .stars{color:#e0a92e;font-size:12px}
.ex .tag{font-size:10.5px;color:var(--muted);background:var(--chip);border-radius:6px;padding:2px 7px}
.ex .txt{color:var(--fg)}
.ex .rep{margin-top:6px;padding-top:6px;border-top:1px dashed var(--line);color:var(--muted)}
.ex .rep b{color:var(--fg)}
.note{font-size:11.5px;color:var(--muted);margin-top:6px}
.themeToggle{position:fixed;top:10px;right:12px;z-index:10;cursor:pointer;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:5px 9px;font-size:12px;color:var(--muted)}
</style>
</head>
<body>
<div class="themeToggle" id="themeToggle">◐ theme</div>
<div class="wrap">
  <h1>Forex Brokers Social Response Benchmark</h1>
  <p class="sub" id="subline"></p>
  <p class="lead">This benchmark measures how four retail forex brokers handled public customer
  complaints on Trustpilot. It reports response rate and speed, reply style, complaint topics, review
  provenance, and complaint geography. All figures derive from public reviews and the brokers' own
  public replies, and are recalculated under the filters below.</p>
  <div class="legend" id="legend"></div>

  <div class="filters">
    <div class="frow">
      <div class="fg"><span class="lab">Broker</span><div class="chips" id="fBrand"></div></div>
      <div class="fg"><span class="lab">Rating</span><div class="chips" id="fRating"></div></div>
      <div class="fg"><span class="lab">Complaint topic</span><select id="fFeature"></select></div>
      <div class="fg"><span class="lab">Review source</span><div class="chips" id="fSource"></div></div>
      <div class="fg"><span class="lab">Period</span><div class="range"><input type="range" id="mMin"><span id="mLab"></span><input type="range" id="mMax"></div></div>
      <div class="fg"><span class="lab">&nbsp;</span><button class="reset" id="reset">Reset</button></div>
    </div>
  </div>

  <div class="kpis" id="kpis"></div>

  <div class="grid">
    <div class="card"><h3>Response rate by rating</h3><p class="cap">Share of reviews in each star band that received a public reply from the broker.</p><div id="cA"></div></div>
    <div class="card"><h3>Median time to first reply</h3><p class="cap">Median hours from review publication to the broker's first public reply, among replied reviews.</p><div id="cB"></div></div>
    <div class="card"><h3>Reply style</h3><p class="cap">Distribution of replies across three types: a substantive public answer, a redirect to a private channel, or a deferral to a regulator or ombudsman.</p><div id="cC"></div></div>
    <div class="card"><h3>Review provenance: organic vs invited</h3><p class="cap">Share of reviews arriving organically rather than through a company invitation, split between complaints and praise.</p><div id="cE"></div></div>
    <div class="card full"><h3>Top complaints matrix</h3><p class="cap">Share of each broker's complaints (1-2★ under the current filters) mentioning each topic. A review may carry more than one topic.</p><div id="cD"></div></div>
    <div class="card"><h3>Complaint geography</h3><p class="cap">Countries accounting for the most complaints (1-2★) under the current filters.</p><div id="cF"></div></div>
    <div class="card"><h3>Complaint language intensity</h3><p class="cap">Average review length in words by star band.</p><div id="cH"></div></div>
    <div class="card"><h3>Distinctive complaint phrases</h3><p class="cap">Word pairs that appear disproportionately often in this broker's 1-2★ reviews compared with the other three. Ranked by how much more common each phrase is here; bar length shows the number of reviews containing it.</p><div class="subsel" id="biSel"></div><div id="cI"></div></div>
  </div>
  <p class="note" style="margin-top:16px">Built from public data collected from Trustpilot reviews of the four brokers and their own public replies, with the full method and limitations documented in the project report (REPORT.md). Independent analysis, not affiliated with or endorsed by any company named.</p>
</div>
<script>
/*__DATA__*/
(function(){
"use strict";
var BC={Exness:getCssVar('--exness'),XM:getCssVar('--xm'),eToro:getCssVar('--etoro'),Plus500:getCssVar('--plus500')};
function getCssVar(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()||'#888';}
var R=DATA.rows, B=DATA.brands, F=DATA.features, FL=DATA.featureLabel, M=DATA.months;
// column indexes
var C={brand:0,rating:1,month:2,org:3,rep:4,rh:5,rt:6,tpl:7,wc:8,exc:9,bits:10,ctry:11};
document.getElementById('subline').textContent=DATA.meta.total.toLocaleString()+" public Trustpilot reviews · "+DATA.brands.join(", ");

var DMIN=0;
var state={brands:new Set(B),ratings:new Set([1,2,3,4,5]),feature:'all',source:'all',mMin:DMIN,mMax:M.length-1,biBrand:B[0],exBrand:B[0]};

// ---------- filter UI ----------
var legend=document.getElementById('legend');
B.forEach(function(b){var s=document.createElement('span');s.className='blab';s.innerHTML='<span class="dot" style="background:'+BC[b]+'"></span>'+b;legend.appendChild(s);});

function chip(txt,on,cb,cls){var c=document.createElement('span');c.className='chip'+(cls?' '+cls:'')+(on?' on':'');c.textContent=txt;c.onclick=function(){cb(c);};return c;}
var fBrand=document.getElementById('fBrand');
B.forEach(function(b){var c=chip(b,true,function(el){toggle(state.brands,b,el);if(!state.brands.has(state.biBrand))state.biBrand=[...state.brands][0]||b;if(!state.brands.has(state.exBrand))state.exBrand=[...state.brands][0]||b;render();},'brand');if(true){c.style.setProperty('--x',BC[b]);}fBrand.appendChild(c);
  c.addEventListener('DOMSubtreeModified',function(){});});
// color brand chips when on
function paintBrandChips(){[].forEach.call(fBrand.children,function(c){var b=c.textContent;c.style.background=state.brands.has(b)?BC[b]:'';});}
var fRating=document.getElementById('fRating');
[1,2,3,4,5].forEach(function(r){fRating.appendChild(chip(r+'★',true,function(el){toggle(state.ratings,r,el);render();}));});
var fSource=document.getElementById('fSource');
[['all','All'],['organic','Organic'],['invited','Invited']].forEach(function(p,i){fSource.appendChild(chip(p[1],i===0,function(el){[].forEach.call(fSource.children,function(x){x.classList.remove('on');});el.classList.add('on');state.source=p[0];render();}));});
var fFeature=document.getElementById('fFeature');
var oAll=document.createElement('option');oAll.value='all';oAll.textContent='All topics';fFeature.appendChild(oAll);
F.forEach(function(f){var o=document.createElement('option');o.value=f;o.textContent=FL[f];fFeature.appendChild(o);});
fFeature.onchange=function(){state.feature=fFeature.value;render();};
var mMin=document.getElementById('mMin'),mMax=document.getElementById('mMax'),mLab=document.getElementById('mLab');
mMin.min=mMax.min=0;mMin.max=mMax.max=M.length-1;mMin.value=DMIN;mMax.value=M.length-1;
function mUpd(){state.mMin=Math.min(+mMin.value,+mMax.value);state.mMax=Math.max(+mMin.value,+mMax.value);mLab.textContent=M[state.mMin]+' → '+M[state.mMax];render();}
mMin.oninput=mMax.oninput=mUpd;
document.getElementById('reset').onclick=function(){state.brands=new Set(B);state.ratings=new Set([1,2,3,4,5]);state.feature='all';state.source='all';state.mMin=DMIN;state.mMax=M.length-1;mMin.value=DMIN;mMax.value=M.length-1;fFeature.value='all';[].forEach.call(fBrand.children,function(c){c.classList.add('on');});[].forEach.call(fRating.children,function(c){c.classList.add('on');});[].forEach.call(fSource.children,function(c,i){c.classList.toggle('on',i===0);});render();};
function toggle(set,v,el){if(set.has(v)){if(set.size>1){set.delete(v);el.classList.remove('on');}}else{set.add(v);el.classList.add('on');}}

// ---------- filtering ----------
function pass(row){
  if(!state.brands.has(B[row[C.brand]]))return false;
  if(!state.ratings.has(row[C.rating]))return false;
  if(state.source==='organic'&&row[C.org]!==1)return false;
  if(state.source==='invited'&&row[C.org]!==0)return false;
  if(state.feature!=='all'){var i=F.indexOf(state.feature);if(!(row[C.bits]&(1<<i)))return false;}
  if(row[C.month]<state.mMin||row[C.month]>state.mMax)return false;
  return true;
}
function filtered(){return R.filter(pass);}
function median(a){if(!a.length)return null;a=a.slice().sort(function(x,y){return x-y;});var m=a.length>>1;return a.length%2?a[m]:(a[m-1]+a[m])/2;}

// ---------- KPIs ----------
function renderKPIs(rows){
  var neg=rows.filter(function(r){return r[C.rating]<=2;});
  var pos=rows.filter(function(r){return r[C.rating]>=4;});
  var negRep=neg.filter(function(r){return r[C.rep];}).length;
  var posRep=pos.filter(function(r){return r[C.rep];}).length;
  var hrs=rows.filter(function(r){return r[C.rep]&&r[C.rh]>=0;}).map(function(r){return r[C.rh];});
  var rep=rows.filter(function(r){return r[C.rep];});
  var tpl=rep.filter(function(r){return r[C.tpl];}).length;
  var org=rows.filter(function(r){return r[C.org];}).length;
  var med=median(hrs);
  var k=[
    ['Reviews',rows.length.toLocaleString(),'Number of reviews matching the current filters.'],
    ['Complaint reply rate',neg.length?pct(negRep/neg.length):'–','Share of 1-2 star reviews that received any public reply from the broker.'],
    ['Median reply time',med==null?'–':(med<48?med.toFixed(0)+'h':(med/24).toFixed(1)+'d'),"Median time from a review being posted to the broker's first public reply. Replied reviews only."],
    ['Praise reply rate',pos.length?pct(posRep/pos.length):'–','Share of 4-5 star reviews that received any public reply.'],
    ['Templated replies',rep.length?pct(tpl/rep.length):'–','Share of replies that reuse a near-identical opening, detected by text similarity.'],
    ['Organic reviews',rows.length?pct(org/rows.length):'–','Share of reviews that are organic (unsolicited) rather than company-invited.']
  ];
  var el=document.getElementById('kpis');el.innerHTML='';
  k.forEach(function(x){var d=document.createElement('div');d.className='kpi';
    d.innerHTML='<span class="info" title="'+x[2].replace(/"/g,'&quot;')+'">?<span class="tip">'+x[2]+'</span></span><div class="v">'+x[1]+'</div><div class="k">'+x[0]+'</div>';
    el.appendChild(d);});
}
function pct(x){return (x*100).toFixed(x*100<10?1:0)+'%';}

// ---------- SVG helpers ----------
function el(tag,at,kids){var e=document.createElementNS('http://www.w3.org/2000/svg',tag);for(var k in at)e.setAttribute(k,at[k]);if(kids)kids.forEach(function(c){e.appendChild(c);});return e;}
function svgRoot(w,h){return el('svg',{viewBox:'0 0 '+w+' '+h,preserveAspectRatio:'xMidYMid meet'});}
function txt(x,y,s,cls,anchor,rot){var t=el('text',{x:x,y:y,class:cls||'tick','text-anchor':anchor||'middle'});if(rot)t.setAttribute('transform','rotate('+rot+' '+x+' '+y+')');t.textContent=s;return t;}
function mount(id,svg){var c=document.getElementById(id);c.innerHTML='';if(svg)c.appendChild(svg);}
function emptyMsg(id){var c=document.getElementById(id);c.innerHTML='<div class="empty">No data for this filter.</div>';}

// grouped vertical bars. cats=[labels], series=[{name,color,vals[]}], fmt(v)->str, yMax
function groupedBars(id,cats,series,fmt,yMax,stacked){
  if(!cats.length||!series.length){emptyMsg(id);return;}
  var W=520,H=240,pl=38,pr=10,pt=12,pb=42;var iw=W-pl-pr,ih=H-pt-pb;
  yMax=yMax||Math.max(1,Math.max.apply(null,series.reduce(function(a,s){return a.concat(s.vals);},[])));
  var svg=svgRoot(W,H);
  [0,.25,.5,.75,1].forEach(function(f){var y=pt+ih*(1-f);svg.appendChild(el('line',{x1:pl,y1:y,x2:W-pr,y2:y,class:'axis','stroke-width':f===0?1:.5,opacity:f===0?1:.5}));svg.appendChild(txt(pl-5,y+3,fmt?fmt(yMax*f):Math.round(yMax*f),'tick','end'));});
  var gw=iw/cats.length, bw=stacked?gw*0.55:(gw*0.7)/series.length;
  cats.forEach(function(cat,ci){
    var gx=pl+gw*ci;
    if(stacked){var acc=0;series.forEach(function(s){var v=s.vals[ci]||0;var hh=ih*(v/yMax);var y=pt+ih-acc-hh;svg.appendChild(el('rect',{x:gx+gw*0.22,y:y,width:bw,height:Math.max(0,hh),fill:s.color,rx:1},[title(s.name+': '+(fmt?fmt(v):v))]));acc+=hh;});}
    else{series.forEach(function(s,si){var v=s.vals[ci]||0;var hh=ih*(v/yMax);var x=gx+gw*0.15+si*bw;svg.appendChild(el('rect',{x:x,y:pt+ih-hh,width:bw*0.9,height:Math.max(0,hh),fill:s.color,rx:1},[title(cat+' · '+s.name+': '+(fmt?fmt(v):v))]));});}
    svg.appendChild(txt(gx+gw/2,H-pb+14,cat,'tick'));
  });
  mount(id,svg);
}
function title(s){var t=el('title',{});t.textContent=s;return t;}

// horizontal bars items=[{label,value,color}]
function hbars(id,items,fmt){
  if(!items.length){emptyMsg(id);return;}
  var rowH=items.length<=5?46:22,W=520,pl=140,pr=44,pt=6,pb=6;var H=pt+pb+items.length*rowH;var iw=W-pl-pr;
  var mx=Math.max.apply(null,items.map(function(i){return i.value;}))||1;
  var svg=svgRoot(W,H);
  items.forEach(function(it,i){var y=pt+i*rowH;var w=iw*(it.value/mx);
    svg.appendChild(txt(pl-6,y+rowH/2+3,it.label,'blab2','end'));
    svg.appendChild(el('rect',{x:pl,y:y+3,width:Math.max(1,w),height:rowH-8,fill:it.color||getCssVar('--accent'),rx:2},[title(it.label+': '+(fmt?fmt(it.value):it.value)+(it.note?' reviews, '+it.note:''))]));
    svg.appendChild(txt(pl+w+4,y+rowH/2+3,fmt?fmt(it.value):it.value,'val','start'));
  });
  mount(id,svg);
}

// heatmap rows=[labels], cols=[labels], mat[r][c] 0..1, fmt
function heatmap(id,rowsL,cols,mat,fmt){
  if(!cols.length){emptyMsg(id);return;}
  var cellH=26,pl=150,pt=24,pr=10,pb=6,W=Math.max(520,pl+cols.length*90+pr);var cw=(W-pl-pr)/cols.length;var H=pt+pb+rowsL.length*cellH;
  var svg=svgRoot(W,H);
  cols.forEach(function(c,ci){svg.appendChild(txt(pl+cw*ci+cw/2,pt-8,c,'blab2'));});
  var h0=getCssVar('--heat0'),h1=getCssVar('--heat1');
  rowsL.forEach(function(rl,ri){var y=pt+ri*cellH;
    svg.appendChild(txt(pl-6,y+cellH/2+3,rl,'blab2','end'));
    cols.forEach(function(c,ci){var v=mat[ri][ci];var x=pl+cw*ci;
      svg.appendChild(el('rect',{x:x+1,y:y+1,width:cw-2,height:cellH-2,fill:mix(h0,h1,v),rx:2},[title(rl+' · '+c+': '+fmt(v))]));
      if(v>0.001)svg.appendChild(txt(x+cw/2,y+cellH/2+3,fmt(v),'val',null));
    });
  });
  // recolor value text for contrast
  mount(id,svg);
  [].forEach.call(svg.querySelectorAll('.val'),function(t){t.setAttribute('fill', '#fff');t.style.mixBlendMode='difference';});
}
function mix(a,b,t){function h2r(h){h=h.replace('#','');if(h.length===3)h=h.split('').map(function(c){return c+c;}).join('');return [parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16)];}var A=h2r(a),Bc=h2r(b);var r=A.map(function(v,i){return Math.round(v+(Bc[i]-v)*t);});return 'rgb('+r.join(',')+')';}

// line chart: xs=[labels], series=[{name,color,vals[],axis?}], markers=[idx]
function lineChart(id,xs,series,markers){
  if(xs.length<2){emptyMsg(id);return;}
  var W=1060,H=250,pl=40,pr=46,pt=14,pb=44;var iw=W-pl-pr,ih=H-pt-pb;
  var svg=svgRoot(W,H);
  var maxL=Math.max(1,Math.max.apply(null,series[0].vals));
  var maxR=series[1]?Math.max(1,Math.max.apply(null,series[1].vals)):1;
  [0,.25,.5,.75,1].forEach(function(f){var y=pt+ih*(1-f);svg.appendChild(el('line',{x1:pl,y1:y,x2:W-pr,y2:y,class:'axis','stroke-width':f===0?1:.5,opacity:f===0?1:.4}));svg.appendChild(txt(pl-5,y+3,Math.round(maxL*f),'tick','end'));if(series[1])svg.appendChild(txt(W-pr+5,y+3,Math.round(maxR*f)+'%','tick','start'));});
  var step=iw/(xs.length-1);
  (markers||[]).forEach(function(mi){var x=pl+step*mi;svg.appendChild(el('line',{x1:x,y1:pt,x2:x,y2:pt+ih,stroke:getCssVar('--xm'),'stroke-width':1,'stroke-dasharray':'3 3',opacity:.7}));});
  function draw(s,mx){var d='';s.vals.forEach(function(v,i){var x=pl+step*i,y=pt+ih*(1-v/mx);d+=(i?'L':'M')+x+' '+y;});svg.appendChild(el('path',{d:d,fill:'none',stroke:s.color,'stroke-width':2}));s.vals.forEach(function(v,i){svg.appendChild(el('circle',{cx:pl+step*i,cy:pt+ih*(1-v/mx),r:2.5,fill:s.color},[title(xs[i]+' · '+s.name+': '+v+(s.pct?'%':''))]));});}
  draw(series[0],maxL);if(series[1])draw(series[1],maxR);
  var lblEvery=Math.ceil(xs.length/12);
  xs.forEach(function(x,i){if(i%lblEvery===0)svg.appendChild(txt(pl+step*i,H-pb+14,x,'tick',null,i%(lblEvery*2)?0:0));});
  // legend
  series.forEach(function(s,i){svg.appendChild(el('rect',{x:pl+i*160,y:H-12,width:10,height:10,fill:s.color}));svg.appendChild(txt(pl+i*160+14,H-3,s.name,'tick','start'));});
  mount(id,svg);
}

// ---------- panels ----------
function activeBrands(){return B.filter(function(b){return state.brands.has(b);});}
function brandRows(rows,b){var bi=B.indexOf(b);return rows.filter(function(r){return r[C.brand]===bi;});}

function panelA(rows){ // response rate by rating
  var rts=[1,2,3,4,5].filter(function(r){return state.ratings.has(r);});
  var series=activeBrands().map(function(b){var br=brandRows(rows,b);
    return {name:b,color:BC[b],vals:rts.map(function(rt){var seg=br.filter(function(r){return r[C.rating]===rt;});return seg.length?seg.filter(function(r){return r[C.rep];}).length/seg.length*100:0;})};});
  groupedBars('cA',rts.map(function(r){return r+'★';}),series,function(v){return Math.round(v)+'%';},100);
}
function panelB(rows){ // median reply time by brand
  var items=activeBrands().map(function(b){var hrs=brandRows(rows,b).filter(function(r){return r[C.rep]&&r[C.rh]>=0;}).map(function(r){return r[C.rh];});var m=median(hrs);return {label:b,value:m==null?0:m,color:BC[b]};});
  hbars('cB',items,function(v){return v<48?v.toFixed(0)+'h':(v/24).toFixed(1)+'d';});
}
function panelC(rows){ // reply style stacked 100%
  var cats=activeBrands();
  var types=[['substantive','Substantive',getCssVar('--etoro')],['redirect','Redirect to private',getCssVar('--exness')],['regulator','Regulator deferral',getCssVar('--plus500')]];
  var series=types.map(function(t){return {name:t[1],color:t[2],vals:cats.map(function(b){var rep=brandRows(rows,b).filter(function(r){return r[C.rep];});if(!rep.length)return 0;var c=rep.filter(function(r){return DATA.replyTypes[r[C.rt]]===t[0];}).length;return c/rep.length*100;})};});
  groupedBars('cC',cats,series,function(v){return Math.round(v)+'%';},100,true);
  legendInline('cC',types.map(function(t){return [t[1],t[2]];}));
}
function panelE(rows){ // organic share neg vs pos
  var cats=activeBrands();
  var series=[['Complaints (1-2★)',getCssVar('--xm')],['Praise (4-5★)',getCssVar('--etoro')]].map(function(p,idx){
    return {name:p[0],color:p[1],vals:cats.map(function(b){var br=brandRows(rows,b).filter(function(r){return idx===0?r[C.rating]<=2:r[C.rating]>=4;});return br.length?br.filter(function(r){return r[C.org];}).length/br.length*100:0;})};});
  groupedBars('cE',cats,series,function(v){return Math.round(v)+'%';},100);
  legendInline('cE',series.map(function(s){return [s.name,s.color];}));
}
function panelD(rows){ // complaints matrix
  var cats=activeBrands();
  var neg=rows.filter(function(r){return r[C.rating]<=2;});
  var feats=F.filter(function(f){return f!=='other';});
  var mat=feats.map(function(f){var fi=F.indexOf(f);return cats.map(function(b){var br=brandRows(neg,b);if(!br.length)return 0;return br.filter(function(r){return r[C.bits]&(1<<fi);}).length/br.length;});});
  heatmap('cD',feats.map(function(f){return FL[f];}),cats,mat,function(v){return Math.round(v*100)+'%';});
}
function panelF(rows){ // geography of complaints
  var neg=rows.filter(function(r){return r[C.rating]<=2&&r[C.ctry];});
  var cnt={};neg.forEach(function(r){cnt[r[C.ctry]]=(cnt[r[C.ctry]]||0)+1;});
  var items=Object.keys(cnt).map(function(k){return {label:k,value:cnt[k],color:getCssVar('--accent')};}).sort(function(a,b){return b.value-a.value;}).slice(0,10);
  hbars('cF',items,function(v){return v;});
}
function panelH(rows){ // intensity: avg word count by rating
  var rts=[1,2,3,4,5].filter(function(r){return state.ratings.has(r);});
  var series=activeBrands().map(function(b){var br=brandRows(rows,b);return {name:b,color:BC[b],vals:rts.map(function(rt){var seg=br.filter(function(r){return r[C.rating]===rt;});return seg.length?seg.reduce(function(a,r){return a+r[C.wc];},0)/seg.length:0;})};});
  groupedBars('cH',rts.map(function(r){return r+'★';}),series,function(v){return Math.round(v)+'w';});
}
function legendInline(id,items){var c=document.getElementById(id);var d=document.createElement('div');d.style.cssText='display:flex;flex-wrap:wrap;gap:12px;margin-top:8px;font-size:11.5px;color:var(--muted)';items.forEach(function(it){var s=document.createElement('span');s.innerHTML='<span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:'+it[1]+';margin-right:5px;vertical-align:middle"></span>'+it[0];d.appendChild(s);});c.appendChild(d);}

function panelI(){ // bigrams
  var sel=document.getElementById('biSel');sel.innerHTML='';
  activeBrands().forEach(function(b){sel.appendChild(chip(b,b===state.biBrand,function(){state.biBrand=b;panelI();}));});
  var bg=(DATA.bigrams[state.biBrand]||[]).slice(0,12);
  hbars('cI',bg.map(function(p){return {label:p[0],value:p[1],color:BC[state.biBrand],
    note:(p[2]!=null?p[2]+'x more common than at the other brokers':null)};}),
    function(v){return v;});
}
// ---------- render ----------
function render(){
  paintBrandChips();
  var rows=filtered();
  renderKPIs(rows);
  if(!rows.length){['cA','cB','cC','cD','cE','cF','cH','cI'].forEach(emptyMsg);return;}
  panelA(rows);panelB(rows);panelC(rows);panelE(rows);panelD(rows);panelF(rows);panelH(rows);panelI();
}
// theme toggle
document.getElementById('themeToggle').onclick=function(){var r=document.documentElement;var cur=r.getAttribute('data-theme');var dark=cur?cur==='dark':window.matchMedia('(prefers-color-scheme:dark)').matches;r.setAttribute('data-theme',dark?'light':'dark');BC={Exness:getCssVar('--exness'),XM:getCssVar('--xm'),eToro:getCssVar('--etoro'),Plus500:getCssVar('--plus500')};render();};
mUpd();
})();
</script>
</body>
</html>"""

if __name__ == "__main__":
    build()
