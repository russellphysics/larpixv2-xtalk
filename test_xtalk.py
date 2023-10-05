import larpix
import larpix.io
import argparse
import time
import os
import shutil
import larpix.format.rawhdf5format as rhdf5
import larpix.format.pacman_msg_format as pacman_msg_fmt

_default_v2a=False
_default_read=False
_default_xtrigger=False
_default_min_dac=20
_default_max_dac=60
_default_run=20
_default_daq_time=1
_default_test_ioc=5
_default_test_chip=43
_default_test_channel=8
_default_vcm_dac=50
_default_vref_dac=225
_default_ref_current_trim=0
_default_tx_diff=0
_default_tx_slice=15

_default_clk_ctrl = 1
clk_ctrl_2_clk_ratio_map = {0: 10, 1: 20, 2: 40, 3: 80}
home_dir='/home/brussell/xtalk/'


def reconcile_software_to_asic(c, chip_key):
    chip_key_registers=[(chip_key, i) \
                        for i in range(c[chip_key].config.num_registers)]
    ok, diff = c.enforce_registers(chip_key_registers, timeout=0.1,\
                                   connection_delay=0.1,\
                                   n=2, n_verify=2)
    return


def crs_power_on(c, io, v2a):

    if v2a:
        RESET_CYCLES=4096
        io.set_reg(0x10,0,io_group=1) # disable tile power
        io.set_reg(0x14,0,io_group=1) # disable global power
        io.set_reg(0x101c, 0x4,io_group=1) # set MCLK to 10 MHz
        time.sleep(0.5)
        io.set_reg(0x14, 1,io_group=1) # enable global power
        
        # set VDDD
        vddd_reg=[0x00024131, 0x00024133, 0x00024135, 0x00024137, \
	          0x00024139, 0x0002413b, 0x0002413d, 0x0002413f]
        vddd_dac=40605
        io.set_reg(vddd_reg[0], vddd_dac,io_group=1)
        for reg in vddd_reg[1:-1]: io.set_reg(reg, 0,io_group=1)
        time.sleep(0.25)    

        # set VDDA
        vdda_reg=[0x00024130, 0x00024132, 0x00024134, 0x00024136, \
                  0x00024138, 0x0002413a, 0x0002413c, 0x0002413e]
        vdda_dac=46020 
        io.set_reg(vdda_reg[0], vdda_dac,io_group=1)
        for reg in vdda_reg[1:-1]: io.set_reg(reg, 0,io_group=1)

        # toggle reset bit
        io.set_reg(0x1014, RESET_CYCLES,io_group=1)
        clk_ctrl = io.get_reg(0x1010,io_group=1)
        io.set_reg(0x1010, clk_ctrl[1]|4,io_group=1)
        io.set_reg(0x1010, clk_ctrl[1],io_group=1)
        
        # enable tile power
        tile_enable_sum=0; tile_enable_val=0
        for PACMAN_TILE in [1]:
            tile_enable_sum = pow(2, PACMAN_TILE-1) + tile_enable_sum
            tile_enable_val=tile_enable_sum+0x0200 # enable one tile at a time
            io.set_reg(0x10, tile_enable_val,io_group=1)
            time.sleep(0.25)
            #print('enabling tilereg 0x10: {0:b}'.format(tile_enable_val) )

        # toggle reset bit
        io.set_reg(0x1014, RESET_CYCLES,io_group=1)
        clk_ctrl = io.get_reg(0x1010,io_group=1)
        io.set_reg(0x1010, clk_ctrl[1]|4,io_group=1)
        io.set_reg(0x1010, clk_ctrl[1],io_group=1)
        
    else: # v2b
        io.set_reg(0x14, 1,io_group=1)
        io.set_reg(0x10, 0,io_group=1)
        io.set_reg(0x101c, 4,io_group=1)
        
        # set VDDD
        vddd_reg=[0x00024020,0x00024021,0x00024022,0x00024023,
                  0x00024024,0x00024025,0x00024026,0x00024027]
        vddd_dac=28000
        io.set_reg(vddd_reg[1], vddd_dac,io_group=1)
        time.sleep(0.25)    

        # set VDDA
        vdda_reg=[0x00024010,0x00024011,0x00024012,0x00024013,
                  0x00024014,0x00024015,0x00024016,0x00024017]
        vdda_dac=44500 
        io.set_reg(vdda_reg[1], vdda_dac,io_group=1)

        bits=list('1000000000')
        bits[-1*2]='1'
        io.set_reg(0x00000010, int("".join(bits),2),io_group=1)
        io.reset_larpix(length=64,io_group=1)



    
def set_transmit_clock(io, io_channels, divisor):
    for tile in range(len(io_channels)):
        for ioc in io_channels[tile]:
            io.set_uart_clock_ratio(ioc, divisor)

            

def v2a_construct_one_way_network(c, io, in_io_channel, chip_list, verbose):

    for i in range(len(chip_list)):
        if verbose: print('chip ',chip_list[i])

        if i==0: packet_direction='right'
        elif chip_list[i]-chip_list[i-1]==1: packet_direction='right' 
        elif chip_list[i]-chip_list[i-1]==10: packet_direction='down'
        elif chip_list[i]-chip_list[i-1]==-1: packet_direction='left'
        elif chip_list[i]-chip_list[i-1]==-10: packet_direction='up'
        
        if i!=0: # not the root chip
            miso_us=[0]*4; miso_ds=[0]*4
            if packet_direction=='right': miso_us=[0,0,1,0]
            elif packet_direction=='down': miso_us=[0,1,0,0]
            elif packet_direction=='left': miso_us=[1,0,0,0]
            elif packet_direction=='up': miso_us=[0,0,0,1]
            parent_key=larpix.key.Key(1,in_io_channel, chip_list[i-1])
            c[parent_key].config.enable_miso_upstream=miso_us
            c[parent_key].config.enable_miso_downstream=miso_us
            c[parent_key].config.enable_miso_differential=[1]*4
            c.write_configuration(parent_key,'enable_miso_upstream')
            c.write_configuration(parent_key,'enable_miso_downstream')
            c.write_configuration(parent_key,'enable_miso_differential')
            if verbose:
                print(c[parent_key].config.enable_miso_upstream, '\t parent upstream')
                print(c[parent_key].config.enable_miso_downstream, '\t parent downstream')
                print(c[parent_key].config.enable_miso_differential, '\t parent differential')

        setup_key = larpix.key.Key(1, in_io_channel, 1)
        c.add_chip(setup_key)
        c[setup_key].config.chip_id = chip_list[i]
        c.write_configuration(setup_key, 'chip_id')
        c.remove_chip(setup_key)
        chip_key=larpix.key.Key(1,in_io_channel, chip_list[i])
        c.add_chip(chip_key)
        c[chip_key].config.chip_id = chip_list[i]

        if packet_direction=='right': c[chip_key].config.enable_mosi=[0,1,0,0]
        elif packet_direction=='down': c[chip_key].config.enable_mosi=[1,0,0,0]
        elif packet_direction=='left': c[chip_key].config.enable_mosi=[0,0,0,1]
        elif packet_direction=='up': c[chip_key].config.enable_mosi=[0,0,1,0]
        c.write_configuration(chip_key, 'enable_mosi')

        if i!=len(chip_list)-1: # all chips except the last chip
            c[chip_key].config.enable_miso_upstream=[0]*4
            c[chip_key].config.enable_miso_downstream=[0]*4
            c[chip_key].config.enable_miso_differential=[1]*4
        if i==len(chip_list)-1: # last chip
            c[chip_key].config.enable_miso_upstream=[1,0,0,0]
            c[chip_key].config.enable_miso_downstream=[1,0,0,0]
            c[chip_key].config.enable_miso_differential=[1]*4
        c.write_configuration(chip_key, 'enable_miso_upstream')
        c.write_configuration(chip_key, 'enable_miso_downstream')
        c.write_configuration(chip_key, 'enable_miso_differential')
        if verbose:
            print(c[chip_key].config.enable_mosi,'\t mosi')
            print(c[chip_key].config.enable_miso_upstream,'\t upstream')
            print(c[chip_key].config.enable_miso_downstream,'\t downstream')
            print(c[chip_key].config.enable_miso_differential,'\t differential\n')



def v2b_construct_one_way_network(c, io, in_io_channel, chip_list,
                                  ref_current_trim, tx_diff, tx_slice, verbose):

    for i in range(len(chip_list)):
        if verbose: print('chip ',chip_list[i])

        if i==0: packet_direction='right'
        elif chip_list[i]-chip_list[i-1]==1: packet_direction='right' 
        elif chip_list[i]-chip_list[i-1]==10: packet_direction='down'
        elif chip_list[i]-chip_list[i-1]==-1: packet_direction='left'
        elif chip_list[i]-chip_list[i-1]==-10: packet_direction='up'
        
        if i!=0: # not the root chip
            parent_key=larpix.key.Key(1,in_io_channel, chip_list[i-1])
            piso=[0]*4
            if packet_direction=='right':
                piso=[0,0,1,0]
                c[parent_key].config.i_tx_diff2=tx_diff; c.write_configuration(parent_key,'i_tx_diff2')
                c[parent_key].config.tx_slices2=tx_slice; c.write_configuration(parent_key,'tx_slices2')
            elif packet_direction=='down':
                piso=[0,1,0,0]
                c[parent_key].config.i_tx_diff1=tx_diff; c.write_configuration(parent_key,'i_tx_diff1')
                c[parent_key].config.tx_slices1=tx_slice; c.write_configuration(parent_key,'tx_slices1')
            elif packet_direction=='left':
                piso=[1,0,0,0]
                c[parent_key].config.i_tx_diff0=tx_diff; c.write_configuration(parent_key,'i_tx_diff0')
                c[parent_key].config.tx_slices0=tx_slice; c.write_configuration(parent_key,'tx_slices0')
            elif packet_direction=='up':
                piso=[0,0,0,1]
                c[parent_key].config.i_tx_diff3=tx_diff; c.write_configuration(parent_key,'i_tx_diff3')
                c[parent_key].config.tx_slices3=tx_slice; c.write_configuration(parent_key,'tx_slices3')
            c[parent_key].config.enable_piso_upstream=piso
            c[parent_key].config.enable_piso_downstream=piso
            c.write_configuration(parent_key,'enable_piso_upstream')
            c.write_configuration(parent_key,'enable_piso_downstream')
            if verbose:
                print(c[parent_key].config.enable_piso_upstream, '\t parent upstream')
                print(c[parent_key].config.enable_piso_downstream, '\t parent downstream')

        setup_key = larpix.key.Key(1, in_io_channel, 1)
        c.add_chip(setup_key, version='2b')
        c[setup_key].config.chip_id = chip_list[i]
        c.write_configuration(setup_key, 'chip_id')
        c.remove_chip(setup_key)
        chip_key=larpix.key.Key(1,in_io_channel, chip_list[i])
        c.add_chip(chip_key, version='2b')
        c[chip_key].config.chip_id = chip_list[i]

        c[chip_key].config.ref_current_trim=ref_current_trim; c.write_configuration(chip_key,'ref_current_trim')
        c[chip_key].config.csa_enable=[0]*64; c.write_configuration(chip_key,'csa_enable')
        c[chip_key].config.channel_mask=[1]*64; c.write_configuration(chip_key,'channel_mask')  


        if packet_direction=='right': c[chip_key].config.enable_posi=[0,1,0,0]
        elif packet_direction=='down': c[chip_key].config.enable_posi=[1,0,0,0]
        elif packet_direction=='left': c[chip_key].config.enable_posi=[0,0,0,1]
        elif packet_direction=='up': c[chip_key].config.enable_posi=[0,0,1,0]
        c.write_configuration(chip_key, 'enable_posi')

        
        if i!=len(chip_list)-1: # all chips except the last chip
            c[chip_key].config.enable_piso_upstream=[0]*4
            c[chip_key].config.enable_piso_downstream=[0]*4
        if i==len(chip_list)-1: # last chip
            c[chip_key].config.ref_current_trim=0; c.write_configuration(chip_key,'ref_current_trim')
            c[chip_key].config.enable_piso_upstream=[1,0,0,0]
            c[chip_key].config.enable_piso_downstream=[1,0,0,0]
            c[chip_key].config.i_tx_diff0=0; c.write_configuration(chip_key,'i_tx_diff0')
            c[chip_key].config.tx_slices0=15; c.write_configuration(chip_key,'tx_slices0')
        c.write_configuration(chip_key, 'enable_piso_upstream')
        c.write_configuration(chip_key, 'enable_piso_downstream')
        if verbose:
            print(c[chip_key].config.enable_posi,'\t posi')
            print(c[chip_key].config.enable_piso_upstream,'\t upstream')
            print(c[chip_key].config.enable_piso_downstream,'\t downstream')



            
def v2a_construct_one_chip_network(c, io, in_io_channel, chip_list):
    for i in range(len(chip_list)):
        
        setup_key = larpix.key.Key(1, in_io_channel, 1)
        c.add_chip(setup_key)
        c[setup_key].config.chip_id = chip_list[i]
        c.write_configuration(setup_key, 'chip_id')
        c.remove_chip(setup_key)
        chip_key=larpix.key.Key(1,in_io_channel, chip_list[i])
        c.add_chip(chip_key)
        c[chip_key].config.chip_id = chip_list[i]

        c[chip_key].config.enable_mosi=[0,1,0,0]
        c.write_configuration(chip_key,'enable_mosi')
        
        if i==0: # debug
            parent_key=chip_key
            c[parent_key].config.enable_miso_upstream=[0]*4#miso
            c[parent_key].config.enable_miso_downstream=[1,0,0,0]
            c[parent_key].config.enable_miso_differential=[1]*4 #miso
            c.write_configuration(parent_key,'enable_miso_upstream')
            c.write_configuration(parent_key,'enable_miso_downstream')
            c.write_configuration(parent_key,'enable_miso_differential')



def v2b_construct_one_chip_network(c, io, in_io_channel, chip_list):
    setup_key = larpix.key.Key(1, in_io_channel, 1)
    c.add_chip(setup_key, version='2b')
    c[setup_key].config.chip_id = chip_list[0]
    c.write_configuration(setup_key, 'chip_id')
    c.remove_chip(setup_key)
    chip_key=larpix.key.Key(1,in_io_channel, chip_list[0])
    c.add_chip(chip_key, version='2b')
    c[chip_key].config.chip_id = chip_list[0]
    
    c[chip_key].config.csa_enable=[0]*64; c.write_configuration(chip_key,'csa_enable')
    c[chip_key].config.channel_mask=[1]*64; c.write_configuration(chip_key,'channel_mask')
    
    c[chip_key].config.ref_current_trim=0; c.write_configuration(chip_key,'ref_current_trim')
    
    c[chip_key].config.enable_posi=[0,1,0,0]; c.write_configuration(chip_key,'enable_posi')
    c[chip_key].config.i_tx_diff0=0; c.write_configuration(chip_key,'i_tx_diff0')
    c[chip_key].config.tx_slices0=15; c.write_configuration(chip_key,'tx_slices0')
    c[chip_key].config.enable_piso_downstream=[1,0,0,0]; c.write_configuration(chip_key, 'enable_piso_downstream')
    c[chip_key].config.enable_piso_upstream=[0]*4; c.write_configuration(chip_key, 'enable_piso_upstream')

        
            
def main(v2a=_default_v2a, \
         read=_default_read, \
         xtrigger=_default_xtrigger, \
         min_dac=_default_min_dac, \
         max_dac=_default_max_dac, \
         run=_default_run, \
         daq_time=_default_daq_time, \
         test_ioc=_default_test_ioc, \
         test_chip=_default_test_chip, \
         test_channel=_default_test_channel, \
         vcm_dac=_default_vcm_dac, \
         vref_dac=_default_vref_dac, \
         ref_current_trim=_default_ref_current_trim, \
         tx_diff=_default_tx_diff, \
         tx_slice=_default_tx_slice, \
         **kwargs):
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True)

    c.io.set_reg(0x18, 0,io_group=1) # turn off all pacman receivers
    if v2a==False:
        inversion_registers=[0x0701c, 0x0801c, 0x0901c, 0x0a01c] # tile 2
        for ir in inversion_registers: c.io.set_reg(ir, 0b11,io_group=1)
    
    crs_power_on(c, c.io, v2a)
    
    debug=False
    
    if v2a:
        # set UART clock speed at 5 MHz
        c.io.set_uart_clock_ratio(1, 10,io_group=1)#clk_ctrl_2_clk_ratio_map[0])

        # enable tile 1 UART
        bits=list('00000000000000000000000000000000')
        for ioc in [1,2,3,4]: bits[-1*ioc]='1'
        c.io.set_reg(0x18, int("".join(bits),2), io_group=1) 

        if debug:
            key = larpix.key.Key(1,1,1)
            c.add_chip(key)
            c[key].config.chip_id=11
            c.write_configuration(key,'chip_id')
            c.remove_chip(key)
            key=larpix.key.Key(1,1,11)
            c.add_chip(key)
            c[key].config.chip_id=key.chip_id
            c[key].config.enable_miso_downstream=[1,0,0,0]
            c[key].config.enable_miso_upstream=[0]*4
            c[key].config.enable_miso_differential=[1,1,1,1]
            c.write_configuration(key,'enable_miso_downstream')
            c.write_configuration(key,'enable_miso_upstream')    
        if debug==False:
            #v2a_construct_one_chip_network(c, c.io, 1, [11])
            v2a_construct_one_way_network(c, c.io, 1, [11,12,13,23,33,43,42,41], False)

            for cid in [41,42,43,33,23,13,12,11]:
                key=larpix.key.Key(1,1,cid)
                c[key].config.clk_ctrl=1
                c.write_configuration(key,'clk_ctrl')
            c.io.set_uart_clock_ratio(1, 20)
    else: # v2b
        if debug:
            v2b_construct_one_chip_network(c, c.io, test_ioc, [test_chip])
            c.io.set_reg(0x18, 2**(test_ioc-1),io_group=1)
        if debug==False:
            v2b_construct_one_way_network(c, c.io, test_ioc, [21,22,23,33,43,42,41],
                                          ref_current_trim, tx_diff, tx_slice, False)
            bits=list('00000000000000000000000000000000')
            for ioc in [test_ioc,test_ioc+1]: bits[-1*ioc]='1'
            c.io.set_reg(0x18, int("".join(bits),2), io_group=1) 

    for ck in c.chips.keys():
        c[ck].config.channel_mask=[1]*64; c.write_configuration(ck,'channel_mask')
        c[ck].config.csa_enable=[1]*64; c.write_configuration(ck,'csa_enable')
        reconcile_software_to_asic(c, ck)


    
    key=larpix.key.Key(1,test_ioc,test_chip)
    print('test chip: ',key)
    c[key].config.channel_mask[test_channel]=0; c.write_configuration(key,'channel_mask')
    c[key].config.csa_enable[test_channel]=1; c.write_configuration(key,'csa_enable')
    c[key].config.vcm_dac=vcm_dac; c.write_configuration(key,'vcm_dac')
    c[key].config.vref_dac=vref_dac; c.write_configuration(key,'vref_dac')
    c[key].config.enable_periodic_reset=1; c.write_configuration(key,'enable_periodic_reset')
    c[key].config.pixel_trim_dac[test_channel]=0; c.write_configuration(key,'pixel_trim_dac')
    c[key].config.enable_hit_veto=1; c.write_configuration(key,'enable_hit_veto')
    ok, diff = c.enforce_registers([(key,[128]),
                                    (key,list(range(131,139))),
                                    (key,list(range(66,74))),
                                    (key,82),(key,83),
                                    (key,list(range(0,64)))], \
                                   timeout=0.1, connection_delay=0.1,n=5,n_verify=5)
    if xtrigger:
        for i in range(test_channel-7, test_channel+8,1):
            chan=i
            if i<0: chan=64+i
            c[key].config.channel_mask[chan]=0
            c[key].config.cross_trigger_mask[chan]=0
            c[key].config.pixel_trim_dac[chan]=0
        c[key].config.enable_cross_trigger=1
        c.write_configuration(key,'channel_mask')
        c.write_configuration(key,'cross_trigger_mask')
        c.write_configuration(key,'pixel_trim_dac')
        c.write_configuration(key,'enable_cross_trigger')
        ok, diff = c.enforce_registers([(key,list(range(131,139))),
                                        (key,list(range(147,155))),
                                        (key,list(range(0,64))),
                                        (key,[128])], \
                                    timeout=0.1, connection_delay=0.1,n=5,n_verify=5)
            
    os.mkdir('run'+str(run))
    
    for i in range(max_dac,min_dac-1,-1):
        c[key].config.threshold_global=i; c.write_configuration(key,'threshold_global')
        ok, diff =c.enforce_registers([(key,64)], timeout=0.1, connection_delay=0.1, n=5, n_verify=5)
        print('Global DAC: ',i)
        time.sleep(0.2)
        now=time.strftime("%Y-%m-%d-%H-%M-%S-%Z")
        key_str='key-'+str(1)+'-'+str(test_ioc)+'-'+str(test_chip)+'-'+str(test_channel)
        global_str='global-dac-'+str(i)
        fname=key_str+'_'+global_str+'_'+now+'.h5'
        if v2a: fname='raw-v2a_'+fname
        else: fname='raw-v2b_'+fname

        c.io.disable_packet_parsing = True
        c.io.enable_raw_file_writing = True
        c.io.raw_filename=fname
        c.io.join()
        rhdf5.to_rawfile(filename=c.io.raw_filename, \
                         io_version=pacman_msg_fmt.latest_version)
        run_start=time.time()
        c.start_listening()
        data_rate_start=time.time()
        while True:
            c.read()
            if read:
                packets=c[key].get_configuration_read_packets([122])
                c.send(packets)
            now=time.time()
            if  now > (run_start+daq_time): break
        c.stop_listening()
        c.read()
        c.io.join()     
        
        shutil.move(home_dir+fname,\
                    home_dir+'run'+str(run)+'/'+fname)
        c.io.disable_packet_parsing = False
        c.io.enable_raw_file_writing = False

    c.io.reset_larpix(length=6400, io_group=1)
    c.io.set_reg(0x10,0,io_group=1) # disable tile power
    c.io.set_reg(0x14,0,io_group=1) # disable global power
    return c

        

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--v2a', default=_default_v2a, \
                        action='store_true', help='''v2a ASIC''')
    parser.add_argument('--read', default=_default_read, \
                        action='store_true', help='''periodic read''')
    parser.add_argument('--xtrigger', default=_default_xtrigger, \
                        action='store_true', help='''Cross trigger''')
    parser.add_argument('--min_dac', default=_default_min_dac, \
                        type=int, help='''Minimum global DAC''')
    parser.add_argument('--max_dac', default=_default_max_dac, \
                        type=int, help='''Maximum global DAC''')
    parser.add_argument('--run', default=_default_run, \
                        type=int, help='''run iteration''')
    parser.add_argument('--daq_time', default=_default_daq_time, \
                        type=int, help='''data acquisition time''')
    parser.add_argument('--test_ioc', default=_default_test_ioc, \
                        type=int, help='''test IO channel''')
    parser.add_argument('--test_chip', default=_default_test_chip, \
                        type=int, help='''test chip ID''')
    parser.add_argument('--test_channel', default=_default_test_channel, \
                        type=int, help='''test channel ID''')
    parser.add_argument('--vcm_dac', default=_default_vcm_dac, \
                        type=int, help='''Vcm DAC''')
    parser.add_argument('--vref_dac', default=_default_vref_dac, \
                        type=int, help='''Vref DAC''')
    parser.add_argument('--ref_current_trim', default=_default_ref_current_trim, \
                        type=int, help='''reference current trim DAC''')
    parser.add_argument('--tx_diff', default=_default_tx_diff, \
                        type=int, help='''TS diff [active low]''')
    parser.add_argument('--tx_slice', default=_default_tx_slice, \
                        type=int, help='''TX slices [active high]''')
    args = parser.parse_args()
    c = main(**vars(args))
