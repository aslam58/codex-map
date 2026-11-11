"""Advisory hook: retain event metadata only. Never blocks or changes a tool."""
import datetime, json, os, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))

def record(data):
    sid=str(data.get('session_id',''))
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',sid): return
    event=data.get('hook_event_name','')
    folder=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'codex-map'/'events'
    folder.mkdir(parents=True,exist_ok=True)
    # Deliberately omit prompts, arguments, command lines, paths and tool output.
    row={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'event':event,'tool':str(data.get('tool_name',''))[:160],'call_id':str(data.get('tool_use_id',data.get('call_id','')))[:160],'agent':str(data.get('agent_id',''))[:160],'model':str(data.get('model',''))[:100]}
    response=data.get('tool_response',{})
    row['error']=isinstance(response,dict) and (response.get('isError') is True or response.get('is_error') is True or response.get('exit_code',0) not in (0,None))
    encoded=(json.dumps(row)+'\n').encode()
    fd=os.open(folder/(sid+'.jsonl'),os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600)
    try: os.write(fd,encoded)
    finally: os.close(fd)
    if event=='SessionStart':
        from start import ensure
        from urllib.parse import urlencode
        url=ensure()+'/?'+urlencode({'session':sid,'pane':'1'})
        print(json.dumps({'hookSpecificOutput':{'hookEventName':'SessionStart','additionalContext':f'Codex Map is enabled by the user. Open {url} beside this chat using open_in_codex with placement right if that tool is available. Reuse an existing map pane. The map is read-only; continue the user task normally. If pane tools are unavailable, provide the URL without claiming it opened.'}}))

if __name__=='__main__':
    try: record(json.load(sys.stdin))
    except Exception: pass  # Visualization faults must not interrupt the agent.
