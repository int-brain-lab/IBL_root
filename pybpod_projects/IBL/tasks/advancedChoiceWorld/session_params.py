# !/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import time
import numpy as np
import scipy.stats as st
from pythonosc import udp_client
import json


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


class rotary_encoder(object):

    def __init__(self, port, stim_positions, gain):
        self.port = port
        self.wheel_perim = 31 * 2 * np.pi  # = 194,778744523
        self.wheel_deg_mm = 360 / self.wheel_perim
        self.factor = self.wheel_deg_mm / gain
        self.SET_THRESHOLDS = [x * self.factor for x in stim_positions]
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
        self.GO_TONE = sounds.make_sound(frequency=self.GO_TONE_FREQUENCY,
                                         duration=self.GO_TONE_DURATION,
                                         amplitude=self.GO_TONE_AMPLITUDE)
        self.WHITE_NOISE = sounds.make_sound(
            frequency=-1,
            duration=self.WHITE_NOISE_DURATION,
            amplitude=self.WHITE_NOISE_AMPLITUDE)
        self.SD = sounds.configure_sounddevice()
        self.OSC_CLIENT = self.osc_client_init()
        self.state_machine_params_init()
        self.INIT_DATETIME = path_helper.init_datetime()
        self.SESSION_NAME = path_helper.session_name(self)

        self.ROOT_DATA_FOLDER = path_helper.root_data_folder(
            self.ROOT_DATA_FOLDER)
        self.MOUSE_DATA_FOLDER = path_helper.mouse_data_folder(self)
        self.SESSION_DATA_FOLDER = path_helper.session_data_folder(self)
        self.SETTINGS_FILE_PATH = path_helper.settings_file_path(self)
        self.DATA_FILE_PATH = path_helper.data_file_path(self)

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

    def state_machine_params_init(self):
        # Names of the RE events generated by Bpod
        self.ENCODER_EVENTS = ['RotaryEncoder{}_{}'.format(
            self.ROTARY_ENCODER_SERIAL_PORT_NUM, x) for x in
            list(range(1, len(self.STIM_POSITIONS) + 1))]
        # Dict mapping threshold crossings with name ov RE event
        self.THRESHOLD_EVENTS = dict(zip(self.STIM_POSITIONS,
                                         self.ENCODER_EVENTS))


class path_helper:

    def init_datetime():
        t = time.localtime()
        datetime = '{}-{}-{}_{}-{}-{}'.format(t.tm_year, t.tm_mon, t.tm_mday,
                                              t.tm_hour, t.tm_min, t.tm_sec)
        return datetime

    def session_name(sph):
        session_name = '{}_{}'.format(sph.MOUSE_NAME, sph.INIT_DATETIME)
        return session_name

    def root_data_folder(root_data_folder):
        # os.path.abspath('.') is C:\IBL_root\pybpod
        if root_data_folder is None:
            out = '../pybpod_projects/IBL/data/'
        else:
            if root_data_folder[-1] == '/':
                out = root_data_folder
            else:
                out = root_data_folder + '/'

        if not os.path.exists(out):
            os.mkdir(out)
        return out

    def mouse_data_folder(sph):
        mdf = sph.ROOT_DATA_FOLDER + sph.MOUSE_NAME + '/'
        if not os.path.exists(mdf):
            os.mkdir(mdf)
        return mdf

    def session_data_folder(sph):
        sdf = sph.MOUSE_DATA_FOLDER + sph.INIT_DATETIME + '/'
        if not os.path.exists(sdf):
            os.mkdir(sdf)
        return sdf

    def settings_file_path(sph):
        fp = sph.SESSION_DATA_FOLDER + sph.SESSION_NAME + '.settings.json'
        return fp

    def data_file_path(sph):
        fp = sph.SESSION_DATA_FOLDER + sph.SESSION_NAME + '.data.json'
        return fp


if __name__ == '__main__':
    pass
    # import settings
    # sph = session_param_handler(settings)

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
