var sensorLib = require("node-dht-sensor")
sensorLib.initialize(22, 12);

var interval = setInterval(function () {
	read();
}, 2000);

function read() {
	var readout = sensorLib.read();
	console.log("temp: " + readout.temperature.toFixed(2) + "C" +
		    " hum: " + readout.humidity.toFixed(2) + "%");
	console.log(readout);
}

