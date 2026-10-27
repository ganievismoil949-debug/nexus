"""Regression checks for fast routing and the local model/tool protocol."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from core import Agent, DesktopTools, Store


class UnderstandingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.home=Path(self.temp.name)
        (self.home/'Documents').mkdir()
        (self.home/'Downloads').mkdir()
        self.store=Store(self.home/'.state')
        self.tools=DesktopTools(self.store,home=self.home)
        self.tools.apps={'Calculator':{'path':'/test/calculator.desktop','exec':'calculator'}}
        self.agent=Agent(self.store,self.tools)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def job(self):
        return {'cancel':threading.Event(),'actions':[],'stage':'thinking','done':False}

    def test_polite_fast_command_preserves_literal_content(self):
        with patch.object(self.agent,'infer',side_effect=AssertionError('No model needed')):
            job=self.job()
            self.agent.run('Could you please create a file named greeting.txt in documents containing exactly "Hello, FRIEND!"',job)
        self.assertEqual((self.home/'Documents/greeting.txt').read_text(),'Hello, FRIEND!')
        self.assertEqual(job['engine'],'direct')
        self.assertGreaterEqual(job['elapsed_ms'],0)

    def test_common_case_and_politeness_variants(self):
        for text in ['show my downloads folder','Can you show my DOWNLOADS folder?','Please, list files in Downloads.']:
            with self.subTest(text=text):
                self.assertEqual(Agent.direct_plan(text),{'tool':'list_files','args':{'path':'Downloads'}})
        self.assertEqual(Agent.direct_plan('What do you remember?'),{'tool':'recall','args':{}})
        self.assertEqual(self.tools.path('documents/note.txt'),self.home/'Documents/note.txt')

    def test_natural_folder_and_read_requests_route_without_model(self):
        plan=Agent.direct_plan('I need a fresh folder for my project called Atlas, inside Documents.')
        self.assertEqual(plan,{'tool':'create_folder','args':{'path':'Documents/Atlas'}})
        read=Agent.direct_plan('Can you take a look at text in notes.txt for me?')
        self.assertEqual(read,{'tool':'read_file','args':{'path':'notes.txt'}})
        self.assertIn('create_folder',Agent.authorized_actions('I need a fresh folder for my project called Atlas, inside Documents.'))
        self.assertIn('read_file',Agent.authorized_actions('Can you take a look at text in notes.txt for me?'))
        self.assertNotIn('create_folder',Agent.authorized_actions("I don't need a fresh folder for my project called Atlas."))

    def test_negation_information_and_quotes_are_not_commands(self):
        for text in ["Don't delete note.txt",'Do not delete note.txt','How do I delete note.txt?',
                     'Should I delete note.txt?', 'The email says "delete note.txt".',
                     'Explain the command: delete note.txt', '"delete note.txt"',
                     'Can you explain how to delete note.txt?', 'Never open YouTube']:
            with self.subTest(text=text):
                self.assertIsNone(Agent.direct_plan(text))
                self.assertNotIn('trash_file',Agent.authorized_actions(text))
                self.assertNotIn('open_url',Agent.authorized_actions(text))

    def test_model_cannot_execute_negated_action(self):
        self.tools.create_file('note.txt','keep')
        self.agent.infer=lambda *args:{'tool':'trash_file','args':{'path':'note.txt'}}
        with patch('core.subprocess.run') as launched:
            job=self.job()
            self.agent.run('Do not delete note.txt; tell me what it contains.',job)
        launched.assert_not_called()
        self.assertTrue((self.home/'Documents/note.txt').exists())
        self.assertIn('not authorized',job['answer'])

    def test_multi_command_never_becomes_file_content_or_folder_name(self):
        for text in ['Create a folder named Notes and open YouTube',
                     'Create a file named note.txt containing Hello then open YouTube',
                     'Remember I like tea and then delete old.txt',
                     'Save Hello in a file note.txt and open Gmail']:
            with self.subTest(text=text):
                self.assertTrue(Agent.compound_command(text))
                self.assertIsNone(Agent.direct_plan(text))
        self.assertIsNotNone(Agent.direct_plan('Create a file named note.txt containing "Hello and open YouTube"'))

    def test_native_multiple_calls_all_execute_and_use_tool_roles(self):
        seen=[]
        def infer(messages,cancel):
            seen.append(json.loads(json.dumps(messages)))
            if len(seen)==1:
                return {'reply':'','tool_calls':[
                    {'function':{'name':'create_file','arguments':{'path':'first.txt','content':'one'}}},
                    {'function':{'name':'create_file','arguments':{'path':'second.txt','content':'two'}}}], 'model':'local-test'}
            return {'tool':'none','reply':'Created both files.'}
        self.agent.infer=infer
        job=self.job()
        self.agent.run('Create first.txt and then create second.txt',job)
        self.assertEqual((self.home/'Documents/first.txt').read_text(),'one')
        self.assertEqual((self.home/'Documents/second.txt').read_text(),'two')
        self.assertEqual(len(job['actions']),2)
        self.assertEqual(job['model'],'local-test')
        tail=seen[1][-3:]
        self.assertEqual([m['role'] for m in tail],['assistant','tool','tool'])
        self.assertEqual(len(tail[0]['tool_calls']),2)
        self.assertEqual(tail[1]['tool_name'],'create_file')
        self.assertNotIn('TOOL RESULT',tail[1]['content'])

    def test_repeat_does_not_lose_completed_action_or_reexecute(self):
        calls=[{'function':{'name':'create_folder','arguments':{'path':'One'}}},
               {'function':{'name':'create_folder','arguments':{'path':'One'}}},
               {'function':{'name':'create_folder','arguments':{'path':'Two'}}}]
        self.agent.infer=lambda *args:{'tool_calls':calls}
        job=self.job(); self.agent.run('Create One and then create Two',job)
        self.assertEqual(len(job['actions']),1)
        self.assertIn('unfinished',job['answer'])
        self.assertFalse((self.home/'Documents/Two').exists())

    def test_stop_between_calls_prevents_later_action(self):
        job=self.job()
        original=self.tools.execute
        def execute(name,args):
            output=original(name,args)
            job['cancel'].set()
            return output
        self.tools.execute=execute
        self.agent.infer=lambda *args:{'tool_calls':[
            {'function':{'name':'create_folder','arguments':{'path':'First'}}},
            {'function':{'name':'create_folder','arguments':{'path':'Never'}}}]}
        self.agent.run('Create First then create Never',job)
        self.assertTrue((self.home/'Documents/First').exists())
        self.assertFalse((self.home/'Documents/Never').exists())
        self.assertIn('Stopped',job['answer'])

    def test_stream_preserves_calls_from_multiple_chunks(self):
        chunks=[{'message':{'tool_calls':[{'function':{'name':'read_file','arguments':{'path':'a.txt'}}}]}},
                {'message':{'tool_calls':[{'function':{'name':'read_file','arguments':{'path':'b.txt'}}}]}}, {'done':True}]
        response=io.BytesIO(b'\n'.join(json.dumps(c).encode() for c in chunks))
        with patch.object(self.agent,'selected_model',return_value='local-test'),patch('core.urllib.request.urlopen',return_value=response) as request:
            result=self.agent.infer([{'role':'user','content':'Read a.txt and read b.txt'}],threading.Event())
        self.assertEqual([c['function']['arguments']['path'] for c in result['tool_calls']],['a.txt','b.txt'])
        payload=json.loads(request.call_args.args[0].data)
        names={t['function']['name'] for t in payload['tools']}
        self.assertIn('read_file',names)
        self.assertNotIn('trash_file',names)
        self.assertNotIn('create_file',names)

    def test_invalid_native_arguments_fail_before_any_action(self):
        response=io.BytesIO(json.dumps({'message':{'tool_calls':[{'function':{'name':'create_file','arguments':'{bad'}}]}}).encode())
        with patch.object(self.agent,'selected_model',return_value='local-test'),patch('core.urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(ValueError,'incomplete tool arguments'):
                self.agent.infer([{'role':'user','content':'Create a file'}],threading.Event())

    def test_missing_model_returns_helpful_local_answer_without_network_call(self):
        with patch.object(self.agent,'selected_model',return_value=''),patch('core.urllib.request.urlopen',side_effect=AssertionError('No request without a model')):
            result=self.agent.infer([{'role':'user','content':'What is a good idea?'}],threading.Event())
        self.assertEqual(result['tool'],'none')
        self.assertIn('No installed model fits the available memory',result['reply'])

    def test_current_request_is_not_truncated_and_prompt_is_not_duplicated(self):
        for n in range(5):
            self.store.add_message('user','Old message '+str(n)+'x'*2000)
            self.store.add_message('assistant','Old response '+str(n)+'y'*2000)
        text='Tell me about '+('abc '*1100)
        captured=[]
        def infer(messages,cancel):
            captured.extend(messages)
            return {'tool':'none','reply':'Here is an answer.'}
        self.agent.infer=infer
        self.agent.run(text,self.job())
        self.assertEqual(captured[-1]['content'],text)
        self.assertNotIn('Available tools',captured[0]['content'])
        self.assertEqual(len(captured),2)

    def test_folder_context_can_be_referenced(self):
        result=self.tools.create_folder('New folder')
        self.assertEqual(self.tools.path('that folder'),Path(result['created_folder']))

    def test_literal_please_is_not_removed_from_file_contents(self):
        plan=Agent.direct_plan('Create a file named manners.txt containing Say please')
        self.assertEqual(plan['args']['content'],'Say please')

    def test_deletion_uses_positive_target_not_an_excluded_name(self):
        self.tools.create_file('old.txt','old')
        self.tools.create_file('keep.txt','keep')
        request='Delete old.txt but do not delete keep.txt'
        self.assertTrue(self.agent.specific_delete_target(request,{'path':'old.txt'}))
        self.assertFalse(self.agent.specific_delete_target(request,{'path':'keep.txt'}))
        self.assertFalse(self.agent.specific_delete_target('Delete everything except keep.txt',{'path':'keep.txt'}))

    def test_ambiguous_stem_requires_clarification(self):
        self.tools.create_file('report.txt','text')
        self.tools.create_file('report.md','markdown')
        self.assertFalse(self.agent.specific_delete_target('Delete report',{'path':'report.txt'}))
        self.assertTrue(self.agent.specific_delete_target('Delete report.txt',{'path':'report.txt'}))

    def test_quoted_filename_can_contain_a_conjunction(self):
        self.tools.create_file('bread and notes.txt','text')
        self.assertTrue(self.agent.specific_delete_target('Delete "bread and notes.txt"',{'path':'bread and notes.txt'}))


if __name__=='__main__':
    unittest.main()
