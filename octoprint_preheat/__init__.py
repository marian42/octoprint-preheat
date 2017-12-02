# coding=utf-8
from __future__ import absolute_import

from flask.ext.login import current_user

import octoprint.filemanager
import octoprint.plugin
from octoprint.util.comm import strip_comment

import flask

class PreheatError(Exception):
	def __init__(self, message):
		super(PreheatError, self).__init__(message)

class PreheatAPIPlugin(octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.SimpleApiPlugin,
					   octoprint.plugin.AssetPlugin,
					   octoprint.plugin.SettingsPlugin):
	
	def get_settings_defaults(self):
		return dict(enable_tool = True,
					enable_bed = True,
					fallback_tool = 0,
					fallback_bed = 0)
					
	def get_template_configs(self):
		return [
			dict(type="settings", custom_bindings = False)
		]
	
	def get_assets(self):
		return dict(
			js = ["js/preheat.js"]
		)
		
	def get_api_commands(self):
		return dict(
			preheat = []
		)
		
	def parse_line(self, line):
		line = strip_comment(line)
		
		tool = "tool0"
		temperature = None
		for item in line.split(" "):
			if item.startswith("S"):
				try:
					value = float(item[1:])
					if value > 0:
						temperature = value
				except ValueError:
					self._logger.warn("Error parsing heat command: {}".format(line))
					pass
			if item.startswith("T"):
				tool = "tool" + item[1:].strip()
				
		return tool, temperature
	
	def apply_fallback_temperature(self):
		fallback_successful = False
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])
		fallback_tool = self._settings.get_float(["fallback_tool"])
		fallback_bed = self._settings.get_float(["fallback_bed"])
		
		printer_profile = self._printer._printerProfileManager.get_current_or_default()
		
		if enable_bed and fallback_bed > 0 and printer_profile["heatedBed"]:
			self._logger.info("Using fallback temperature, preheating bed to " + str(fallback_bed))
			self._printer.set_temperature("bed", fallback_bed)
			fallback_successful = True
	
		if enable_tool and fallback_tool > 0:
			extruder_count = printer_profile["extruder"]["count"]
			for i in range(extruder_count):
				tool = "tool" + str(i)
				self._logger.info("Using fallback temperature, preheating " + tool + " to " + str(fallback_tool))
				self._printer.set_temperature(tool, fallback_tool)
			fallback_successful = True
		
		return fallback_successful

	def get_temperatures(self):
		printer = self._printer
		
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])
		
		if (printer.get_current_job()["file"]["path"] == None):
			raise PreheatError("No gcode file loaded.")
			
		file_name = printer.get_current_job()["file"]["path"]
		
		if printer.get_current_job()["file"]["origin"] != octoprint.filemanager.FileDestinations.LOCAL:
			raise PreheatError("Can't read the temperature from a gcode file stored on the SD card.")
		path_on_disk = octoprint.server.fileManager.path_on_disk(octoprint.filemanager.FileDestinations.LOCAL, file_name)
		
		file = open(path_on_disk, 'r')
		line = file.readline()
		max_lines = 1000
		temperatures = dict()
		try:
			with open(path_on_disk, "r") as file:
				while max_lines > 0:
					line = file.readline()
					if line == "":
						break
					if enable_tool and (line.startswith("M104") or line.startswith("M109")):	# Set tool temperature
						tool, temperature = self.parse_line(line)
						if temperature != None and tool not in temperatures:
							temperatures[tool] = temperature
					if enable_bed and (line.startswith("M190") or line.startswith("M140")):	# Set bed temperature
						_, temperature = self.parse_line(line)
						if temperature != None and "bed" not in temperatures:
							temperatures["bed"] = temperature
						
					max_lines -= 1
		except:
			self._logger.exception("Something went wrong while trying to read the preheat temperature from {}".format(path_on_disk))
		
		if len(temperatures) == 0:
			raise PreheatError("Could not find a preheat command in the gcode file.")
		return temperatures
		
	def preheat(self):
		if not self._printer.is_operational() or self._printer.is_printing():
			raise PreheatError("Can't set the temperature because the printer is not ready.")
		
		try:
			temperatures = self.get_temperatures()
			
			for key in temperatures:
				self._logger.info("Preheating " + key + " to " + str(temperatures[key]))
				self._printer.set_temperature(key, temperatures[key])
		except PreheatError as error:
			if not self.apply_fallback_temperature():
				raise PreheatError(str(error.message) + "\n" + "You can configure fallback temperatures in the plugin settings for this case.") 
	
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
				
	def get_update_information(self, *args, **kwargs):
		return dict(
			preheat = dict(
				displayName=self._plugin_name,
				displayVersion=self._plugin_version,
				
				type="github_release",
				current=self._plugin_version,
				user="marian42",
				repo="octoprint-preheat",
				
				pip="https://github.com/marian42/octoprint-preheat/archive/{target}.zip"
			)
		)


__plugin_name__ = "Preheat Button"
__plugin_implementation__ = PreheatAPIPlugin()

__plugin_hooks__ = {
	"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
}