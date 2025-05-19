# Preheat Button

This Octoprint plugin adds a preheat button to preheat the nozzle and bed to the printing temperature of the selected gcode file.
This can be done manually but this plugin makes it more convenient.
If the target temperature is not zero, the button will instead turn off nozzle heating (cooldown).

![Screenshot](https://i.imgur.com/5eTx0pb.png)

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/marian42/octoprint-preheat/archive/master.zip

## Support for segmented print bed with M555 (Prusa XL)

In the settings of this plugin you find the checkbox "Enable print area parsing (e.g. Prusa XL)".
With it you can enable the support for M555 parsing and sending.

The M555 command will be parsed from selected file and the command will be sent to the printer before sending the temperatures to the printer.

When selecting "Cooldown" also the M555 is sent to the printer, to reset the print area.
This is done by sending M555 with coordinates X=0, Y=0 and not width or heigt.
The current M555 implementation of Prusa XL uses the total area if parameters W### and H### are missing.
Unfortunately I have not found a proper gcode number or parameter to reset the area.


## Troubleshooting

If you have a printer that adds image data to the top of the G-Code file (Prusa Mini), the default of checking the first 1000 lines for set temperature commands might not be enough. Use the setting labeled "Max number of lines to look for preheat commands" to adjust how many lines are looked at.
