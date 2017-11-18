$(function() {
	function PreheatViewModel(parameters) {
		var self = this;
		self.settings = undefined;
		self.btnPreheat = undefined;
		
        self.allSettings = parameters[0];
        self.loginState = parameters[1];
        self.printerState = parameters[2];
		
		self.onAfterBinding = function() {
			// self.settings = self.allSettings.settings.plugins.preheat;
		};

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
		
		
		self.btnPreheatClick = function() {
			self.preheat();
		}
		
		self.initializeButton = function() {
			var buttonContainer = $('#job_print')[0].parentElement;
			buttonContainer.children[0].style.width = "100%";
			buttonContainer.children[0].style.marginBottom = "10px";
			buttonContainer.children[1].style.marginLeft = "0";
			
			self.btnPreheat = document.createElement("button");
			self.btnPreheat.classList.add("btn");
			self.btnPreheat.classList.add("span4");
			self.btnPreheat.title = "Preheats the nozzle for the loaded gcode file.";
			self.btnPreheat.innerText = "Preheat";
			self.btnPreheat.addEventListener("click", self.btnPreheatClick);
			buttonContainer.appendChild(self.btnPreheat);
		};

		self.initializeButton();
	}
	
	// view model class, parameters for constructor, container to bind to
	OCTOPRINT_VIEWMODELS.push([
		PreheatViewModel,
		["settingsViewModel", "loginStateViewModel", "printerStateViewModel"],
		[]
	]);
});