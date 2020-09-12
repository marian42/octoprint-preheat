# Preheat Button

This Octoprint plugin adds a preheat button to preheat the nozzle and bed to the printing temperature of the selected gcode file.
This can be done manually but this plugin makes it more convenient.
If the target temperature is not zero, the button will instead turn off nozzle heating (cooldown).

![Screenshot](https://i.imgur.com/5eTx0pb.png)

## Setup

Install via the bundled [Plugin Manager](https://github.com/foosel/OctoPrint/wiki/Plugin:-Plugin-Manager)
or manually using this URL:

    https://github.com/marian42/octoprint-preheat/archive/master.zip

## Troubleshooting

If you have a printer that adds image data to the top of the G-Code file (Prusa Mini), the default of checking the first 1000 lines for set temperature commands might not be enough. Use the setting labeled "Max number of lines to look for preheat commands" to adjust how many lines are looked at.
