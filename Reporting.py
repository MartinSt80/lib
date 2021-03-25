#!/usr/bin/env python
# -*- coding: utf-8 -*-

import email.utils
import smtplib
from email.mime.text import MIMEText

from ppms_lib import Options


def sendMail(msg, type):

	MAIL_OPTIONS = Options.OptionReader('MailOptions.txt')

	if type == 'alert':
		msg['To'] = email.utils.formataddr(('', MAIL_OPTIONS.getValue('alertmail_recipients')))
	elif type == 'publication':
		msg['To'] = email.utils.formataddr(('', MAIL_OPTIONS.getValue('publicationmail_recipients')))
	else:
		return

	msg['From'] = email.utils.formataddr((MAIL_OPTIONS.getValue('mail_from'), MAIL_OPTIONS.getValue('mail_sender')))

	if type == 'alert':
		recipients = MAIL_OPTIONS.getValue('alertmail_recipients').split(',')
	elif type == 'publication':
		recipients = MAIL_OPTIONS.getValue('publicationmail_recipients').split(',')
	else:
		return

	with open(MAIL_OPTIONS.getValue('mail_credentials'), 'r') as f:
		password = f.read()[:-1]
	server_connection = smtplib.SMTP(MAIL_OPTIONS.getValue('mail_server'), int(MAIL_OPTIONS.getValue('mail_port')))
	try:
		# initiate connection
		server_connection.ehlo()
		# Try to encrypt the session
		if server_connection.has_extn('STARTTLS'):
			server_connection.starttls()
			# reinitiate server connection over TLS
			server_connection.ehlo()
		server_connection.login(MAIL_OPTIONS.getValue('mail_user'), password)
		server_connection.sendmail(MAIL_OPTIONS.getValue('mail_sender'), recipients, msg.as_string())
	finally:
		server_connection.quit()


def reportError(error):

	if error.__class__.__name__ == 'NetworkError':
		msg = MIMEText(error.msg)
		msg['Subject'] = error.msg

	elif error.__class__.__name__ == 'TemperatureError':
		if error.condition == 'limit':
			msg = MIMEText('Sensor ' + error.id + ' measures a temperature of {:.1f} °C'.format(error.temp) + ' in room ' + error.name + '!', 'plain', 'utf-8')
		elif error.condition == 'unstable':
			msg = MIMEText('Sensor ' + error.id + ' measures a temperature fluctuation of more than {:.1f} °C'.format(error.temp) + ' in room ' + error.name + '!', 'plain', 'utf-8')
		else:
			return
		msg['Subject'] = 'Temperature alarm: ' + error.name

	elif error.__class__.__name__ == 'SensorError':
		msg = MIMEText('Sensor '+ error.ID + ' in room ' + error.name + ' is not responding!')
		msg['Subject'] = 'Sensor alarm: ' + error.name
	else:
		return

	sendMail(msg, 'alert')

def reportPublications(publication_list):

	# Create the message
	mailtext = 'These publications from BIC user groups may acknowledge the BIC:\n\n '
	for publication in publication_list:
		mailtext += publication.PI + ' has published a paper by ' + publication.FirstAuthor + ' (PMID: ' + publication.PMID + ') Link: http://doi.org/' + publication.doi + '\n'
	msg = MIMEText(mailtext, 'plain', 'utf-8')
	if len(publication_list) == 1:
		msg['Subject'] = publication_list[0].PI + ' has published a new paper!'
	else:
		msg['Subject'] = 'New publications probably containing BIC data!'

	sendMail(msg, 'publication')
