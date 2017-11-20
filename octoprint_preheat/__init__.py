# coding=utf-8
from __future__ import absolute_import

from flask.ext.login import current_user

import octoprint.filemanager
import octoprint.plugin

import flask

class PreheatError(Exception):
	def __init__(self, message):
		super(PreheatError, self).__init__(message)

class PreheatAPIPlugin(octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.SimpleApiPlugin,
					   octoprint.plugin.AssetPlugin):
	
	def get_assets(self):
		return dict(
			js = ["js/preheat.js"]
		)
		
	def get_api_commands(self):
		return dict(
			preheat = []
		)

	def get_print_temperature(self):
		printer = self._printer
		
		if (printer.get_current_job()["file"]["path"] == None):
			raise PreheatError("No gcode file loaded.")
			
		file_name = printer.get_current_job()["file"]["path"]
		path_on_disk = octoprint.server.fileManager.path_on_disk(octoprint.filemanager.FileDestinations.LOCAL, file_name)
		
		file = open(path_on_disk, 'r')
		line = file.readline()
		max_lines = 1000
		try:
			with open(path_on_disk, "r") as file:
				while max_lines > 0:
					line = file.readline().strip()
					if line == "":
						break
					if line.startswith("M104 S") or line.startswith("M109 S"):
						if line.index(';') != -1:
							line = line[:line.index(';')].strip()
						try:
							value = float(line[6:])
							if value > 0:
								return value
						except ValueError:
							self._logger.warn("Error parsing heat command: {}".format(line))
							pass
					max_lines -= 1
		except:
			self._logger.exception("Something went wrong while trying to read the preheat temperature from {}".format(path_on_disk))

		raise PreheatError("Could not find a preheat command in the gcode file.")
		
	def preheat(self):
		if not self._printer.is_operational() or self._printer.is_printing():
			raise PreheatError("Can't set the temperature because the printer is not ready.")
		new_target = self.get_print_temperature()
		self._logger.info("Print temp: " + str(new_target))
		self._printer.set_temperature("tool0", new_target)
	
	def on_api_command(self, command, data):
		import flask
		if command == "preheat":
			if current_user.is_anonymous():
				return "Insufficient rights", 403
			try:
				self.preheat()
			except PreheatError as error:
				self._logger.info("Preheat error: " + str(error.message))
				return str(error.message), 405

__plugin_name__ = "Preheat"
__plugin_implementation__ = PreheatAPIPlugin()
