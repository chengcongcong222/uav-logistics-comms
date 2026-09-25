"""Export a figure of independently validated near-fast tradeoffs."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from src.bench_p1_4.common import *

def main():
    archive=read(OUT/'validated_archive.json');front=read(OUT/'near_fast_frontier.json')['solutions'];ids={r['id'] for r in front}
    fig,ax=plt.subplots(figsize=(9,5.5));fig.subplots_adjust(bottom=.19,top=.90,left=.10,right=.98);colors={23:'#6f4e7c',24:'#1b9e77',25:'#d95f02',26:'#4776b4',27:'#777777'}
    plotted=set()
    for r in sorted(archive,key=lambda r:r['metrics']['transport_sorties']):
        m=r['metrics'];n=m['transport_sorties'];label=f'{n} transport sorties' if n not in plotted else None;plotted.add(n)
        marker='o' if r['source']=='P1_4_NEW' else 's'
        ax.scatter(m['joint_makespan_s']/60,m['total_energy_kwh'],c=colors.get(n,'#444'),s=75,marker=marker,label=label,alpha=1 if r['id'] in ids else .3,edgecolors='white',linewidths=.7,zorder=3)
        name=r['pid']+(' fixed' if 'C1_FIXED' in r['id'] else '')
        if r['id'] in ids:
            offset=(6,8) if name not in ['T01','T02'] else (-12,12)
            ax.annotate(name,(m['joint_makespan_s']/60,m['total_energy_kwh']),xytext=offset,textcoords='offset points',fontsize=8)
    for cap in [6155,6250,6350,6500]:ax.axvline(cap/60,color='#aaaaaa',lw=.7,ls='--',zorder=0)
    ax.set(xlabel='Joint completion time (min)',ylabel='Total transport + relay energy (kWh)',title='Validated near-fast execution archive (zero lateness, relay sorties <= 3)')
    ax.grid(alpha=.2);legend=ax.legend(loc='upper right',fontsize=8);ax.margins(.12)
    for h in legend.legend_handles:h.set_alpha(1)
    fig.text(.01,.02,'Circles: P1.4; squares: P1.3-C anchors. Faded: dominated within this finite archive only.\nFull comparison also retains J_norm and both sortie counts.',fontsize=7)
    dest=OUT/'figures';dest.mkdir(exist_ok=True)
    for ext in ['png','svg','pdf']:fig.savefig(dest/f'near_fast_tradeoffs.{ext}',dpi=180,bbox_inches='tight')
    plt.close(fig)
if __name__=='__main__':main()
