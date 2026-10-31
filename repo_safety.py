"""Source-only Git publication audit. Never prints matched secret contents."""
import argparse,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TEXT={'.py','.js','.cjs','.css','.html','.sh','.bat'}
VENDOR={'three.core.js','three.module.js','THREE-LICENSE.txt','PretendardVariable.woff2','Pretendard-LICENSE.txt'}

def allowed(name):
    path=Path(name)
    if path.is_absolute() or '..' in path.parts:return False
    if len(path.parts)==1:
        return name in ('.gitignore','README.md','AGENTS.md','mobile-requirements.txt') or (path.suffix in TEXT and name!='serve-reference.py')
    if path.parts[0]=='docs':return len(path.parts)==2 and path.suffix=='.md'
    if path.parts[0]=='settings':return name.replace('\\','/') in ('settings/runtime-lock.json','settings/scenarios.json','settings/requirements.lock.txt')
    if path.parts[0]=='mobile':return name.replace('\\','/') in ('mobile/app.js','mobile/index.html')
    if path.parts[0]=='course_ui':
        return (len(path.parts)==2 and path.suffix in TEXT) or (len(path.parts)==3 and path.parts[1]=='vendor' and path.name in VENDOR)
    return False

def check_content(name,data):
    if len(data)>5*1024*1024:raise ValueError('Oversized file: '+name)
    if name.endswith('.woff2'):return
    if re.search(rb'(?m)^\s*(?:#|//|\*)\s*SPDX-License-Identifier:\s*LicenseRef-NvidiaProprietary',data):
        raise ValueError('Proprietary SDK source: '+name)
    patterns=[rb'(?m)^-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'gh[pousr]_[A-Za-z0-9]{30,}',rb'github_pat_[A-Za-z0-9_]{40,}']
    if any(re.search(pattern,data) for pattern in patterns):raise ValueError('Potential credential material: '+name)

def audit(staged=True):
    cmd=['git','diff','--cached','--name-only','--diff-filter=ACMR','-z'] if staged else ['git','ls-files','-z']
    names=[s for s in subprocess.check_output(cmd,cwd=ROOT).decode('utf-8').split('\0') if s]
    for name in names:
        if not allowed(name):raise ValueError('Not approved source path: '+name)
        data=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        check_content(name,data)
    return len(names)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--tracked',action='store_true');args=ap.parse_args()
    print('Source-only audit passed: '+str(audit(not args.tracked))+' files')
