### FIX ME:
### (1) change version to pacman version (discriminate from asic version)
### (2) substitute inversion table for hex(0x0201c+0x01000*ioc)
### (3) debug enable_pacman_uart bit declaration
import larpix
import larpix.io
from base import utility_base
import argparse
import time
import math
import asyncio
from RUNENV import *

#from timebudget import timebudget
#from base.v2a_base import *
##########################################################################
#---------------PACMAN UART INVERSION/DISABLE/ENABLE---------------------#
##########################################################################



def invert_pacman_uart(io, io_group, asic_version, tile):
    if asic_version!='2b': return
    inversion_registers={1:0x0301c, 2:0x0401c, 3:0x0501c, 4:0x0601c,
                         5:0x0701c, 6:0x0801c, 7:0x0901c, 8:0x0a01c,
                         9:0x0b01c, 10:0x0c01c, 11:0x0d01c, 12:0x0e01c,
                         13:0x0f01c, 14:0x1001c, 15:0x1101c, 16:0x1201c,
                         17:0x1301c, 18:0x1401c, 19:0x1501c, 20:0x1601c,
                         21:0x1701c, 22:0x1801c, 23:0x1901c, 24:0x1a01c,
                         25:0x1b01c, 26:0x1c01c, 27:0x1d01c, 28:0x1e01c,
                         29:0x1f01c, 30:0x2001c, 31:0x2101c, 32:0x2201c}
    io_channel=utility_base.tile_to_io_channel(tile)
    for ioc in io_channel:
        io.set_reg(inversion_registers[ioc], 0b11, io_group=io_group)
    return

def enable_pacman_uart_from_io_channel(io, io_group, io_channel):
    bits=list('00000000000000000000000000000000')
    for ioc in io_channel:
        bits[-1*ioc]='1'
    io.set_reg(0x18, int("".join(bits),2), io_group=io_group)
    return

def enable_all_pacman_uart_from_io_group(io, io_group, true_all=False):
    bits=list('111111111111111111111111111111')
    if not true_all:
        enable_pacman_uart_from_tile(io, io_group, io_group_pacman_tile_[io_group])
    else:
        io.set_reg(0x18, int("".join(bits),2), io_group=io_group)
    return



def enable_pacman_uart_from_tile(io, io_group, tile):
    bits=list('00000000000000000000000000000000')
    io_channel=utility_base.tile_to_io_channel(tile)
    for ioc in io_channel:
        bits[-1*ioc]='1'
    io.set_reg(0x18, int("".join(bits),2), io_group=io_group)
    return



def enable_pacman_uart_from_io_channels(io, io_group, io_channels):
    bits=list('00000000000000000000000000000000')
    for ioc in io_channels:
        bits[-1*ioc]='1'
    io.set_reg(0x18, int("".join(bits),2), io_group=io_group)
    return



def enable_pacman_uart_from_io_channel(io, io_group, io_channels):
    bits=list('00000000000000000000000000000000')
    for io_channel in io_channels:
        try:
            bits[-1*io_channel]='1'
        except:
            print('failed attemping to enable  io_channell:', io_channel)
    io.set_reg(0x18, int("".join(bits),2), io_group=io_group)
    return

    
    
def disable_all_pacman_uart(io, io_group):
    io.set_reg(0x18, 0x0, io_group=io_group)
    return



##########################################################################
#---------------------------POWER SET/READBACK---------------------------#
##########################################################################


# original: vdda_step=500, vddd_step=500
def power_up(io, io_group, pacman_version, ramp, tile, vdda_dac, vddd_dac, \
             reset_length=600000000, vdda_step=1000, vddd_step=1000, \
             ramp_wait=30, warm_wait=20):
    print(io, io_group, pacman_version, ramp, tile, vdda_dac, vddd_dac)   
    io.set_reg(0x00000014, 1, io_group=io_group)
    #io.set_reg(0x00000010, 0, io_group=io_group) 
    bits=list('1000000000')
    if ramp==True and pacman_version=='v1rev4':
        io.reset_larpix(length=reset_length, io_group=io_group)
        clock_start=time.time()
        for i in tile:
            if pacman_version=='v1rev4':
                io.set_reg(0x24010+(i-1), 0, io_group=io_group)
                io.set_reg(0x24020+(i-1), 0, io_group=io_group)
            elif pacman_version=='v1rev3' or pacman_version=='v1revS1':
                vdda_offset=(i-1)*2
                vddd_offset=((i-1)*2)+1
                io.set_reg(0x24130+vdda_offset, 0, io_group=io_group)
                io.set_reg(0x24130+vddd_offset, 0, io_group=io_group)
            else:
                print('WARNING: PACMAN version ',pacman_version,' unknown')
                return
            bits[-1*i]='1'
        io.set_reg(0x00000010, int("".join(bits),2), io_group=io_group)
        for i in tile:
            ctr=0; vdda=0
            print('Tile ',i,' VDDA DAC: ',vdda_dac[i-1])
            while vdda<vdda_dac[i-1]:
                if ctr==0: start=time.time()
                ctr+=1; vdda+=vdda_step
                if pacman_version=='v1rev4':
                    io.set_reg(0x24010+(i-1), vdda, io_group=io_group)
                elif pacman_version=='v1rev3' or pacman_version=='v1revS1':
                    vdda_offset=(i-1)*2
                    io.set_reg(0x24130+vdda_offset, 0, io_group=io_group)
                time.sleep(0.1)
            if vdda>=vdda_dac[i-1]:
                print('Tile ',i,': ',time.time()-start,\
                      ' s ramping VDDA ', vdda)
        print(time.time()-clock_start,'s VDDA set w.r.t. hard reset')
        time.sleep(ramp_wait)
        print(time.time()-clock_start,'s start ramping VDDD w.r.t. hard reset')
        for i in tile:
            ctr=0; vddd=0
            print('Tile ',i,' VDDD DAC: ',vddd_dac[i-1])
            while vddd<vddd_dac[i-1]:
                if ctr==0: start=time.time()
                ctr+=1; vddd+=vddd_step
                if pacman_version=='v1rev4':
                    io.set_reg(0x24020+(i-1), vddd, io_group=io_group)
                elif pacman_version=='v1rev3' or pacman_version=='v1revS1':
                    vddd_offset=((i-1)*2)+1
                    io.set_reg(0x24130+vddd_offset, 0, io_group=io_group)
                time.sleep(0.15)
            if vddd>=vddd_dac[i-1]:
                print('Tile ',i,': ',time.time()-start,
                      ' s ramping VDDD ', vddd)
        print(time.time()-clock_start,'s VDDD set w.r.t. hard reset')
        io.set_reg(0x101c, 4, io_group=io_group)
        print(time.time()-clock_start,'s MCLK started w.r.t. hard reset')
        time.sleep(warm_wait)
        print(time.time()-clock_start,'s wait time done w.r.t. hard reset')
    if ramp==False:
        io.set_reg(0x101c, 4, io_group=io_group)
        for i in tile:
            if pacman_version=='v1rev4':
                io.set_reg(0x24010+(i-1), vdda_dac[i-1], io_group=io_group)
                io.set_reg(0x24020+(i-1), vddd_dac[i-1], io_group=io_group)
            elif pacman_version in ['v1rev3', 'v1rev3b', 'v1revS1']:
                io.set_reg(vdda_reg[i], vdda_dac[i-1], \
                           io_group=io_group)
                io.set_reg(vddd_reg[i], vddd_dac[i-1], \
                           io_group=io_group)
            else:
                print('WARNING: version ',pacman_version,' unknown')
                return  
            bits[-1*i]='1'
        print(bits)
        io.set_reg(0x00000010, int("".join(bits),2), io_group=io_group)
        io.reset_larpix(length=64, io_group=io_group)
        io.set_reg(0x00000018,0b11111111111111111111111111111111)
    return



def power_down_all_tiles(io, io_group, pacman_version):
    for i in range(1,9,1):
        if pacman_version=='v1rev4':
            io.set_reg(0x24010+(i-1), 0, io_group=io_group)
            io.set_reg(0x24020+(i-1), 0, io_group=io_group)
        elif pacman_version=='v1rev3' or pacman_version=='v1revS1':
            vdda_offset=(i-1)*2
            vddd_offset=((i-1)*2)+1
            io.set_reg(0x24130+vdda_offset, 0, io_group=io_group)
            io.set_reg(0x24131+vddd_offset, 0, io_group=io_group)
        else:
            print('WARNING: PACMAN version ',pacman_version,' unknown')
            return  
            
    # disable tile power
    io.set_reg(0x00000010, 0, io_group=io_group)

    ### test to debug i2c problems
    # disable global power
    #io.set_reg(0x00000014, 0, io_group=io_group)
    return



def power_readback(io, io_group, pacman_version, tile):
    readback={}
    for i in tile:
        readback[i]=[]
        if pacman_version=='v1rev4':
            vdda=io.get_reg(0x24030+(i-1), io_group=io_group)
            vddd=io.get_reg(0x24040+(i-1), io_group=io_group)
            idda=io.get_reg(0x24050+(i-1), io_group=io_group)
            iddd=io.get_reg(0x24060+(i-1), io_group=io_group)
            print('Tile ',i,'  VDDA: ',vdda,' mV  IDDA: ',idda*0.1,' mA  ',
                  'VDDD: ',vddd,' mV  IDDD: ',abs(iddd>>12),' mA')
            readback[i]=[vdda, idda*0.1, vddd, iddd>>12]
        elif pacman_version=='v1rev3' or 'v1revS1':
            vdda=io.get_reg(0x00024001+(i-1)*32+1, io_group=io_group)
            idda=io.get_reg(0x00024001+(i-1)*32, io_group=io_group)
            vddd=io.get_reg(0x00024001+(i-1)*32+17, io_group=io_group)
            iddd=io.get_reg(0x00024001+(i-1)*32+16, io_group=io_group)
            print('Tile ',i,'  VDDA: ',(((vdda>>16)>>3)*4),' mV  IDDA: ',
                  (((idda>>16)-(idda>>31)*65535)*500*0.001),' mV  VDDD: ',\
                  (((vddd>>16)>>3)*4),' mV  IDDD: ',
                  (((iddd>>16)-(iddd>>31)*65535)*500*0.001),' mA')
            readback[i]=[(((vdda>>16)>>3)*4),
                         (((idda>>16)-(idda>>31)*65535)*500*0.001),
                         (((vddd>>16)>>3)*4),
                         (((iddd>>16)-(iddd>>31)*65535)*500*0.001)]
        else:
            print('WARNING: PACMAN version ',pacman_version,' unknown')
            return readback
    return readback


def power_readback_to_slowcontrol(io, io_group, pacman_version, tile):
    readback={}
    for i in tile:
        readback[i]=[]
        if pacman_version=='v1rev4':
            vdda=io.get_reg(0x24030+(i-1), io_group=io_group)
            vddd=io.get_reg(0x24040+(i-1), io_group=io_group)
            idda=io.get_reg(0x24050+(i-1), io_group=io_group)
            iddd=io.get_reg(0x24060+(i-1), io_group=io_group)
            post1="crs,tpc="+str(io_group)+",meas=VDDA value="+str(vdda)
            post1="crs,tpc="+str(io_group)+",meas=VDDA value="+str(vdda)
            post1="crs,tpc="+str(io_group)+",meas=VDDA value="+str(vdda)
            post1="crs,tpc="+str(io_group)+",meas=VDDA value="+str(vdda)
            print('Tile ',i,'  VDDA: ',vdda,' mV  IDDA: ',idda*0.1,' mA  ',
                  'VDDD: ',vddd,' mV  IDDD: ',iddd>>12,' mA')
            readback[i]=[vdda, idda*0.1, vddd, iddd>>12]
        elif pacman_version=='v1rev3' or 'v1revS1':
            vdda=io.get_reg(0x00024001+(i-1)*32+1, io_group=io_group)
            idda=io.get_reg(0x00024001+(i-1)*32, io_group=io_group)
            vddd=io.get_reg(0x00024001+(i-1)*32+17, io_group=io_group)
            iddd=io.get_reg(0x00024001+(i-1)*32+16, io_group=io_group)
            print('Tile ',i,'  VDDA: ',(((vdda>>16)>>3)*4),' mV  IDDA: ',
                  (((idda>>16)-(idda>>31)*65535)*500*0.001),' mV  VDDD: ',\
                  (((vddd>>16)>>3)*4),' mV  IDDD: ',
                  (((iddd>>16)-(iddd>>31)*65535)*500*0.001),' mA')
            readback[i]=[(((vdda>>16)>>3)*4),
                         (((idda>>16)-(idda>>31)*65535)*500*0.001),
                         (((vddd>>16)>>3)*4),
                         (((iddd>>16)-(iddd>>31)*65535)*500*0.001)]
        else:
            print('WARNING: PACMAN version ',pacman_version,' unknown')
            return readback
    return readback
    
