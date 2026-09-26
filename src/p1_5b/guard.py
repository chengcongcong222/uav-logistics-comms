"""Default-deny publication sources; rendering runtime is explicitly separate."""
import json,hashlib,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/p1_5b'
class Guard:
    def __init__(self):
        p=OUT/'PAPER_SOURCE_WHITELIST.json';self.policy=json.loads(p.read_text())
        self.entries={x['path']:x['sha256'] for x in self.policy['sources']}
        self.fonts={x['path']:x['sha256'] for x in self.policy['runtime_fonts']}
        self.reads=set();self.checking=False
    def verify(self,p):
        p=Path(p).resolve()
        try:r=p.relative_to(ROOT).as_posix()
        except ValueError:raise PermissionError('Non-project publication source denied')
        if r not in self.entries:raise PermissionError('Source not admitted: '+r)
        self.checking=True
        try:data=p.read_bytes()
        finally:self.checking=False
        if hashlib.sha256(data).hexdigest()!=self.entries[r]:raise PermissionError('Source changed: '+r)
        self.reads.add(r);return data
    def text(self,p):return self.verify(p).decode('utf-8')
    def json(self,p):return json.loads(self.text(p))
    def install(self):
        def hook(event,args):
            if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
            p=Path(os.fsdecode(args[0])).resolve()
            mode=args[1];flags=args[2]
            writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC))
            if writing:
                if not p.is_relative_to(OUT):raise PermissionError('Publication write outside B1')
                return
            if self.checking:return
            if str(p) in self.fonts:
                self.checking=True
                try:h=hashlib.sha256(p.read_bytes()).hexdigest()
                finally:self.checking=False
                assert h==self.fonts[str(p)]
                return
            if str(p).startswith(('/usr/lib/','/usr/share/','/etc/')) or p.is_relative_to(ROOT/'.venv'):return
            if p.is_relative_to(ROOT/'src') and p.suffix in ['.py','.pyc']:return
            self.verify(p)
        sys.addaudithook(hook)
