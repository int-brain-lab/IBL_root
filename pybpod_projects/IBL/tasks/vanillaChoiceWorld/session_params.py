# -*- coding: utf-8 -*-
# @Author: Niccolò Bonacchi
# @Date:   2018-02-02 17:19:09
# @Last Modified by:   Niccolò Bonacchi
# @Last Modified time: 2018-02-26 16:07:42
import os
import datetime
import numpy as np
import scipy.stats as st
from pythonosc import udp_client
import json
import glob


class sounds():
    """Software solution for playing sounds"""
    def configure_sounddevice(SD=None):
        if SD is None:
            import sounddevice as SD
        SD.default.latency = 'low'
        SD.default.channels = 2
        return SD

    def make_sound(frequency=10000, duration=0.1, amplitude=1, fade_in=0.01):
        """builds sound to feed to sounddevice lib
        if frequency is set to -1 will produce white noise"""
        FsOut = 44100  # sample rate, depend on the sound card
        toneDuration = duration  # sec
        amplitude = amplitude  # [0->1]
        frequency = frequency  # Hz
        onsetDur = fade_in  # sec

        tvec = np.linspace(0, toneDuration, toneDuration * FsOut)
        sound = amplitude * np.sin(2 * np.pi * frequency * tvec)  # sound vec
        size = FsOut * onsetDur / 2  #
        dist = st.expon(0., size)  # distribution object provided by scipy
        F = dist.cdf  # cumulative density function
        ker = F(range(int(FsOut * toneDuration)))
        sound = sound * ker
        if frequency == -1:
            sound = amplitude * np.random.rand(sound.size)
        return sound

    def play_sound(sound):
        pass


class rotary_encoder(object):  # TODO: SAVE THIS IN SETTINGS FILE ALSO

    def __init__(self, port, stim_positions, quiescence_thresholds, gain):
        self.port = port
        self.wheel_perim = 31 * 2 * np.pi  # = 194,778744523
        self.wheel_deg_mm = 360 / self.wheel_perim
        self.factor = self.wheel_deg_mm / gain
        self.all_thresholds = stim_positions + quiescence_thresholds
        self.SET_THRESHOLDS = [x * self.factor for x in self.all_thresholds]
        self.ENABLE_THRESHOLDS = [(True if x != 0
                                   else False) for x in self.SET_THRESHOLDS]
        # ENABLE_THRESHOLDS needs 8 bools even if only 2 thresholds are set
        while len(self.ENABLE_THRESHOLDS) < 8:
            self.ENABLE_THRESHOLDS.append(False)

    def configure(self, RotaryEncoderModule):
        m = RotaryEncoderModule(self.port)
        m.set_zero_position()  # Not necessarily needed
        m.set_thresholds(self.SET_THRESHOLDS)
        m.enable_thresholds(self.ENABLE_THRESHOLDS)
        m.close()


class session_param_handler(object):
    """Session object copies settings parameters and calculates other secondary
    session parameters, saves all params in a settings file.json"""

    def __init__(self, task_settings):
        tsp = {i: task_settings.__dict__[i]
               for i in [x for x in dir(task_settings) if '__' not in x]}
        self.__dict__.update(tsp)

        self.VALVE_TIME = self.CALIBRATION_VALUE * self.TARGET_REWARD

        self.GO_TONE = sounds.make_sound(frequency=self.GO_TONE_FREQUENCY,
                                         duration=self.GO_TONE_DURATION,
                                         amplitude=self.GO_TONE_AMPLITUDE)
        self.WHITE_NOISE = sounds.make_sound(
            frequency=-1,
            duration=self.WHITE_NOISE_DURATION,
            amplitude=self.WHITE_NOISE_AMPLITUDE)
        self.SD = sounds.configure_sounddevice()
        self.OSC_CLIENT = self.osc_client_init()

        self.ALL_THRESHOLDS = (self.STIM_POSITIONS +
                               self.QUIESCENCE_THRESHOLDS)
        # Names of the RE events generated by Bpod
        self.ENCODER_EVENTS = ['RotaryEncoder{}_{}'.format(
            self.ROTARY_ENCODER_SERIAL_PORT_NUM, x) for x in
            list(range(1, len(self.ALL_THRESHOLDS) + 1))]
        # Dict mapping threshold crossings with name ov RE event
        self.THRESHOLD_EVENTS = dict(zip(self.ALL_THRESHOLDS,
                                         self.ENCODER_EVENTS))

        self.SESSION_NAME = datetime.datetime.now().isoformat().replace(':',
                                                                        '_')
        self.TASK_NAME = '{}_{}'.format('pycw', self.TASK.strip('ChoiceWorld'))

        self.SESSION_ID = '{}_{}_{}'.format(self.MOUSE_NAME,
                                            self.SESSION_NAME,
                                            self.TASK_NAME)

        self.ROOT_DATA_FOLDER = path_helper.root_data_folder(
            self.ROOT_DATA_FOLDER)
        self.MOUSE_DATA_FOLDER = path_helper.mouse_data_folder(self)
        self.PREVIOUS_DATA_FILE = path_helper.previous_data_file(self)
        self.SESSION_DATA_FOLDER = path_helper.session_data_folder(self)
        self.SETTINGS_FILE_PATH = path_helper.settings_file_path(self)
        self.DATA_FILE_PATH = path_helper.data_file_path(self)

        self.STATE_AFTER_START = ('stim_on' if self.QUIESCENT_PERIOD == 0
                                  else 'quiescent_period')

        self.save_session_settings()

    def reprJSON(self):
        d = self.__dict__.copy()
        d['GO_TONE'] = 'sounds.make_sound(frequency={}, duration={}, \
amplitude={})'.format(self.GO_TONE_FREQUENCY, self.GO_TONE_DURATION,
                      self.GO_TONE_AMPLITUDE)
        d['WHITE_NOISE'] = 'sounds.make_sound(frequency=-1, duration={}, \
amplitude={})'.format(self.WHITE_NOISE_DURATION, self.WHITE_NOISE_AMPLITUDE)
        d['SD'] = str(d['SD'])
        d['OSC_CLIENT'] = str(d['OSC_CLIENT'])
        return d

    def save_session_settings(self):
        with open(self.SETTINGS_FILE_PATH, 'a') as f:
            f.write(json.dumps(self.reprJSON()))
            f.write('\n')
        return

    def osc_client_init(self):
        osc_client = udp_client.SimpleUDPClient(self.OSC_CLIENT_IP,
                                                self.OSC_CLIENT_PORT)
        return osc_client


class path_helper:

    def root_data_folder(rdf):
        # if running as main
        if __name__ == '__main__' and os.name == 'nt':
            return 'C:\\IBL_root\\pybpod_projects\\IBL\\data/'
        elif __name__ == '__main__' and os.name == 'posix':
            return '/home/nico/Projects/IBL/IBL-github/pybpod_projects/IBL/\
data/'

        # If no data folder was defined in settings file use default folder
        if rdf is None:
            out = 'C:/IBL_root/pybpod_data/'  # '../pybpod_projects/IBL/data/'
        else:
            # If folder was defined in settings check if endswith '/'
            out = rdf if rdf.endswith('/') else rdf + '/'

        if not os.path.exists(out):
            os.mkdir(out)
        return out

    def mouse_data_folder(sph):
        mdf = sph.ROOT_DATA_FOLDER + sph.MOUSE_NAME + '/'
        if not os.path.exists(mdf):
            os.mkdir(mdf)
        return mdf

    def session_data_folder(sph):
        sdf = sph.MOUSE_DATA_FOLDER + sph.SESSION_NAME + '/'
        if not os.path.exists(sdf):
            os.mkdir(sdf)
        return sdf

    def settings_file_path(sph):
        return (sph.SESSION_DATA_FOLDER + sph.TASK_NAME + '.settings.json')

    def data_file_path(sph):
        return (sph.SESSION_DATA_FOLDER + sph.TASK_NAME + '.data.json')

    def previous_data_file(sph):
        session_list = glob.glob(sph.MOUSE_DATA_FOLDER + '*')
        if not session_list:
            return None
        latest_session = max(session_list, key=os.path.getctime)
        prev_session_files = glob.glob(latest_session + '/*')
        prev_data_file = [x for x in prev_session_files if 'data.' in x]
        if prev_data_file:
            return prev_data_file[0]
        else:
            # Alternatively could call myself again after deleting session...
            del_file = open(latest_session + '/NO_DATA_FOUND_DELETE_SESSION',
                            'a')
            del_file.close()
            return None

        return prev_data_file


if __name__ == '__main__':
    import task_settings
    sph = session_param_handler(task_settings)

    # session_settings = []
    # with open(sph.SETTINGS_FILE_PATH, 'r') as f:
    #     for line in f:
    #         dict_obj = json.loads(line)
    #         session_settings.append(dict_obj)
    # print(dict_obj)

    # f = open(sph.SETTINGS_FILE_PATH + 'dump', 'w')
    # json.dump(sph.reprJSON(), f)
    # f.close()

    # f = open(sph.SETTINGS_FILE_PATH + 'dump', 'r')
    # bla = json.load(f)
    # f.close()
    # print(bla)
