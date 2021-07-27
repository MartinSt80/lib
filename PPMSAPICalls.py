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

from ppms_lib import Options, Errors


class NewCall:

	def __init__(self, mode, system_options=None):
		self.mode = mode

		# if we want to contact the Proxy, we need SystemOptions.txt for the AESkey and Proxy address:port
		if self.mode == 'Proxy':
			if system_options is not None:
				self.SYSTEMoptions = system_options
				required_keys = ('AES_key', 'proxy_address', 'API_port')
				self.SYSTEMoptions.checkKeys(required_keys)
			else:
				raise Errors.FatalError(msg='SystemOptions info not provided, only direct API calls possible')

		# if we want to contact the API directly, we need ProxyOptions for the APIkeys and URLs
		if self.mode == 'PPMS API':
			try:
				self.APIoptions = Options.OptionReader('ProxyOptions.txt')
			except:
				raise Errors.FatalError(msg='ProxyOptions.txt is missing, only Proxy calls possible')

	def _performCall(self, parameters):
		if self.mode == 'PPMS API':
			response = self._sendToAPI(parameters)
			# check if we got a proper response, i.e. HTTP status code == 200
			if not response.status_code == 200:
				raise Errors.APIError(True, False, msg='Error ' + str(response.status_code) + ': API didn\'t return a proper response')

			# check if there is some data in the response
			if response.text:
				return response.text
			else:
				raise Errors.APIError(False, True, msg='Empty response from API')

		elif self.mode == 'Proxy':
			response = self._sendToProxy(parameters)
			# the proxy may forward an exception or a proper response
			try:
				raise response
			except TypeError:
				return response
		else:
			raise Errors.FatalError(msg='Unknown communication method, must be \'PPMS API\' or \'Proxy\'')


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
			raise Errors.APIError(msg='Unknown API interface type, must be \'PUMAPI\' or \'API2\'')

		return requests.post(URL, headers=header, data=parameters)



	# dict is pickled and encrypted and sent to proxy, response is decrypted, unpickled and returned
	def	_sendToProxy(self, param_dict):

		pickled_dict = pickle.dumps(param_dict, protocol=2)

		iv = Random.new().read(AES.block_size)

		AES_plainkey = self.SYSTEMoptions.getValue('AES_key').encode('utf8')
		AES_key = SHA256.new()
		AES_key.update(AES_plainkey)
		AES_key = AES_key.digest()

		encryptor = AES.new(AES_key, AES.MODE_CFB, iv)
		encrypted_dict = iv + encryptor.encrypt(pickled_dict)
		packed_dict = bytes(struct.pack('>I', len(encrypted_dict))) + encrypted_dict

		proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			proxy_socket.connect((self.SYSTEMoptions.getValue('proxy_address'), int(self.SYSTEMoptions.getValue('API_port'))))
			proxy_socket.sendall(packed_dict)
		except socket.error as e:
			raise Errors.APIError(msg=e)

		#From here we handle the encrypted response from the proxy
		encrypted_call = self._receive_data(proxy_socket)
		proxy_socket.close()
		iv_response = encrypted_call[:AES.block_size]
		encrypted_response = encrypted_call[AES.block_size:]

		decryptor = AES.new(AES_key, AES.MODE_CFB, iv_response)
		decrypted_response = decryptor.decrypt(encrypted_response)

		#try to catch wrong AES-keys at unpickle step with KeyError
		try:
			response = pickle.loads(decrypted_response)
		except KeyError:
			raise Errors.APIError(msg='Unpickle step failed, probably AES-keys don\'t match')
		return response


	def _receive_data(self, sock):	# Read message length and unpack it into an integer
		raw_msglen = self._recvall(sock, 4)
		if not raw_msglen:
			return None
		msglen = struct.unpack('>I', raw_msglen)[0]
		# Read the message data
		return self._recvall(sock, msglen)

	def _recvall(self, sock, n): # Helper function to recv n bytes or return None if EOF is hit
		data = b''
		while len(data) < n:
			packet = sock.recv(n - len(data))
			if not packet:
				return None
			data += packet
		return data

	# get the bookings for the current day on a certain machine,
	# return start, stop, user for each session as dict


	def getBookedSessionsPeriod(self):
		parameters = {
			'action': 'Report70',
			'startdate': '2021-07-07',
			'enddate': '2021-07-31',
			# 'dateformat': 'print',
			'outformat': 'json',
			'coreid': '2',
			'API_type': 'API2',
		}

		try:
			response = self._performCall(parameters)
		except Errors.APIError as e:
			if e.request_not_successful:
				raise e
			else:
				if e.empty_response:
					return []
		else:
			return json.loads(response)

	def getTodaysBookings(self, PPMS_facility_id, PPMS_name=None, filter=True, day=time.strftime('%Y-%m-%d', time.localtime())):
		parameters = {
			'action': 'getrunningsheet',
			'plateformid': PPMS_facility_id,
			'day': day,
			'API_type': 'PUMAPI',
			'format': 'csv',
			'noheaders': 'true',
		}

		try:
			response = self._performCall(parameters).split('\r\n')
			print(response)
		except Errors.APIError as e:
			if e.request_not_successful:
				raise e
			else:
				if e.empty_response:
					return []

		if filter and PPMS_name:
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

		else:
			return response


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

		return json.loads(self._performCall(parameters))[0]


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

	def getGroupFullInfo(self, group_id):
		parameters = {
			'action': 'getgroup',
			'API_type': 'PUMAPI',
			'unitlogin': group_id,
			'format': 'json',
		}
		return json.loads(self._performCall(parameters))

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
		except Errors.APIError:
			return []

	def getAllUsers(self, active=None):
		parameters = {
			'action': 'getusers',
			'API_type': 'PUMAPI',
			'format': 'csv',
			'noheaders': 'true',
		}
		if active is not None:
			if active:
				parameters['active'] = 'true'
			else:
				parameters['active'] = 'false'
		try:
			return self._performCall(parameters).replace('"', '').split()
		except Errors.APIError:
			return []

	def getRunningSheet(self, PPMS_facility_id, day):
			parameters = {
				'action': 'getrunningsheet',
				'plateformid': PPMS_facility_id,
				'day': day,
				'API_type': 'PUMAPI',
				'format': 'csv',
				'noheaders': 'true',
			}
			return self._performCall(parameters)

	def getUserRights(self, login=None, system_id=None):
		if not (login or system_id):
			raise Errors.APIError(msg='User login or system id have to be specified!')
		if login:
			parameters = {
					'action': 'getuserrights',
					'login': login,
					'API_type': 'PUMAPI',
					'format': 'csv',
					'noheaders': 'true',
				}
		if system_id:
			parameters = {
				'action': 'getsysrights',
				'id': system_id,
				'API_type': 'PUMAPI',
				'format': 'csv',
				'noheaders': 'true',
			}
		return self._performCall(parameters).split()

	def getSystems(self):
		parameters = {
			'action': 'getsystems',
			'API_type': 'PUMAPI',
			'format': 'csv',
			'noheaders': 'true',
		}
		return self._performCall(parameters).rstrip().split('\r\n')

	# get the bookings for a specified date,
	# return start, stop for each session as dict
	def getSystemBookings(self, PPMS_facility_id, datetime_date):
		parameters = {
			'action': 'getrunningsheet',
			'plateformid': PPMS_facility_id,
			'day': datetime_date.strftime('%Y-%m-%d'),
			'API_type': 'PUMAPI',
			'format': 'csv',
			'noheaders': 'true',
		}

		filtered_response = []

		try:
			response = self._performCall(parameters).split('\r\n')
		except Errors.APIError:
			pass
		else:
			for entry in response:
				entry = entry.split(',')
				if len(entry) > 3:
					if entry[1][1:3] == entry[2][1:3]:  # sessions shorter than 1 hour have same start and stop hour
						filtered_response.append({'start': int(entry[1][1:3]),
												  'stop': int(entry[2][1:3]) + 1,
												  'system': entry[3][1:-1]})
					else:
						filtered_response.append({'start': int(entry[1][1:3]),
												  'stop': int(entry[2][1:3]),
												  'system': entry[3][1:-1]})
		finally:
			return filtered_response

	# get the time a system was used last by a user
	def getLastUsage(self, login=None, system_id=None):
		if not (login or system_id):
			raise Errors.APIError(msg='User login or system id have to be specified!')
		parameters = {
			'action': 'getuserexp',
			'API_type': 'PUMAPI',
			'format': 'json',
		}
		if login:
			parameters['login'] = login
		if system_id:
			parameters['id'] = system_id

		try:
			response_json = self._performCall(parameters)
		except Errors.APIError as e:
			if e.empty_response:
				response_json = '{}'
			else:
				raise e
		return json.loads(response_json)


	def getUserFullInfo(self, user_login):
		parameters = {
				'action': 'getuser',
				'login': user_login,
				'API_type': 'PUMAPI',
				'format': 'json',
		}

		response = json.loads(self._performCall(parameters))
		return response

	def setUserRight(self, system_id, user_login, user_right=None):
		valid_user_rights = ['A', 'N', 'S', 'D']
		if not user_right:
			user_right = 'A'
		if user_right not in valid_user_rights:
			raise Errors.APIError("User right abbreviation not valid! Must be 'A', 'N', 'S' or 'D'")
		parameters = {
				'action': 'setright',
				'id': str(system_id),
				'login': user_login,
				'type': user_right,
				'API_type': 'PUMAPI',
		}
		self._performCall(parameters)