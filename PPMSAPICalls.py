#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import pickle
import requests
import socket
import struct
import time

from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Hash import SHA256

import Options, Errors


class NewCall:

	def __init__(self, mode):
		self.mode = mode
		self.SYSTEMoptions = Options.OptionReader('SystemOptions.txt')

		# if we want to contact the API directly, we need ProxyOptions for the APIkeys and URLs
		if self.mode == 'PPMS API':
			try:
				self.APIoptions = Options.OptionReader('ProxyOptions.txt')
			except:
				exit('ProxyOptions.txt is missing, only Proxy calls possible')

	def _performCall(self, parameters):
		if self.mode == 'PPMS API':
			response = self._sendToAPI(parameters)

			# check if we got a proper response, HTTP status code == 200
			if not response.status_code == 200:
				raise RuntimeError('API didn\'t return a proper response')

			# check if there is some data in the response, empty response, check parameters, options
			if response.text:
				return response.text
			else:
				raise RuntimeError('Empty response from API')

		elif self.mode == 'Proxy':
			response = self._sendToProxy(parameters)
			# the proxy may forward an exception or a proper response
			try:
				raise response
			except:
				return response.text

		else:
			exit('Unknown communication method, must be PPMS API or Proxy')


	def _sendToAPI(self, parameters):

		header = {'Content-Type': 'application/x-www-form-urlencoded'}
		API_type = parameters.pop('API_type')

		if API_type == 'PUMAPI':
			parameters['apikey'] = self.APIoptions.getValue('PUMAPI_key')
			URL = self.APIoptions.getValue('PUMAPI_URL')
		elif API_type == 'API2':
			parameters['apikey'] = self.APIoptions.getValue('API2_key')
			URL = self.APIoptions.getValue('API2_URL')
		else:
			exit('Unknown API interface type, must be PUMAPI or API2')

		return requests.post(URL, headers=header, data=parameters)



	# dict is pickled and sent to proxy, response is unpickled and returned
	def	_sendToProxy(self, param_dict):

		pickled_dict = pickle.dumps(param_dict)

		iv = Random.new().read(AES.block_size)

		AES_plainkey = self.SYSTEMoptions.getValue('AES_key')
		AES_key = SHA256.new()
		AES_key.update(AES_plainkey)
		AES_key = AES_key.digest()

		encryptor = AES.new(AES_key, AES.MODE_CFB, iv)
		encrypted_dict = iv + encryptor.encrypt(pickled_dict)
		packed_dict = struct.pack('>I', len(encrypted_dict)) + encrypted_dict

		proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		proxy_socket.connect((self.SYSTEMoptions.getValue('proxy_address'), int(self.SYSTEMoptions.getValue('API_port'))))
		proxy_socket.sendall(packed_dict)

		encrypted_call = self._receive_data(proxy_socket)
		proxy_socket.close()

		iv_response = encrypted_call[:AES.block_size]
		encrypted_response = encrypted_call[AES.block_size:]

		decryptor = AES.new(AES_key, AES.MODE_CFB, iv_response)
		return pickle.loads(decryptor.decrypt(encrypted_response))

	def _receive_data(self, sock):	# Read message length and unpack it into an integer
		raw_msglen = self._recvall(sock, 4)
		if not raw_msglen:
			return None
		msglen = struct.unpack('>I', raw_msglen)[0]
		# Read the message data
		return self._recvall(sock, msglen)

	def _recvall(self, sock, n): # Helper function to recv n bytes or return None if EOF is hit
		data = ''
		while len(data) < n:
			packet = sock.recv(n - len(data))
			if not packet:
				return None
			data += packet
		return data

	# get the bookings for the current day on a certain machine,
	# return start, stop, user for each session as dict
	def getTodaysBookings(self, PPMS_facility_id, PPMS_name):
		parameters = {
			'action': 'getrunningsheet',
			'plateformid': PPMS_facility_id,
			'day': time.strftime('%Y-%m-%d', time.localtime()),
			'API_type': 'PUMAPI',
			'format': 'csv',
			'noheaders': 'true',
		}

		response = self._performCall(parameters).split('\r\n')

		filtered_response = []
		for entry in response:
			entry = entry.split(',')
			if len(entry) > 3:
				if entry[3][1:-1] == PPMS_name: # getrunningsheet returns all bookings on a certain day
					if entry[1][1:3] == entry[2][1:3]: # sessions shorter than 1 hour have same start and stop hour
						filtered_response.append({'start': int(entry[1][1:3]),
												  'stop': int(entry[2][1:3]) + 1,
												  'user': entry[4][1:-1]})
					else:
						filtered_response.append({'start': int(entry[1][1:3]),
												  'stop': int(entry[2][1:3]),
												  'user': entry[4][1:-1]})
		return filtered_response


	# get the User Name from the login
	def getUserFullName(self, user_login):
		parameters = {
				'action': 'getuser',
				'login': user_login,
				'API_type': 'PUMAPI',
				'format': 'json',
		}

		response = json.loads(self._performCall(parameters))
		return {'fname': response['fname'], 'lname': response['lname']}


	# get hours on instrument
	def getExperience(self, user_login, PPMS_system_id):
		parameters = {
			'action': 'getuserexp',
			'login': user_login,
			'id': PPMS_system_id,
			'API_type': 'PUMAPI',
			'format': 'json',
		}
		#somehow in this case json.loads returns a list of length one containing the dict
		response = json.loads(self._performCall(parameters))[0]
		return response['booked hours'] + response['used hours']


	def makeBooking(self, start, stop, time, user_id, PPMS_system_id, PPMS_facility_id):
		parameters = {
			'action': 'SetSessionBooking',
			'userid': str(user_id),
			'coreid': PPMS_facility_id,
			'API_type': 'API2',
			'pdate': time,
			'systemid': PPMS_system_id,
			'projectid': '0',
			'SE1': 'false',
			'SE2': 'false',
			'comment': '',
			'repeat': '0',
			'user': str(user_id),
			'assisted': 'false',
			'assistant': '0',
			'form': '',
			'start': start,
			'end': stop,
			'outformat': 'json',
		}

		try:
			response = json.loads(self._performCall(parameters))[0]
			session_id = response['id']
			return session_id
		except RuntimeError:
			return None


	def getUserID(self, user_name, PPMS_facility_id):
		parameters = {
			'action': 'GetUsersList',
			'API_type': 'API2',
			'coreid': PPMS_facility_id,
			'filter': 'active',
			'outformat': 'json',
		}

		user_list = json.loads(self._performCall(parameters))

		for user_entry in user_list:
			if user_entry['firstName'] == user_name['fname'] and user_entry['lastName'] == user_name['lname']:
				return user_entry['id']
		else:
			return None

	def getSystemName(self, PPMS_system_id):
		parameters = {
			'action': 'getsystems',
			'API_type': 'PUMAPI',
			'id': PPMS_system_id,
			'format': 'csv',
			'noheaders': 'true',

		}
		system_name = self._performCall(parameters).split(',')[3].strip('"')
		return system_name

	def getGroupList(self):
		parameters = {
			'action': 'getgroups',
			'API_type': 'PUMAPI',
			'active': 'true',
			'format': 'csv',
			'noheaders': 'true',
		}

		return self._performCall(parameters).replace('"', '').split()

	def getGroupPI(self, group_id):
		parameters = {
			'action': 'getgroup',
			'API_type': 'PUMAPI',
			'unitlogin': group_id,
			'format': 'json',
		}

		return json.loads(self._performCall(parameters))['headname']

	def getGroupUsers(self, group_id):
		parameters = {
			'action': 'getgroupusers',
			'API_type': 'PUMAPI',
			'unitlogin': group_id,
			'active': 'true',
			'format': 'csv',
			'noheaders': 'true',
		}
		try:
			return self._performCall(parameters).replace('"', '').split()
		except RuntimeError:
			return []

