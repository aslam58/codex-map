"""Read-only Codex session visualizer. No dependencies or external requests."""
import argparse, json, os, re, time
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
ROOT = Path(__file__).parent
SESSIONS = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))) / 'sessions'
CACHE = {}
HOOKS = SESSIONS.parent / 'codex-map' / 'events'

def classify(name):
    n = name.lower()
    for station, words in [('Agents', ['agent','spawn','collaboration','thread']), ('Browser',['browser','cua','screenshot']), ('Memory',['memory']), ('Skills',['skill']), ('Files',['file','patch','read','write','search_code']), ('Network',['web','fetch','github','search','mcp__']), ('Shell',['exec','stdin','shell','terminal','bash'])]:
        if any(w in n for w in words): return station
    return 'Tools'

def files():
    return sorted(SESSIONS.glob('*/*/*/*.jsonl'), key=lambda p:p.stat().st_mtime, reverse=True)[:100]

def parse(path):
    stamp = (path.stat().st_mtime_ns, path.stat().st_size)
    if path in CACHE and CACHE[path][0] == stamp: return CACHE[path][1]
    events=[]; calls={}; meta={}; model='Codex'; context=None; state='idle'
    with path.open() as f:
        for i,line in enumerate(f):
            try: r=json.loads(line)
            except (ValueError, UnicodeError): continue
            p=r.get('payload',{}); typ=p.get('type'); ts=r.get('timestamp','')
            def add(station,label,status='done', key=None):
                e=dict(id=key or str(i),station=station,label=label,status=status,time=ts)
                events.append(e); return e
            if r.get('type')=='session_meta': meta=p
            if r.get('type')=='turn_context': model=p.get('model',model)
            if typ in ('task_started','turn_started'): state='working'
            if typ in ('task_complete','task_completed','turn_aborted'): state='idle'; add('You','Answer ready' if typ!='turn_aborted' else 'Turn interrupted')
            if typ=='token_count':
                info=p.get('info') or {}; usage=info.get('last_token_usage') or {}; window=info.get('model_context_window')
                if window: context=round(100*usage.get('total_tokens',0)/window,1)
            if r.get('type')=='response_item':
                if typ in ('function_call','custom_tool_call'):
                    name=p.get('name','tool'); name=(p.get('namespace','')+'.'+name).lstrip('.'); cid=p.get('call_id',p.get('id',str(i)))
                    calls[cid]=add(classify(name),name,'running',cid)
                elif typ in ('function_call_output','custom_tool_call_output'):
                    e=calls.get(p.get('call_id'))
                    if e:
                        output=str(p.get('output',''))
                        e['status']='error' if re.search(r'"isError"\s*:\s*true|Process exited with code [1-9]|"exit_code"\s*:\s*[1-9]',output) else 'done'
                elif typ=='message' and p.get('role')=='user': add('You','Message received')
                elif typ=='reasoning': add('Model','Model step')
                elif typ=='message' and p.get('role')=='assistant' and p.get('phase')=='final': state='idle'
    result=dict(id=meta.get('id',path.stem),name=Path(meta.get('cwd','Unknown workspace')).name,cwd=meta.get('cwd',''),model=model,context=context,state=state,events=events[-250:],updated=stamp[0]/1e9,source='Local session log',agent=meta.get('source'))
    CACHE[path]=(stamp,result)
    return result

def with_hooks(session):
    session = dict(session)
    sid = session['id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',sid): return session
    path=HOOKS/(sid+'.jsonl')
    if not path.exists(): return session
    events=[]; calls={}; agents={}; model_calls=[]
    try:
        with path.open() as hook_file:
            for i,line in enumerate(hook_file):
                try: row=json.loads(line)
                except ValueError: continue
                kind=row.get('event'); tool=row.get('tool') or 'Tool'; key=row.get('call_id') or tool
                e=dict(id='hook-'+str(i),station=classify(tool),label=tool,status='done',time=row['time'])
                if kind=='PreToolUse':
                    e['status']='running'; calls.setdefault(key,[]).append(e); events.append(e)
                elif kind=='PostToolUse':
                    pending=calls.get(key,[])
                    target=pending.pop(0) if pending else e
                    target['status']='error' if row.get('error') else 'done'
                    target['completed']=row['time']
                    if target is e: events.append(e)
                elif kind=='SubagentStart':
                    e.update(station='Agents',label='Subagent '+(row.get('agent') or 'started'),status='running')
                    agents[row.get('agent') or str(i)]=e;events.append(e)
                elif kind=='SubagentStop':
                    agent=agents.get(row.get('agent'))
                    if agent: agent.update(status='done',completed=row['time'])
                elif kind=='PreModelRequest':
                    e.update(station='Model',label='Model request',status='running');model_calls.append(e);events.append(e)
                elif kind=='PostModelRequest':
                    if model_calls: model_calls.pop(0).update(status='done',completed=row['time'])
                elif kind in ('Stop','Interrupt','SessionEnd'):
                    session['state']='idle'
                    for old in events:
                        if old['status']=='running':old['status']='interrupted' if kind=='Interrupt' else 'unknown'
                    e.update(station='You',label='Answer ready' if kind=='Stop' else kind);events.append(e)
                elif kind in ('SessionStart','UserPromptSubmit'):
                    session['state']='working' if kind=='UserPromptSubmit' else session['state']
                    e.update(station='You',label='Message received' if kind=='UserPromptSubmit' else 'Session connected');events.append(e)
                elif kind in ('PreCompact','PostCompact'):
                    e.update(station='Model',label='Context compaction');events.append(e)
                if row.get('model'):session['model']=row['model']
    except OSError:return session
    if events:
        # Hooks are authoritative from the time they first become available.
        first=events[0]['time']
        events=[e for e in session['events'] if e['time']<first]+events
        session.update(events=events[-250:],source='Lifecycle hooks + local session log',agents=[e for e in agents.values() if e['status']=='running'])
    return session

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*a,**kw): super().__init__(*a,directory=str(ROOT/'public'),**kw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=='/api/health':
            body=b'{"app":"codex-map","version":"0.2.0"}'
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body); return
        if u.path=='/api/state':
            paths=files(); wanted=parse_qs(u.query).get('session',[''])[0]
            summaries=[]; selected=None
            for path in paths:
                # Metadata is cached; only the selected log is fully parsed.
                try:
                    with path.open() as f: meta=json.loads(f.readline()).get('payload',{})
                    sid=meta.get('id',path.stem)
                    summaries.append(dict(id=sid,name=Path(meta.get('cwd','Unknown')).name,updated=path.stat().st_mtime))
                    if sid==wanted or (not wanted and selected is None): selected=path
                except (OSError,ValueError): continue
            body=json.dumps(dict(sessions=summaries,session=with_hooks(parse(selected)) if selected else None)).encode()
            self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
        else: super().do_GET()
    def log_message(self,*a): pass

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--port',type=int,default=4318); args=ap.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Codex Map → http://127.0.0.1:{args.port}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()
