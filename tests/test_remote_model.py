import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from core import Agent, DesktopTools, Store


class RemoteModelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.home=Path(self.temp.name)
        self.store=Store(self.home/'.state')
        self.agent=Agent(self.store,DesktopTools(self.store,home=self.home))

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_remote_url_requires_https_and_rejects_embedded_secrets(self):
        self.assertEqual(Agent.validate_remote_endpoint('https://models.example/ollama/'),'https://models.example/ollama')
        self.assertEqual(Agent.validate_remote_endpoint('http://127.0.0.1:11434'),'http://127.0.0.1:11434')
        for value in ('http://models.example','https://name:secret@models.example',
                      'https://models.example?token=secret','https://models.example/#fragment',''):
            with self.subTest(value=value),self.assertRaises(ValueError):
                Agent.validate_remote_endpoint(value)

    def test_remote_model_list_uses_bearer_token_and_remote_selection(self):
        self.store.set_setting('ai_mode','remote')
        self.store.set_setting('remote_endpoint','https://models.example')
        self.store.set_setting('remote_token','private-token')
        self.store.set_setting('remote_model','qwen3.5:9b')
        with patch.object(Agent,'request_json',side_effect=[
            {'models':[{'name':'qwen3.5:9b','size':7_000_000_000}]},
            {'models':[]},
        ]) as request:
            models=self.agent.models()
        self.assertEqual(models,['qwen3.5:9b'])
        self.assertEqual(self.agent.selected_model(models),'qwen3.5:9b')
        for call in request.call_args_list:
            self.assertEqual(call.kwargs['headers'],{'Authorization':'Bearer private-token'})
        self.assertEqual(request.call_args_list[0].args[0],'https://models.example/api/tags')

    def test_remote_chat_uses_https_and_bearer_token(self):
        self.store.set_setting('ai_mode','remote')
        self.store.set_setting('remote_endpoint','https://models.example/ollama')
        self.store.set_setting('remote_token','private-token')
        self.store.set_setting('remote_model','qwen3.5:9b')
        self.agent.models=lambda:['qwen3.5:9b']
        response=io.BytesIO(b'{"message":{"content":"Hello from remote AI."},"done":true}\n')
        with patch('core.urllib.request.urlopen',return_value=response) as urlopen:
            result=self.agent.infer([{'role':'user','content':'Hello'}],threading.Event())
        request=urlopen.call_args.args[0]
        self.assertEqual(request.full_url,'https://models.example/ollama/api/chat')
        self.assertEqual(request.get_header('Authorization'),'Bearer private-token')
        self.assertEqual(json.loads(request.data)['model'],'qwen3.5:9b')
        self.assertEqual(result['reply'],'Hello from remote AI.')


if __name__=='__main__':
    unittest.main()
