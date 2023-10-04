import larpix
import larpix.format.rawhdf5format as rhdf5
import larpix.format.pacman_msg_format as pacman_msg_fmt
import numpy as np
import time
import json
#import asyncio
import os
import subprocess
from signal import signal, SIGINT

global oldfilename

_broadcast_disable_nwrite=3


def now():
    return time.strftime("%Y_%m_%d_%H_%M_%Z")

def broadcast_disable(c, target_chips=None):
    broadcast_form = '{}-{}-255'

    target_channels = set()

    if not (target_chips is None):
        for chip in target_chips: target_channels.add( (chip.io_group, chip.io_channel) )

    target_channels = list(target_channels)

    for io_group, io_channels in c.network.items():
        for io_channel in io_channels:
            broadcast=broadcast_form.format(io_group, io_channel)

            if not (target_chips is None):
                if not ( (io_group, io_channel) in target_channels): continue

            if not (broadcast in c.chips): c.add_chip(broadcast)

            #print('Broadcast disable on (io_group, io_channel)=(', io_group, ',', io_channel, ')' )

            c[broadcast].config.channel_mask = [0]*64
            c[broadcast].config.test_mode_uart0 = 0
            c[broadcast].config.test_mode_uart1 = 0
            c[broadcast].config.test_mode_uart2 = 0
            c[broadcast].config.test_mode_uart3 = 0

            for __ in range(_broadcast_disable_nwrite):
                c.write_configuration(broadcast, 'test_mode_uart0')
                c.write_configuration(broadcast, 'test_mode_uart1')
                c.write_configuration(broadcast, 'test_mode_uart2')
                c.write_configuration(broadcast, 'test_mode_uart3')
                c.write_configuration(broadcast, 'channel_mask')

            c.remove_chip(broadcast)



def flush_data(c, runtime=0.1, rate_limit=0., max_iterations=10):
    for _ in range(max_iterations):
        c.run(runtime, 'flush data')
        if len(c.reads[-1])/runtime<=rate_limit:
            break


def data_filename(c, packet):
    now=time.strftime("%Y_%m_%d_%H_%M_%Z")
    if packet==True:
        fname='packets-'+now+'.h5'
    else:
        fname='binary-'+now+'.h5'

    return fname



def data(c, runtime, packet, LRS=False, fname=None):
    if packet==True:
        if fname is None: fname='packets-'+now+'.h5'
        c.logger = larpix.logger.HDF5Logger(filename=fname)
        
        if LRS: 
            subprocess.call(["echo 1 > ~/.adc_watchdog_file"],shell=True)  #start LRS

        print('filename: ',c.logger.filename)
        c.logger.enable()
        c.run(runtime,' collecting data')
        c.logger.flush()
        c.logger.disable()
        
        if LRS: 
            subprocess.call(["echo 0 > ~/.adc_watchdog_file"],shell=True) #stop LRS
            time.sleep(1)
        
    else:
        c.io.disable_packet_parsing = True
        c.io.enable_raw_file_writing = True
        if fname is None: fname='binary-'+now+'.h5'
        c.io.raw_filename=fname
        c.io.join()
        rhdf5.to_rawfile(filename=c.io.raw_filename, \
                         io_version=pacman_msg_fmt.latest_version)
        
        print('filename: ',c.io.raw_filename)
        run_start=time.time()
        c.start_listening()
        if LRS: 
            subprocess.call(["echo 1 > ~/.adc_watchdog_file"],shell=True)  #start LRS
            print('starting LRS ...')
        data_rate_refresh = 5.
        data_rate_start = time.time()
        last_counter = 0
        oldfilename=c.io.raw_filename
        while True:
            c.read()
            now=time.time()
            if now-data_rate_start>data_rate_refresh:
                if c.io.raw_filename and os.path.isfile(c.io.raw_filename):
                    counter = rhdf5.len_rawfile(c.io.raw_filename, attempts=0)
                    print('average message rate: {:0.2f} Hz\r'.format( (counter-last_counter)/data_rate_refresh ),end='') 
                    if LRS:
                        post = 'datarate,sens=larpix1 value={:0.02f}'.format((counter-last_counter)/(data_rate_refresh))
                        subprocess.call(["curl","--silent","-XPOST", "http://130.92.128.162:8086/write?db=singlemodule_nov2020", "--data-binary", post])
                    last_counter=counter
                data_rate_start = now
                data_rate_counter = 0
            if now>(run_start+runtime): break
        c.stop_listening()
        if LRS: 
            subprocess.call(["echo 0 > ~/.adc_watchdog_file"],shell=True) #stop LRS
            time.sleep(0.3)
        c.read()
        c.io.join()

    return fname


async def async_reconcile_configuration(c, chip_keys, verbose, \
                                        timeout=0.01, connection_delay=0.01, \
                                        n=3, n_verify=3):
    return await asyncio.to_thread(reconcile_configuration, c, chip_keys, verbose, \
                                        timeout=0.01, connection_delay=0.01, \
                                        n=3, n_verify=3)


def reconcile_configuration(c, chip_keys, verbose, \
                            timeout=0.01, connection_delay=0.01, \
                            n=2, n_verify=2):
    if isinstance(chip_keys, (str, larpix.key.Key)): chip_keys = [chip_keys]
    chip_key_register_pairs = [(chip_key, \
                                range(c[chip_key].config.num_registers)) \
                               for chip_key in chip_keys]
    return reconcile_registers(c, chip_key_register_pairs, verbose, \
                               timeout=timeout, \
                               connection_delay=connection_delay, \
                               n=n, n_verify=n_verify)


def reconcile_configuration_bool(c, chip_keys, verbose, \
                                        timeout=0.01, connection_delay=0.01, \
                                        n=2, n_verify=2):
    if isinstance(chip_keys, (str, larpix.key.Key)): chip_keys = [chip_keys]
    chip_key_register_pairs = [(chip_key, \
                                range(c[chip_key].config.num_registers)) \
                               for chip_key in chip_keys]
    return reconcile_registers_bool(c, chip_key_register_pairs, \
                                    verbose, timeout=timeout, \
                                    connection_delay=connection_delay, \
                                    n=n, n_verify=n_verify)


def reconcile_registers(c, chip_key_register_pairs, verbose, timeout=0.02, \
                        connection_delay=0.01, n=2, n_verify=2):
    ok, diff = c.verify_registers(chip_key_register_pairs, timeout=timeout, \
                                  connection_delay=connection_delay,
                                  n=n_verify)
    #print(c.reads[-1])
    if diff!={}:
        flag = True
        for a in diff.keys():
            if flag == False: break
            for b in diff[a].keys():
                pair = diff[a][b]
                if verbose: print(a,'\t',n,':\t',b,'\t',pair)
                if pair[1]==None: flag=False; break
    if not ok:
        chip_key_register_pairs = [(chip_key, register) \
                                   for chip_key in diff \
                                   for register in diff[chip_key]]
        c.multi_write_configuration(chip_key_register_pairs, write_read=0, \
                                    connection_delay=connection_delay)
        if n!=1:
            ok,diff = reconcile_registers(c, chip_key_register_pairs, \
                                          verbose, timeout=timeout,
                                          connection_delay=connection_delay,
                                          n=n-1, n_verify=n_verify)
        else:
            ok, diff = c.verify_registers(chip_key_register_pairs, \
                                          timeout=timeout, \
                                          connection_delay=connection_delay, \
                                          n=n_verify)
    return ok, diff

def reconcile_registers_bool(c, chip_key_register_pairs, verbose, \
                                    timeout=1, connection_delay=0.02, \
                                    n=1, n_verify=1):
    ok, diff = c.verify_registers(chip_key_register_pairs, timeout=timeout, \
                                  connection_delay=connection_delay,
                                  n=n_verify)
#    await asyncio.sleep(1.)
    if diff!={}:
        flag = True
        for a in diff.keys():
            if flag == False: break
            for b in diff[a].keys():
                pair = diff[a][b]
                if verbose: print(a,'\t',n,':\t',b,'\t',pair)
                if pair[1]==None: flag=False; break
    if not ok:
        chip_key_register_pairs = [(chip_key, register) \
                                   for chip_key in diff \
                                   for register in diff[chip_key]]
        c.multi_write_configuration(chip_key_register_pairs, write_read=0, \
                                    connection_delay=connection_delay)
        if n!=1:
            ok,diff = reconcile_registers(c, chip_key_register_pairs, \
                                          verbose, timeout=timeout,
                                          connection_delay=connection_delay,
                                          n=n-1, n_verify=n_verify)
        else:
            ok, diff = c.verify_registers(chip_key_register_pairs, \
                                          timeout=timeout, \
                                          connection_delay=connection_delay, \
                                          n=n_verify)
    result=0
    if ok==True: result=1
    return result


def lsb(vdda, vref_dac, vcm_dac, bits=2**8):
    return ( (vdda*(vref_dac/bits))-(vdda*(vcm_dac/bits)) ) / bits
    

def global_dac_step(vdda, global_dac, bits=2**8):
    return vdda*(global_dac/bits)



def ADC_to_mV(adc, vdda, vref_dac, vcm_dac, bits=2**8):
    vref = vdda * (vref_dac/bits)
    vcm = vdda * (vcm_dac/bits)
    return (adc * ((vref-vcm)/bits)) + vcm



def partition_chip_keys_by_io_group_tile(chip_keys):
    io_group_list=[]
    for chip in chip_keys:
        if chip.io_group not in io_group_list:
            io_group_list.append(chip.io_group)
    d={}
    for iog in io_group_list:
        for i in range(1,9): d[(iog,i)]=[]
    for key in d.keys():
        for ck in chip_keys:
            if ck.io_group==key[0] and \
               io_channel_to_tile(ck.io_channel)==key[1]:
                d[key].append(ck)
    return d

def partition_chip_keys_by_tile(chip_keys):
    d={}
    for i in range(1,9): d[i]=[]
    for ck in chip_keys:
        d[io_channel_to_tile(ck.io_channel)].append(ck)
    return d        

def all_io_channels(c, io_group):
    io_channel=set()
    for ck in c.chips: 
        if ck.io_group==io_group: 
            ioc = ck.io_channel
            io_channel.add(ioc)
    return list(io_channel)

def all_chip_key_to_tile(c, io_group):
    io_channel=set()
    for ck in c.chips: 
        if ck.io_group==io_group: io_channel.add(ck.io_channel)
    pacman_tile=set()
    for ioc in io_channel: pacman_tile.add(io_channel_to_tile(ioc))
    pacman_tile=list(pacman_tile)
    return pacman_tile


def chip_key_to_io_group(ck): return int(ck.split('-')[0])


def chip_key_to_io_channel(ck): return int(ck.split('-')[1])


def chip_key_to_chip_id(ck): return int(ck.split('-')[-1])


def iog_tile_to_iog_ioc_cid(io_group_pacman_tile, asic_version):
    result=[]
    for iog in io_group_pacman_tile.keys():
        for tile in io_group_pacman_tile[iog]:
            io_channel=tile_to_io_channel([tile])
            ioc_root_map=io_channel_to_root_chip(io_channel, asic_version)
            for ioc in ioc_root_map.keys():
                result.append( (iog, ioc, ioc_root_map[ioc]) )
    return result


def tile_to_io_channel(tile):
    io_channel=[]
    for t in tile:
        for i in range(1,5,1):
            io_channel.append( ((t-1)*4)+i )
    return io_channel


def unique_to_chip_key(i):
    chip_key=str(unique_to_io_group(i))+'-'+ \
        str(unique_to_io_channel(i))+'-'+ \
        str(unique_to_chip_id(i))
    return chip_key


def io_channel_to_tile(io_channel):
    return int(np.floor((io_channel-1-((io_channel-1)%4))/4+1))

def io_channel_list_to_tile(io_channel):
    io_channel = np.array(io_channel)
    return list(np.array(np.floor((io_channel-1-((io_channel-1)%4))/4+1)))



def io_channel_to_root_chip(io_channel, asic_version):
    root_chips=[11,41,71,101]
    if asic_version=='2b': root_chips=[21,41,61,91]
    mapping={}
    for i in range(4, len(io_channel)+1, 4):
        ioc=io_channel[i-4:i]
        for j in range(len(ioc)): mapping[ioc[j]]=root_chips[j]
    return mapping



def save_json(d, prefix):
    now=time.strftime("%Y_%m_%d_%H_%M_%Z")
    fname=prefix+'-'+now+'.json'
    with open(fname,'w') as outfile:
        json.dump(d, outfile, indent=4)
    print('disabled filename: ',fname)
    return


def save_asic_config(c):
    now=time.strftime("%Y_%m_%d_%H_%M_%Z")
    for ck in c.chips:
        fname='config-'+str(ck)+'-'+now+'.json'
        c[ck].config.write(fname, force=True)
    return
    
def unique(io_group, io_channel, chip_id, channel_id):
    return ((io_group*256+io_channel)*256+ chip_id)*64 + channel_id

def unique_channel_id(d):
    return ((d['io_group'].astype(int)*1000+d['io_channel'].astype(int))*1000 \
            + d['chip_id'].astype(int))*100 + d['channel_id'].astype(int)

def unique_channel_id_args(io_group, io_channel, chip_id, channel_id):
    return ((io_group*1000+io_channel)*1000 \
            + chip_id)*100 + channel_id

def unique_to_chip_key(i):
    chip_key=str(unique_to_io_group(i))+'-'+ \
        str(unique_to_io_channel(i))+'-'+ \
        str(unique_to_chip_id(i))
    return chip_key

def unique_to_channel_id(unique):
    return int(unique % 100)

def unique_to_chip_id(unique):
    return int((unique// 100) % 1000)

def unique_to_io_channel(unique):
    return int((unique//(100*1000)) % 1000)

def unique_to_io_group(unique):
    return int((unique // (100*1000*1000)) % 1000)

def chip_key_to_asic_id(chip_key):
    args = str(chip_key).split('-')
    return '{}-{}-{}'.format(args[0], io_channel_to_tile(int(args[1])), args[2])

