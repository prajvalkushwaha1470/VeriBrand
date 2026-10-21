from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import sqlite3, json, re, os

ROOT = Path(__file__).parent
DB = ROOT / 'veribrand.db'
app = FastAPI(title='VeriBrand API', version='1.0.0', description='Brand governance MVP')
app.add_middleware(CORSMiddleware, allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS facts(id INTEGER PRIMARY KEY, name TEXT, value TEXT, source TEXT, updated TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY, rule TEXT, kind TEXT, severity TEXT, enabled INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, title TEXT, draft TEXT, findings TEXT, status TEXT DEFAULT 'In review', created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS decisions(id INTEGER PRIMARY KEY, review_id INTEGER, finding_id TEXT, decision TEXT, note TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);''')
        if c.execute('SELECT COUNT(*) FROM facts').fetchone()[0] == 0:
            c.executemany('INSERT INTO facts(name,value,source) VALUES(?,?,?)', [
                ('Starter plan price','Rs 399','Lumio Pricing Sheet v3'),('Brand tone','Calm, helpful, confident; avoid hype','Lumio Brand Voice Guide §2.1'),('Approved product name','Lumio budgeting app','Lumio Terminology List v1')])
        if c.execute('SELECT COUNT(*) FROM rules').fetchone()[0] == 0:
            c.executemany('INSERT INTO rules(rule,kind,severity) VALUES(?,?,?)', [
                ('Avoid unsupported superlatives such as #1, number one, best, leading','unsupported_claim','High'),
                ('Avoid stacked exclamation marks','tone','Low'),
                ('Use the approved Starter price: Rs 399','price','High'),
                ('Use calm, helpful language; avoid hype','tone','Medium')])
init()

class FactIn(BaseModel): name:str; value:str; source:str='User supplied brand kit'
class ReviewIn(BaseModel): title:str='Untitled draft'; draft:str
class DecisionIn(BaseModel): finding_id:str; decision:str; note:str=''

@app.get('/api/health')
def health(): return {'ok':True,'service':'VeriBrand','database':'SQLite'}
@app.get('/api/facts')
def facts():
    with conn() as c: return [dict(r) for r in c.execute('SELECT * FROM facts ORDER BY id DESC')]
@app.post('/api/facts')
def add_fact(f:FactIn):
    with conn() as c:
        cur=c.execute('INSERT INTO facts(name,value,source) VALUES(?,?,?)',(f.name,f.value,f.source)); return dict(c.execute('SELECT * FROM facts WHERE id=?',(cur.lastrowid,)).fetchone())
@app.delete('/api/facts/{fid}')
def del_fact(fid:int):
    with conn() as c: c.execute('DELETE FROM facts WHERE id=?',(fid,)); return {'ok':True}
@app.get('/api/rules')
def rules():
    with conn() as c: return [dict(r) for r in c.execute('SELECT * FROM rules ORDER BY id')]

def analyze(draft):
    low=draft.lower(); findings=[]
    def add(fid,issue,severity,reason,source,confidence,fix,matched=''):
        findings.append({'id':fid,'issue':issue,'severity':severity,'reason':reason,'source':source,'confidence':confidence,'fix':fix,'matched':matched,'decision':'Pending'})
    if re.search(r'\b(india\s*[’\']?s\s*)?#\s*1\b|\b(number one|best|leading|no\. 1)\b',low):
        m=re.search(r'\b(india\s*[’\']?s\s*)?#\s*1\b|\b(number one|best|leading|no\. 1)\b',draft,re.I)
        add('claim-1','Potentially unsupported superlative','High','A ranking claim needs verifiable evidence. No evidence source was attached to this draft.','Lumio Brand Governance Rule: unsupported claims','High','Remove the ranking or attach a verifiable, approved source.',m.group(0) if m else '')
    if '!!' in draft or '!!!' in draft:
        add('tone-1','Stacked exclamation marks','Low','The brand voice guide calls for calm, helpful language and discourages hype.','Lumio Brand Voice Guide §2.1','High','Replace stacked exclamation marks with a calm call to action.')
    price=re.search(r'(?:rs\.?\s*|₹\s*)(\d+(?:,\d{3})*)',draft,re.I)
    with conn() as c: facts=[dict(r) for r in c.execute('SELECT * FROM facts')]
    approved=next((f for f in facts if 'price' in f['name'].lower() or 'starter' in f['name'].lower()),None)
    if price and approved:
        seen=price.group(1).replace(',',''); expected=re.search(r'\d[\d,]*',approved['value'])
        if expected and seen != expected.group(0).replace(',',''):
            add('fact-price','Price differs from approved fact','High',f"Draft mentions Rs {price.group(1)} but the approved fact is {approved['value']}.",approved['source'],'High',f"Use the approved price: {approved['value']}.",price.group(0))
    if re.search(r'\b(guaranteed|instant riches|miracle|unbelievable)\b',low):
        m=re.search(r'\b(guaranteed|instant riches|miracle|unbelievable)\b',draft,re.I)
        add('tone-2','Potentially hype-heavy wording','Medium','This wording may conflict with the calm and confident brand voice. Human review is recommended.','Lumio Brand Voice Guide §2.1','Medium','Use specific, factual language instead.',m.group(0))
    if not findings:
        add('review-note','No configured rule matched','Info','No issue was found by the current deterministic checks. This is not a guarantee that the draft is compliant.','Configured VeriBrand rules','Medium','Ask a reviewer to verify any claims and confirm brand fit.')
    return findings

@app.post('/api/reviews')
def create_review(r:ReviewIn):
    findings=analyze(r.draft)
    with conn() as c:
        cur=c.execute('INSERT INTO reviews(title,draft,findings) VALUES(?,?,?)',(r.title,r.draft,json.dumps(findings)))
        return dict(c.execute('SELECT * FROM reviews WHERE id=?',(cur.lastrowid,)).fetchone())
@app.get('/api/reviews')
def reviews():
    with conn() as c:
        out=[]
        for r in c.execute('SELECT * FROM reviews ORDER BY id DESC'):
            d=dict(r); d['findings']=json.loads(d['findings']); out.append(d)
        return out
@app.get('/api/reviews/{rid}')
def review(rid:int):
    with conn() as c:
        r=c.execute('SELECT * FROM reviews WHERE id=?',(rid,)).fetchone()
        if not r: raise HTTPException(404,'Review not found')
        d=dict(r); d['findings']=json.loads(d['findings']); return d
@app.post('/api/reviews/{rid}/decisions')
def decision(rid:int, d:DecisionIn):
    if d.decision not in ('Accept','Edit','Dismiss','Approve','Request changes'): raise HTTPException(400,'Invalid decision')
    with conn() as c:
        r=c.execute('SELECT * FROM reviews WHERE id=?',(rid,)).fetchone()
        if not r: raise HTTPException(404,'Review not found')
        findings=json.loads(r['findings']); found=False
        for f in findings:
            if f['id']==d.finding_id: f['decision']=d.decision; found=True
        if not found and d.finding_id!='workflow': raise HTTPException(404,'Finding not found')
        status = d.decision if d.finding_id=='workflow' and d.decision in ('Approve','Request changes') else r['status']
        c.execute('UPDATE reviews SET findings=?,status=? WHERE id=?',(json.dumps(findings),status,rid))
        c.execute('INSERT INTO decisions(review_id,finding_id,decision,note) VALUES(?,?,?,?)',(rid,d.finding_id,d.decision,d.note))
        updated=dict(c.execute('SELECT * FROM reviews WHERE id=?',(rid,)).fetchone()); updated['findings']=json.loads(updated['findings']); return updated
@app.get('/api/metrics')
def metrics():
    with conn() as c:
        rs=[dict(r) for r in c.execute('SELECT * FROM reviews')]
    return {'reviews':len(rs),'approved':sum(r['status']=='Approve' for r in rs),'in_review':sum(r['status']=='In review' for r in rs),'findings':sum(len(json.loads(r['findings'])) for r in rs)}

app.mount('/', StaticFiles(directory=ROOT/'frontend', html=True), name='frontend')
