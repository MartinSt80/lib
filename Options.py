#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys
import Errors

class OptionReader:

	def __init__(self, file_name, required_keys=()):
		option_file = os.path.join(sys.path[0], file_name)
		try:
			with open(option_file, 'r') as f:
				content = f.readlines()
		except IOError:
			raise Errors.FatalError(file_name + ' not found!')

		self.options = {}
		for line in content:
			if not (line.startswith('#') or line in ['\n', '\r\n']):
				single_option = line.strip('\r\n').split('=')
				self.options[single_option[0].strip(' ')] = single_option[1].strip(' ')

		for key in required_keys:
			if key not in self.options:
				raise Errors.FatalError(key + ' was not found in ' + file_name)


	def getValue(self, key):
		return self.options[key]

	def setValue(self, key, value):
		self.options[key] = value


