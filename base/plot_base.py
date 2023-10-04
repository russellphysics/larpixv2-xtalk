from base import utility_base
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import yaml
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from matplotlib import cm
from matplotlib.colors import Normalize
import numpy as np
import yaml


def load_yaml(asic_version='2b'):
    if asic_version=='2b':
        geometrypath='/home/brussell/2x2-daq/tile/layout-2.5.0.yaml'
        with open(geometrypath) as fi:
            geo = yaml.full_load(fi)
            chip_pix = dict([(chip_id, pix) for chip_id,pix in geo['chips']])
            vlines=np.linspace(-1*(geo['width']/2), geo['width']/2, 11)
            hlines=np.linspace(-1*(geo['height']/2), geo['height']/2, 11)
        pitch=3.8 # mm
    return geo, chip_pix, vlines, hlines, pitch



def n_disabled_per_tile(disabled,nchan=6400):
    d={}
    for i in range(1,9,1): d[i]=0
    for key in disabled.keys():
        tile = utility_base.io_channel_to_tile(utility_base.chip_key_to_io_channel(key))
        d[tile]+=len(disabled[key])
    for tile in d.keys():
        n=d[tile]
        d[tile]=n/6400.
    return d


def compare_n_tile_disabled(d1, d2, prefix, show=False):
    fig, ax = plt.subplots(figsize=(8,6))
    ntpc1=[d1[key] for key in d1.keys()]
    ntpc2=[d2[key] for key in d2.keys()]
    xbins = np.linspace(0,100,21)
    ax.hist(ntpc1, bins=xbins, alpha=0.5, color='b', label='TPC 1')
    ax.hist(ntpc2, bins=xbins, alpha=0.5, color='r', label='TPC 2')
    ax.set_ylabel('Tile Count')
    ax.set_xlabel('Disabled Channels per Tile')
    ax.grid(True)
    ax.legend()
    if show==True: plt.show()
    if show==False: plt.savefig(prefix+'_'+'disabled_channel_per_tile.png')
    return



def eight_tile_xy(geo, chip_pix, vertical_lines, \
                 horizontal_lines, pitch):
    fig, ax = plt.subplots(2,4,figsize=(28,14))
    tile_title={(0,0):'Tile 1',(0,1):'Tile 2',(0,2):'Tile 3',(0,3):'Tile 4',
                (1,0):'Tile 5',(1,1):'Tile 6',(1,2):'Tile 7',(1,3):'Tile 8'}
    for x in range(2):
        for y in range(4):
            ax[x][y].get_xaxis().set_visible(False)
            ax[x][y].get_yaxis().set_visible(False)
            ax[x][y].set_title(tile_title[(x,y)])
            ax[x][y].set_xticks(vertical_lines, color='w')
            ax[x][y].set_yticks(horizontal_lines, color='w')
            ax[x][y].set_xlim(vertical_lines[0]*1.1,vertical_lines[-1]*1.1)
            ax[x][y].set_ylim(horizontal_lines[0]*1.1,horizontal_lines[-1]*1.1)
            for vl in vertical_lines:
                ax[x][y].vlines(x=vl, ymin=horizontal_lines[0], \
                                ymax=horizontal_lines[-1], colors=['k'], \
                                linestyle='dotted')
            for hl in horizontal_lines:
                ax[x][y].hlines(y=hl, xmin=vertical_lines[0], \
                                xmax=vertical_lines[-1], colors=['k'], \
                                linestyle='dotted')

    chip_id_pos = dict()
    for chipid in chip_pix.keys():
        x,y = [[] for i in range(2)]
        for channelid in range(64):
            x.append( geo['pixels'][chip_pix[chipid][channelid]][1] )
            y.append( geo['pixels'][chip_pix[chipid][channelid]][2] )
        avgX = (max(x)+min(x))/2.
        avgY = (max(y)+min(y))/2.
        chip_id_pos[chipid]=dict(minX=min(x), maxX=max(x), \
                                avgX=avgX, minY=min(y), \
                                maxY=max(y), avgY=avgY)
        for x in range(2):
            for y in range(4):
                ax[x][y].annotate(str(chipid), [avgX,avgY], \
                                  ha='center', va='center')
    return fig, ax



def plot_eight_tile_metric_xy(d, prefix, metric, geo, chip_pix, \
                              vertical_lines, horizontal_lines, pitch, \
                              rangeMin, rangeMax, show=False):
    fig, ax = eight_tile_xy(geo, chip_pix, vertical_lines, \
                            horizontal_lines, pitch)
                
    a=[d[key] for key in d.keys()]
    rangeMax=int(max(a))
    rangeMin=int(min(a))
    for key in d.keys():
        r = find_pixel_xy_from_unique(key, d[key], geo, chip_pix, pitch, \
                          rangeMin, rangeMax)
        if r==-1: continue
        io_channel = utility_base.unique_to_io_channel(key)
        if io_channel in list(range(1,5,1)): ax[0][0].add_patch(r)
        if io_channel in list(range(5,9,1)): ax[0][1].add_patch(r)
        if io_channel in list(range(9,13,1)): ax[0][2].add_patch(r)
        if io_channel in list(range(13,17,1)): ax[0][3].add_patch(r)
        if io_channel in list(range(17,21,1)): ax[1][0].add_patch(r)
        if io_channel in list(range(21,25,1)): ax[1][1].add_patch(r)
        if io_channel in list(range(25,29,1)): ax[1][2].add_patch(r)
        if io_channel in list(range(29,33,1)): ax[1][3].add_patch(r)
    plt.tight_layout()
    if show==True: plt.show()
    if show==False: plt.savefig(prefix+'_'+'tileXY'+'_'+metric+'.png')
    return


def plot_eight_tile_pixel_trim_xy(d, prefix, geo, chip_pix, \
                                  vertical_lines, horizontal_lines, pitch, \
                                  rangeMin=0, rangeMax=31, show=False):
    fig, ax = eight_tile_xy(geo, chip_pix, vertical_lines, \
                            horizontal_lines, pitch)
    for key in d.keys():
        for channel in range(len(d[key]['trim_dac'])):
            r = find_pixel_xy_from_chip_key_channel(key, channel, \
                                                    d[key]['trim_dac'][channel]/rangeMax, \
                                                    geo, chip_pix, pitch,'k')
            if r==-1: continue
            io_channel = utility_base.chip_key_to_io_channel(key)
            if io_channel in list(range(1,5,1)): ax[0][0].add_patch(r)
            if io_channel in list(range(5,9,1)): ax[0][1].add_patch(r)
            if io_channel in list(range(9,13,1)): ax[0][2].add_patch(r)
            if io_channel in list(range(13,17,1)): ax[0][3].add_patch(r)
            if io_channel in list(range(17,21,1)): ax[1][0].add_patch(r)
            if io_channel in list(range(21,25,1)): ax[1][1].add_patch(r)
            if io_channel in list(range(25,29,1)): ax[1][2].add_patch(r)
            if io_channel in list(range(29,33,1)): ax[1][3].add_patch(r)
    plt.tight_layout()
    if show==True: plt.show()
    if show==False: plt.savefig(prefix+'_pixel_trim_DAC_'+'tileXY'+'.png')
    return



def plot_eight_tile_threshold_mV(d, prefix, geo, chip_pix, \
                                 vertical_lines, horizontal_lines, \
                                 pitch, vdda=1700., cryo=True, show=False):
    fig, ax = eight_tile_xy(geo, chip_pix, vertical_lines, \
                            horizontal_lines, pitch)
    if cryo==False:
        a=[d[key]['global_dac']+210+d[key]['trim_dac'][channel]*1.45\
        for key in d.keys() for channel in range(len(d[key]['trim_dac']))]
    if cryo==True:
        a=[d[key]['global_dac']+465+d[key]['trim_dac'][channel]*2.34\
        for key in d.keys() for channel in range(len(d[key]['trim_dac']))]
    minRange=min(a)
    maxRange=max(a)
    diffRange=maxRange-minRange
    for key in d.keys():
        for channel in range(len(d[key]['trim_dac'])):
            if cryo==False:value = d[key]['global_dac']+210+\
               d[key]['trim_dac'][channel]*1.45
            if cryo==True: value = d[key]['global_dac']+465+\
               d[key]['trim_dac'][channel]*2.34
            value= (value-minRange)/diffRange
            if value>1: value=1.
            r = find_pixel_xy_from_chip_key_channel(key, channel, value, \
                                                    geo, chip_pix, pitch,'k')
            if r==-1: continue
            io_channel = utility_base.chip_key_to_io_channel(key)
            if io_channel in list(range(1,5,1)): ax[0][0].add_patch(r)
            if io_channel in list(range(5,9,1)): ax[0][1].add_patch(r)
            if io_channel in list(range(9,13,1)): ax[0][2].add_patch(r)
            if io_channel in list(range(13,17,1)): ax[0][3].add_patch(r)
            if io_channel in list(range(17,21,1)): ax[1][0].add_patch(r)
            if io_channel in list(range(21,25,1)): ax[1][1].add_patch(r)
            if io_channel in list(range(25,29,1)): ax[1][2].add_patch(r)
            if io_channel in list(range(29,33,1)): ax[1][3].add_patch(r)
    plt.tight_layout()
    if show==True: plt.show()
    if show==False: plt.savefig(prefix+'_threshold_mV_'+'tileXY'+'.png')
    return



def plot_eight_tile_disable_xy(d1, d2, prefix, geo, chip_pix, \
                               vertical_lines, horizontal_lines, pitch, \
                               show=False):
    fig, ax = eight_tile_xy(geo, chip_pix, vertical_lines, \
                            horizontal_lines, pitch)
    value=1.0
    for key in d1.keys():
        for channel in d1[key]:
            r = find_pixel_xy_from_chip_key_channel(key, channel, value, geo, \
                                                    chip_pix, pitch,'r')
            if r==-1: continue
            io_channel = utility_base.chip_key_to_io_channel(key)
            if io_channel in list(range(1,5,1)): ax[0][0].add_patch(r)
            if io_channel in list(range(5,9,1)): ax[0][1].add_patch(r)
            if io_channel in list(range(9,13,1)): ax[0][2].add_patch(r)
            if io_channel in list(range(13,17,1)): ax[0][3].add_patch(r)
            if io_channel in list(range(17,21,1)): ax[1][0].add_patch(r)
            if io_channel in list(range(21,25,1)): ax[1][1].add_patch(r)
            if io_channel in list(range(25,29,1)): ax[1][2].add_patch(r)
            if io_channel in list(range(29,33,1)): ax[1][3].add_patch(r)
    for key in d2.keys():
        for channel in d2[key]:
            r = find_pixel_xy_from_chip_key_channel(key, channel, value, geo, \
                                                    chip_pix, pitch,'orange')
            if r==-1: continue
            io_channel = utility_base.chip_key_to_io_channel(key)
            if io_channel in list(range(1,5,1)): ax[0][0].add_patch(r)
            if io_channel in list(range(5,9,1)): ax[0][1].add_patch(r)
            if io_channel in list(range(9,13,1)): ax[0][2].add_patch(r)
            if io_channel in list(range(13,17,1)): ax[0][3].add_patch(r)
            if io_channel in list(range(17,21,1)): ax[1][0].add_patch(r)
            if io_channel in list(range(21,25,1)): ax[1][1].add_patch(r)
            if io_channel in list(range(25,29,1)): ax[1][2].add_patch(r)
            if io_channel in list(range(29,33,1)): ax[1][3].add_patch(r)
    plt.tight_layout()
    if show==True: plt.show()
    if show==False: plt.savefig(prefix+'_'+'disabled_8tileXY.png')
    return



def find_pixel_xy_from_unique(key, value, geo, chip_pix, pitch, \
                              rangeMin, rangeMax):
    channel_id = utility_base.unique_to_channel_id(key)
    if channel_id>63: r=-1; return r
    chip_id = utility_base.unique_to_chip_id(key)
    if chip_id<11 or chip_id>110: r=-1; return r
    x = geo['pixels'][chip_pix[chip_id][channel_id]][1]
    y = geo['pixels'][chip_pix[chip_id][channel_id]][2]
    weight = value/rangeMax
    if weight>1.0: weight=1.0
    r = Rectangle( ( x-(pitch/2.), y-(pitch/2.) ), pitch, pitch, \
                   color='k', alpha=weight )
    return r



def find_pixel_xy_from_chip_key_channel(key, channel_id, value, geo, chip_pix, 
                                        pitch, color):
    if channel_id>63: r=-1; return r
    chip_id = utility_base.chip_key_to_chip_id(key)
    if chip_id<11 or chip_id>110: r=-1; return r
    x = geo['pixels'][chip_pix[chip_id][channel_id]][1]
    y = geo['pixels'][chip_pix[chip_id][channel_id]][2]
    weight = value
    r = Rectangle( ( x-(pitch/2.), y-(pitch/2.) ), pitch, pitch, \
                   color=color, alpha=weight )
    return r    
        



def plot_2d(d, metric, element, prefix):
    x, y = [[] for i in range(2)]
    ctr={}
    for key in d.keys():
        if element=='chip_key': e=utility_base.unique_to_chip_key(key)
        elif element=='io_group': e=utility_base.unique_to_io_group(key)
        elif element=='io_channel': e=utility_base.unique_to_io_channel(key)
        elif element=='chip_id': e=utility_base.unique_to_chip_id(key)
        elif element=='channel_id': e=utility_base.unique_to_channel_id(key)
        y.append(e)
        x.append(d[key])
        if e not in ctr: ctr[e]=0
        ctr[e]+=1

    ybins=None
    if element=='chip_key': ybins=np.linspace(0, len(ctr.keys()),\
                                              len(ctr.keys())+1)
    else: ybins=np.linspace(min(ctr.keys()), max(ctr.keys()), \
                            (max(ctr.keys())-min(ctr.keys()))+1)
    xbins=np.linspace(int(min(x)), int(max(x)), int(max(x)-min(x))+1)

    fig, ax = plt.subplots(figsize=(8,6))
    ax.hist2d(x, y, bins=[xbins, ybins], norm=LogNorm())
    ax.set_xlabel(metric)
    ax.set_ylabel(element)
    ax.grid(True)
    plt.show()
#    plt.savefig(prefix+'_'+element+'_'+metric+'.png')                         
    return


def plot_1d_by_tile(d, metric, prefix, linear=False):
    if linear==False: xbins=np.linspace(0,255,256)
    if linear==True: xbins=np.linspace(0,10,41)
    fig, ax = plt.subplots(figsize=(10,6))
    for key in d.keys():
        ax.hist(d[key], bins=xbins, histtype='step', label=str(key))
    ax.set_xlabel(metric)
    ax.set_ylabel('channel count')
    ax.set_yscale('log')
    if linear==False: ax.set_xscale('log')
    if linear==True: ax.set_xlim(0,10)
    ax.grid(True)
    ax.legend(title='Tile')
    plt.savefig(prefix+'_1D_'+metric+'.png')
    return


def plot_1d(d, metric, prefix):
    fig, ax = plt.subplots(figsize=(8,6))
    x=[d[key] for key in d.keys()]
    xbins=np.linspace(int(min(x)), int(max(x)), int(max(x)-min(x))+1)
    ax.hist(x, bins=xbins, histtype='step')
    ax.set_xlabel(metric)
    ax.set_ylabel('channel count')
    ax.set_yscale('log')
    ax.grid(True)
    plt.savefig(prefix+'_'+metric+'.png')
    return


def plot_global_dac(d, prefix):
    g=[d[key]['global_dac'] for key in d.keys()]
    hmin=min(g)
    hmax=max(g)
    nbins=1+(hmax-hmin)
    fig, ax = plt.subplots(figsize=(8,6))
    ax.hist(g,bins=np.linspace(hmin,hmax,nbins),histtype='step')
    ax.set_xlabel('Global DAC')
    ax.set_ylabel('ASIC Count')
    plt.savefig(prefix+'_global_DAC.png')
    return



def plot_pixel_trim_dac(d, prefix):
    p=[d[key]['trim_dac'][i] for key in d.keys() \
       for i in range(len(d[key]['trim_dac'])) \
       if d[key]['channel_mask'][i]==0]
    nbins=np.linspace(0,31,32)
    fig, ax = plt.subplots(figsize=(8,6))
    ax.hist(p,bins=nbins,histtype='step')
    ax.set_xlabel('Pixel Trim DAC')
    ax.set_ylabel('Channel Count')
    #ax.set_yscale('log')
    plt.savefig(prefix+'_pixel_trim_DAC.png')
    return
