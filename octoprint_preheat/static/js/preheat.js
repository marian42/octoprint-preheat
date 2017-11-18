$(function() {
	function PreheatViewModel(parameters) {
		var self = this;
		self.settings = undefined;
		
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
		
		self.enablePreheat = function() {
			return true;
		};

		self.visibleTest = function() {
			return self.loginState.isUser() && self.printerState.isOperational();
		};
	}

	
	// view model class, parameters for constructor, container to bind to
	OCTOPRINT_VIEWMODELS.push([
		PreheatViewModel,
		["settingsViewModel", "loginStateViewModel", "printerStateViewModel"],
		["#sidebar_plugin_preheat"]
	]);
});