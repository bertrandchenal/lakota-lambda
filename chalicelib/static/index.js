
function load_graph(uri, elm_id, page_len) {
	const request = new Request(uri);
	fetch(request)
		.then(response => response.json())
		.then(resp => plot(resp, elm_id, page_len))
}

function plot(resp, elm_id, page_len) {
	var el = document.getElementById(elm_id);
	resp.options.width = el.clientWidth;
	let uplot = new uPlot(resp.options, resp.data, document.getElementById(elm_id));

	// Disable next button
	console.log(resp.data[0].length);
	if (resp.data[0].length < page_len) {
		var btn = document.getElementById('next-btn');
		if (btn) {
			btn.setAttribute("disabled", "true");
		}
	}
}
