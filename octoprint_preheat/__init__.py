# coding=utf-8
from __future__ import absolute_import

import octoprint.filemanager
import octoprint.plugin

import flask

class PreheatError(Exception):
	def __init__(self, message):
		super(PreheatError, self).__init__(message)

class PreheatAPIPlugin(octoprint.plugin.StartupPlugin,
					   octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.SimpleApiPlugin,
					   octoprint.plugin.AssetPlugin):
	
	def on_after_startup(self):
		pass

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
		while line and max_lines > 0:
			if (line.startswith("M104 S") or line.startswith("M104 S")):
				value = int(line[6:])
				if (value > 0):
					return value
			line = file.readline()
			max_lines -= 1
		raise PreheatError("Could not find a preheat command in the gcode file.")
		
	def preheat(self):
		if not self._printer.is_operational() or self._printer.is_printing():
			raise PreheatError("Can't set the temperature because the printer is not ready.")
		current_target = self._printer.get_current_temperatures()["tool0"]["target"]
		new_target = self.get_print_temperature()
		self._logger.info("Print temp: " + str(new_target))
		self._printer.set_temperature("tool0", new_target)
		
	def on_api_command(self, command, data):
		import flask
		if command == "preheat":
			try:
				self.preheat()
			except PreheatError as error:
				self._logger.info("Preheat error: " + str(error.message))
				return str(error.message), 405

__plugin_name__ = "Preheat"
__plugin_implementation__ = PreheatAPIPlugin()
