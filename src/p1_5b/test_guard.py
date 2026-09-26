"""Adversarial regression checks for publication-source admission."""
import hashlib,json
from pathlib import Path
from src.p1_5b.guard import Guard,ROOT,OUT
def main():
    fixture=OUT/'_guard_fixture.txt';alias=OUT/'_guard_alias.txt'
    assert not fixture.exists() and not alias.exists()
    fixture.write_text('unadmitted fixture')
    alias.symlink_to(fixture)
    guard=Guard();good=OUT/'admitted_comparators.json';key=good.relative_to(ROOT).as_posix();original=guard.entries[key]
    results=[]
    def denied(name,fn):
        try:fn()
        except PermissionError:results.append(dict(test=name,passed=True));return
        raise AssertionError('Read was not blocked: '+name)
    guard.verify(good);results.append(dict(test='admitted_hash_match',passed=True))
    guard.verify(good.parent/'figure_data/../admitted_comparators.json');results.append(dict(test='canonical_allowed_path',passed=True))
    denied('unlisted_API',lambda:guard.text(fixture))
    denied('symlink_to_unlisted_API',lambda:guard.text(alias))
    guard.entries[key]='0'*64;denied('changed_hash_API',lambda:guard.text(good));guard.entries[key]=original
    denied('outside_repository_API',lambda:guard.text(Path('/tmp/nonpublication.txt')))
    guard.install()
    good.read_text();results.append(dict(test='direct_open_admitted',passed=True))
    denied('direct_open_unlisted',lambda:fixture.read_text())
    denied('direct_open_symlink_unlisted',lambda:alias.read_text())
    guard.entries[key]='0'*64;denied('direct_open_changed_hash',lambda:good.read_text());guard.entries[key]=original
    denied('write_outside_stage',lambda:(ROOT/'_guard_write_must_not_exist.txt').write_text('no'))
    # Use a disposable admitted fixture to verify real byte tampering, not only metadata mismatch.
    fkey=fixture.relative_to(ROOT).as_posix();guard.entries[fkey]=hashlib.sha256(b'unadmitted fixture').hexdigest()
    fixture.write_text('changed bytes');denied('actual_content_mutation',lambda:fixture.read_text())
    del guard.entries[fkey];alias.unlink();fixture.unlink()
    (OUT/'paper/guard_tests.json').write_text(json.dumps(dict(status='PASSED',cases=results),indent=2)+'\n')
    print('GUARD_TESTS',len(results),flush=True)
if __name__=='__main__':main()
