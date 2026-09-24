"""G2: native raster supercover along UTM49N straight flight segments.

G1 (exact lon/lat chord) is kept as a separate intermediate comparison.
No DEM reprojection. Rasterio/GDAL affine includes PixelIsPoint registration.
"""
import hashlib,json,math,shutil
from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.optimize import brentq
from src.common.terrain import Dem
from src.common.paths import DEM_TIF
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/reset';DATA=OUT/'geometry'
VERSION='G2_UTM49N_STRAIGHT_NATIVE_SUPERCOVER_V1'
TF=Transformer.from_crs(32649,4326,always_xy=True)
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

class FlightDem:
    def __init__(self):self.dem=Dem();self.inv=~self.dem.transform;self.cache={}
    def pixels(self,a,b,t):
        a=np.asarray(a);b=np.asarray(b);q=a+(b-a)*np.asarray(t)[...,None]
        lon,lat=TF.transform(q[...,0],q[...,1]);c,r=self.inv*(lon,lat)
        return np.stack([c,r],axis=-1)
    def maximum(self,a,b):
        key=tuple(sorted([tuple(map(float,a)),tuple(map(float,b))]))
        if key in self.cache:return self.cache[key]
        p,q=self.pixels(a,b,[0.,1.]);probe=self.pixels(a,b,np.linspace(0,1,257))
        for axis in range(2):
            delta=np.diff(probe[:,axis]);assert np.all(delta>=-1e-10) or np.all(delta<=1e-10),'Non-monotone projected segment: subdivide before traversal'
        cuts=[0.,1.]
        for axis in range(2):
            if abs(q[axis]-p[axis])<1e-10:continue
            for v in range(math.ceil(min(p[axis],q[axis])),math.floor(max(p[axis],q[axis]))+1):
                if abs(p[axis]-v)<1e-9:cuts.append(0.);continue
                if abs(q[axis]-v)<1e-9:cuts.append(1.);continue
                cuts.append(brentq(lambda t:float(self.pixels(a,b,t)[axis])-v,0.,1.,xtol=1e-13))
        cuts=sorted(set(cuts));ts=cuts+[(u+v)/2 for u,v in zip(cuts[:-1],cuts[1:])];cells=set()
        for xy in self.pixels(a,b,ts):
            choices=[[round(v)-1,round(v)] if abs(v-round(v))<1e-7 else [math.floor(v)] for v in xy]
            for c in choices[0]:
                for r in choices[1]:
                    assert 0<=r<self.dem.arr.shape[0] and 0<=c<self.dem.arr.shape[1]
                    cells.add((r,c))
        vals=[float(self.dem.arr[r,c]) for r,c in cells];assert all(np.isfinite(v) and v!=self.dem.nodata for v in vals)
        out=dict(max_dem_m=max(vals),cells=len(cells),events=len(cuts),monotonicity_samples=257)
        self.cache[key]=out;return out

def tables():
    from src.q2.solve_q2 import load_tables
    t=load_tables();t['geom']=pd.read_csv(DATA/'route_geometry.csv',float_precision='round_trip');return t

def main():
    DATA.mkdir(parents=True,exist_ok=True)
    for p in (ROOT/'data/processed').glob('*'):
        if p.is_file():shutil.copyfile(p,DATA/p.name)
    nodes=pd.read_csv(DATA/'nodes.csv').set_index('node_id');old=pd.read_csv(DATA/'route_geometry.csv')
    g1=pd.read_csv(ROOT/'results/xb1/exact_geometry_sensitivity.csv').set_index(['from_id','to_id']);engine=FlightDem();rows=[];diff=[]
    for r in old.to_dict('records'):
        a=nodes.loc[r['from_id']];b=nodes.loc[r['to_id']];z=engine.maximum((a.x_m,a.y_m),(b.x_m,b.y_m))['max_dem_m']
        v1=float(g1.loc[(r['from_id'],r['to_id'])].max_dem_elevation_m)
        diff.append(dict(from_id=r['from_id'],to_id=r['to_id'],G0_sample_m=r['max_dem_elevation_m'],G1_lonlat_cells_m=v1,G2_utm_cells_m=z,sampling_change_m=v1-r['max_dem_elevation_m'],path_definition_change_m=z-v1))
        r.update(max_dem_elevation_m=z,planned_cruise_altitude_m=z+50,climb_height_m=max(0,z+50-r['origin_operation_altitude_m']),descent_height_m=max(0,z+50-r['destination_operation_altitude_m']))
        rows.append(r)
    pd.DataFrame(rows).to_csv(DATA/'route_geometry.csv',index=False);pd.DataFrame(diff).to_csv(DATA/'version_comparison.csv',index=False)
    config=dict(version=VERSION,path='straight UTM EPSG:32649; inverse-project to native EPSG:4326 raster for cell-boundary roots',registration='native GDAL affine, no extra half-cell shift',boundary='supercover, both sides of touched edges and all corner cells',nodata='fail closed, including out-of-raster',root_tolerance_parameter=1e-13,pixel_boundary_tolerance=1e-7,monotonicity_guard_samples=257,radio_LOS='existing frozen terrain_los primitive unchanged',transport_and_relay_flight_geometry='same FlightDem routine',G0_G1_G2_changes_reported_separately=True)
    write(DATA/'config.json',config)
    write(DATA/'manifest.json',dict(version=VERSION,hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [DEM_TIF,DATA/'route_geometry.csv',Path(__file__),ROOT/'src/common/terrain.py',ROOT/'src/q3/terrain_los.py']}))
    print(pd.DataFrame(diff)[['sampling_change_m','path_definition_change_m']].describe().to_string(),flush=True)
if __name__=='__main__':main()
