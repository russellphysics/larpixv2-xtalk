import larpix
from base import utility_base
import numpy as np
import h5py
import json
import glob

def find_pixel_trim_adc(target, chip_global, pedestal, \
                    vdda, vref_dac, vcm_dac, cryo=True, adc_slope=None,\
                    ref_adc=None, global_ref=None, trim_ref=None,trim_scale_dict=None, global_scale_dict=None, bits=256):
    result={}
    found_keys=0
    for chip_key in pedestal.keys():
        adc=0
        keys = chip_key.split('-')
        iog, ioch, chid = int(keys[0]), int(keys[1]), int(keys[2])
        tile=utility_base.io_channel_to_tile(ioch)
        trims=[]
        _global=[]
        lookup_key = '{}-{}-{}'.format(iog, 4*tile, chid)
        if not ( (lookup_key in trim_scale_dict.keys()) and (lookup_key in global_scale_dict.keys()) ): 
            #print('not found!!!')
            trims=[2.34]*64
            _globals=[ (vdda/bits)/adc_slope ]*64
        else:
            found_keys+=1
            trims=trim_scale_dict[lookup_key]
            global_slopes=global_scale_dict[lookup_key]
            adc = ref_adc[lookup_key][0]

        if not lookup_key in ref_adc.keys(): continue
        
        threshold_global=chip_global[chip_key]
                
        if chip_key not in result: result[chip_key]=[0]*64
        for channel_id in range(64): 
            
            global_slope=_globals[channel_id]
            global_slope = global_slope if global_slope < 6.0 else 6.0
            global_slope = global_slope if global_slope > 0.2 else 0.2

            trim_scale=trims[channel_id] if trims[channel_id] > 0.2 else 0.2
            trim_scale=trim_scale if trim_scale < 1 else 1
            
            ped_adc = pedestal[chip_key][channel_id][0]
            
           
            target_adc = target/adc_slope + ped_adc
            

            delta_adc = target_adc - (adc + global_slope*(threshold_global-global_ref))

            delta_trim_dac = delta_adc/trim_scale

            dac = delta_trim_dac+trim_ref
            
            if dac<=0: 
                dac=0
            if dac>31:
                dac=31
            
            if adc==0:
                dac=31 
            result[chip_key][channel_id]=int(dac)
        
            #print('global dac:', global_slope)
            #print('\tped_adc:', ped_adc, '\tcalo_adc:', adc, '\delta_adc:', delta_adc, '\ttrim_scale:', trim_scale)
            #print('target_adc:', target_adc, '\tdelta_trim_dac:', delta_trim_dac, '\tdac:', dac)
    print('found keys:', found_keys)
    return result, [20]*64

def find_pixel_trim(target, chip_global, pedestal, \
                    vdda, vref_dac, vcm_dac, cryo=True, \
                    calo_threshold=None, calo_measured=None, trim_scale_dict=None, offset_dict=None):
    result={}
    calibrated = 0
    gain=0.2210 #ke-/mV
    trim_scale=1.45; offset=210
    if cryo==True: _default_trim_scale=2.34; _default_offset=363 #465
    for chip_key in pedestal.keys():
        if chip_key not in result: result[chip_key]=[0]*64
        keys = chip_key.split('-')
        iog, ioch, chid = int(keys[0]), int(keys[1]), int(keys[2])
        tile=utility_base.io_channel_to_tile(ioch)
        possible_io_channel=utility_base.tile_to_io_channel([tile])
        found=False
        if not calo_measured is None:
            if str(utility_base.unique(iog, ioch, chid, 0)) in calo_measured.keys(): found=True
        chid = utility_base.chip_key_to_chip_id(chip_key)
        trims=[]
        offsets=[]
        lookup_key = '{}-{}-{}'.format(iog, 4*tile, chid)
        if not (lookup_key in trim_scale_dict.keys() and (lookup_key in offset_dict.keys())): 
            trims=[2.3]*64
            offsets=[360]*64
        else:
            trims=trim_scale_dict[lookup_key]
            offsets=offset_dict[lookup_key]
        
        channel_offsets = [0]*64
        if not calo_measured is None: 
            if lookup_key in calo_measured.keys() and not (calo_threshold is None):
                for i in range(64): 
                    if calo_measured[lookup_key][i] < 0:
                        calo_measured[lookup_key][i]=calo_threshold 

                channel_offset =  calo_threshold - np.array(calo_measured[lookup_key])
                calibrated += 1
                
    
        for channel_id in range(64): 
            channel_offset=channel_offsets[channel_id]
            trim_scale=trims[channel_id] if trims[channel_id] > 2 else 2
            trim_scale=trim_scale if trim_scale < 3.8 else 3.8
            offset=offsets[channel_id] if offsets[channel_id] > 315 else 315
            offset=offset if offset < 415 else 415

            ped_mV = utility_base.ADC_to_mV(pedestal[chip_key][channel_id][0], vdda, vref_dac, vcm_dac)

            #if not found: print(iog,ioch, possible_io_channel, chid, channel_id, unq)
            
            
            threshold_mV = ped_mV + target
            global_mV=chip_global[chip_key]*(vdda/2**8)+offset
           
            #print('target threshold:', threshold_mV, '\t global setting:', global_mV)
            diff=threshold_mV-global_mV
            diff=diff+channel_offset
            #print(channel_offset)
            dac=int(diff/trim_scale)
            if dac<=0: 
                dac=0
                #print(chip_key, channel_id, 'dac min out')
            if dac>31:
                dac=31
                #print(chip_key,' ',channel_id,\
                #      ' pixel trim DAC exceeded range')
            #print('ped:',ped_mV,'\tglobal mV:', global_mV, \
            #      'global DAC: ',chip_global[chip_key],\
            #      '\tpixel trim mV:',dac*trim_scale )
            #print('diff:', (global_mV+dac*trim_scale - ped_mV) )
            result[chip_key][channel_id]=dac

            #print('found dac', dac, 'using trim scale:', trim_scale, '\t offset:', offset)

    print('calibrated', calibrated, 'channel pixel trims!')
    return result

def debug_find_pixel_trim(target, chip_global, pedestal, \
                          vdda, vref_dac, vcm_dac, trim_scale, cryo=True):
    result={}
    offset=210
    if cryo==True: offset=363 #465
    for chip_key in pedestal.keys():
        if chip_key not in result: result[chip_key]=[0]*64
        for channel_id in range(64):
            ped_mV = utility_base.ADC_to_mV(pedestal[chip_key][channel_id][0], \
                                            vdda, vref_dac, vcm_dac)
            threshold_mV = ped_mV + target
            global_mV=chip_global[chip_key]*(vdda/2**8)+offset
            
            diff=threshold_mV-global_mV
            dac=int(diff/trim_scale)
            if dac<=0: 
                dac=0
                #print(chip_key, channel_id, 'dac min out')
            if dac>31:
                dac=31
                #print(chip_key,' ',channel_id,\
                #      ' pixel trim DAC exceeded range')
            print('ped:',ped_mV,'\tglobal mV:', global_mV, \
                  'global DAC: ',chip_global[chip_key],\
                  '\tpixel trim mV:',dac*trim_scale )
            print('diff:', (global_mV+dac*trim_scale - ped_mV) )
            result[chip_key][channel_id]=dac
    return result


def adc_dict(pedestal, disabled, vdda):
    result={}

    for chip_key in pedestal.keys():
        if chip_key not in result: result[chip_key]=(10000,-1)
        for channel_id in range(64):
            if chip_key in disabled.keys():
                if pedestal[chip_key][channel_id][0] < 0: continue
                if channel_id in disabled[chip_key]: continue
            adc = pedestal[chip_key][channel_id][0]
            
            if adc<result[chip_key][0]:
                result[chip_key]=(adc, result[chip_key][1])
            if adc>result[chip_key][1]:
                result[chip_key]=(result[chip_key][0], adc)
    return result


def dV_dict(pedestal, disabled, vdda, vref_dac, vcm_dac):
    result={}

    for chip_key in pedestal.keys():
        if chip_key not in result: result[chip_key]=(10000,-1)
        for channel_id in range(64):
            if chip_key in disabled.keys():
                if pedestal[chip_key][channel_id][0] < 0: continue
                if channel_id in disabled[chip_key]: continue
            mV = utility_base.ADC_to_mV(pedestal[chip_key][channel_id][0], \
                                        vdda, vref_dac, vcm_dac)
            #print(mV,pedestal[chip_key][channel_id][0] )
            if mV<result[chip_key][0]:
                result[chip_key]=(mV, result[chip_key][1])
            if mV>result[chip_key][1]:
                result[chip_key]=(result[chip_key][0], mV)
    return result



def debug_find_global_dac(d, vdda, target, trim_scale, bits=2**8, cryo=True):
    #target in mV
    offest=210
    if cryo==True: offset=363 #465
    result={}
    for key in d.keys():
        global_step=vdda/bits
        global_mV = target+d[key][1]-trim_scale*16
        global_DAC = int((global_mV-offset)/global_step)
        #min_global=int(round((d[key][0]-offset)/global_step)) #convert to DAC
        #max_global=int(round((d[key][1]-offset)/global_step)) #convert to DAC
        #print('min, max global DACs:', min_global, max_global)
        result[key] = global_DAC if global_DAC > 0 else 0
        print(d[key][1], global_mV, global_DAC)
    return result

def find_global_dac_adc(d, vdda, target, trim_scale_dict=None, global_scale_dict=None, bits=2**8, cryo=True, ref_adc=None, ref_trim=None, ref_global=None, adc_slope=None):
    #target in adc
    result={}
    found_keys=0
    _sum=0
    n=0
    for key in d.keys():
        keys = key.split('-')
        iog, ioch, chid = int(keys[0]), int(keys[1]), int(keys[2])
        tile=utility_base.io_channel_to_tile(ioch)
        trims=[]
        _globals=[]
        lookup_key = '{}-{}-{}'.format(iog, 4*tile, chid)
        if not (lookup_key in trim_scale_dict.keys() and lookup_key in global_scale_dict.keys()): 
            trims=[2.34]*64
            _globals=[vdda/bits]*64
        else:
            found_keys+=1
            trims=trim_scale_dict[lookup_key]
            _globals=global_scale_dict[lookup_key]
        if not lookup_key in ref_adc.keys():
            continue 
        
        trim_scale=np.median([val for val in trims if val>0 ]) 
        global_scale=np.median([val for val in _globals if val>0 ])
        ped_avg = (d[key][1]+d[key][0])/2 #NEEDS TO BE ADC
        mean_ref_adc=np.mean([val for val in ref_adc[lookup_key] if val>0 ])
        global_dac=-1

        #if (d[key][1]-d[key][0])<(32*min(trims)): #pixel trim range sufficient
        #    target_adc = target/adc_slope + ped_avg
        #    delta_adc = target_adc-mean_ref_adc-trim_scale*(16-ref_trim)
        #    delta_global_dac = delta_adc/global_scale
        #    global_dac = delta_global_dac+ref_global
        #else:
        if True:
            target_adc = target/adc_slope + d[key][1]
            delta_adc = target_adc - (mean_ref_adc + trim_scale*(31-ref_trim))
            delta_global_dac = delta_adc/global_scale
            global_dac = delta_global_dac+ref_global
        
        global_dac = global_dac if global_dac < 255 else 255
        result[key] = int(global_dac) if global_dac > 0 else 0
        _sum+= global_dac
        n+=1

    print('FOUND KEYS:', found_keys, '/', len(d.keys()) )
    return result, int(_sum/n)


def find_global_dac(d, vdda, target,   trim_scale_dict=None, offsets_dict=None, bits=2**8, cryo=True,):
    #target in mV
    #trim_scale=1.44; offest=210
    #if cryo==True: trim_scale=2.34; offset=363 #465
    result={}
    found_keys=0
    for key in d.keys():
        keys = key.split('-')
        iog, ioch, chid = int(keys[0]), int(keys[1]), int(keys[2])
        tile=utility_base.io_channel_to_tile(ioch)
        trims=[]
        offsets=[]
        lookup_key = '{}-{}-{}'.format(iog, 4*tile, chid)
        if not (lookup_key in trim_scale_dict.keys() and lookup_key in offsets_dict.keys()): 
            trims=[2.34]*64
            offsets=[360]*64
        else:
            found_keys+=1
            trims=trim_scale_dict[lookup_key]
            offsets=offsets_dict[lookup_key]
        
        offset=np.median( [val for val in offsets if val>0 ] )
        trim_scale=np.median([val for val in trims if val>0 ])
        global_step=vdda/bits
        global_mV = target+d[key][1]-trim_scale*16
        global_DAC = int((global_mV-offset)/global_step)
        #min_global=int(round((d[key][0]-offset)/global_step)) #convert to DAC
        #max_global=int(round((d[key][1]-offset)/global_step)) #convert to DAC
        #print('min, max global DACs:', min_global, max_global)
        result[key] = global_DAC if global_DAC > 0 else 0
    #    print(d[key][1], global_mV, global_DAC)
    

    print('FOUND KEYS:', found_keys, '/', len(d.keys()) )
    return result



def global_dac_from_pedestal(c, chip_pedestal, vdda=1700.):
    d={}
    global_dac_lsb = vdda/256.
    chip_config_pairs=[]
    for ck in chip_pedestal.keys():
        mV = utility_base.ADC_to_mV(vdda, c[ck].config.vref_dac, \
                                    c[ck].config.vcm_dac, \
                                    chip_pedestal[ck]['metric'])
        global_dac = int(round(mV/global_dac_lsb))
        d[ck]=global_dac
    return d



def chip_pedestal(adc, unique_id, disable, noise_cut):
    d=disable; 
    unique_id_set = np.unique(unique_id)

    channel_pedestal={}
    for i in unique_id_set:
        id_mask = unique_id == i
        masked_adc = adc[id_mask]        
        mu = np.mean(masked_adc)
        std = np.std(masked_adc)
        if len(masked_adc)<2 or std>noise_cut or mu>200. or mu==0.:
            ck=utility_base.unique_to_chip_key(i)
            if ck not in d: d[ck]=[]
            channel = int(utility_base.unique_to_channel_id(i))
            if channel not in d[ck]: d[ck].append(channel)
            continue
        channel_pedestal[i]=dict(mu=mu, std=std)

    temp, temp_mu, temp_std = [{} for i in range(3)]
    for i in channel_pedestal.keys():
        ck=utility_base.unique_to_chip_key(i)
        if ck not in temp:
            temp[ck], temp_mu[ck], temp_std[ck] = [[] for i in range(3)]
        temp[ck].append(channel_pedestal[i]['mu']+channel_pedestal[i]['std'])
        temp_mu[ck].append(channel_pedestal[i]['mu'])
        temp_std[ck].append(channel_pedestal[i]['std'])

    chip_pedestal={}
    for ck in temp.keys():
        chip_pedestal[ck]=dict( metric = np.mean(temp[ck]),
                                mu = np.mean(temp_mu[ck]),
                                median = np.median(temp_mu[ck]),
                                std = np.mean(temp_std[ck]) )
    return chip_pedestal, d
        


def parse_file(filename, packet_type):
    f = h5py.File(filename, 'r')
    data_mask=f['packets'][:]['packet_type']==packet_type
    valid_parity_mask=f['packets'][:]['valid_parity']==1
    mask = np.logical_and(data_mask, valid_parity_mask)
    adc=f['packets']['dataword'][mask]
    unique_id = utility_base.unique_channel_id(f['packets'][mask])
    return adc, unique_id



def metric_by_tile(adc, unique_id, metric):
    d = {}
    unique_id_set = np.unique(unique_id)
    for i in unique_id_set:
        id_mask = unique_id == i
        io_channel = utility_base.unique_to_io_channel(i)
        tile = utility_base.io_channel_to_tile(io_channel)
        if tile not in d: d[tile]=[]
        masked_adc = adc[id_mask]
        value=0
        if metric=='mean': value = np.mean(masked_adc)
        if metric=='std': value = np.std(masked_adc)
        d[tile].append(value)
    return d



def metric(adc, unique_id, metric):
    d = {}
    unique_id_set = np.unique(unique_id)
    for i in unique_id_set:
        id_mask = unique_id == i
        masked_adc = adc[id_mask]
        value=0
        if metric=='mean': value = np.mean(masked_adc)
        if metric=='std': value = np.std(masked_adc)
        d[i]=value
    return d



def metric_cut(adc, unique_id, metric, cut, disable):
    d=disable
    unique_id_set = np.unique(unique_id)
    for i in unique_id_set:
        id_mask = unique_id == i
        masked_adc = adc[id_mask]
        value=0
        if metric=='mean': value = np.mean(masked_adc)
        if metric=='std': value = np.std(masked_adc)
        if value>cut:
            chip_key=utility_base.unique_to_chip_key(i)
            if chip_key not in d: d[chip_key]=[]
            channel = int(utility_base.unique_to_channel_id(i))
            if channel not in d[chip_key]:
                d[chip_key].append(channel)
    return d
    


def asic_config_parse(input_dir):
    d={}
    for filename in glob.glob(input_dir+'*.json'):
        data = dict()
        ck=filename.split('config-')[-1].split('-2022')[0]
        with open(filename,'r') as f: data = json.load(f)
        trim_dac = data['register_values']['pixel_trim_dac']
        global_dac = data['register_values']['threshold_global']
        channel_mask = data['register_values']['channel_mask']
        d[ck]=dict(trim_dac=trim_dac,
                   global_dac=global_dac,
                   channel_mask=channel_mask)
    return d


