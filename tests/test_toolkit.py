import importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('toolkit',Path(__file__).parents[1]/'toolkit.py');toolkit=importlib.util.module_from_spec(spec);spec.loader.exec_module(toolkit)
class ToolkitTests(unittest.TestCase):
    def test_refused_routes_and_real_missing_executable(self):
        with tempfile.TemporaryDirectory()as tmp:
            for args in [['context','inspect'],['publish','upload'],['kb','pr']]:
                with self.assertRaises(ValueError):toolkit.run(tmp,'universal-modder',args)
            with self.assertRaises(ValueError):toolkit.run(tmp,'rea',['setup'])
            with patch.object(toolkit.shutil,'which',return_value=None):
                with self.assertRaisesRegex(ValueError,'unavailable'):toolkit.run(tmp,'rea',['inventory'])
    def test_real_cli_read_only_help(self):
        with tempfile.TemporaryDirectory()as tmp:
            for key,name in [('universal-modder','um'),('rea','rea')]:
                if not toolkit.shutil.which(name):continue
                result=toolkit.run(tmp,key,['--help']);self.assertEqual(result['exit_code'],0);self.assertTrue(result['result'])
    def test_native_original_result_and_context_preserved(self):
        import sys,types,json
        spec=importlib.util.spec_from_file_location('modlab_native_fixture',Path(__file__).parents[1]/'__init__.py',submodule_search_locations=[str(Path(__file__).parents[1])]);module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
        storage=types.ModuleType('plugins.plugin_storage');storage.plugin_data_dir=lambda name:None
        refusal={'error':'provider denied','original_evidence':{'kept':True}};calls=[]
        class Host:
            def get_config(self,key):return 'real_native_rea'
            def dispatch_tool(self,name,args,**context):calls.append((name,args,context));return refusal
        with patch.dict(sys.modules,{'plugins':types.ModuleType('plugins'),'plugins.plugin_storage':storage}):
            result=module.invoke('modlab_rea_native',{'arguments':{'target':'fixture'}},Host(),session_id='native-session',private='omit')
            self.assertIs(result,refusal);self.assertEqual(calls[0][2],{'session_id':'native-session'})
            host=Host();host.get_config=lambda key:'modlab_rea_native'
            self.assertIn('recursive',json.loads(module.invoke('modlab_rea_native',{'arguments':{}},host))['error'])
if __name__=='__main__':unittest.main()
