#!/usr/bin/env python3
"""Nexus desktop entry point: GTK/WebKit window and loopback-only authenticated API."""
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
import uuid

from core import Agent, BASE, DATA, DesktopTools, Store
from integrations import Integrations
from voice import Voice


class Application:
    def __init__(self,store=None):
        self.store=store or Store()
        self.integrations=Integrations(self.store)
        self.tools=DesktopTools(self.store,integrations=self.integrations)
        self.agent=Agent(self.store,self.tools)
        self.voice=Voice(self.store.directory)
        self.jobs={}
        self.job_lock=threading.Lock()
        self.busy=None
        self.token=secrets.token_urlsafe(32)
        self.origin=None

    def start_chat(self,text):
        text=str(text).strip()[:6000]
        if not text:
            raise ValueError('Write a message first.')
        with self.job_lock:
            if self.busy and not self.jobs[self.busy]['done']:
                raise ValueError('A request is still running. Stop it or wait for it to finish.')
            job={'id':uuid.uuid4().hex,'stage':'thinking','done':False,'answer':'','actions':[],'cancel':threading.Event()}
            self.jobs[job['id']]=job
            self.busy=job['id']
            # Only retain a small number of completed jobs in RAM.
            for key in list(self.jobs)[:-10]:
                if self.jobs[key]['done']:
                    del self.jobs[key]
        def run():
            answer=self.agent.run(text,job,finish=False)
            if self.store.setting('auto_speak',True) and not job['cancel'].is_set():
                job['stage']='speaking'
                try:
                    self.voice.speak(answer)
                except Exception:
                    job['voice_error']='Speech playback failed; the text response is available.'
            job.update(done=True,stage='idle')
        threading.Thread(target=run,daemon=True).start()
        return {'job':job['id']}

    def stop(self):
        if self.busy:
            self.jobs[self.busy]['cancel'].set()
        self.voice.stop()
        return {'stopping':True}

    def status(self):
        models=self.agent.models()
        selected=self.store.setting('model','auto')
        recommended=self.agent.recommended_model(models)
        resolved=self.agent.selected_model(models)
        return {'models':models,'model':selected,'recommended_model':recommended,'resolved_model':resolved,
                'ready':bool(resolved),
                'voice':self.voice.status(),'auto_speak':self.store.setting('auto_speak',True),
                'animation':self.store.setting('animation',True),'collapsed':self.store.setting('collapsed',False),
                'session':os.environ.get('XDG_SESSION_TYPE','unknown'),
                'gmail':self.store.setting('gmail_email',''),'telegram':self.store.setting('telegram_connected',False),
                'busy':self.busy if self.busy and not self.jobs[self.busy]['done'] else None}


def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        server_version='Nexus'
        def log_message(self,*args):
            pass  # Never log URL session tokens or request bodies.

        def send(self,status,body,content_type='application/json'):
            if isinstance(body,(dict,list)):
                body=json.dumps(body,ensure_ascii=False).encode()
            elif isinstance(body,str):
                body=body.encode()
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):
                pass

        def valid_host(self):
            return self.headers.get('Host')==urllib.parse.urlparse(app.origin).netloc

        def authorized(self):
            origin=self.headers.get('Origin')
            return self.valid_host() and (not origin or origin==app.origin) and hmac.compare_digest(self.headers.get('X-Nexus-Token',''),app.token)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403,{'error':'Invalid host.'})
            parsed=urllib.parse.urlparse(self.path)
            path=parsed.path
            if path=='/':
                token=urllib.parse.parse_qs(parsed.query).get('session',[''])[0]
                if not hmac.compare_digest(token,app.token):
                    return self.send(403,{'error':'Open Nexus using Launch Nexus.sh.'})
                html=(BASE/'static/index.html').read_text().replace('__NEXUS_TOKEN__',app.token)
                return self.send(200,html,'text/html; charset=utf-8')
            static={'/style.css':'style.css','/app.js':'app.js','/icons.js':'icons.js','/icon.svg':'icon.svg'}
            if path in static:
                file=BASE/'static'/static[path]
                return self.send(200,file.read_bytes(),mimetypes.guess_type(str(file))[0] or 'application/octet-stream')
            if not self.authorized():
                return self.send(403,{'error':'Unauthorized local request.'})
            try:
                if path=='/api/status':
                    return self.send(200,app.status())
                if path=='/api/history':
                    return self.send(200,app.store.history())
                if path=='/api/memories':
                    return self.send(200,app.store.memories())
                if path=='/api/activity':
                    return self.send(200,app.store.activity())
                if path.startswith('/api/jobs/'):
                    job=app.jobs.get(path.rsplit('/',1)[-1])
                    if not job:
                        return self.send(404,{'error':'Request not found.'})
                    return self.send(200,{k:v for k,v in job.items() if k!='cancel'})
                return self.send(404,{'error':'Not found.'})
            except Exception as error:
                return self.send(400,{'error':str(error)[:600]})

        def do_POST(self):
            if not self.authorized():
                return self.send(403,{'error':'Unauthorized local request.'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=100000:
                    raise ValueError('Invalid request size.')
                if not self.headers.get('Content-Type','').startswith('application/json'):
                    raise ValueError('Expected a JSON request.')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):
                    raise ValueError('Expected an object.')
                path=urllib.parse.urlparse(self.path).path
                if path=='/api/chat':
                    result=app.start_chat(body.get('text',''))
                elif path=='/api/stop':
                    result=app.stop()
                elif path=='/api/new-chat':
                    if app.busy and not app.jobs[app.busy]['done']:
                        raise ValueError('Wait for the current request to stop before starting a new chat.')
                    app.store.clear_history();app.tools.last_file=None;result={'cleared':True}
                elif path=='/api/memory':
                    result={'id':app.store.memory(body.get('text',''))}
                elif path=='/api/forget':
                    app.store.forget(str(body.get('id','')));result={'removed':True}
                elif path=='/api/settings':
                    for key in ['animation','collapsed','auto_speak']:
                        if key in body and isinstance(body[key],bool):
                            app.store.set_setting(key,body[key])
                    if 'model' in body:
                        if body['model']!='auto' and body['model'] not in app.agent.models():
                            raise ValueError('Choose an installed local model.')
                        app.store.set_setting('model',body['model'])
                    result={'saved':True}
                elif path=='/api/voice/listen':
                    result=app.voice.listen()
                elif path=='/api/voice/test':
                    app.voice.speak('Good evening. I am Nexus, your personal assistant. How may I help?')
                    result={'spoken':True}
                elif path=='/api/connect/gmail':
                    result=app.integrations.connect_gmail(str(body.get('email','')),str(body.get('password','')))
                elif path=='/api/connect/telegram':
                    result=app.integrations.telegram_begin(body.get('api_id',''),body.get('api_hash',''),body.get('phone',''))
                elif path=='/api/connect/telegram/verify':
                    result=app.integrations.telegram_verify(body.get('code',''),body.get('password',''))
                elif path=='/api/disconnect':
                    result=app.integrations.disconnect(body.get('service',''))
                else:
                    return self.send(404,{'error':'Not found.'})
                return self.send(200,result)
            except Exception as error:
                return self.send(400,{'error':str(error)[:600]})
    return Handler


def run_window(url,app,server):
    # Shared-memory rendering avoids Intel/Wayland DMABuf failures on this machine.
    os.environ.setdefault('WEBKIT_DISABLE_DMABUF_RENDERER','1')
    import gi
    gi.require_version('Gtk','3.0')
    gi.require_version('WebKit2','4.1')
    from gi.repository import Gtk, WebKit2
    window=Gtk.Window(title='Nexus')
    window.set_default_size(1120,820)
    window.set_icon_from_file(str(BASE/'static/icon.svg'))
    web=WebKit2.WebView.new_with_context(WebKit2.WebContext.new_ephemeral())
    settings=web.get_settings()
    settings.set_enable_developer_extras(False)
    settings.set_hardware_acceleration_policy(WebKit2.HardwareAccelerationPolicy.NEVER)
    def navigation(view,decision,kind):
        if kind==WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            uri=decision.get_navigation_action().get_request().get_uri()
            if not uri.startswith(app.origin+'/'):
                decision.ignore()
                if uri.startswith(('https://','http://')):
                    app.tools.open_url(uri)
                return True
        return False
    web.connect('decide-policy',navigation)
    web.connect('load-changed',lambda view,event:print('Nexus interface loaded.',flush=True) if event==WebKit2.LoadEvent.FINISHED else None)
    web.connect('context-menu',lambda *args:True)
    window.add(web)
    window.connect('destroy',lambda *args:Gtk.main_quit())
    web.load_uri(url)
    window.show_all()
    Gtk.main()
    app.stop()
    server.shutdown()


def start_local_engine(directory):
    """Reuse a running Ollama service; start an installed local engine if needed."""
    def available():
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=1):
                return True
        except Exception:
            return False
    if available():
        return None
    executable=shutil.which('ollama')
    if not executable:
        candidate=Path.home()/'.local/bin/ollama'
        executable=str(candidate) if candidate.is_file() else None
    if not executable:
        return None
    environment=dict(os.environ,OLLAMA_HOST='127.0.0.1:11434')
    with (directory/'ollama.log').open('a') as log:
        process=subprocess.Popen([executable,'serve'],stdout=log,stderr=log,env=environment)
    for _ in range(30):
        if available() or process.poll() is not None:
            break
        time.sleep(.2)
    return process


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--headless',action='store_true',help='Serve the authenticated UI without opening a native window.')
    parser.add_argument('--port',type=int,default=0)
    parser.add_argument('--write-session',help='Write the local session URL to a private file for testing.')
    args=parser.parse_args()
    os.umask(0o077)
    app=Application()
    engine=start_local_engine(app.store.directory)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(app))
    app.origin=f'http://127.0.0.1:{server.server_port}'
    url=app.origin+'/?session='+app.token
    if args.write_session:
        session_file=Path(args.write_session)
        session_file.write_text(json.dumps({'url':url,'token':app.token,'origin':app.origin}))
        session_file.chmod(0o600)
    try:
        if args.headless:
            print('Nexus local server ready.',flush=True)
            server.serve_forever()
        else:
            threading.Thread(target=server.serve_forever,daemon=True).start()
            run_window(url,app,server)
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
        server.server_close()
        if engine and engine.poll() is None:
            engine.terminate()


if __name__=='__main__':
    main()
