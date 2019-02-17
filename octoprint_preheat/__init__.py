# coding=utf-8
from __future__ import absolute_import

from flask.ext.login import current_user

import octoprint.filemanager
import octoprint.plugin
from octoprint.util.comm import strip_comment

import flask
import time
from threading import Thread

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
					fallback_bed = 0,
					wait_for_bed = False)

					
	def get_template_configs(self):
		return [
			dict(type="settings", custom_bindings = False)
		]

	
	def get_assets(self):
		return dict(
			js = ["js/preheat.js"],
			css = ["css/preheat.css"]
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


	def read_temperatures_from_file(self, path_on_disk):
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])

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
					if enable_tool and (line.startswith("M104") or line.startswith("M109")): # Set tool temperature
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
		
		return temperatures
	
	
	def get_fallback_temperatures(self):
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])
		fallback_tool = self._settings.get_float(["fallback_tool"])
		fallback_bed = self._settings.get_float(["fallback_bed"])
		
		printer_profile = self._printer._printerProfileManager.get_current_or_default()

		result = dict()
		
		if enable_bed and fallback_bed > 0 and printer_profile["heatedBed"]:
			result["bed"] = fallback_bed
	
		if enable_tool and fallback_tool > 0:
			extruder_count = printer_profile["extruder"]["count"]
			for i in range(extruder_count):
				tool = "tool" + str(i)
				result[tool] = fallback_tool
		
		return result


	def get_temperatures(self):
		if (self._printer.get_current_job()["file"]["path"] == None):
			raise PreheatError("No gcode file loaded.")
		
		if self._printer.get_current_job()["file"]["origin"] == octoprint.filemanager.FileDestinations.SDCARD:
			temperatures = self.get_fallback_temperatures()

			if len(temperatures) == 0:
				raise PreheatError("Can't read the temperature from a gcode file stored on the SD card.")
			else:
				self._logger.info("Can't read the temperatures from the SD card, using fallback temperatures.")
		else:
			file_name = self._printer.get_current_job()["file"]["path"]
			path_on_disk = octoprint.server.fileManager.path_on_disk(octoprint.filemanager.FileDestinations.LOCAL, file_name)		
			temperatures = self.read_temperatures_from_file(path_on_disk)

			if len(temperatures) == 0:
				temperatures = self.get_fallback_temperatures()
			if len(temperatures) == 0:
				raise PreheatError("Could not find any preheat commands in the gcode file. You can configure fallback temperatures for this case.")
			else:
				self._logger.info("Could not find any preheat commands in the gcode file, using fallback temperatures.")

		offsets = self._printer.get_current_data()["offsets"]
		for tool in temperatures:
			if tool in offsets:
				temperatures[tool] += offsets[tool]
		
		return temperatures


	def check_state(self):
		if not self._printer.is_operational() or self._printer.is_printing():
			raise PreheatError("Can't set the temperature because the printer is not ready.")
	

	def start_preheat_sequence(self):
		self.check_state()
		
		preheat_temperatures = self.get_temperatures()
		
		if "bed" not in preheat_temperatures:
			self.preheat()
			return
		
		bed_temp = preheat_temperatures["bed"]
		self._logger.info("Preheating bed to " + str(bed_temp) + " and waiting.")
		self._printer.set_temperature("bed", bed_temp)

		thread = Thread(target = self.wait_for_bed_and_preheat, args = (preheat_temperatures, ))
		thread.start()


	def wait_for_bed_and_preheat(self, preheat_temperatures):
		current_temperatures = self._printer.get_current_temperatures()

		initial_targets = {tool: current_temperatures[tool]["target"] for tool in preheat_temperatures.keys()}
		initial_targets["bed"] = preheat_temperatures["bed"]

		while (True):
			time.sleep(0.4)

			current_temperatures = self._printer.get_current_temperatures()
			for tool in preheat_temperatures.keys():
				if current_temperatures[tool]["target"] != initial_targets[tool]:
					self._logger.info("Preheating cancelled because the temperature was changed manually.")
					return

			if abs(current_temperatures["bed"]["actual"] - current_temperatures["bed"]["target"]) < 4:
				break
		
		try:
			self.preheat_all(preheat_temperatures)
		except PreheatError as error:
			self._logger.info("Preheat error: " + str(error.message))


	def preheat_all(self, temperatures = None):
		self.check_state()

		if temperatures is None:
			temperatures = self.get_temperatures()
		
		for tool, target in temperatures.iteritems():
			self._logger.info("Preheating " + tool + " to " + str(target) + ".")
			self._printer.set_temperature(tool, target)

	def preheat(self):
		if self._settings.get_boolean(["wait_for_bed"]):
			self.start_preheat_sequence()
		else:
			self.preheat_all()
	
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