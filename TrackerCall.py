#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pickle
import socket

import requests


class NewTrackeroverProxy:

    def __init__(self, login, system_options):
        self.tracker_data = TrackerData(system_options.getValue('PPMS_systemid'),
                                        system_options.getValue('tracker_frequency'),
                                        login,
                                        system_options.getValue('PPMS_systemcode'),
                                        )

        self.proxy_address = system_options.getValue('proxy_address')
        self.tracker_port = int(system_options.getValue('tracker_port'))

        if login not in system_options.getValue('ignored_logins').split(','):
            self.sendtoTracker()

    # dict is pickled and sent to proxy
    def sendtoTracker(self):
        self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_socket.connect((self.proxy_address, self.tracker_port))
        pickled_dict = pickle.dumps(self.tracker_data.data, protocol=2)
        self.proxy_socket.sendall(pickled_dict)
        self.proxy_socket.close()


class NewTrackerCall:

    def __init__(self, login, system_options, proxy_options):
        self.tracker_data = TrackerData(system_options.getValue('PPMS_systemid'),
                                        system_options.getValue('tracker_frequency'),
                                        login,
                                        system_options.getValue('PPMS_systemcode'),
                                        proxy_options.getValue('tracker_URL')
                                        )

        if login not in system_options.getValue('ignored_logins').split(','):
            self.sendtoPPMSAPI()

    def sendtoPPMSAPI(self):
        requests.post(self.tracker_data.url, headers=self.tracker_data.header, data=self.tracker_data.code)


class TrackerData:

    def __init__(self, id, freq, login, code, url=None):
        self.data = {
            'id': id,
            'freq': freq,
            'user': login,
            'code': code,
        }

        self.url = ''
        if url is not None:
            self.url = url + '?i=' + id + '&f=' + freq + '&u=' + login

        self.header = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        self.code = code
