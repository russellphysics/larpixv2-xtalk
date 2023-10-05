import h5py
import numpy as np
import matplotlib.pyplot as plt
import glob
import argparse

_default_input_path='/home/brussell/xtalk/run24/'
_default_min_dac=20
_default_max_dac=60

def tick_function(X):
    mV=210+(1800/256.)*X
    return ["%.0f" % v for v in mV]

def main(input_path=_default_input_path, \
         min_dac=_default_min_dac, \
         max_dac=_default_max_dac, \
         **kwargs):

    select_run=int(_default_input_path.split("run")[-1].split("/")[0])
    d={}
    for filename in glob.glob(input_path+'packet*.h5'):
        run=int(filename.split("run")[-1].split("/")[0])
        asic=filename.split("v2")[-1].split('_')[0]
        chip=int(filename.split("key-1-")[-1].split("-")[1])
        channel=int(filename.split("key-1-")[-1].split("-")[2].split("_")[0])
        gdac=int(filename.split("dac-")[-1].split("_")[0])
        

        f = h5py.File(filename,'r')
#        valid_mask=f['packets']['valid_parity']==1
        type_mask=f['packets']['packet_type']==0
        channel_mask=f['packets']['channel_id']==channel
        chip_mask=f['packets']['chip_id']==chip
#        mask=np.logical_and(valid_mask,\
#                            np.logical_and(type_mask,\
#                                           np.logical_and(channel_mask,\
#                                                          chip_mask)))
        mask=np.logical_and(type_mask, np.logical_and(channel_mask,chip_mask))
        adc=f['packets'][mask]['dataword']
        print(len(adc))
#        print('global DAC: ',gdac,'\tmean ADC: ',np.mean(adc),'\t',len(adc))
        if len(adc)<1:
            d[gdac]=dict(
                run=run,
                mean=0,
                std=0,
                rate=0,
                asic=asic,
                chip=chip,
                channel=channel)
        else:
            d[gdac]=dict(
                run=run,
                mean=np.mean(adc),
                std=np.std(adc),
                rate=len(adc)/1.,
                asic=asic,
                chip=chip,
                channel=channel)

    valid_gdac=[gd for gd in range(min_dac,max_dac+1,1) if gd in d.keys()]


    fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(15,6))
    ax[0].plot([k for k in valid_gdac],
               [d[k]['mean'] for k in valid_gdac if d[k]['run']==select_run],
               'bo', label=str(select_run))
    ax0twinX=ax[0].twinx()
    ax0twinX.plot([k for k in valid_gdac],
               [d[k]['std'] for k in valid_gdac if d[k]['run']==select_run],
                  'r*')
    ax[1].plot([k for k in valid_gdac],
               [d[k]['rate'] for k in valid_gdac if d[k]['run']==select_run],
               'ko', label=str(select_run))

    new_tick_locations=np.array(np.linspace(min_dac,max_dac+1,10))

    for i in range(2):
        ax[i].grid(True)
        ax[i].set_xlabel('Global Threshold DAC')
        if i==0: ax[i].set_ylabel('Dataword Mean [ADC]', color='b')
        if i==1:
            ax[i].set_ylabel('Packet Rate [Hz]')
            ax[i].set_yscale('log')
    ax0twinX.set_ylabel('Dataword Standard Deviation [ADC]', color='r')
    ax0twinY=ax[0].twiny()
    ax0twinY.set_xlim(ax[0].get_xlim())
    ax0twinY.set_xticks(new_tick_locations)
    ax0twinY.set_xticklabels(tick_function(new_tick_locations))
    ax0twinY.set_xlabel('Approximate Channel Threshold [mV]')
    ax1twinY=ax[1].twiny()
    ax1twinY.set_xlim(ax[1].get_xlim())
    ax1twinY.set_xticks(new_tick_locations)
    ax1twinY.set_xticklabels(tick_function(new_tick_locations))
    ax1twinY.set_xlabel('Approximate Channel Threshold [mV]')
    plt.tight_layout()
    plt.savefig('response_xtalk.png')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--input_path', default=_default_input_path, \
                        type=str, help='''Input file path''')
    parser.add_argument('--min_dac', default=_default_min_dac, \
                        type=int, help='''Minimum global DAC''')
    parser.add_argument('--max_dac', default=_default_max_dac, \
                        type=int, help='''Maximum global DAC''')
    args=parser.parse_args()
    main(**vars(args))
