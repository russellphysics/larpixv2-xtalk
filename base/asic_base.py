import larpix
from base import pacman_base
from base import utility_base
from copy import deepcopy
#from memory_profiler import profile
import json
import time
import numpy as np
#from timebudget import timebudget
#import asyncio
from base import ana_base
#@profile

v2a_nonrouted_channels=[6, 7, 8, 9, 22, 23, 24, 25, 38, 39, 40, 54, 55, 56, 57]


def regulate_rate_fractional(c, io, io_group, set_rate, disable, sample_time=0.5, ioch=None):
    return disable
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = []
    if ioch==None: 
        pacman_tile = utility_base.all_chip_key_to_tile(c, io_group) 
        pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    else:
        ##print(ioch, type(ioch))
        pacman_base.enable_pacman_uart_from_io_channel(io, io_group, ioch)
        time.sleep(1)
    flag=True
    counter=0
    while flag and counter<5:
        counter+=1
        c.reads=[]
        #utility_base.flush_data(c) # explodes memory usage
        c.multi_read_configuration(c.chips, timeout=sample_time, \
                                   message='rate check')
        triggers=c.reads[-1].extract('chip_key', 'channel_id', packet_type=0)
        c.reads=[]
        count=0
        total_rate = len(triggers)/sample_time
        print('Total trigger rate:', total_rate, 'Hz')
        chips_to_enforce=[]
        for chip_key, channel in set(map(tuple,triggers)):
            if chip_key not in c.chips: continue
            rate = triggers.count([chip_key,channel])/sample_time
            if rate/total_rate>set_rate:
                disable_channel_csa_trigger(c, chip_key, channel)
                if chip_key not in disable: disable[chip_key]=[]
                disable[chip_key].append(channel)
                c[chip_key].config.channel_mask[channel]=1
                c[chip_key].config.csa_enable[channel]=0
                count+=1
                print('DISABLE ',chip_key,'  ',channel,'\trate: ',rate,' Hz')
        c.reads=[] 
        c.enforce_configuration(chips_to_enforce, timeout=0.02, n=5)
        dname = 'disable-current.json'
        print('Saving disabled list: {}'.format(dname))
        new_disable = {}
        for key in disable.keys(): new_disable[str(key)]=disable[key]
        with open(dname, 'w') as f: json.dump(new_disable, f)
        if count==0: flag=False
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    c.reads=[]
    return disable


def regulate_rate(c, io, io_group, set_rate, disable, sample_time=0.5):
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    flag=True
    while flag:
        c.reads=[]
        #utility_base.flush_data(c) # explodes memory usage
        c.multi_read_configuration(c.chips, timeout=sample_time, \
                                   message='rate check')
        triggers=c.reads[-1].extract('chip_key', 'channel_id', packet_type=0)
        c.reads=[]
        count=0
        for chip_key, channel in set(map(tuple,triggers)):
            if chip_key not in c.chips: continue
            rate = triggers.count([chip_key,channel])/sample_time
            if rate>set_rate:
                disable_channel_csa_trigger(c, chip_key, channel)
                if chip_key not in disable: disable[chip_key]=[]
                disable[chip_key].append(channel)
                count+=1
                print('DISABLE ',chip_key,'  ',channel,'\trate: ',rate,' Hz')
        c.reads=[]
        if count==0: flag=False
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    c.reads=[]
    return disable


def update_chip(c, status):
    chip_register_pairs = []
    for chip_key in status.keys():
        chip_register_pairs.append( (chip_key, \
                                     list(range(64))+ \
                                     list(range(66,74))+\
                                     list(range(131,139) ) ))
        c[chip_key].config.pixel_trim_dac = status[chip_key]['pixel_trim']
        for channel in range(64):
            if status[chip_key]['disable'][channel] == True or \
               status[chip_key]['active'][channel] == False:
                c[chip_key].config.csa_enable[channel] = 0
                c[chip_key].config.channel_mask[channel] = 1
    c.multi_write_configuration(chip_register_pairs, connection_delay=0.001)
    return


def enable_io(c, io, io_group):
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    return


def disable_io(c, io, io_group):
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    


def toggle_global_dac(c, io, io_group, set_rate, sample_time, \
                      initial_global=25):
    enable_io(c, io, io_group)
    for ck in c.chips:
        c[ck].config.threshold_global=initial_global
        c.write_configuration(ck,'threshold_global')

    flag=True
    while flag:
        c.reads=[]
        c.multi_read_configuration(c.chips, timeout=sample_time, \
                                   message='rate check')
        triggers=c.reads[-1].extract('chip_key', 'channel_id', packet_type=0)
        count=0
        for chip_key, channel in set(map(tuple,triggers)):
            if chip_key not in c.chips: continue
            rate = triggers.count([chip_key,channel])/sample_time
            if rate>set_rate:
                if rate>100*set_rate:
                    c[chip_key].config.channel_mask[channel]=0
                    c.write_configuration(chip_key,'channel_mask')
                    print('DISABLE ',chip_key,'  ',channel,'\trate: ',\
                          rate,' Hz')
                c[chip_key].config.threshold_global=c[chip_key].config.threshold_global+1
                c.write_configuration(chip_key,'threshold_global')
                print(chip_key,' threshold DAC ',\
                      c[chip_key].config.threshold_global)
        c.reads=[]
        if count==0: flag=False
    c.reads=[]
    disable_io(c, io, io_group)
    return


def toggle_pixel_trim_dac(c, io, io_group, disable, set_rate, \
                          verbose=True, sample_time=0.5):
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    status = {}
    for chip_key in c.chips:
        l = list(c[chip_key].config.pixel_trim_dac)
        status[chip_key] = dict( pixel_trim=l,
                                 active=[True]*64,
                                 disable=[False]*64)
        if chip_key in disable:
            for channel in disable[chip_key]:
                status[chip_key]['active'][channel] = False
                status[chip_key]['disable'][channel] = True

    iter_ctr = 0
    flag = True
    while flag:
        c.reads=[]
        #utility_base.flush_data(c)
        timeStart = time.time()
        iter_ctr += 1
        c.multi_read_configuration(c.chips, timeout=sample_time, \
                                   message='rate check')
        triggers = c.reads[-1].extract('chip_key','channel_id',packet_type=0)
        print('total rate={}Hz'.format(len(triggers)/sample_time))
        fired_channels = {}
        for chip_key, channel in set(map(tuple,triggers)):
            if chip_key not in fired_channels: fired_channels[chip_key] = []
            fired_channels[chip_key].append(channel)
            rate = triggers.count([chip_key,channel])/sample_time
            if chip_key not in status.keys(): continue
            if status[chip_key]['active'][channel] == False: continue

            if rate >= set_rate:
                if verbose:
                    print(chip_key,' channel ',channel,' pixel trim',\
                          status[chip_key]['pixel_trim'][channel],\
                          'below noise floor -- increasing trim')
                status[chip_key]['pixel_trim'][channel] += 1
                if status[chip_key]['pixel_trim'][channel]>31:
                    status[chip_key]['pixel_trim'][channel] = 31
                    status[chip_key]['disable'][channel] = True
                    status[chip_key]['active'][channel] = False
                    if chip_key not in disable: disable[chip_key]=[]
                    disable[chip_key].append(channel)
                    if verbose:
                        print(chip_key,' channel ',channel,\
                              'pixel trim maxed out below noise floor!!! \
                              -- channel CSA disabled')
                else:
                    status[chip_key]['active'][channel] = False
                    if verbose:
                        print('pixel trim set at',\
                              status[chip_key]['pixel_trim'][channel])
            else:
                status[chip_key]['pixel_trim'][channel] -= 1
                if status[chip_key]['pixel_trim'][channel]<0:
                    status[chip_key]['pixel_trim'][channel] = 0
                    status[chip_key]['active'][channel] = False
                    if verbose:
                        print('pixel trim bottomed out above noise floor!!!')

        for chip_key in c.chips:
            if status[chip_key]['active'] == [False]*64: continue
            for channel in list(range(64)):
                if status[chip_key]['active'][channel] == False: continue
                if chip_key in fired_channels:
                    if channel in fired_channels[chip_key]: continue
                status[chip_key]['pixel_trim'][channel] -= 1
                if status[chip_key]['pixel_trim'][channel]<0:
                    status[chip_key]['pixel_trim'][channel] = 0
                    status[chip_key]['active'][channel] = False
                    if verbose:
                        print('pixel trim bottomed out above noise floor!!!')

        update_chip(c, status)
        count = 0
        for chip_key in status:
            if True in status[chip_key]['active']: count+=1
            if count == 1: break
        if count == 0: flag = False
        timeEnd = time.time()-timeStart
        print('iteration ', iter_ctr,\
              ' processing time %.3f seconds\n\n'%timeEnd)
    c.reads=[]
    #utility_base.flush_data(c)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return disable



def global_dac_from_file(c, global_json):
    global_dac=dict()
    with open(global_json,'r') as f: global_dac=json.load(f)

    chip_config_pairs=[]
    for ck in global_dac:
        if ck not in c.chips: continue
        c[ck].config.threshold_global=global_dac[ck]
        chip_config_pairs,append((chip_key,[64]))
    c.multi_write_configuration(chip_config_pairs)
                                   
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    return ok, diff


#@profile
def enable_selftrigger_config(c, io, io_group, periodic_reset_cycles=64):
    io.set_reg(0x18, 0, io_group=io_group)
    chip_config_pairs=[]
    for chip_key, chip in c.chips.items():
        initial_config=deepcopy(chip.config)
        chip.config.threshold_global = 255
        chip.config.pixel_trim_dac = [31]*64
        chip.config.enable_periodic_reset=1
        chip.config.enable_rolling_periodic_reset=1
        chip.config.periodic_reset_cycles=periodic_reset_cycles
        chip.config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    c.reads=[]
    return ok, diff



def enable_pedestal_config(c, io_group, \
                           vref_dac, vcm_dac, \
                           periodic_trigger_cycles, \
                           periodic_reset_cycles):
    for chip_key, chip in c.chips.items():
        if chip_key.io_group!=io_group: continue
        chip.config.vref_dac=vref_dac
        chip.config.vcm_dac=vcm_dac
        chip.config.enable_periodic_trigger=1
        chip.config.enable_rolling_periodic_trigger=1
        chip.config.periodic_trigger_cycles=periodic_trigger_cycles
        chip.config.enable_periodic_reset=1
        chip.config.enable_rolling_periodic_reset=0
        chip.config.periodic_reset_cycles=periodic_reset_cycles
        chip.config.enable_hit_veto=0
        chip.config.enable_periodic_trigger_veto=0
        chip.config.periodic_trigger_mask=[0]*64
    return c

def enable_pedestal_config_by_io_channel(c, io, chips, vref_dac=185, \
                                         vcm_dac=50, \
                                         periodic_trigger_cycles=100000, \
                                         periodic_reset_cycles=4096):
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.enable_periodic_trigger=1
        c[chip_key].config.enable_rolling_periodic_trigger=1
        c[chip_key].config.periodic_trigger_cycles=periodic_trigger_cycles
        c[chip_key].config.enable_periodic_reset=1
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.periodic_reset_cycles=periodic_reset_cycles
        c[chip_key].config.enable_hit_veto=0
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    
    all_ok = True
    all_diff = {}
    if True:
        ok, diff = c.enforce_registers(chip_reg_pairs,timeout=0.1, n=10, n_verify=2)
        if not ok:
            all_ok = ok
            all_diff.update(diff)
    
    if all_ok: 
        print('Done')
    else:
        print(all_diff)

    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff

def enable_pedestal_adc_burst_config_by_io_channel(c, io, chips, vref_dac=185, \
                                         vcm_dac=50, \
                                         periodic_trigger_cycles=2000000, \
                                         periodic_reset_cycles=4096, \
                                         adc_burst_length=255):
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.enable_periodic_trigger=1
        c[chip_key].config.enable_rolling_periodic_trigger=1
        c[chip_key].config.periodic_trigger_cycles=periodic_trigger_cycles
        c[chip_key].config.enable_periodic_reset=1
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.periodic_reset_cycles=periodic_reset_cycles
        c[chip_key].config.enable_hit_veto=0
        c[chip_key].config.adc_burst_length=adc_burst_length
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    for chip_key in chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff



def debug_enable_response_trigger_config_by_io_channel(c, io, chips, global_dac,\
                                                       vref_dac=185, vcm_dac=50, periodic_reset_cycles=6400, \
                                                       tx_diff=0, tx_slice=15):    

    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in c.chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.threshold_global=global_dac
        
        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.enable_periodic_reset=1
        c[chip_key].config.enable_rolling_periodic_reset=1
        c[chip_key].config.periodic_reset_cycles=periodic_reset_cycles
        c[chip_key].config.enable_hit_veto=0

        c[chip_key].config.i_tx_diff0=tx_diff
        c[chip_key].config.i_tx_diff1=tx_diff
        c[chip_key].config.i_tx_diff2=tx_diff
        c[chip_key].config.i_tx_diff3=tx_diff

        c[chip_key].config.tx_slices0=tx_slice
        c[chip_key].config.tx_slices1=tx_slice
        c[chip_key].config.tx_slices2=tx_slice
        c[chip_key].config.tx_slices3=tx_slice
        
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    for chip_key in chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff

def debug_disable_response_trigger_config_by_io_channel(c, io, chips):

    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in c.chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.channel_mask=[0]*64
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    for chip_key in chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff

def enable_fixed_register_trigger_config_by_io_channel(c, io, chips,\
                                                 vref_dac=185, \
                                                 vcm_dac=50, vdda=1650.,\
                                                 periodic_reset_cycles=6400, \
                                                 pedestal=None,\
                                                 disabled=None,\
                                                 trim_dac=None, threshold_global=None, cryo=True):

    print('ENABLING CONFIG: trim_dac={}, global_threshold={}'.format(trim_dac, threshold_global) )
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.threshold_global=threshold_global
        c[chip_key].config.pixel_trim_dac=[trim_dac]*64
        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.enable_periodic_reset=0
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
    print(2**(chips[0].io_channel-1)) 
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    all_ok = True
    all_diff = {}
    for chip_key in chips:
        #ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
        ## DD 2023/01/30: Only check registers that were being altered (consider connection delay of 0.02)
        ok, diff = utility_base.reconcile_registers(c, chip_reg_pairs, verbose=False, timeout=0.1,
                                                    connection_delay=0.02, n=5, n_verify=5)
        if not ok:
            all_ok = ok
            all_diff.update(diff)
    
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return all_ok, all_diff


def enable_fixed_target_trigger_config_by_io_channel(c, io, chips, vref_dac=185, \
                                                 vcm_dac=50, vdda=1650.,\
                                                 periodic_reset_cycles=6400, \
                                                 pedestal=None,\
                                                 disabled=None,\
                                                 target=30, cryo=True, pixel_trim=None, global_offset=None, calo_threshold=None, calo_measured=None):
    

    print('TARGET VOLTAGE',target, 'mV ABOVE PEDESTAL' )
    mV_range=ana_base.dV_dict(pedestal, disabled, vdda, \
                              vref_dac, vcm_dac)
    chip_global=ana_base.find_global_dac(mV_range, vdda, target, pixel_trim, global_offset)

    chip_pixel=ana_base.find_pixel_trim(target, chip_global, pedestal, \
                                        vdda, vref_dac, vcm_dac, cryo, calo_threshold=calo_threshold,\
                                        calo_measured=calo_measured, trim_scale_dict=pixel_trim, offset_dict=global_offset)
    
    default_global_dac=int(sum([chip_global[kk] for kk in chip_global.keys()])/len(chip_global.keys()))#+8
    default_pixel_trim_dac = [20]*64
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        if not chip_key in chip_global: 
            # !!! make IO channel agnostic owing to different networks by
            # using IO group tile ID \
            tile=utility_base.io_channel_to_tile(chip_key.io_channel)
            possible_io_channel=utility_base.tile_to_io_channel([tile])
            found=False
            for ioc in possible_io_channel:
                if ioc==chip_key.io_channel: continue
                candidate = larpix.key.Key(chip_key.io_group, ioc, chip_key.chip_id)
                if candidate in chip_global:
                    c[chip_key].config.threshold_global=chip_global[candidate]
                    for channel in range(64):
                        c[chip_key].config.pixel_trim_dac[channel]=chip_pixel[candidate][channel]
                    found = True
                    break
            
            if not found:
                c[chip_key].config.threshold_global=default_global_dac
                c[chip_key].config.pixel_trim_dac=default_pixel_trim_dac
        else:
            c[chip_key].config.threshold_global=chip_global[chip_key]
            for channel in range(64):
                c[chip_key].config.pixel_trim_dac[channel]=chip_pixel[chip_key][channel]

        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.enable_periodic_reset=0
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    for chip_key in chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff


def enable_response_trigger_config_by_io_channel(c, io, chips, vref_dac=185, \
                                                 vcm_dac=50, vdda=1650.,\
                                                 periodic_reset_cycles=6400, \
                                                 pedestal=None,\
                                                 disabled=None,\
                                                 target=30, cryo=True,\
                                                 calo_threshold=None, global_offset=None, pixel_trim=None,\
                                                 calo_measured=None):
    
    print('TARGET VOLTAGE',target, 'mV ABOVE PEDESTAL' )
    mV_range=ana_base.dV_dict(pedestal, disabled, vdda, \
                              vref_dac, vcm_dac)
    

    chip_global=ana_base.find_global_dac(mV_range, vdda, target, pixel_trim, global_offset)

    chip_pixel=ana_base.find_pixel_trim(target, chip_global, pedestal, \
                                        vdda, vref_dac, vcm_dac, cryo, calo_threshold=calo_threshold,\
                                        calo_measured=calo_measured, trim_scale_dict=pixel_trim, offset_dict=global_offset)
    
    default_global_dac=int(sum([chip_global[kk] for kk in chip_global.keys()])/len(chip_global.keys()))#+8
    default_pixel_trim_dac = [20]*64
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        if not chip_key in chip_global: 
            # !!! make IO channel agnostic owing to different networks by
            # using IO group tile ID \
            tile=utility_base.io_channel_to_tile(chip_key.io_channel)
            possible_io_channel=utility_base.tile_to_io_channel([tile])
            found=False
            for ioc in possible_io_channel:
                if ioc==chip_key.io_channel: continue
                candidate = larpix.key.Key(chip_key.io_group, ioc, chip_key.chip_id)
                if candidate in chip_global:
                    c[chip_key].config.threshold_global=chip_global[candidate]
                    for channel in range(64):
                        c[chip_key].config.pixel_trim_dac[channel]=chip_pixel[candidate][channel]
                    found = True
                    break
            
            if not found:
                c[chip_key].config.threshold_global=default_global_dac
                c[chip_key].config.pixel_trim_dac=default_pixel_trim_dac
        else:
            c[chip_key].config.threshold_global=chip_global[chip_key]
            for channel in range(64):
                c[chip_key].config.pixel_trim_dac[channel]=chip_pixel[chip_key][channel]

        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        
        c[chip_key].config.enable_periodic_reset=0
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.periodic_reset_cycles=periodic_reset_cycles
        c[chip_key].config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    all_ok = True
    all_diff = {}
    for chip_key in chips:
        #ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
        ## DD 2023/01/30: Only check registers that were being altered
        ok, diff = utility_base.reconcile_registers(c, chip_reg_pairs, verbose=False, timeout=0.1,
                                                    connection_delay=0.02, n=5, n_verify=5)
        if not ok:
            all_ok = ok
            all_diff.update(diff)

    if all_ok: print('Done')
    #if not ok:
    #    print('Configuration error; re-enforcing correct registers on chips', diff.keys())
    #    ok, diff = c.enforce_configuration(list(diff.keys()), timeout=0.05, \
    #                                   connection_delay=0.01, \
    #                                   n=10, n_verify=10) 

    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return all_ok, all_diff


def enable_leakage_current_config(c, io, io_group, vref_dac=255, vcm_dac=50, \
                                  periodic_trigger_cycles=100000):
    io.set_reg(0x18, 0, io_group=io_group)
    chip_config_pairs=[]
    for chip_key, chip in c.chips.items():
        initial_config=deepcopy(chip.config)
        chip.config.vref_dac=vref_dac
        chip.config.vcm_dac=vcm_dac
        chip.config.threshold_global=255
        chip.config.pixel_trim_dac=[31]*64
        chip.config.enable_periodic_trigger=1
        chip.config.enable_rolling_periodic_trigger=1
        chip.config.periodic_trigger_cycles=periodic_trigger_cycles
        chip.config.enable_periodic_reset=0
        chip.config.enable_rolling_periodic_reset=0
        chip.config.enable_hit_veto=0
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    if not ok:
        print('Configuration error; re-enforcing correct registers on chips', diff.keys())
        ok, diff = c.enforce_configuration(list(diff.keys()), timeout=0.05, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff


def enable_leakage_current_by_io_channel(c, io, chips, vref_dac=255, \
                                         vcm_dac=50, \
                                         periodic_trigger_cycles=100000):
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    chip_config_pairs=[]
    for chip_key in chips:
        initial_config=deepcopy(c[chip_key].config)
        c[chip_key].config.channel_mask=[1]*64
        c[chip_key].config.vref_dac=vref_dac
        c[chip_key].config.vcm_dac=vcm_dac
        c[chip_key].config.threshold_global=255
        c[chip_key].config.pixel_trim_dac=[31]*64
        c[chip_key].config.enable_periodic_trigger=1
        c[chip_key].config.enable_rolling_periodic_trigger=1
        c[chip_key].config.periodic_trigger_cycles=periodic_trigger_cycles
        c[chip_key].config.enable_periodic_reset=0
        c[chip_key].config.enable_rolling_periodic_reset=0
        c[chip_key].config.enable_hit_veto=0
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    for chip_key in chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff



def disable_leakage_current_config(c, io, io_group, periodic_reset_cycles):
    io.set_reg(0x18, 0, io_group=io_group)
    
    chip_config_pairs=[]
    for chip_key, chip in c.chips.items():
        initial_config=deepcopy(chip.config)
        chip.config.enable_periodic_trigger=0
        chip.config.enable_rolling_periodic_trigger=0
        chip.config.enable_periodic_reset=1
        chip.config.enable_rolling_periodic_reset=0
        chip.config.periodic_reset_cycles=periodic_reset_cycles
        chip.config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
        
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False    
    return ok, diff


    
def disable_pedestal_config(c, io, io_group, periodic_reset_cycles=4096):
    io.set_reg(0x18, 0, io_group=io_group)
    chip_config_pairs=[]
    for chip_key, chip in c.chips.items():
        initial_config=deepcopy(chip.config)
        chip.config.enable_periodic_trigger=0
        chip.config.enable_rolling_periodic_trigger=0
        chip.config.enable_periodic_reset=1
        chip.config.enable_rolling_periodic_reset=0
        chip.config.periodic_reset_cycles=periodic_reset_cycles
        chip.config.enable_hit_veto=1
        chip_config_pairs.append((chip_key,initial_config))
    chip_reg_pairs=c.differential_write_configuration(chip_config_pairs, \
                                                      write_read=0, \
                                                      connection_delay=0.01)
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    return ok, diff





def enable_periodic_triggering(c, io, io_group, disabled):
    io.set_reg(0x18, 0, io_group=io_group)
    registers_to_write=list(range(66,74))+\
        list(range(131,139))+list(range(155,163))
    chip_config_pairs=[]
    for chip_key, chip in reversed(c.chips.items()):
        if chip_key.io_group!=io_group: continue
        chip.config.periodic_trigger_mask=[0]*64
        chip.config.channel_mask=[0]*64
        chip.config.csa_enable=[1]*64
        if chip_key in disabled.keys():
            for disabled_channel in disabled[chip_key]:
                chip.config.periodic_trigger_mask[disabled_channel]=1
                chip.config.channel_mask[disabled_channel]=1
                chip.config.csa_enable[disabled_channel]=0        
        chip_config_pairs.append( (chip_key,registers_to_write) )

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    c.multi_write_configuration(chip_config_pairs)

#    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
#                                       connection_delay=0.01, \
#                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    ok=True
    diff={}
    return ok, diff



def enable_self_triggering(c, io, io_group, disabled, set_rate=None):
    io.set_reg(0x18, 0, io_group=io_group)
    registers_to_write=list(range(66,74))+\
        list(range(131,139))+list(range(155,163))
    chip_config_pairs=[]
    chip_config_pairs_write_first = []
    for chip_key, chip in reversed(c.chips.items()):
        if chip_key.io_group!=io_group: continue
        chip.config.channel_mask=[0]*64
        chip.config.csa_enable=[1]*64
        #if chip_key in disabled.keys():
        #    for disabled_channel in disabled[chip_key]:
        #        chip.config.channel_mask[disabled_channel]=1
        #        chip.config.csa_enable[disabled_channel]=0 
        #        print('Disabled channel:', chip_key, disabled_channel)
        if True:
            tile=utility_base.io_channel_to_tile(chip_key.io_channel)
            possible_io_channel=utility_base.tile_to_io_channel([tile])
            for ioc in possible_io_channel:
                #if ioc==chip_key.io_channel: continue
                candidate = larpix.key.Key(chip_key.io_group, ioc, chip_key.chip_id)
                if candidate in disabled.keys():
                    for disabled_channel in disabled[candidate]:
                        chip.config.channel_mask[disabled_channel]=1
                        chip.config.csa_enable[disabled_channel]=0 
    
        if chip_key in disabled.keys(): chip_config_pairs_write_first.append((chip_key, registers_to_write))
        chip_config_pairs.append( (chip_key,registers_to_write) )

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io_channels_to_enable = list(utility_base.all_io_channels(c, io_group))
    for ioc in io_channels_to_enable:
        ##evaluate rate and disable channels here if flag is set!!!
        pacman_base.enable_pacman_uart_from_io_channel(io, io_group, [ioc])
        if not (set_rate is None):
            print('Regulate rate on io_channel:', ioc)
            disabled = regulate_rate_fractional(c, io, io_group, set_rate, disabled, sample_time=0.5, ioch=[ioc])

    pacman_base.enable_pacman_uart_from_io_channel(io, io_group, io_channels_to_enable)
    print("Warning!!!: These configuration register write commands are never checked!!!")
    c.multi_write_configuration(chip_config_pairs_write_first)
    c.multi_write_configuration(chip_config_pairs)


        #for chip_key, chip in reversed(c.chips.items()):
    #    if chip_key in disabled.keys():
            #print(chip.config.csa_enable)    

    #ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
    #                                   connection_delay=0.01, \
    #                                   n=10, n_verify=10)
    #print(ok, diff)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    ok=True
    diff={}
    return ok, diff


def enable_periodic_triggering_by_io_channel(c, io, chips, disabled):
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    registers_to_write=list(range(66,74))+\
        list(range(131,139))+list(range(155,163))
    chip_config_pairs=[]
    for chip_key in chips:
        c[chip_key].config.periodic_trigger_mask=[0]*64
        c[chip_key].config.channel_mask=[0]*64
        c[chip_key].config.csa_enable=[1]*64
        if chip_key in disabled.keys():
            for disabled_channel in disabled[chip_key]:
                c[chip_key].config.periodic_trigger_mask[disabled_channel]=1
                c[chip_key].config.channel_mask[disabled_channel]=1
                c[chip_key].config.csa_enable[disabled_channel]=0        
        chip_config_pairs.append( (chip_key,registers_to_write) )

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
    c.multi_write_configuration(chip_config_pairs)
    for chip_key in c.chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    return ok, diff



def enable_self_triggering_by_io_channel(c, io, chips, disabled):
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    registers_to_write=list(range(66,74))+\
        list(range(131,139))+list(range(155,163))
    chip_config_pairs=[]
    for chip_key in chips:
        c[chip_key].config.channel_mask=[0]*64
        c[chip_key].config.csa_enable=[1]*64
        if chip_key in disabled.keys():
            for disabled_channel in disabled[chip_key]:
                c[chip_key].config.channel_mask[disabled_channel]=1
                c[chip_key].config.csa_enable[disabled_channel]=0        
        chip_config_pairs.append( (chip_key,registers_to_write) )

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    io.set_reg(0x18, 2**(chips[0].io_channel-1), io_group=chips[0].io_group)
    c.multi_write_configuration(chip_config_pairs)
    for chip_key in c.chips:
        ok, diff = utility_base.reconcile_configuration(c, chip_key, False)
    io.set_reg(0x18, 0, io_group=chips[0].io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    return ok, diff



def disable_periodic_triggering(c, io, io_group):
    io.set_reg(0x18, 0, io_group=io_group)
    registers_to_write=list(range(66,74))+\
        list(range(131,139))+list(range(155,163))
    chip_config_pairs=[]
    for chip_key, chip in reversed(c.chips.items()):
        chip.config.periodic_trigger_mask=[1]*64
        chip.config.channel_mask=[1]*64
        chip.config.csa_enable=[0]*64
        chip_config_pairs.append( (chip_key,registers_to_write) )

    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    c.multi_write_configuration(chip_config_pairs)                  
    ok, diff = c.enforce_configuration(list(c.chips.keys()), timeout=0.01, \
                                       connection_delay=0.01, \
                                       n=10, n_verify=10)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    return ok, diff        



def enable_csa_trigger(c, io, io_group, disable):
    io.set_reg(0x18, 0, io_group=io_group)
    chip_register_pairs=[]
    for ck in disable.keys():
        if ck not in c.chips: continue
        c[ck].config.csa_enable=[1]*64
        c[ck].config.channel_mask=[0]*64
        for channel in disable[ck]:
            c[ck].config.csa_enable[channel]=0
            c[ck].config.channel_mask[channel]=1
        chip_register_pairs.append( (ck, \
                                     list(range(66,74))+list(range(131,139)) ))
    io.group_packets_by_io_group=True
    io.double_send_packets=True
    pacman_tile = utility_base.all_chip_key_to_tile(c, io_group)
    pacman_base.enable_pacman_uart_from_tile(io, io_group, pacman_tile)
    c.multi_write_configuration(chip_register_pairs, connection_delay=0.001)
    io.set_reg(0x18, 0, io_group=io_group)
    io.group_packets_by_io_group=False
    io.double_send_packets=False
    return



def disable_chip_csa_trigger(c, chip_key):
    c[chip_key].config.csa_enable=[0]*64
    c.write_configuration(chip_key, 'csa_enable')
    c[chip_key].config.channel_mask=[1]*64
    c.write_configuration(chip_key, 'channel_mask')
    return



def disable_channel_csa_trigger(c, chip_key, channel):
    c[chip_key].config.csa_enable[channel]=0
    c.write_configuration(chip_key, 'csa_enable')
    c[chip_key].config.channel_mask[channel]=1
    c.write_configuration(chip_key, 'channel_mask')
    for i in range(10):
        c.write_configuration(chip_key, 'csa_enable')
        c.write_configuration(chip_key, 'channel_mask')

    return



def set_ref_current_trim(c, chip_key, ref_current_trim):
    c[chip_key].config.ref_current_trim=ref_current_trim
    c.write_configuration(chip_key, 'ref_current_trim')
    return
