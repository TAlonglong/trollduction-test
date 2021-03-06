#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016

# Author(s):

#   Trygve Aspenes

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Run the calibration script from AAPP for HIRS
Relay on several other steps before this can be DONE
"""

import os
import logging

from helper_functions import run_shell_command

LOG = logging.getLogger(__name__)

def do_hirs_calibration(process_config, timestamp):
    
    return_status = True
    
    #A list of accepted return codes for the various scripts/binaries run in this function
    accepted_return_codes_hirs_historic_file_manage = [0]

    #This function relays on beeing in a working directory
    current_dir = os.getcwd() #Store the dir to change back to after function complete
    os.chdir(process_config['working_directory'])

    hirs_version_use = None
    hirs_version = os.getenv('HIRSCL_VERSION',0)
    hirs_version_list = hirs_version.split()
    hirs_sats = os.getenv('HIRSCL_SAT','default')
    hirs_sat_list = hirs_sats.split() 
    index = 0
    for sat in hirs_sat_list:
        if sat in process_config['platform']:
            hirs_version_use = hirs_version_list[index]
        else:
            hirs_version_def = hirs_version_list[index]
            
        index+=1
        
    if hirs_version_use == None:
        hirs_version_use = hirs_version_def
         
    hirs_script = "hirscl"
    hirs_err_file = "hirscl.err"
    calibration_location = process_config['calibration_location']
    
    print "hirs_version_use {}".format(hirs_version_use)

    #pdb.set_trace()

    if int(hirs_version_use) > 1: # no calibration, just navigation
        calibration_location = "-l"
    elif  int(hirs_version_use) == 0 or "".join(process_config['a_tovs']) == 'TOVS':
        calibration_location = "-c -l"
    elif int(hirs_version_use) == 1:
        file_historic = os.path.join(os.getenv('PAR_CALIBRATION_MONITOR'), process_config['platform'],"hirs_historic.txt")
        if os.path.exists(file_historic):
            cmd="hirs_historic_file_manage -m {} -r {} -n {} {}".format(os.getenv('HIST_SIZE_HIGH'),os.getenv('HIST_SIZE_LOW'),os.getenv('HIST_NMAX'),file_historic)
            try:
                status, returncode, std, err = run_shell_command(cmd)
            except:
                LOG.error("Command {} failed.".format(cmd))
                return_status = False
            else:
                if returncode in accepted_return_codes_hirs_historic_file_manage:
                    LOG.debug("Command complete.")
                else:
                    LOG.error("Command {} failed with returncode {}".format(cmd, returncode))
                    LOG.error("stdout was: {}".format(std))
                    LOG.error("stderr was: {}".format(err))
                    return_status = False
        
        if return_status:
            cmd = "hcalcb1_algoV4 -s {0} -y {1:%Y} -m {1:%m} -d {1:%d} -h {1:%H} -n {1:%M}".format(process_config['platform'],timestamp)
            try:
                status, returncode, std, err = run_shell_command(cmd)
            except:
                import sys
                LOG.error("Command {} failed with {}.".format(cmd,sys.exc_info()[0]))
            else:
                if returncode != 0:
                    LOG.error("Command {} failed with {}".format(cmd, returncode))
                    _hirs_file = open(hirs_err_file,"w")
                    _hirs_file.write(std)
                    _hirs_file.write(err)
                    _hirs_file.close()
                    return_status = False
                    
            hirs_script = "hirscl_algoV4"
            hirs_err_file = "hirscl_algoV4.err"
            calibration_location = "-c -l"
    else:
        LOG.error("Can not figure out which hirs calibration algo version to use.")
        return_status = False
    
    if return_status:
        #Default AAPP config for PAR_NAVIGATION_DEFAULT_LISTESAT Metop platform is M01, M02, M04
        #but needed names are metop01 etc. Replace this inside the processing from now on.
        aapp_satellite_list = os.getenv('PAR_NAVIGATION_DEFAULT_LISTESAT').split()
        if process_config['platform'] not in aapp_satellite_list:
            LOG.warning("Can not find this platform in AAPP config variable PAR_NAVIGATION_DEFAULT_LISTESAT. Will try to find matches. But it can be a good idea to change this variable in the ATOVS_ENV7 file.")
            LOG.warning("Platform {} not in list: {}".format(process_config['platform'],aapp_satellite_list))
            if 'metop' in process_config['platform'] and (('M01' or 'M02' or 'M03' or 'M04') in aapp_satellite_list):
                LOG.info("Replace in this processing")
                PAR_NAVIGATION_DEFAULT_LISTESAT = os.getenv('PAR_NAVIGATION_DEFAULT_LISTESAT')
                PAR_NAVIGATION_DEFAULT_LISTESAT = PAR_NAVIGATION_DEFAULT_LISTESAT.replace('M01','metop01')
                PAR_NAVIGATION_DEFAULT_LISTESAT = PAR_NAVIGATION_DEFAULT_LISTESAT.replace('M02','metop02') 
                PAR_NAVIGATION_DEFAULT_LISTESAT = PAR_NAVIGATION_DEFAULT_LISTESAT.replace('M03','metop03') 
                PAR_NAVIGATION_DEFAULT_LISTESAT = PAR_NAVIGATION_DEFAULT_LISTESAT.replace('M04','metop04')
                os.environ['PAR_NAVIGATION_DEFAULT_LISTESAT'] = PAR_NAVIGATION_DEFAULT_LISTESAT
        
        cmd = "{} {} -s {} -d {:%Y%m%d} -h {:%H%M} -n {:05d} {}".format(hirs_script,calibration_location,
                                                                        process_config['platform'],timestamp,timestamp,
                                                                        process_config['orbit_number'], process_config['hirs_file'])
        try:
            status, returncode, out, err = run_shell_command(cmd, stdout_logfile="{}.log".format(hirs_script), stderr_logfile="{}".format(hirs_err_file))
        except:
            import sys
            LOG.error("Command {} failed {}.".format(cmd, sys.exc_info()[0]))
        else:
            if ( returncode != 0):
                LOG.error("Command {} failed with {}".format(cmd, returncode))
                _hirs_file = open(hirs_err_file,"w")
                _hirs_file.write(out)
                _hirs_file.write(err)
                _hirs_file.close()
                return_status = False

    #Change back after this is done
    os.chdir(current_dir)

    LOG.info("do_hirs_calibration complete!")
    
    return return_status