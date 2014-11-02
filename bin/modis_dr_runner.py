# -*- coding: utf-8 -*-
"""Level-1 processing for Terra/Aqua Modis Direct Readout data. Using the SPA
modis level-1 processor from the NASA Direct Readout Lab (DRL). Listens for
pytroll messages from the Nimbus server (PDS file dispatch) and triggers
processing on direct readout data
"""


import os
import glob

import modis_runner
_PACKAGEDIR = modis_runner.__path__[0]
_CONFIG_PATH = os.path.join(os.path.dirname(_PACKAGEDIR), 'etc')

SPA_HOME = os.environ.get("SPA_HOME", '')
APPL_HOME = os.environ.get('MODIS_LVL1PROC', '')
ETC_DIR = os.path.join(SPA_HOME, 'etc')

import ConfigParser
CONFIG_PATH = os.environ.get('MODIS_LVL1PROC_CONFIG_DIR', _CONFIG_PATH)
print "CONFIG_PATH: ", CONFIG_PATH

CONF = ConfigParser.ConfigParser()
CONF.read(os.path.join(CONFIG_PATH, "modis_dr_config.cfg"))

MODE = os.getenv("SMHI_MODE")
if MODE is None:
    MODE = "offline"

OPTIONS = {}
for option, value in CONF.items(MODE, raw=True):
    OPTIONS[option] = value

DAYS_BETWEEN_URL_DOWNLOAD = OPTIONS.get('days_between_url_download', 14)
DAYS_KEEP_OLD_ETC_FILES = OPTIONS.get('days_keep_old_etc_files', 60)
URL = OPTIONS['url_modis_navigation']
NAVIGATION_HELPER_FILES = ['utcpole.dat', 'leapsec.dat']

SERVERNAME = OPTIONS['servername']

from datetime import datetime
from logging import handlers
import logging
LOG = logging.getLogger('modis-lvl1-processing')


#: Default time format
_DEFAULT_TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

#: Default log format
_DEFAULT_LOG_FORMAT = '[%(levelname)s: %(asctime)s : %(name)s] %(message)s'

import sys
_MODIS_LVL1PROC_LOG_FILE = os.environ.get('MODIS_LVL1PROC_LOG_FILE', None)


if _MODIS_LVL1PROC_LOG_FILE:
    #handler = logging.FileHandler(_MODIS_LVL1PROC_LOG_FILE)
    ndays = int(OPTIONS.get("log_rotation_days", 1))
    ncount = int(OPTIONS.get("log_rotation_backup", 5))
    handler = handlers.TimedRotatingFileHandler(_MODIS_LVL1PROC_LOG_FILE,
                                                when='midnight',
                                                interval=ndays,
                                                backupCount=ncount,
                                                encoding=None,
                                                delay=False,
                                                utc=True)

else:
    handler = logging.StreamHandler(sys.stderr)

formatter = logging.Formatter(fmt=_DEFAULT_LOG_FORMAT,
                              datefmt=_DEFAULT_TIME_FORMAT)
handler.setFormatter(formatter)

handler.setLevel(logging.DEBUG)
LOG.setLevel(logging.DEBUG)
LOG.addHandler(handler)


PACKETFILE_AQUA_PRFX = "P154095715409581540959"
MODISFILE_AQUA_PRFX = "P1540064AAAAAAAAAAAAAA"
MODISFILE_TERRA_PRFX = "P0420064AAAAAAAAAAAAAA"


from urlparse import urlparse
import posttroll.subscriber
from posttroll.publisher import Publish
from posttroll.message import Message


def clean_utcpole_and_leapsec_files(thr_days=60):
    """Clean any old *leapsec.dat* and *utcpole.dat* backup files, older than
    *thr_days* old

    """
    from glob import glob
    from datetime import datetime, timedelta
    import os

    now = datetime.utcnow()
    deltat = timedelta(days=int(thr_days))

    # Make the list of files to clean:
    flist = glob(os.path.join(ETC_DIR, '*.dat_*'))
    for filename in flist:
        lastpart = os.path.basename(filename).split('dat_')[1]
        tobj = datetime.strptime(lastpart, "%Y%m%d%H%M")
        if (now - tobj) > deltat:
            LOG.info("File to old, cleaning: %s " % filename)
            os.remove(filename)

    return


def check_utcpole_and_leapsec_files(thr_days=14):
    """Check if the files *leapsec.dat* and *utcpole.dat* are available in the
    etc directory and check if they are fresh.
    Return True if fresh/new files exists, otherwise False

    """

    from glob import glob
    from datetime import datetime, timedelta

    now = datetime.utcnow()
    tdelta = timedelta(days=int(thr_days))

    files_ok = True
    for bname in NAVIGATION_HELPER_FILES:
        LOG.info("File " + str(bname) + "...")
        filename = os.path.join(ETC_DIR, bname)
        if os.path.exists(filename):
            # Check how old it is:
            realpath = os.path.realpath(filename)
            # Get the timestamp in the file name:
            try:
                tstamp = os.path.basename(realpath).split('.dat_')[1]
            except IndexError:
                files_ok = False
                break
            tobj = datetime.strptime(tstamp, "%Y%m%d%H%M")

            if (now - tobj) > tdelta:
                LOG.info("File too old! File=%s " % filename)
                files_ok = False
                break
        else:
            LOG.info("No navigation helper file: %s" % filename)
            files_ok = False
            break

    return files_ok


def update_utcpole_and_leapsec_files():
    """
    Function to update the ancillary data files *leapsec.dat* and
    *utcpole.dat* used in the navigation of MODIS direct readout data.

    These files need to be updated at least once every 2nd week, in order to
    achieve the best possible navigation.

    """
    import urllib2
    import os
    import sys
    from datetime import datetime

    # Start cleaning any possible old files:
    clean_utcpole_and_leapsec_files(DAYS_KEEP_OLD_ETC_FILES)

    try:
        usock = urllib2.urlopen(URL)
    except urllib2.URLError:
        LOG.warning('Failed opening url: ' + URL)
        return
    else:
        usock.close()

    LOG.info("Start downloading....")
    now = datetime.utcnow()
    timestamp = now.strftime('%Y%m%d%H%M')
    for filename in NAVIGATION_HELPER_FILES:
        try:
            usock = urllib2.urlopen(URL + filename)
        except urllib2.HTTPError:
            LOG.warning("Failed opening file " + filename)
            continue

        data = usock.read()
        usock.close()
        LOG.info("Data retrieved from url...")

        # I store the files with a timestamp attached, in order not to remove
        # the existing files.  In case something gets wrong in the download, we
        # can handle this by not changing the sym-links below:
        newname = filename + '_' + timestamp
        outfile = os.path.join(ETC_DIR, newname)
        linkfile = os.path.join(ETC_DIR, filename)
        fd = open(outfile, 'w')
        fd.write(data)
        fd.close()

        LOG.info("Data written to file " + outfile)
        # Here we could make a check on the sanity of the downloaded files:
        # TODO!

        # Update the symlinks (assuming the files are okay):
        if os.path.islink(linkfile):
            os.unlink(linkfile)

        os.symlink(outfile, linkfile)

    return


# ---------------------------------------------------------------------------
def run_terra_l0l1(pdsfile):
    """Process Terra MODIS level 0 PDS data to level 1a/1b"""

    from subprocess import Popen, PIPE, STDOUT

    working_dir = OPTIONS['working_dir']
    # Change working directory:
    if not os.path.exists(working_dir):
        try:
            os.makedirs(working_dir)
        except OSError:
            LOG.error("Failed creating working directory %s" % working_dir)
            working_dir = '/tmp'
            LOG.info("Will use /tmp")

    #fdwork = os.open(working_dir, os.O_RDONLY)
    # os.fchdir(fdwork)

    level1b_home = OPTIONS['level1b_home']
    filetype_terra = OPTIONS['filetype_terra']
    geofile_terra = OPTIONS['geofile_terra']
    level1a_terra = OPTIONS['level1a_terra']
    level1b_terra = OPTIONS['level1b_terra']
    level1b_250m_terra = OPTIONS['level1b_250m_terra']
    level1b_500m_terra = OPTIONS['level1b_500m_terra']

    # Get the observation time from the filename as a datetime object:
    bname = os.path.basename(pdsfile)
    obstime = datetime.strptime(bname, filetype_terra)

    # level1_home
    proctime = datetime.now()
    lastpart = proctime.strftime("%Y%j%H%M%S.hdf")
    firstpart = obstime.strftime(level1b_terra)
    mod021km_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(level1b_250m_terra)
    mod02qkm_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(level1b_500m_terra)
    mod02hkm_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    lastpart = proctime.strftime("%Y%j%H%M%S.hdf")
    firstpart = obstime.strftime(level1a_terra)
    mod01_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(geofile_terra)
    mod03_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)

    retv = {'mod021km_file': mod021km_file,
            'mod02hkm_file': mod02hkm_file,
            'mod02qkm_file': mod02qkm_file,
            'level1a_file': mod01_file,
            'geo_file': mod03_file}

    mod01files = glob.glob("%s/%s*hdf" % (level1b_home, firstpart))
    if len(mod01files) > 0:
        LOG.warning(
            "Level 1 file for this scene already exists: %s" % mod01files[0])
        # return retv

    LOG.info("Level-1 filename: " + str(mod01_file))
    satellite = "Terra"
    wrapper_home = os.path.join(SPA_HOME, "modisl1db/wrapper/l0tol1")
    cmdstr = ("%s/run modis.pds %s sat %s modis.mxd01 %s modis.mxd03 %s" %
              (wrapper_home, pdsfile, satellite, mod01_file, mod03_file))

    # Run the command:
    modislvl1b_proc = Popen(cmdstr, shell=True,
                            cwd=working_dir,
                            stderr=PIPE, stdout=PIPE)

    while True:
        line = modislvl1b_proc.stdout.readline()
        if not line:
            break
        LOG.info(line)

    while True:
        errline = modislvl1b_proc.stderr.readline()
        if not errline:
            break
        LOG.info(errline)

    modislvl1b_proc.poll()
    #modislvl1b_status = modislvl1b_proc.returncode

    # Now do the level1a-1b processing:
    lut_home = os.path.join(SPA_HOME, "modisl1db/algorithm/data/modist/cal")
    refl_lut = os.path.join(lut_home, "MOD02_Reflective_LUTs.V6.1.6.0_OC.hdf")
    emiss_lut = os.path.join(lut_home, "MOD02_Emissive_LUTs.V6.1.6.0_OC.hdf")
    qa_lut = os.path.join(lut_home, "MOD02_QA_LUTs.V6.1.6.0_OC.hdf")

    wrapper_home = os.path.join(SPA_HOME, "modisl1db/wrapper/l1atob")
    cmdstr = ("%s/run modis.mxd01 %s modis.mxd03 %s modis_reflective_luts %s modis_emissive_luts %s modis_qa_luts %s modis.mxd021km %s modis.mxd02hkm %s modis.mxd02qkm %s" %
              (wrapper_home, mod01_file, mod03_file,
               refl_lut, emiss_lut, qa_lut, mod021km_file, mod02hkm_file, mod02qkm_file))
    # Run the command:
    modislvl1b_proc = Popen(cmdstr, shell=True,
                            cwd=working_dir,
                            stderr=PIPE, stdout=PIPE)

    while True:
        line = modislvl1b_proc.stdout.readline()
        if not line:
            break
        LOG.info(line)

    while True:
        errline = modislvl1b_proc.stderr.readline()
        if not errline:
            break
        LOG.info(errline)

    modislvl1b_proc.poll()

    # Close working directory:
    # os.close(fdwork)

    return retv

# ---------------------------------------------------------------------------


def run_aqua_gbad(obs_time):
    """Run the gbad for aqua"""

    from subprocess import Popen, PIPE, STDOUT

    level0_home = OPTIONS['level0_home']
    packetfile = os.path.join(level0_home,
                              obs_time.strftime(OPTIONS['packetfile_aqua']))

    att_dir = OPTIONS['attitude_home']
    eph_dir = OPTIONS['ephemeris_home']
    spa_config_file = OPTIONS['spa_config_file']
    att_file = os.path.basename(packetfile).split('.PDS')[0] + '.att'
    att_file = os.path.join(att_dir, att_file)
    eph_file = os.path.basename(packetfile).split('.PDS')[0] + '.eph'
    eph_file = os.path.join(eph_dir, eph_file)
    LOG.info("eph-file = " + eph_file)

    wrapper_home = SPA_HOME + "/gbad/wrapper/gbad"
    cmdstr = ("%s/run aqua.gbad.pds %s aqua.gbad_att %s aqua.gbad_eph %s configurationfile %s" %
              (wrapper_home, packetfile, att_file, eph_file, spa_config_file))
    LOG.info("Command: " + cmdstr)
    # Run the command:
    # os.system(cmdstr)
    modislvl1b_proc = Popen(cmdstr, shell=True,
                            stderr=PIPE, stdout=PIPE)

    while True:
        line = modislvl1b_proc.stdout.readline()
        if not line:
            break
        LOG.info(line)

    while True:
        errline = modislvl1b_proc.stderr.readline()
        if not errline:
            break
        LOG.info(errline)

    modislvl1b_proc.poll()

    return att_file, eph_file

# ---------------------------------------------------------------------------


def run_aqua_l0l1(pdsfile):
    """Process Aqua MODIS level 0 PDS data to level 1a/1b"""
    import os
    from subprocess import Popen, PIPE, STDOUT

    working_dir = OPTIONS['working_dir']
    if not os.path.exists(working_dir):
        try:
            os.makedirs(working_dir)
        except OSError:
            LOG.error("Failed creating working directory %s" % working_dir)
            working_dir = '/tmp'
            LOG.info("Will use /tmp")

    #ephemeris_home = OPTIONS['ephemeris_home']
    #attitude_home = OPTIONS['attitude_home']
    level1b_home = OPTIONS['level1b_home']
    filetype_aqua = OPTIONS['filetype_aqua']
    geofile_aqua = OPTIONS['geofile_aqua']
    level1a_aqua = OPTIONS['level1a_aqua']
    level1b_aqua = OPTIONS['level1b_aqua']
    level1b_250m_aqua = OPTIONS['level1b_250m_aqua']
    level1b_500m_aqua = OPTIONS['level1b_500m_aqua']

    # Get the observation time from the filename as a datetime object:
    bname = os.path.basename(pdsfile)
    obstime = datetime.strptime(bname, filetype_aqua)

    # Get ephemeris and attitude names! FIXME!
    attitude, ephemeris = run_aqua_gbad(obstime)
    #ephemeris = "%s/P15409571540958154095911343000923001.eph" % ephemeris_home
    #attitude  = "%s/P15409571540958154095911343000923001.att" % attitude_home

    leapsec_name = os.path.join(ETC_DIR, "leapsec.dat")
    utcpole_name = os.path.join(ETC_DIR, "utcpole.dat")
    geocheck_threshold = 50  # Hardcoded threshold!

    proctime = datetime.now()
    lastpart = proctime.strftime("%Y%j%H%M%S.hdf")
    firstpart = obstime.strftime(level1a_aqua)
    mod01files = glob.glob("%s/%s*hdf" % (level1b_home, firstpart))
    if len(mod01files) > 0:
        LOG.warning(
            "Level 1 file for this scene already exists: %s" % mod01files[0])
        # return

    mod01_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(geofile_aqua)
    mod03_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)

    LOG.warning("Level-1 filename: " + str(mod01_file))
    satellite = "Aqua"
    wrapper_home = os.path.join(SPA_HOME, "modisl1db/wrapper/l0tol1")
    cmdstr = ("%s/run modis.pds %s sat %s modis.mxd01 %s modis.mxd03 %s gbad_eph %s gbad_att %s leapsec %s utcpole %s geocheck_threshold %s" %
              (wrapper_home, pdsfile, satellite, mod01_file, mod03_file,
               ephemeris, attitude, leapsec_name, utcpole_name, geocheck_threshold))
    # Run the command:
    modislvl1b_proc = Popen(cmdstr, shell=True,
                            cwd=working_dir,
                            stderr=PIPE, stdout=PIPE)

    while True:
        line = modislvl1b_proc.stdout.readline()
        if not line:
            break
        LOG.info(line)

    while True:
        errline = modislvl1b_proc.stderr.readline()
        if not errline:
            break
        LOG.info(errline)

    modislvl1b_proc.poll()

    # Now do the level1a-1b processing:
    lut_home = os.path.join(SPA_HOME, "modisl1db/algorithm/data/modisa/cal")
    refl_lut = os.path.join(lut_home, "MYD02_Reflective_LUTs.V6.1.7.1_OCb.hdf")
    emiss_lut = os.path.join(lut_home, "MYD02_Emissive_LUTs.V6.1.7.1_OCb.hdf")
    qa_lut = os.path.join(lut_home, "MYD02_QA_LUTs.V6.1.7.1_OCb.hdf")

    wrapper_home = os.path.join(SPA_HOME, "modisl1db/wrapper/l1atob")
    # level1_home
    proctime = datetime.now()
    lastpart = proctime.strftime("%Y%j%H%M%S.hdf")
    firstpart = obstime.strftime(level1b_aqua)
    mod021km_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(level1b_250m_aqua)
    mod02qkm_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    firstpart = obstime.strftime(level1b_500m_aqua)
    mod02hkm_file = "%s/%s_%s" % (level1b_home, firstpart, lastpart)
    cmdstr = ("%s/run modis.mxd01 %s modis.mxd03 %s modis_reflective_luts %s modis_emissive_luts %s modis_qa_luts %s modis.mxd021km %s modis.mxd02hkm %s modis.mxd02qkm %s" %
              (wrapper_home, mod01_file, mod03_file,
               refl_lut, emiss_lut, qa_lut, mod021km_file, mod02hkm_file, mod02qkm_file))

    modislvl1b_proc = Popen(cmdstr, shell=True,
                            cwd=working_dir,
                            stderr=PIPE, stdout=PIPE)

    while True:
        line = modislvl1b_proc.stdout.readline()
        if not line:
            break
        LOG.info(line)

    while True:
        errline = modislvl1b_proc.stderr.readline()
        if not errline:
            break
        LOG.info(errline)

    modislvl1b_proc.poll()

    retv = {'mod021km_file': mod021km_file,
            'mod02hkm_file': mod02hkm_file,
            'mod02qkm_file': mod02qkm_file,
            'level1a_file': mod01_file,
            'geo_file': mod03_file}

    return retv


def send_message(this_publisher, msg):
    """Send a message for down-stream processing"""

    LOG.debug("sending: " + str(msg))
    this_publisher.send(msg)

    return


def create_message(mda, filename, level):
    LOG.debug("type(mda): " + str(type(mda)))
    to_send = mda.copy()
    if isinstance(filename, (list, tuple, set)):
        del to_send['uri']
        del to_send['uid']
        to_send['dataset'] = [{'uri': 'file://' + fname,
                               'uid': os.path.basename(fname)}
                              for fname in filename]
        mtype = 'dataset'
    else:
        to_send['uri'] = ('file://' + filename)
        to_send['uid'] = os.path.basename(filename)
        mtype = 'file'
    to_send['format'] = 'EOS'
    to_send['data_processing_level'] = level
    to_send['type'] = 'HDF4'

    message = Message('/'.join(('',
                                str(to_send['format']),
                                str(to_send['data_processing_level']),
                                'norrköping',
                                MODE,
                                'polar'
                                'direct_readout')),
                      mtype, to_send).encode()
    return message


def start_modis_lvl1_processing(level1b_home, eos_files,
                                mypublisher, message):
    """From a posttroll message start the modis lvl1 processing"""

    LOG.info("")
    LOG.info("EOS files: " + str(eos_files))
    LOG.info("\tMessage:")
    LOG.info(message)
    urlobj = urlparse(message.data['uri'])
    LOG.info("Server = " + str(urlobj.netloc))
    if urlobj.netloc != SERVERNAME:
        return eos_files
    LOG.info("Ok... " + str(urlobj.netloc))
    LOG.info("Sat and Instrument: " + str(message.data['platform_name']) + " "
             + str(message.data['sensor']))

    if 'start_time' in message.data:
        start_time = message.data['start_time']
    else:
        LOG.warning("No start time in message!")
        start_time = None

    if 'end_time' in message.data:
        end_time = message.data['end_time']
    else:
        LOG.warning("No end time in message!")
        end_time = None

    if (message.data['platform_name'] == "EOS-Terra" and
            message.data['sensor'] == 'modis'):
        orbnum = message.data.get('orbit_number', None)

        path, fname = os.path.split(urlobj.path)
        if fname.find(MODISFILE_TERRA_PRFX) == 0 and fname.endswith('001.PDS'):
            # Check if the file exists:
            if not os.path.exists(urlobj.path):
                LOG.warning("File is reported to be dispatched " +
                            "but is not there! File = " +
                            urlobj.path)
                return eos_files

            # Do processing:
            LOG.info("Level-0 to lvl1 processing on terra start!" +
                     " Start time = " + str(start_time))
            # Start checking and dowloading the luts (utcpole.dat and
            # leapsec.dat):
            LOG.info("Checking the modis luts and updating " +
                     "from internet if necessary!")
            fresh = check_utcpole_and_leapsec_files(DAYS_BETWEEN_URL_DOWNLOAD)
            if fresh:
                LOG.info("Files in etc dir are fresh! No url downloading....")
            else:
                LOG.warning("Files in etc are non existent or too old. " +
                            "Start url fetch...")
                update_utcpole_and_leapsec_files()

            if orbnum:
                LOG.info("Orb = %d" % orbnum)
            LOG.info("File = " + str(urlobj.path))
            result_files = run_terra_l0l1(urlobj.path)

            LOG.info("Result files: " + str(result_files))

            # Assume everything has gone well!
            # Add intelligence to run-function. FIXME!
            # Now publish:

            l1b_files = [result_files[key] for key in ['geo_file',
                                                       'mod021km_file',
                                                       'mod02hkm_file',
                                                       'mod02qkm_file']]
            LOG.debug("Mesage:")
            LOG.debug(message)
            LOG.debug("Message data: " + str(message.data))

            send_message(mypublisher, create_message(message.data,
                                                     l1b_files,
                                                     "1b"))

            l1a_file = result_files['level1a_file']

            send_message(mypublisher, create_message(message.data,
                                                     l1a_file,
                                                     "1a"))

    elif (message.data['platform_name'] == "AQUA" and
          (message.data['sensor'] == 'modis' or
           message.data['sensor'] == 'gbad')):
        orbnum = message.data.get('orbit_number')

        if start_time:
            scene_id = start_time.strftime('%Y%m%d%H%M')
        else:
            LOG.warning("No start time!!!")
            return eos_files

        path, fname = os.path.split(urlobj.path)
        LOG.debug("Path and filename: " + str(path) + ' ' + str(fname))
        if ((fname.find(MODISFILE_AQUA_PRFX) == 0 or
             fname.find(PACKETFILE_AQUA_PRFX) == 0) and
                fname.endswith('001.PDS')):
            # Check if the file exists:
            if not os.path.exists(urlobj.path):
                LOG.warning("File is reported to be dispatched " +
                            "but is not there! File = " +
                            urlobj.path)
                return eos_files

            if not scene_id in eos_files:
                eos_files[scene_id] = []
            if len(eos_files[scene_id]) == 0:
                eos_files[scene_id] = [urlobj.path]
            else:
                if not urlobj.path in eos_files[scene_id]:
                    eos_files[scene_id].append(urlobj.path)

        if scene_id in eos_files and len(eos_files[scene_id]) == 2:
            LOG.info("aqua files with scene-id = %r :" % scene_id +
                     str(eos_files[scene_id]))

            aquanames = [os.path.basename(s) for s in eos_files[scene_id]]
            LOG.info('aquanames: ' + str(aquanames))

            if (aquanames[0].find(MODISFILE_AQUA_PRFX) == 0 and
                    aquanames[1].find(PACKETFILE_AQUA_PRFX) == 0):
                modisfile = eos_files[scene_id][0]
            elif (aquanames[1].find(MODISFILE_AQUA_PRFX) == 0 and
                  aquanames[0].find(PACKETFILE_AQUA_PRFX) == 0):
                modisfile = eos_files[scene_id][1]
            else:
                LOG.error("Either MODIS file or packet file not there!?")
                return eos_files

            # Do processing:
            LOG.info("Level-0 to lvl1 processing on aqua start! " +
                     "Scene = %r" % scene_id)

            # Start checking and dowloading the luts (utcpole.dat and
            # leapsec.dat):
            LOG.info("Checking the modis luts and updating " +
                     "from internet if necessary!")
            fresh = check_utcpole_and_leapsec_files(DAYS_BETWEEN_URL_DOWNLOAD)
            if fresh:
                LOG.info("Files in etc dir are fresh! No url downloading....")
            else:
                LOG.warning("Files in etc are non existent or too old. " +
                            "Start url fetch...")
                update_utcpole_and_leapsec_files()

            LOG.info("File = " + str(modisfile))
            result_files = run_aqua_l0l1(modisfile)

            LOG.info("Result files: " + str(result_files))
            # Clean register: aqua_files dict
            LOG.info('Clean the internal aqua_files register')
            eos_files = {}

            # Now publish:
            l1b_files = [result_files[key] for key in ['geo_file',
                                                       'mod021km_file',
                                                       'mod02hkm_file',
                                                       'mod02qkm_file']]
            send_message(mypublisher, create_message(l1b_files,
                                                     message.data,
                                                     "1b"))

            l1a_file = result_files['level1a_file']

            send_message(mypublisher, create_message(l1a_file,
                                                     message.data,
                                                     "1a"))

    else:
        return eos_files

    return eos_files


def modis_live_runner():
    """Listens and triggers processing"""

    lvl1b_home = OPTIONS['level1b_home']
    # Roll over log files at application start:
    try:
        LOG.handlers[0].doRollover()
    except AttributeError:
        LOG.warning("No log rotation supported for this handler...")
    LOG.info("*** Start the MODIS level-1 runner:")
    with posttroll.subscriber.Subscribe('receiver', ['PDS/0', ], True) as subscr:
        with Publish('modis_dr_runner', 0) as publisher:
            aquafiles = {}
            for msg in subscr.recv():
                aquafiles = start_modis_lvl1_processing(lvl1b_home,
                                                        aquafiles,
                                                        publisher, msg)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    modis_live_runner()

    #aqua_modis_file = '/san1/polar_in/direct_readout/modis/P1540064AAAAAAAAAAAAAA12298130323001.PDS'

    # print DAYS_BETWEEN_URL_DOWNLOAD
    # LOG.info("Checking the modis luts and updating " +
    #         "from internet if necessary!")
    #fresh = check_utcpole_and_leapsec_files(DAYS_BETWEEN_URL_DOWNLOAD)
    # print "fresh: ", fresh
    # if fresh:
    #    LOG.info("Files in etc dir are fresh! No url downloading....")
    # else:
    #    LOG.warning("Files in etc are non existent or too old. " +
    #                "Start url fetch...")
    #    update_utcpole_and_leapsec_files()

    #LOG.info("File = " + str(aqua_modis_file))

    #lvl1filename = run_aqua_l0l1(aqua_modis_file)
