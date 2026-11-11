import importlib.util, json, tempfile, unittest
from pathlib import Path
import server
spec=importlib.util.spec_from_file_location('observe',Path(__file__).parents[1]/'hooks/observe.py')
observe=importlib.util.module_from_spec(spec);spec.loader.exec_module(observe)

class EventsTest(unittest.TestCase):
    def test_hook_lifecycle_and_privacy(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            old=os.environ.get('CODEX_HOME'); original=server.HOOKS
            os.environ['CODEX_HOME']=folder;server.HOOKS=Path(folder)/'codex-map/events'
            try:
                for event in ['PreToolUse','PostToolUse']:
                    observe.record(dict(session_id='test-session',hook_event_name=event,tool_name='Bash',tool_use_id='call-1',tool_input={'command':'SECRET'},tool_response={'exit_code':1}))
                raw=(server.HOOKS/'test-session.jsonl').read_text()
                self.assertNotIn('SECRET',raw)
                result=server.with_hooks(dict(id='test-session',events=[],state='working'))
                self.assertEqual(len(result['events']),1)
                self.assertEqual(result['events'][0]['status'],'error')
                self.assertEqual(result['events'][0]['station'],'Shell')
            finally:
                server.HOOKS=original
                if old is None:os.environ.pop('CODEX_HOME',None)
                else:os.environ['CODEX_HOME']=old
    def test_partial_log_and_call_pairing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.jsonl'
            rows=[{'type':'session_meta','payload':{'id':'fixture','cwd':'/work/project'}},{'type':'response_item','timestamp':'2026-11-11T00:00:00Z','payload':{'type':'function_call','name':'apply_patch','call_id':'a'}},{'type':'response_item','payload':{'type':'function_call_output','call_id':'a','output':'ok'}}]
            path.write_text(''.join(json.dumps(r)+'\n' for r in rows)+'{"partial":')
            data=server.parse(path)
            self.assertEqual(data['events'][0]['status'],'done')
            self.assertEqual(data['events'][0]['station'],'Files')
    def test_stop_resolves_pending(self):
        with tempfile.TemporaryDirectory() as folder:
            original=server.HOOKS; server.HOOKS=Path(folder)
            try:
                rows=[dict(event='PreToolUse',tool='Bash',call_id='a',time='2026-11-11T00:00:00Z'),dict(event='Interrupt',time='2026-11-11T00:00:01Z')]
                (Path(folder)/'fixture.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                result=server.with_hooks(dict(id='fixture',events=[],state='working'))
                self.assertEqual(result['state'],'idle');self.assertEqual(result['events'][0]['status'],'interrupted')
            finally:server.HOOKS=original
if __name__=='__main__':unittest.main()
