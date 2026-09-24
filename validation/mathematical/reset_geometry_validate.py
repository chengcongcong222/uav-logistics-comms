"""Independent G2 row-strip clipping, with bisection rather than event Brent roots."""
import json,math,sys
from pathlib import Path
import numpy as np
import pandas as pd
from pyproj import Transformer
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from src.common.terrain import Dem
TF=Transformer.from_crs(32649,4326,always_xy=True)
def independent_max(dem,a,b):
    inv=~dem.transform;dx=b[0]-a[0];dy=b[1]-a[1]
    def xy(t):return inv*TF.transform(a[0]+t*dx,a[1]+t*dy)
    p=xy(0);q=xy(1)
    def crossing(axis,value):
        if abs(value-p[axis])<1e-9:return 0.
        if abs(value-q[axis])<1e-9:return 1.
        lo,hi=0.,1.;inc=q[axis]>p[axis]
        for _ in range(48):
            mid=(lo+hi)/2
            if (xy(mid)[axis]<value)==inc:lo=mid
            else:hi=mid
        return (lo+hi)/2
    maximum=-float('inf');cells=0
    for r in range(math.floor(min(p[1],q[1])-1e-8),math.floor(max(p[1],q[1])+1e-8)+1):
        low=max(r,min(p[1],q[1]));high=min(r+1,max(p[1],q[1]))
        if low>high+1e-9:continue
        if abs(q[1]-p[1])<1e-10:u,v=0.,1.
        else:u,v=crossing(1,low),crossing(1,high)
        c0,c1=sorted([xy(u)[0],xy(v)[0]])
        for c in range(math.floor(c0-1e-7),math.floor(c1+1e-7)+1):
            if not (0<=r<dem.arr.shape[0] and 0<=c<dem.arr.shape[1]):raise ValueError('Out-of-raster native cell')
            value=float(dem.arr[r,c]);assert np.isfinite(value) and value!=dem.nodata
            maximum=max(maximum,value);cells+=1
    assert cells
    return maximum

def main():
    base=ROOT/'results/reset/geometry';nodes=pd.read_csv(base/'nodes.csv').set_index('node_id');geo=pd.read_csv(base/'route_geometry.csv');dem=Dem();rows=[];cache={}
    for r in geo.itertuples():
        a=nodes.loc[r.from_id];b=nodes.loc[r.to_id];key=tuple(sorted([r.from_id,r.to_id]))
        if key not in cache:cache[key]=independent_max(dem,(a.x_m,a.y_m),(b.x_m,b.y_m))
        value=cache[key];assert abs(value-r.max_dem_elevation_m)<1e-6,(key,value,r.max_dem_elevation_m)
        rows.append(dict(from_id=r.from_id,to_id=r.to_id,independent_max_dem_m=value))
    pd.DataFrame(rows).to_csv(base/'independent_geometry.csv',index=False)
    result=dict(status='G2_NATIVE_CELL_GEOMETRY_INDEPENDENTLY_VALIDATED',directed_legs=len(rows),independent_method='row-strip clipping and 48-step bisection',shared='source raster and CRS transformer only',native_registration='GDAL affine unchanged',boundary='all touched native cells',numerical_scope='local projection axis-monotonic segments; generator guards monotonicity; numerical roots, not symbolic algebra')
    (base/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(result,flush=True)
if __name__=='__main__':main()
