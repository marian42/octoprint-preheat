$(function() {
	function PreheatViewModel(parameters) {
		var self = this;
		self.settings = undefined;
		self.btnPreheat = undefined;
		
		self.MODE_PREHEAT = 0;
		self.MODE_COOLDOWN = 1;
		
		self.mode = self.MODE_PREHEAT;
		
		self.loginState = parameters[0];
		self.temperatureState = parameters[1];
		self.printerState = parameters[2];

		self.preheat = function() {
			$.ajax({
				url: API_BASEURL + "plugin/preheat",
				type: "POST",
				dataType: "json",
				data: JSON.stringify({
					command: "preheat"
				}),
				contentType: "application/json; charset=UTF-8",
				error: function (data, status) {
					var options = {
						title: "Preheating failed.",
						text: data.responseText,
						hide: true,
						buttons: {
							sticker: false,
							closer: true
						},
						type: "error"
					};
					
					new PNotify(options);
				}
			});
		};
		
		self.cooldown = function() {
			$.ajax({
				url: API_BASEURL + "printer/tool",
				type: "POST",
				dataType: "json",
				data: JSON.stringify({
					command: "target",
					targets: {
						tool0: 0
					}
				}),
				contentType: "application/json; charset=UTF-8"
			});
		};
		
		
		self.btnPreheatClick = function() {
			if (self.mode == self.MODE_PREHEAT) {
				self.preheat();
			}
			if (self.mode == self.MODE_COOLDOWN) {
				self.cooldown();
			}
		}
		
		self.initializeButton = function() {
			var buttonContainer = $('#job_print')[0].parentElement;
			buttonContainer.children[0].style.width = "100%";
			buttonContainer.children[0].style.marginBottom = "10px";
			buttonContainer.children[1].style.marginLeft = "0";
			
			self.btnPreheat = document.createElement("button");
			self.btnPreheat.classList.add("btn");
			self.btnPreheat.classList.add("span4");
			self.btnPreheat.innerText = "Preheat";
			self.btnPreheat.addEventListener("click", self.btnPreheatClick);
			buttonContainer.appendChild(self.btnPreheat);
			
			if (typeof(TouchUI) != "undefined") {
				$('.progress-text-centered')[0].style.top = "calc(2.125rem + 90px)";
				$('#state')[0].style.paddingTop = "155px";
				self.btnPreheat.style.fontSize = "1.4rem";
				self.btnPreheat.style.display = "block";
			}
		};
		
		self.updateButton = function() {
			var target = self.temperatureState.tools()[0].target();
			
			if (target == 0) {
				self.mode = self.MODE_PREHEAT;
				self.btnPreheat.title = "Preheats the nozzle for the loaded gcode file.";
				self.btnPreheat.innerText = "Preheat";
			} else {
				self.mode = self.MODE_COOLDOWN;
				self.btnPreheat.title = "Disables tool heating.";
				self.btnPreheat.innerText = "Cooldown";
			}
			
			self.btnPreheat.disabled = !self.temperatureState.isReady()
				|| self.temperatureState.isPrinting()
				|| !self.loginState.isUser()
				|| (target == 0 && self.printerState.filename() == null);
		};
		
		self.initializeButton();		
		self.fromCurrentData = function() { self.updateButton(); };
	}
	
	OCTOPRINT_VIEWMODELS.push([
		PreheatViewModel,
		["loginStateViewModel", "temperatureViewModel", "printerStateViewModel"],
		[]
	]);
});