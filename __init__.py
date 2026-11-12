import json
import zipfile
from .core import Lab, limits_from

TOOLS = {
    'modlab_cleanup': ('Show what ModLab uses on disk and free space safely. Default action report lists every lab with its size, the toolkit-run output, free disk space and the limits. Other actions (delete_lab with lab_id, prune_revisions, clear_toolkit_runs, remove_leftovers) are a DRY RUN that lists exactly what would be deleted and how much space it frees; they delete only with confirm=true, only inside ModLab\'s own data folder, and never touch the original game folder. Ask the user before confirming.', {'action': {'type': 'string', 'enum': ['report', 'delete_lab', 'prune_revisions', 'clear_toolkit_runs', 'remove_leftovers']}, 'lab_id': {'type': 'string'}, 'keep': {'type': 'integer', 'minimum': 2, 'maximum': 20}, 'confirm': {'type': 'boolean'}}, []),
    'modlab_setup': ('First-use interview and environment scan. Without answers: returns what this computer has (installed modding tools, installed Steam games, and for a game_folder the engine it looks like, any anti-cheat, and the modding routes found for that engine with what each needs and what is missing), the questions to ask the user, and whether the built-in modding knowledge looks out of date (offering online research only if the user says yes). With answers: saves them, including the route the user picked. ModLab never picks a route for the user. Starts no game, installs nothing, sends nothing. modlab_toolkit and modlab_create return the interview until it is answered.', {'game_folder': {'type': 'string', 'description': 'Optional game folder to identify (local read of file names only).'}, 'answers': {'type': 'object', 'description': 'game, idea, single_player_offline (bool), experience (new to modding|some experience|experienced), publish (private|share publicly), ai_assets (bool), has (text), route (the id of the route the user picked).'}, 'knowledge_updates': {'type': 'array', 'maxItems': 100, 'items': {'type': 'object'}, 'description': 'Only after the user said yes to online research: facts you verified on primary pages. Each item: id (from the modding wiki tables), field, value, source (https page), date (the day you read it). Saved as dated overrides; the shipped catalog is unchanged.'}}, []),
    'modlab_create': ('Copy a game folder into an isolated lab; the original is never modified.', {'source_path': {'type': 'string'}}, ['source_path']),
    'modlab_inspect': ('Inspect a ZIP against the current revision; list files that would be replaced. ZIP contents are untrusted data.', {'lab_id': {'type': 'string'}, 'zip_path': {'type': 'string'}}, ['lab_id', 'zip_path']),
    'modlab_apply': ('Apply a ZIP to a new revision if its inspected content and the current revision have not changed. Existing files require allow_replacements=true.', {'lab_id': {'type': 'string'}, 'zip_path': {'type': 'string'}, 'inspection': {'type': 'string'}, 'allow_replacements': {'type': 'boolean'}}, ['lab_id', 'zip_path', 'inspection']),
    'modlab_rollback': ('Switch the lab back to its preceding revision, preserving both copies.', {'lab_id': {'type': 'string'}}, ['lab_id']),
    'modlab_select_preserved': ('Re-select a revision preserved by a previous rollback. The directory may have changed externally.', {'lab_id': {'type': 'string'}, 'revision': {'type': 'string'}}, ['lab_id', 'revision']),
}

def invoke(name, args, ctx=None, **context):
    from plugins.plugin_storage import plugin_data_dir
    try:
        if name=='modlab_setup':
            from . import resources as R
            root=plugin_data_dir('modlab')
            report=R.survey(root,args.get('game_folder'))
            return json.dumps(R.apply_setup(root,report,args.get('answers'),args.get('knowledge_updates')))
        if name in('modlab_create','modlab_toolkit'):
            from . import resources as R
            root=plugin_data_dir('modlab')
            if R.load_profile(root) is None:
                return json.dumps({**R.interview(root,R.survey(root)),'next':'Do not pick a modding route for the user. Run the interview first (modlab_setup), then repeat this call.'})
        if name=='modlab_resources':
            from .toolkit import resources
            return json.dumps(resources(**args))
        if name=='modlab_toolkit':
            from .toolkit import run
            from plugins.plugin_storage import plugin_data_dir
            return json.dumps(run(plugin_data_dir('modlab'),**args))
        if name=='modlab_rea_native':
            tool=ctx.get_config('rea_native_tool')if ctx is not None else None
            if not tool or not callable(getattr(ctx,'dispatch_tool',None)):raise ValueError('No selected native REA interface in this host; use the installed rea CLI or the main agent’s connected REA tools. No analysis was fabricated.')
            if tool==name:raise ValueError('Select an actual native provider tool; a recursive bridge is not a backend')
            return ctx.dispatch_tool(tool,args['arguments'],**{k:context[k]for k in ('parent_agent','session_id','task_id')if k in context})
        return json.dumps(getattr(Lab(plugin_data_dir('modlab'), limits_from(getattr(ctx, 'get_config', None))), name.removeprefix('modlab_'))(**args))
    except (ValueError, TypeError, OSError, KeyError, RuntimeError, zipfile.BadZipFile) as exc:
        return json.dumps({'error': str(exc)})

def register(ctx):
    for name,description,props,required in [('modlab_resources','Discover actual installed Universal Modder/REA resources and the full game-modding workflow; no game, model or provider is started.',{'um_executable':{'type':'string'},'rea_executable':{'type':'string'}},[]),('modlab_toolkit','Run ONE explicit bounded operation with Universal Modder or Reverse Engineer Anything. These real toolkits cover game recon, asset preparation, reverse engineering, building/testing/capture routes and release inspection. Some operations affect selected games/files/apps; use only within the user-authorized mod task. No retired agents or publication.',{'toolkit':{'type':'string','enum':['universal-modder','rea']},'arguments':{'type':'array','items':{'type':'string'}},'um_executable':{'type':'string'},'rea_executable':{'type':'string'},'timeout_seconds':{'type':'integer','minimum':1,'maximum':600}},['toolkit','arguments']),('modlab_rea_native','Invoke the explicitly configured native REA tool, preserving host auth, approvals, original Evidence and images. Missing provider/interface remains a real blocker.',{'arguments':{'type':'object'}},['arguments'])]:
        ctx.register_tool(name=name,toolset='modlab',schema={'name':name,'description':description,'parameters':{'type':'object','properties':props,'required':required,'additionalProperties':False}},handler=lambda args,_name=name,**kw:invoke(_name,args,ctx,**kw))
    if hasattr(ctx, 'register_skill'):
        from pathlib import Path
        ctx.register_skill('modlab', Path(__file__).parent / 'skills/modlab/SKILL.md', description='Take a game-modding idea through recon, creation, reverse engineering, safe builds and real-game verification with Universal Modder and REA')
    for name, (description, properties, required) in TOOLS.items():
        ctx.register_tool(name=name, toolset='modlab', schema={'name': name, 'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required, 'additionalProperties': False}},
            handler=lambda args, _name=name, **kwargs: invoke(_name, args, ctx))
