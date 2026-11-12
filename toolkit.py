"""Use real user-selected Universal Modder/REA interfaces, not worker agents."""
import json,os,re,shutil,signal,subprocess,tempfile
from pathlib import Path

UM_GROUPS={'scan','sprite','render3d','video','win','backup','kb','publish'}
REA_ADMIN={'setup','uninstall','install','update','upgrade','config','doctor','serve','server'}

def resources(settings=None):
    settings=settings or {}
    um_executable=settings.get('um_executable','');rea_executable=settings.get('rea_executable','')
    def resolve(chosen,name):
        value=str(Path(chosen).expanduser())if chosen else shutil.which(name)
        return {'installed':bool(value and Path(value).is_file()),'executable':value,'notice':'CLI presence only; game/platform/provider capabilities require the selected operation’s actual contract.'}
    return {'universal_modder':resolve(um_executable,'um'),'reverse_engineer_anything':resolve(rea_executable,'rea'),'workflow':['Define game/platform/idea and user resources','Recon and choose the actual modding route','Create a safe lab and build one working slice','Generate/review needed art directly in the MAIN session with native tools','Build and test in the real game using supported interfaces','Record the result; publication remains a separate explicitly authorized action'],'image_policy':'No retired context routes, worker agents or silent local image-model substitution. Native main-session image tools own image generation/review.'}

MAX_RUN_FOLDERS = 20
MAX_RUN_BYTES = 64 * 1024**2


def prune_runs(root):
    """Keep the newest toolkit run folders (and at most 64 MB); delete the rest. Only folders inside ModLab's own toolkit-runs folder."""
    runs = Path(root) / 'toolkit-runs'
    if not runs.is_dir(): return 0
    folders = sorted((r for r in runs.iterdir() if r.is_dir() and not r.is_symlink() and r.name.startswith('run-')), key=lambda r: r.stat().st_mtime, reverse=True)
    def size(r): return sum(f.stat().st_size for f in r.rglob('*') if f.is_file() and not f.is_symlink())
    kept, total, removed = 0, 0, 0
    for r in folders:
        s_ = size(r)
        if kept >= MAX_RUN_FOLDERS or total + s_ > MAX_RUN_BYTES:
            shutil.rmtree(r, ignore_errors=True); removed += 1
        else:
            kept += 1; total += s_
    return removed


def run(root,toolkit,arguments,timeout_seconds=60,settings=None):
    settings=settings or {}
    um_executable=settings.get('um_executable','');rea_executable=settings.get('rea_executable','')
    if toolkit not in('universal-modder','rea')or not isinstance(arguments,list)or not arguments or len(arguments)>80 or not all(isinstance(x,str)and 0<len(x)<=4000 for x in arguments):raise ValueError('Select a real toolkit and bounded argument array')
    if type(timeout_seconds)is not int or not 1<=timeout_seconds<=600:raise ValueError('Choose a1–600second explicit operation bound')
    if toolkit=='universal-modder':
        if arguments[0]not in UM_GROUPS|{'--help','--version'}:raise ValueError('Use a supported game-modding group; image work stays with the main agent’s native tools')
        if arguments[0]=='kb'and any(x in('pr','publish','push','submit')for x in arguments[1:]):raise ValueError('Publishing/PRs require the separate final-authorized publication workflow')
        if arguments[0]=='publish'and(len(arguments)<2 or arguments[1]not in('check','--help')):raise ValueError('This interface allows release inspection, not publication')
        executable=um_executable or shutil.which('um')
    else:
        if arguments[0]in REA_ADMIN:raise ValueError('Select an analysis operation; this tool does not alter REA/client installations')
        executable=rea_executable or shutil.which('rea')
    if not executable or not Path(executable).expanduser().is_file():raise ValueError('Selected toolkit is unavailable; configure an installed executable or use supported native REA tools')
    base=root;root=Path(root)/'toolkit-runs';root.mkdir(parents=True,exist_ok=True,mode=0o700);work=Path(tempfile.mkdtemp(prefix='run-',dir=root));output=work/'stdout.txt';error=work/'stderr.log'
    env={k:v for k,v in os.environ.items()if k in('PATH','HOME','LANG','LC_ALL','SystemRoot','TEMP','TMP','TMPDIR')}
    with output.open('wb')as out,error.open('wb')as err:
        output.chmod(0o600);error.chmod(0o600);process=subprocess.Popen([str(Path(executable).expanduser()),*arguments],stdout=out,stderr=err,stdin=subprocess.DEVNULL,env=env,start_new_session=os.name!='nt')
        try:process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            if os.name!='nt':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
            process.wait(timeout=5);raise RuntimeError('Owned toolkit operation timed out; no retry/fallback performed')from None
    if output.stat().st_size>2*1024**2:raise ValueError('Toolkit output exceeds2MiB; request a bounded operation or use its supported retained-evidence interface. Private full output retained.')
    if process.returncode:raise RuntimeError('Selected toolkit operation failed; inspect its private diagnostics. No success or automatic retry inferred.')
    body=output.read_text(errors='replace')
    prune_runs(base)
    try:result=json.loads(body)
    except ValueError:result={'text':body}
    return {'toolkit':toolkit,'exit_code':0,'result':result,'notice':'Actual selected CLI output; provider/platform readiness and result meaning depend on the operation. No model worker was launched.'}
