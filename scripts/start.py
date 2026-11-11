"""Ensure the loopback map service is ready; print a session-bound pane URL."""
import argparse, json, os, subprocess, sys, time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
ROOT = Path(__file__).resolve().parents[1]

def ensure(port=4318):
    url=f'http://127.0.0.1:{port}'
    def ready():
        try:
            with urlopen(url+'/api/health',timeout=.5) as response:
                return json.load(response).get('app')=='codex-map'
        except Exception: return False
    if not ready():
        data=Path(os.environ.get('PLUGIN_DATA',str(Path.home()/'.codex/codex-map')))
        data.mkdir(parents=True,exist_ok=True)
        with (data/'server.log').open('ab') as log:
            proc=subprocess.Popen([sys.executable,str(ROOT/'server.py'),'--port',str(port)],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
        for _ in range(30):
            if ready(): break
            if proc.poll() is not None: raise RuntimeError('Map server could not start; check '+str(data/'server.log'))
            time.sleep(.1)
        else: raise RuntimeError('Map server did not become ready')
    return url

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--session',default='');ap.add_argument('--port',type=int,default=4318);args=ap.parse_args()
    print(ensure(args.port)+'/?'+urlencode({'session':args.session,'pane':'1'}))
