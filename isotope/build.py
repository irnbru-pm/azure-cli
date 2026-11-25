"""Package and test the reviewed Isotope checkout on Apple Silicon."""
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile

src = Path(__file__).resolve().parent
tree = src.parent
output = Path(sys.argv[1]).resolve()
version = sys.argv[2]
output.parent.mkdir(parents=True, exist_ok=True)
identity = 'Developer ID Application: Max Howell (ZU76A67LGU)'

def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)

def sign(path, identifier=None):
    options = ['--identifier', identifier] if identifier else []
    run('codesign', '-f', '-s', identity, '--options', 'runtime', '--timestamp', *options, path)

inputs = json.loads((src / 'inputs.json').read_text())
if version.split('-irnbru.')[0] != inputs['az']['version']:
    raise ValueError('Review the Azure SDK inputs for this version')

def unpack(component, destination):
    spec = inputs[component]
    pkg = stage / (component + '-input.tgz')
    if not pkg.exists() or hashlib.sha256(pkg.read_bytes()).hexdigest() != spec['sha256']:
        run('curl', '-fLsS', '--proto', '=https', '--proto-redir', '=https', spec['url'], '-o', pkg)
    if hashlib.sha256(pkg.read_bytes()).hexdigest() != spec['sha256']:
        raise ValueError('Input digest mismatch: ' + component)
    run('tar', 'xf', pkg, '-C', destination)


tool = 'az'
name = tool.capitalize()
with tempfile.TemporaryDirectory(dir=output.parent) as temp:
    stage = Path(temp)
    bundle = stage / (name + '.app')
    contents = bundle / 'Contents'
    mac, helpers, resources = (contents / folder for folder in ('MacOS','Helpers','Resources'))
    for directory in (mac,helpers,resources):
        directory.mkdir(parents=True)
    worker = helpers / 'worker'
    unpack('az',stage)
    unpack('python',resources)
    python = resources / 'python'
    (stage / 'libexec/lib/python3.14/site-packages').rename(resources / 'sdk')
    for filename in ['LICENSE','ThirdPartyNotices.txt','NOTICE.txt']:
        shutil.copy(stage / filename, resources)
    for filename in ['bootstrap.py','store.py']:
        shutil.copy(src / filename, resources)
    (resources / 'extensions').mkdir()
    run(python / 'bin/python3','-I','-B','-S',src / 'msal_cache.py',resources)
    shutil.rmtree(python / 'bin')
    for cache in resources.rglob('__pycache__'):
        shutil.rmtree(cache)
    run('clang++','-std=c++17','-I'+str(python/'include/python3.14'),src/'worker.cc',
        '-L'+str(python/'lib'),'-lpython3.14','-Wl,-rpath,@executable_path/../Resources/python/lib','-o',worker)
    for path in resources.rglob('*'):
        if path.is_symlink():
            target = path.resolve(strict=True)
            if not target.is_relative_to(resources) or not target.is_file(): raise ValueError('unexpected SDK link')
            path.unlink()
            shutil.copyfile(target, path)
        elif path.is_file():
            with path.open('rb') as stream:
                native = stream.read(4) in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe')
            if native: sign(path)
    run('clang++','-std=c++17','-fobjc-arc','-framework','Foundation','-framework','Security',
        f'-DTOOL="{tool}"',f'-DBUNDLE="{name}"','-D'+tool.upper(),src/'launcher.mm','-o',mac/tool)
    (contents/'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier='dev.mxcl.irnbru.'+tool,
        CFBundleExecutable=tool,CFBundlePackageType='APPL',CFBundleVersion=version.split('-')[0], CFBundleShortVersionString=version)))
    sign(worker, 'dev.mxcl.irnbru.' + tool + '.worker')
    sign(bundle)
    run('codesign','--verify','--deep','--strict',bundle)
    run(sys.executable, src / 'test_dispatch.py', worker)
    run('tar','czf',stage/'artifact.tgz','-C',stage,bundle.name,env=dict(os.environ,COPYFILE_DISABLE='1'))
    (stage/'artifact.tgz').replace(output)
