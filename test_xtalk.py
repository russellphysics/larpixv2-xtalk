import larpix
import larpix.io
import argparse
import time
import os
import shutil
import larpix.format.rawhdf5format as rhdf5
import larpix.format.pacman_msg_format as pacman_msg_fmt

_default_v2a=False
_default_run=0
_default_daq_time=1
_default_test_ioc=1
_default_test_chip=43
_default_test_channel=8
_default_clk_ctrl = 1
clk_ctrl_2_clk_ratio_map = {0: 10, 1: 20, 2: 40, 3: 80}
home_dir='/home/brussell/xtalk/'


def reconcile_software_to_asic(c, chip_key):
    chip_key_registers=[(chip_key, i) \
                        for i in range(c[chip_key].config.num_registers)]
    ok, diff = c.enforce_registers(chip_key_registers, timeout=0.1,\
                                   connection_delay=0.1,\
                                   n=5, n_verify=5)
    return



def v2a_crs_power_on(c, io):
    RESET_CYCLES=4096

    io.set_reg(0x10,0) # disable tile power
    io.set_reg(0x14,0) # disable global power
    io.set_reg(0x101c, 0x4) # set MCLK to 10 MHz
    time.sleep(0.5)
    io.set_reg(0x14, 1) # enable global power
    
    # set VDDD
    vddd_reg=[0x00024131, 0x00024133, 0x00024135, 0x00024137, \
	      0x00024139, 0x0002413b, 0x0002413d, 0x0002413f]
    vddd_dac=40605
    io.set_reg(vddd_reg[0], vddd_dac)
    for reg in vddd_reg[1:-1]: io.set_reg(reg, 0)
    time.sleep(0.25)    

    # set VDDA
    vdda_reg=[0x00024130, 0x00024132, 0x00024134, 0x00024136, \
              0x00024138, 0x0002413a, 0x0002413c, 0x0002413e]
    vdda_dac=46020 
    io.set_reg(vdda_reg[0], vdda_dac)
    for reg in vdda_reg[1:-1]: io.set_reg(reg, 0)

    # toggle reset bit
    io.set_reg(0x1014, RESET_CYCLES)
    clk_ctrl = io.get_reg(0x1010)
    io.set_reg(0x1010, clk_ctrl[1]|4)
    io.set_reg(0x1010, clk_ctrl[1])

    # enable tile power
    tile_enable_sum=0; tile_enable_val=0
    for PACMAN_TILE in [1]:
        tile_enable_sum = pow(2, PACMAN_TILE-1) + tile_enable_sum
        tile_enable_val=tile_enable_sum+0x0200 # enable one tile at a time
        io.set_reg(0x10, tile_enable_val)
        time.sleep(0.25)
        print('enabling tilereg 0x10: {0:b}'.format(tile_enable_val) )

    # toggle reset bit
    io.set_reg(0x1014, RESET_CYCLES)
    clk_ctrl = io.get_reg(0x1010)
    io.set_reg(0x1010, clk_ctrl[1]|4)
    io.set_reg(0x1010, clk_ctrl[1])


    
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
            print(c[chip_key].config.enable_miso_upstream,'\t differential\n')


            
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


            
def main(v2a=_default_v2a, \
         run=_default_run, \
         daq_time=_default_daq_time, \
         test_ioc=_default_test_ioc, \
         test_chip=_default_test_chip, \
         test_channel=_default_test_channel, \
         **kwargs):
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True)

    # set UART clock speed at 5 MHz
    c.io.set_uart_clock_ratio(1, clk_ctrl_2_clk_ratio_map[0])
        
    if v2a:
        # enable tile 1 UARTs
        bits=list('00000000000000000000000000000000')
        for ioc in [1,2,3,4]: bits[-1*ioc]='1'
        c.io.set_reg(0x18, int("".join(bits),2), io_group=1) 
        
        v2a_crs_power_on(c, c.io)

        debug=False
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
            v2a_construct_one_way_network(c, c.io, 1, [11,12,13,23,33,43,42,41], True)
    else:
        # enable tile 2 UARTs
        bits=list('00000000000000000000000000000000')
        for ioc in [5,6,7,8]: bits[-1*ioc]='1'
        c.io.set_reg(0x18, int("".join(bits),2), io_group=1) 

    for ck in c.chips.keys():
        c[ck].config.channel_mask=[1]*64; c.write_configuration(ck,'channel_mask')
        c[ck].config.csa_enable=[1]*64; c.write_configuration(ck,'csa_enable')
        reconcile_software_to_asic(c, ck)

    key=larpix.key.Key(1,test_ioc,test_chip)
    print('test chip: ',key)
    c[key].config.channel_mask[test_channel]=0; c.write_configuration(key,'channel_mask')
    c[key].config.vcm_dac=40; c.write_configuration(key,'vcm_dac')
    c[key].config.vref_dac=185; c.write_configuration(key,'vref_dac')
    os.mkdir('run'+str(run))

    c.io.disable_packet_parsing = True
    c.io.enable_raw_file_writing = True
    
    for i in range(10,12,1):
        c[key].config.threshold_global=i; c.write_configuration(key,'threshold_global')
        time.sleep(0.2)
        now=time.strftime("%Y-%m-%d-%H-%M-%S-%Z")
        key_str='key-'+str(1)+'-'+str(test_ioc)+'-'+str(test_chip)+'-'+str(test_channel)
        global_str='global-dac-'+str(i)
        fname=key_str+'_'+global_str+'_'+now+'.h5'
        if v2a: fname='raw-v2a_'+fname
        else: fname='raw-v2b_'+fname
        #c.logger=larpix.logger.HDF5Logger(filename=fname)
        #c.logger.enable()
        #c.run(daq_time, message=global_str)
        #c.logger.flush()
        #c.logger.disable()
        c.io.raw_filename=fname
        c.io.join()
        rhdf5.to_rawfile(filename=c.io.raw_filename, \
                         io_version=pacman_msg_fmt.latest_version)
        run_start=time.time()
        c.start_listening()
        data_rate_start=time.time()
        while True:
            c.read()
            now=time.time()
            if  now > (run_start+daq_time): break
        c.stop_listening()
        c.read()
        c.io.join()     
        
        shutil.move(home_dir+fname,\
                    home_dir+'run'+str(run)+'/'+fname)
        
    return c

        

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--v2a', default=_default_v2a, \
                        action='store_true', help='''v2a ASIC''')
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
    args = parser.parse_args()
    c = main(**vars(args))
