from pathlib import Path
import json,copy,contextlib,io,importlib.util,tempfile
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v',R/'validate_one_stop_probe.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
base=R/'solutions/R_BALANCED/one_stop_h7200_t180_energy_local_polished_schedule.json'
sol=json.loads(base.read_text());mutations={}
a=copy.deepcopy(sol);a[1]['boxes'][0]=a[0]['boxes'][0];mutations['duplicate_box']=a
a=copy.deepcopy(sol);a[0]['start']=-1;mutations['negative_start']=a
a=copy.deepcopy(sol);a[0]['energy']+=.1;mutations['energy_tamper']=a
a=copy.deepcopy(sol);g=a[0]['type'];a[0]['uav_id']=('B' if g!='B' else 'C')+'-U1';mutations['wrong_type']=a
out={}
with tempfile.TemporaryDirectory() as td:
 for k,a in mutations.items():
  f=Path(td)/f'{k}_schedule.json';f.write_text(json.dumps(a))
  try:
   with contextlib.redirect_stdout(io.StringIO()):v.validate(f)
   out[k]='UNEXPECTED_PASS'
  except AssertionError:out[k]='REJECTED_AS_REQUIRED'
assert all(x=='REJECTED_AS_REQUIRED' for x in out.values())
(R/'probe_regression_results.json').write_text(json.dumps(out,indent=2));print(out)
