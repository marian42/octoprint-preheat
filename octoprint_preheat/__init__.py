# coding=utf-8
from __future__ import absolute_import

from flask_login import current_user

import octoprint.filemanager
import octoprint.plugin
from octoprint.util.comm import strip_comment
from octoprint.printer import PrinterInterface

import flask
import time
from threading import Thread

__plugin_pythoncompat__ = ">=2.7,<4"

class PreheatError(Exception):
	def __init__(self, message):
		super(PreheatError, self).__init__(message)
		self.message = message

class PreheatAPIPlugin(octoprint.plugin.TemplatePlugin,
					   octoprint.plugin.SimpleApiPlugin,
					   octoprint.plugin.AssetPlugin,
					   octoprint.plugin.SettingsPlugin):
	
	def get_settings_defaults(self):
		return dict(enable_tool = True,
					enable_bed = True,
					enable_chamber = True,
					fallback_tool = 0,
					fallback_bed = 0,
					fallback_chamber = 0,
					wait_for_bed = False,
					on_start_send_gcode = False,
					on_start_send_gcode_command = "M117 Preheating... ; Update LCD",
					on_complete_show_popup = False,
					on_conplete_send_gcode = False,
					on_conplete_send_gcode_command = "M117 Preheat complete. ; Update LCD\nM300 S660 P200 ; Beep",
					use_fallback_when_no_file_selected = False,
					max_gcode_lines = 1000
		)

					
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

		
	def parse_line(self, line, tool="tool0"):
		line = strip_comment(line)
		
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
				new_tool = "tool" + item[1:].strip()
				if PrinterInterface.valid_heater_regex.match(new_tool):
					tool = new_tool
				
		return tool, temperature


	def read_temperatures_from_file(self, path_on_disk):
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])
		enable_chamber = self._settings.get_boolean(["enable_chamber"])

		file = open(path_on_disk, 'r')
		line = file.readline()
		max_lines = self._settings.get_int(["max_gcode_lines"])
		temperatures = dict()
		current_tool = "tool0"
		try:
			with open(path_on_disk, "r") as file:
				while max_lines > 0:
					line = file.readline()
					if line == "":
						break
					if line.startswith("T"): # Select tool
						new_tool = "tool" + strip_comment(line)[1:].strip()
						if new_tool == "tool":
							new_tool = "tool0"
						if PrinterInterface.valid_heater_regex.match(new_tool):
							current_tool = new_tool
					if enable_tool and (line.startswith("M104") or line.startswith("M109")): # Set tool temperature
						tool, temperature = self.parse_line(line, current_tool)
						if temperature != None and tool not in temperatures:
							temperatures[tool] = temperature
					if enable_bed and (line.startswith("M190") or line.startswith("M140")):	# Set bed temperature
						_, temperature = self.parse_line(line)
						if temperature != None and "bed" not in temperatures:
							temperatures["bed"] = temperature
					if enable_chamber and (line.startswith("M191") or line.startswith("M141")):	# Set chamber temperature
						_, temperature = self.parse_line(line)
						if temperature != None and "chamber" not in temperatures:
							temperatures["chamber"] = temperature
						
					max_lines -= 1
		except:
			self._logger.exception("Something went wrong while trying to read the preheat temperature from {}".format(path_on_disk))
		
		return temperatures
	
	
	def get_fallback_temperatures(self):
		enable_bed = self._settings.get_boolean(["enable_bed"])
		enable_tool = self._settings.get_boolean(["enable_tool"])
		enable_chamber = self._settings.get_boolean(["enable_chamber"])
		fallback_tool = self._settings.get_float(["fallback_tool"])
		fallback_bed = self._settings.get_float(["fallback_bed"])
		fallback_chamber = self._settings.get_float(["fallback_chamber"])

		printer_profile = self._printer._printerProfileManager.get_current_or_default()

		result = dict()
		
		if enable_bed and fallback_bed > 0 and printer_profile["heatedBed"]:
			result["bed"] = fallback_bed

		if enable_chamber and fallback_chamber > 0 and printer_profile["heatedChamber"]:
			result["chamber"] = fallback_chamber
	
		if enable_tool and fallback_tool > 0:
			extruder_count = printer_profile["extruder"]["count"]
			for i in range(extruder_count):
				tool = "tool" + str(i)
				result[tool] = fallback_tool
		
		return result


	def get_temperatures(self):
		if not self._settings.get_boolean(["enable_bed"]) and \
		not self._settings.get_boolean(["enable_tool"]) and \
		not self._settings.get_boolean(["enable_chamber"]):
			raise PreheatError("Preheating is disabled in the plugin settings.")

		if (self._printer.get_current_job()["file"]["path"] == None):
			if self._settings.get_boolean(["use_fallback_when_no_file_selected"]):
				temperatures = self.get_fallback_temperatures()
			else:
				raise PreheatError("No gcode file loaded.")
		
		elif self._printer.get_current_job()["file"]["origin"] == octoprint.filemanager.FileDestinations.SDCARD:
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
	

	def preheat_and_wait(self, preheat_temperatures):
		self.preheat_immediately(preheat_temperatures)
		
		current_temperatures = self._printer.get_current_temperatures()
		initial_targets = {tool: current_temperatures[tool]["target"] for tool in preheat_temperatures.keys()}
		for tool, temperature in preheat_temperatures.items():
			initial_targets[tool] = temperature

		while (True):
			time.sleep(0.4)

			current_temperatures = self._printer.get_current_temperatures()
			for tool in initial_targets:
				if current_temperatures[tool]["target"] != initial_targets[tool]:
					raise PreheatError("Preheating cancelled because the temperature was changed manually.")

			if not self._printer.is_operational() or self._printer.is_printing():
				raise PreheatError("Preheating cancelled because the printer state changed.")

			complete = [abs(current_temperatures[tool]["actual"] - preheat_temperatures[tool]) < 4 for tool in preheat_temperatures]
			if all(complete):
				return

	
	def notify_preheat_complete(self):
		self._logger.info("Preheating complete.")
		if self._settings.get_boolean(["on_complete_show_popup"]):
			self._plugin_manager.send_plugin_message(self._identifier, dict(type="preheat_complete"))
		if self._settings.get_boolean(["on_conplete_send_gcode"]):
			command = self._settings.get(["on_conplete_send_gcode_command"])
			self._printer.commands(command.split("\n"))
	

	def is_notify_on_complete_enabled(self):
		return self._settings.get_boolean(["on_complete_show_popup"]) \
			or self._settings.get_boolean(["on_conplete_send_gcode"])

	def preheat_thread(self, preheat_temperatures):
		try:
			shoud_wait_for_bed = self._settings.get_boolean(["wait_for_bed"]) and "bed" in preheat_temperatures
			should_wait_for_chamber = self._settings.get_boolean(["wait_for_bed"]) and self._settings.get_boolean(["enable_chamber"]) and "chamber" in preheat_temperatures
			if shoud_wait_for_bed or should_wait_for_chamber:
				items_to_wait_for = {}
				if shoud_wait_for_bed:
					items_to_wait_for["bed"] = preheat_temperatures["bed"]
				if should_wait_for_chamber:
					items_to_wait_for["chamber"] = preheat_temperatures["chamber"]
				self.preheat_and_wait(items_to_wait_for)
			
			if self.is_notify_on_complete_enabled():
				self.preheat_and_wait(preheat_temperatures)
				self.notify_preheat_complete()
			else:
				self.preheat_immediately(preheat_temperatures)
		except PreheatError as error:
			self._logger.warn("Preheat error: " + str(error.message))
			self._plugin_manager.send_plugin_message(self._identifier, dict(type="preheat_warning", message=error.message))


	def preheat_immediately(self, preheat_temperatures):
		for tool, target in preheat_temperatures.items():
			self._logger.info("Preheating " + tool + " to " + str(target) + ".")
			self._printer.set_temperature(tool, target)

	def preheat(self):
		self.check_state()

		if self._settings.get_boolean(["on_start_send_gcode"]):
			command = self._settings.get(["on_start_send_gcode_command"])
			self._printer.commands(command.split("\n"))

		preheat_temperatures = self.get_temperatures()

		use_thread = self._settings.get_boolean(["wait_for_bed"]) or self.is_notify_on_complete_enabled()

		if use_thread:
			thread = Thread(target = self.preheat_thread, args = (preheat_temperatures, ))
			thread.start()
		else:
			self.preheat_immediately(preheat_temperatures)
	
	def on_api_command(self, command, data):
		if command == "preheat":
			if current_user.is_anonymous():
				return "Insufficient rights", 403
			try:
				self.preheat()
			except PreheatError as error:
				self._logger.info("Preheat error: " + str(error.message))
				return str(error.message), 405

	def get_gcode_script_variables(self, comm, script_type, script_name, *args, **kwargs):
		if not script_type == "gcode":
			return None

		prefix = None
		postfix = None
		try:
			variables = self.get_temperatures()
		except PreheatError:
			variables = {}
		return prefix, postfix, variables


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
	"octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information,
	"octoprint.comm.protocol.scripts": __plugin_implementation__.get_gcode_script_variables
}