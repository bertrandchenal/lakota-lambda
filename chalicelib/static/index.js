
function load_graph(uri, elm_id) {
	const request = new Request(uri);
	fetch(request)
		.then(response => response.json())
		.then(resp => plot(resp, elm_id))
}

function plot(resp, elm_id) {
	// let opts = resp.options;
	// console.log(opts);
	// for (pos in opts.series) {
	// 	var series = opts.series[pos];
	// 	series['value'] = (self, rawValue) => rawValue.toFixed(2);
	// }
	var el = document.getElementById(elm_id);
	resp.options.width = el.clientWidth;
	let uplot = new uPlot(resp.options, resp.data, document.getElementById(elm_id));
}
	// let options = {
	// 	// title: title,
	// 	// id: "chart1",
	// 	// class: "my-chart",
	// 	width: width,
	// 	height: width,
	// 	series: [
	// 		{},
	// 		{
	// 			// initial toggled state (optional)
	// 			show: true,
	// 			spanGaps: false,
	// 			// in-legend display
	// 			label: "Value1",
	// 			value: (self, rawValue) => rawValue.toFixed(2),

	// 			// series style
	// 			stroke: "red",
	// 			width: 1,
	// 			fill: "rgba(255, 0, 0, 0.3)",
	// 			dash: [10, 5],
	// 		},
	// 		{
	// 			// initial toggled state (optional)
	// 			show: true,
	// 			spanGaps: false,
	// 			// in-legend display
	// 			label: "Value2",
	// 			value: (self, rawValue) => rawValue.toFixed(2),

	// 			// series style
	// 			stroke: "green",
	// 			width: 1,
	// 			fill: "rgba(0, 255, 0, 0.3)",
	// 			dash: [10, 5],
	// 		}
	// 	],
	// };
