"""Full non-destructive verification: test suites, syntax, source integrity."""
from pathlib import Path
from time import time_ns
import ast,json,hashlib,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'data/verification'/str(time_ns());out.mkdir(parents=True)
steps=[]
for name,cmd in [('python_tests',[sys.executable,'-m','unittest','discover','-s','tests','-v']),('javascript_tests',['node','--test',*map(str,sorted((root/'tests').glob('*.test.cjs')))])]:
    result=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
    with (out/(name+'.log')).open('x') as stream:stream.write(result.stdout+result.stderr)
    steps.append({'name':name,'exit_code':result.returncode,'log':str(out/(name+'.log'))})
    print(name,':',result.returncode);print((result.stdout+result.stderr)[-950:])
syntax=[]
for file in list((root/'core').glob('*.py'))+list((root/'api').glob('*.py'))+list((root/'tools').glob('*.py'))+list((root/'tests').glob('*.py')):
    ast.parse(file.read_text(),filename=str(file));syntax.append(str(file.relative_to(root)))
for file in (root/'static').glob('*.js'):
    result=subprocess.run(['node','--check',str(file)],capture_output=True,text=True)
    if result.returncode:raise SystemExit(result.stderr)
    syntax.append(str(file.relative_to(root)))
manifest=json.loads((root/'SOURCE_V3.json').read_text());changed=[]
for name,digest in manifest.items():
    if hashlib.sha256((root.parent/'v3'/name).read_bytes()).hexdigest()!=digest:changed.append(name)
assert not changed,'V3 source changed: '+str(changed)
report={'steps':steps,'syntax_files':len(syntax),'v3_source_files_verified':len(manifest),'v3_changes':changed,'deletions':0}
with (out/'verification.json').open('x') as stream:json.dump(report,stream,indent=2)
print('Verification report:',out/'verification.json');print(json.dumps(report,indent=2));sys.exit(int(any(s['exit_code'] for s in steps)))
