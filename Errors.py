#!/usr/bin/env python
# -*- coding: utf-8 -*-


class NetworkError(Exception):
	"""Raised when the NAS is not mounted

	Attributes:
		entity -- 'NAS' - only the NAS storage is affected 'network' - no connection to LAN
		msg  -- explains what is going wrong
	"""
	def __init__(self, entity, msg):
		self.entity = entity
		self.msg = msg

class SensorError(Exception):
	"""Raised when a sensor is malfunctioning

	Attributes:
		ID -- Sensor ID
		name -- Sensor name/Location
	 """
	def __init__(self, ID, name):
		self.ID = ID
		self.name = name

class TemperatureError(Exception):
	"""Raised when a temperature value exceeds the limits set in the options or fluctuates too much

	Attributes:
		temp -- measured temperature
		ID -- Sensor ID
		name -- Sensor name/Location
		condition -- 'limit' -  upper or lower limit reached, 'unstable' - temperature is fluctuating too much
	 """
	def __init__(self, temp, ID, name, condition):
		self.temp = temp
		self.ID = ID
		self.name = name
		self.condition = condition

class APIError(Exception):
	"""Raised when the PPMS-API request was not successful or no response was returned

	Attributes:
		request_not_successful -- HTTP request unsuccessful
		no_response -- API response was empty
	 """
	def __init__(self, request_not_successful=False, no_response=False, msg=''):
		self.request_not_successful = request_not_successful
		self.no_response = no_response
		self.msg = msg