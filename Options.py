#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
from ppms_lib import Errors

class OptionReader:

	def __init__(self, file_name, required_keys=()):

		self.option_file = os.path.join(sys.path[0], file_name)

		try:
			with open(self.option_file, 'r') as f:
				content = f.readlines()
		except FileNotFoundError:
			raise Errors.FatalError(file_name + ' not found!')

		self.options = {}
		for line in content:
			if not (line.startswith('#') or line in ['\n', '\r\n']):
				single_option = line.strip('\r\n').split('=')
				self.options[single_option[0].strip(' ')] = single_option[1].strip(' ')

		self.checkKeys(required_keys)

	def getValue(self, key):
		return self.options[key]

	def setValue(self, key, value):
		self.options[key] = value

	def checkKeys(self, required_keys):
		for key in required_keys:
			try:
				_ = self.options[key]
			except KeyError:
				raise Errors.FatalError(key + ' was not found in ' + self.option_file)
