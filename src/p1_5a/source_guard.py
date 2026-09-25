"""Hash-bound allowlist for the new publication entry point.

No historical builder is modified or granted publication authority.
"""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
WL=ROOT/'results/p1_5a/PAPER_SOURCE_WHITELIST.json'
class SourceGuard:
    def __init__(self,path=WL):
        self.root=ROOT
        self.whitelist_path=Path(path).resolve()
        policy=json.loads(self.whitelist_path.read_text())
        self.entries={e['path']:e for e in policy['sources']}
        assert len(self.entries)==len(policy['sources'])
        self.accesses=set();self.active=False;self.checking=False
        self.output_root=(ROOT/'results/p1_5a/paper_export').resolve()
    def authorize(self,path):
        p=Path(path).resolve()
        try:rel=p.relative_to(self.root).as_posix()
        except ValueError:raise PermissionError('Publication data outside project denied')
        if rel not in self.entries:raise PermissionError('Publication source not whitelisted: '+rel)
        entry=self.entries[rel]
        raw=p.read_bytes() if not self.active else self._verified_read(p)
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise PermissionError('Publication source hash mismatch: '+rel)
        self.accesses.add(rel)
        return raw
    def _verified_read(self,p):
        self.checking=True
        try:return p.read_bytes()
        finally:self.checking=False
    def text(self,path):return self.authorize(path).decode('utf-8')
    def json(self,path):return json.loads(self.text(path))
    def install(self):
        """Block implicit file reads as well as explicit loader API reads."""
        def hook(event,args):
            if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):return
            p=Path(os.fsdecode(args[0])).resolve()
            try:rel=p.relative_to(self.root).as_posix()
            except ValueError:
                # Python runtime libraries are permitted; arbitrary data are not.
                if p.suffix in ['.py','.pyc','.so','.pyd'] or str(p).startswith(('/usr/lib/','/usr/share/zoneinfo/','/etc/')):
                    return
                raise PermissionError('Publication data outside project denied')
            if '/.venv/' in str(p) and p.suffix in ['.py','.pyc','.so']:return
            mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
            writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing:
                if not p.is_relative_to(self.output_root):raise PermissionError('Publication write outside isolated export')
                return
            if self.checking:return
            if rel not in self.entries:raise PermissionError('Publication source not whitelisted: '+rel)
            self.checking=True
            try:h=hashlib.sha256(p.read_bytes()).hexdigest()
            finally:self.checking=False
            if h!=self.entries[rel]['sha256']:raise PermissionError('Publication source hash mismatch: '+rel)
            self.accesses.add(rel)
        sys.addaudithook(hook);self.active=True
