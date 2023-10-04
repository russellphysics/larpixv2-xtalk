#!/usr/bin/env python3

import argparse
from copy import deepcopy

import larpix
import larpix.io
import larpix.logger
import numpy as np
import time
import json

_default_pacman_tile=1
_default_io_group=1

vdda_reg = dict()
vdda_reg[1] = 0x00024130
vdda_reg[2] = 0x00024132
vdda_reg[3] = 0x00024134
vdda_reg[4] = 0x00024136
vdda_reg[5] = 0x00024138
vdda_reg[6] = 0x0002413a
vdda_reg[7] = 0x0002413c
vdda_reg[8] = 0x0002413e

vddd_reg = dict()
vddd_reg[1] = 0x00024131
vddd_reg[2] = 0x00024133
vddd_reg[3] = 0x00024135
vddd_reg[4] = 0x00024137
vddd_reg[5] = 0x00024139
vddd_reg[6] = 0x0002413b
vddd_reg[7] = 0x0002413d
vddd_reg[8] = 0x0002413f

power_val=dict()
#power_val[1]=0b00000001
#power_val[2]=0b00000010
#power_val[3]=0b00000100
#power_val[4]=0b00001000
#power_val[5]=0b00010000
#power_val[6]=0b00100000
#power_val[7]=0b01000000
#power_val[8]=0b10000000
power_val[1]=0b1000000001
power_val[2]=0b1000000010
power_val[3]=0b1000000100
power_val[4]=0b1000001000
power_val[5]=0b1000010000
power_val[6]=0b1000100000
power_val[7]=0b1001000000
power_val[8]=0b1010000000



def set_pacman_power(io, io_group, tile, vdda=46020, vddd=40605):
    io.set_reg(vdda_reg[tile], vdda, io_group=io_group)
    io.set_reg(vddd_reg[tile], vddd, io_group=io_group)
    io.set_reg(0x00000014, 1, io_group=io_group) # enable global larpix power
    io.set_reg(0x00000010, power_val[tile], io_group=io_group) # enable tiles to be powered
    io.set_reg(0x101C, 4, io_group=io_group)
    io.set_reg(0x18, 0xffffffff, io_group=io_group)
    time.sleep(0.1)


    
def power_registers():
    adcs=['VDDA', 'IDDA', 'VDDD', 'IDDD']
    data = {}
    for i in range(1,9,1):
        l = []
        offset = 0
        for adc in adcs:
            if adc=='VDDD': offset = (i-1)*32+17
            if adc=='IDDD': offset = (i-1)*32+16
            if adc=='VDDA': offset = (i-1)*32+1
            if adc=='IDDA': offset = (i-1)*32
            l.append( offset )
        data[i] = l
    return data



def report_power(io, io_group, tile):
    power = power_registers()
    adc_read = 0x00024001
    val_vdda = io.get_reg(adc_read+power[tile][0], io_group=io_group)
    val_idda = io.get_reg(adc_read+power[tile][1], io_group=io_group)
    val_vddd = io.get_reg(adc_read+power[tile][2], io_group=io_group)
    val_iddd = io.get_reg(adc_read+power[tile][3], io_group=io_group)
    print('TILE',tile,
          '\tVDDA:',(((val_vdda>>16)>>3)*4),'mV',
          '\tIDDA:',(((val_idda>>16)-(val_idda>>31)*65535)*500*0.01),'mA'
          '\tVDDD:',(((val_vddd>>16)>>3)*4),'mV'
          '\tIDDD:',(((val_iddd>>16)-(val_iddd>>31)*65535)*500*0.01),'mA'
    )

def write_power(io, io_group, tile):
    power = power_registers()
    adc_read = 0x00024001
    val_vdda = io.get_reg(adc_read+power[tile][0], io_group=io_group)
    val_idda = io.get_reg(adc_read+power[tile][1], io_group=io_group)
    val_vddd = io.get_reg(adc_read+power[tile][2], io_group=io_group)
    val_iddd = io.get_reg(adc_read+power[tile][3], io_group=io_group)
    time_format = time.strftime('%Y_%m_%d_%H_%S_%Z')
    filename = 'power-up-'+time_format+'.json'

    report = {}

    # !!!! TEMPERARY !!!!!
    tile_id = tile+62
    if tile == 1: tile_id = 83
    if tile == 2: tile_id = 85
    if tile == 3: tile_id = 76
    if tile == 4: tile_id = 80
    if tile == 5: tile_id = 89
    if tile == 6: tile_id = 88
    if tile == 7: tile_id = 66
    if tile == 8: tile_id = 75

    report['tile_id'] = tile_id
    report['pacman_id'] = 30
    report['pacman_tile'] = tile
    report['cable_length'] = 0.
    #report['vdda_dac'] = val_vdda
    report['vdda_dac'] = 46020
    report['vdda_mV'] = (((val_vdda>>16)>>3)*4)
    report['idda_mA'] = (((val_idda>>16)-(val_idda>>31)*65535)*500*0.01)
    #report['vddd_dac'] = val_vddd
    report['vddd_dac'] = 40605
    report['vddd_mV'] = (((val_vddd>>16)>>3)*4)
    report['iddd_mA'] = (((val_iddd>>16)-(val_iddd>>31)*65535)*500*0.01)

    json_string = json.dumps(report, indent=4)
    json_file = open(filename,"w")
    json_file.write(json_string)
    json_file.close()

    
def main(io_group=_default_io_group,
         pacman_tile=_default_pacman_tile,
         **kwargs):

    ###### create controller with pacman io
    c = larpix.Controller()
    c.io = larpix.io.PACMAN_IO(relaxed=True)
    
    ###### set power to tile    
    set_pacman_power(c.io, io_group, pacman_tile)
    report_power(c.io, io_group, pacman_tile)
    write_power(c.io, io_group, pacman_tile)

    ###### disable tile power
    c.io.set_reg(0x00000010, 0, io_group=io_group)
    
    return c



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--io_group', default=_default_io_group, type=int, help='''IO group ''')
    parser.add_argument('--pacman_tile', default=_default_pacman_tile, type=int, help='''PACMAN tile ''')
    args = parser.parse_args()
    c = main(**vars(args))


