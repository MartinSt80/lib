#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pickle
import socket

class NewTrackeroverProxy:

	def __init__(self, login, system_options):
		self.id = system_options.getValue('PPMS_systemid')
		self.code = system_options.getValue('PPMS_systemcode')
		self.freq = system_options.getValue('tracker_frequency')
		self.proxy_address = system_options.getValue('proxy_address')
		self.tracker_port = int(system_options.getValue('tracker_port'))
		self.login = login

		if self.login not in system_options.getValue('ignored_logins').split(','):
			self.tracker_parameters = self._createTrackerCallDict()
			self.sendtoTracker()

	# dict is pickled and sent to proxy
	def	sendtoTracker(self):
		self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.proxy_socket.connect((self.proxy_address, self.tracker_port))
		print(self.proxy_socket.getsockname())
		pickled_dict = pickle.dumps(self.tracker_parameters, protocol=2)
		self.proxy_socket.sendall(pickled_dict)
		self.proxy_socket.close()

	def _createTrackerCallDict(self):
		parameters = {
			'id': self.id,
			'freq': self.freq,
			'user': self.login,
			'code': self.code,
		}

		return parameters

