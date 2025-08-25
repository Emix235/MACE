// object to manage calendar
var cal = {
	//today's date
	currDate: new Date(),
	//current calendar grid month date
	gridDate: new Date(),
	//stores event with event.id as key
	eventsById: {},
	//stores event.id of events with its GID as key
	syncedGids: {},
	//stores current month day-cells
	dayCells: [],
	$weekdays: $("#week-days li.week-day"),
	$monthLong: $(".month-long"),
	$year: $(".year"),
	$calThumb: $("#cal-thumb-content-grid"),
	$calContentGrid: $("#cal-content-grid"),
	$monthup: $("#cal-content-month-up"),
	$monthdn: $("#cal-content-month-dn"),

	$hour: $("#hour"),
	$minutes: $("#minutes"),
	$ampm: $("#am-pm"),

	$weathericon: $("#weather-type-icon"),
	$weathertext: $("#weather-type-text"),
	$weathermax: $("#weather-max"),
	$weathermin: $("#weather-min"),
	$todayEvents: $("#today-events"),

	owAPIKey: "d0e73cddeb2e577dd6d738ca85acfbb6",

	//select cuurent date week
	selectWeekDay: function () {
		cal.$weekdays
			.removeClass("selected");
		cal.$weekdays
			.eq(cal.currDate.getDay())
			.addClass("selected");
	},

	// generate the calendar grid and thumb
	render: function () {
		//update grid month name and year
		cal.$monthLong
			.html(cal.gridDate.toLocaleDateString("en-us", {
				month: "long"
			}));
		cal.$year.html(cal.gridDate.getFullYear());

		//remove previous days from grid and thumb grid
		cal.dayCells = [];
		$(".week-row").remove();
		$(".thumb-week-row").remove();

		//shift date to first cell date
		var date = new Date(cal.gridDate.getFullYear(), cal.gridDate.getMonth(), 1);
		date.shiftDay(-date.getDay());

		for (var r = 1; r <= 6; ++r) {
			var $weekrow = $("<div class='week-row'><ul></ul></div>"),
				$weekrowul = $weekrow.find("ul:first");

			var $thumbweekrow = $("<div class='thumb-week-row'><ul></ul></div>"),
				$thumbweekrowul = $thumbweekrow.find("ul:first");

			for (var c = 1; c <= 7; ++c) {
				var cls = "week-row-cell",
					thumbcls = "";
				if (date.getMonth() != cal.gridDate.getMonth()) {
					cls += " disabled";
					thumbcls += "disabled";
				}
				if (c == 7) {
					cls += " last";
				}

				if (date.toDateString() == cal.currDate.toDateString()) {
					cls += " selected";
					thumbcls += " selected";
				}
				// append to thumb cal and cal grid
				$thumbweekrowul.append(cal.getThumbWeekCell(date.getDate(), thumbcls));
				var $dayCell = cal.getWeekCell(date, cls)
				$weekrowul.append($dayCell);

				if (date.getMonth() == cal.gridDate.getMonth())
					cal.dayCells.push($dayCell);

				date.shiftDay(1);
			}

			if (r == 6) {
				$weekrow.addClass("last");
			}

			cal.$calContentGrid.append($weekrow);
			cal.$calThumb.append($thumbweekrow);
		}

		cal.getMonthEvents();
	},

	//generate cell li of week row of calendar grid
	getWeekCell: function (date, cls) {
		var $li = $("<li>", {
			class: cls
		});

		var $litop = $("<div class='cell-top'>");

		var $dayno = $("<span class='cell-dayno'>");
		$dayno.text(date.getDate());
		$litop.append($dayno);

		var $weather = $("<span class='cell-weather'>");
		$litop.append($weather);

		var $addevent = $("<span class='btn-fa btn-add'>");
		$addevent.data("date", date.toISOString());
		$addevent.html("<i class='fa fa-calendar-plus-o'></i>");
		$addevent.click(cal.showAddForm);

		$litop.append($addevent);

		$li.append($litop);

		var $celllist = $("<div class='cell-list'><ul></ul></div>");
		$li.append($celllist);

		return $li;
	},
	//generate cell li of thumb calendar
	getThumbWeekCell: function (dayno, cls) {
		var $li = $("<li>", {
			class: cls
		});
		$li.html(dayno);
		return $li;
	},
	//get weather font awesome icon from weather id
	getWeatherfaicon: function (weatherid) {
		var ico = "fa-sun-o";
		if (weatherid > 800 && weatherid < 900)
			ico = "fa-cloud";
		else if (weatherid >= 200 && weatherid < 300)
			ico = "fa-bolt";

		return $("<i>", {
			class: "fa " + ico
		})
	},
	//get city using ip
	getCity: function (callback) {
		$.get("http://ipinfo.io/json", function (res) {
			if (callback !== undefined) {
				callback(res.city);
			}
		});
	},
	// get current month events form db
	getMonthEvents: function () {
		var start = new Date(cal.gridDate.getTime());
		start.setDate(1);
		var end = new Date(start.getTime());
		end.shiftMonth(1);

		cal.getEvents(start, end, function (response) {
			if (response.success) {
				response.data.forEach(function (event) {
					//console.log(event);
					cal.addEventLi(event);
				})

				sync.syncEvents();
			}
		})
	},
	// gets events with start date within [start,end)
	getEvents: function (start, end, callback) {
		if (callback === undefined)
			return;

		var url = "/calendar/event/get/";
		url += start.toISOString() + "/";
		url += end.toISOString() + "/";
		console.log(url);

		$.get({
			url: url,
			success: function (response) {
				callback(response);
			}
		})
	},
	//generate event li
	getEventli: function (event) {
		var $li = $("<li class='event-li'>");

		var $ename = $("<span class='event-li-name'>");
		$ename.text(event.name);
		$li.append($ename);

		var $etime = $("<span class='event-li-time'>");
		var start = new Date(event.start),
			h = cal.getHourStr(start.getHours());

		$etime.text(h);
		$li.append($etime);

		// add data-eid attribute for detail show
		$li.data("eid", event.id);
		$li.click(cal.showDetailForm);

		cal.eventsById[event.id].eventli.push($li);

		return $li;
	},
	//hour string format: (hour)(a/p)
	getHourStr: function (h) {
		return (h < 13 ? h : h - 12) + (h < 12 ? "a" : "p");
	},
	//get events to fill today ul
	getTodayEvents: function () {
		var start = new Date(cal.currDate.getTime());
		var end = new Date(start.getTime());
		end.shiftHour(5);

		var $lis={};
		var $ul = cal.$todayEvents.find("ul:first");
		$ul.children().remove();
		for (var x = new Date(start.getTime()), i = 0; i < 5; ++i) {
			var h=x.getHours(),
				hstr = cal.getHourStr(h),
				$li = $("<li>" + hstr + "</li>");
			
			$ul.append($li);
			$lis[h] = $li;

			x.shiftHour(1);
		}

		cal.getEvents(start, end, function (response) {
			if (response.success) {
				console.log("today events", response);
				response.data.forEach(function(event){
					var h = new Date(event.start).getHours();
					$lis[h].append(", "+event.name);
				})
			}
		});
	},
	//go to previous month
	prevMonth: function () {
		cal.gridDate.shiftMonth(-1);
		cal.render();
	},
	//go to next month
	nextMonth: function () {
		cal.gridDate.shiftMonth(1);
		cal.render();
	},
	// to show time
	tickTime: function () {
		var time = new Date(),
			hour = time.getHours(),
			min = time.getMinutes(),
			ampm = (hour < 12 ? "am" : "pm");

		hour = (hour > 12 ? hour - 12 : hour);
		min = (min < 10 ? '0' + min : min);

		cal.$hour.text(hour);
		cal.$minutes.text(min);
		cal.$ampm.text(ampm);

		setTimeout(cal.tickTime, 1000);
		//console.log(time);
	},
	//weather initialization
	setupWeather: function () {
		cal.getCity(function (city) {
			cal.setCurrWeather(city);
			//console.log(city); 
		});
	},
	//set current weather
	setCurrWeather: function (city) {
		var url = "http://api.openweathermap.org/data/2.5/weather?";
		url += "appid=" + cal.owAPIKey;
		url += "&q=kolkata";
		url += "&units=metric";
		console.log("curr weather", url);

		$.get(url, function (response) {
			//console.log(response);
			var wid = response.weather[0].id,
				wtext = response.weather[0].main,
				wmax = Math.floor(response.main.temp_max) + "º",
				wmin = Math.floor(response.main.temp_min) + "º C";

			cal.$weathericon.html(cal.getWeatherfaicon(wid));
			cal.$weathertext.html(wtext);

			cal.$weathermax.html(wmax);
			cal.$weathermin.html(wmin);
		})
	},
	
	$formwrappers: $(".form-wrapper"),
	$formclose: $(".form-close"),

	$addEventForm: $("#add-event-form"),
	$addEventAction: $("#add-event-action"),
	$addEventEid: $("#add-event-eid"),
	$addEventSynced: $("#add-event-synced"),
	$addEventTop: $("#add-event-top"),
	$addEventName: $("#add-event-name"),
	$addEventLocation: $("#add-event-location"),
	$addEventSdate: $("#add-event-sdate"),
	$addEventStime: $("#add-event-stime"),
	$addEventEdate: $("#add-event-edate"),
	$addEventEtime: $("#add-event-etime"),
	$addEventAllday: $("#add-event-allday"),
	$addEventDesc: $("#add-event-desc"),

	$detailEventForm: $("#detail-event-form"),
	$detailEventName: $("#detail-event-name"),
	$detailEventLocation: $("#detail-event-location"),
	$detailEventDate: $("#detail-event-date"),
	$detailEventDescription: $("#detail-event-desc"),
	$btnEdit: $("#btn-edit"),
	$btnDelete: $("#btn-delete"),

	//to show add event form
	showAddForm: function () {
		cal.$addEventAction.val("add");
		cal.$addEventSynced.val("false");

		//init inputs
		cal.$addEventName.val("");
		cal.$addEventLocation.val("");
		cal.$addEventAllday[0].checked = false;
		cal.$addEventDesc.val("");

		var date = new Date($(this).data("date"));
		cal.$addEventTop.text(date.toDateString());

		date.setHours(cal.currDate.getHours());
		date.setMinutes(cal.currDate.getMinutes());

		cal.$addEventSdate.val(date.toDateInput());
		cal.$addEventStime.val(date.toTimeInput());
		date.shiftHour(1);
		cal.$addEventEdate.val(date.toDateInput());
		cal.$addEventEtime.val(date.toTimeInput());

		cal.$addEventForm.addClass("visible");
	},
	//to show edit form
	showEditForm: function (eid) {
		cal.$addEventAction.val("edit");
		cal.$addEventSynced.val("false");
		cal.$addEventEid.val(eid);

		var event = cal.eventsById[eid];
		cal.$addEventName.val(event.name);
		cal.$addEventLocation.val(event.location);
		var start = new Date(event.start);
		cal.$addEventSdate.val(start.toDateInput())
		cal.$addEventStime.val(start.toTimeInput())
		var end = new Date(event.end);
		cal.$addEventEdate.val(end.toDateInput())
		cal.$addEventEtime.val(end.toTimeInput())
		cal.$addEventAllday[0].checked = event.allday
		cal.$addEventDesc.val(event.description)

		cal.$addEventForm.addClass("visible");
	},
	//onsubmit of add edit form
	addFormSubmit: function (ev) {
		ev.preventDefault();

		var start = new Date(cal.$addEventSdate.val() + " " + cal.$addEventStime.val());
		var end = new Date(cal.$addEventEdate.val() + " " + cal.$addEventEtime.val());
		
		if(start.getTime()>end.getTime()) {
			alert("Event cannot end before it starts");
			return false;
		}
			

		var values = {
			action: cal.$addEventAction.val(),
			synced: (cal.$addEventSynced.val() == "true"),
			eid: cal.$addEventEid.val(),
			name: cal.$addEventName.val().trim(),
			location: cal.$addEventLocation.val().trim(),
			start: start.toISOString(),
			end: end.toISOString(),
			allday: cal.$addEventAllday[0].checked,
			description: cal.$addEventDesc.val(),
			csrfmiddlewaretoken: csrf_token
		}

		//console.log(values);
		cal.addEditEvent(values);
		//sync.addEditEvent(values);

		cal.closeForms();
		return false;
	},
	//to show details form
	showDetailForm: function () {
		var eid = $(this).data("eid"),
			event = cal.eventsById[eid];

		cal.$detailEventName.text(event.name);
		cal.$detailEventLocation.text(event.location);

		var date = new Date(event.start),
			datestr = date.toTimeInput() + ", " + date.toDateString();
		cal.$detailEventDate.text(datestr);

		cal.$detailEventDescription.text(event.description);
		cal.$btnEdit.data("eid", event.id);
		cal.$btnDelete.data("eid", event.id);

		cal.$detailEventForm.addClass("visible");
	},
	//delete event by eid from db
	deleteEvent: function (eid) {
		$.post({
			url: "/calendar/event/delete/",
			data: {
				eid: eid,
				csrfmiddlewaretoken: csrf_token
			},
			success: function (response) {
				console.log("delete", response);
				if (response.success) {
					eid = response.eid;

					if (cal.eventsById[eid].gid != '') {
						sync.deleteEvent(cal.eventsById[eid].gid)
					}

					cal.deleteEventLi(eid)
					delete cal.eventsById[eid];
				}
			}
		})
	},
	//delete lis on delete of event
	deleteEventLi: function (eid) {
		cal.eventsById[eid].eventli.forEach(function (li) {
			li.remove();
		})
	},
	//add or edit event in db
	addEditEvent: function (values) {
		// google calendar stores all day with end date as exclusive
		if (!values.synced && values.allday) {
			var end = new Date(values.end);
			end.shiftDay(1);
			values.end = end.toISOString()
		}

		$.post({
			url: "/calendar/event/addedit/",
			data: values,
			success: function (response) {
				console.log("add/edit", response);
				if (response.success) {
					var event = response.data;

					//delete eventli if action was edit and eventli exists
					if (cal.eventsById.hasOwnProperty(event.id)) {
						cal.deleteEventLi(event.id)
					}
					cal.addEventLi(event);

					// if not synced sync
					if (!event.synced) {
						event.action = values.action;
						sync.addEditEvent(event);
					}
				}
			}
		})
	},
	//add event li
	addEventLi: function (event) {
		cal.syncedGids[event.gid] = event.id;
		cal.eventsById[event.id] = event;
		cal.eventsById[event.id].eventli = [];

		var start = new Date(event.start),
			end = new Date(event.end);

		if (event.allday) {
			end.shiftDay(-1);
		}

		for (var d = start.getDate(); d <= end.getDate(); ++d) {
			cal.dayCells[d - 1]
				.find("ul:first")
				.append(cal.getEventli(event));
		}
	},
	// set synced true for given eid 
	setSync: function (eid, gid) {
		$.post({
			url: "/calendar/event/setsync/",
			data: {
				eid: eid,
				gid: gid,
				csrfmiddlewaretoken: csrf_token
			},
			success: function (response) {
				console.log("set sync", response);
				if (response.success) {
					cal.syncedGids[response.gid] = response.eid
				}
			}
		})
	},
	//close any form visible
	closeForms: function () {
		cal.$formwrappers.removeClass("visible");
	},

	//initialize calendar
	initForms: function () {
		// addedit form submit
		cal.$addEventForm
			.find("form:first")
			.submit(cal.addFormSubmit);

		//edit and delete button
		cal.$btnEdit.click(function () {
			cal.closeForms();
			cal.showEditForm($(this).data("eid"));
		})
		cal.$btnDelete.click(function () {
			cal.deleteEvent($(this).data("eid"));
			cal.closeForms();
		})

		// setup cancel close and outside click form close 
		cal.$formclose.click(cal.closeForms);
		cal.$formwrappers.click(function (ev) {
			if (ev.target === this)
				cal.closeForms();
		});
	},
	init: function () {
		cal.selectWeekDay();
		cal.render();

		cal.$monthup.click(cal.prevMonth);
		cal.$monthdn.click(cal.nextMonth);

		cal.tickTime();

		cal.setupWeather();

		cal.initForms();
	}
};

// increase or decrease by hour value of Date object
Date.prototype.shiftHour = function (hours) {
	this.setHours(this.getHours() + hours);
}
// increase or decrease by Date value of Date object
Date.prototype.shiftDay = function (days) {
	this.setDate(this.getDate() + days);
}
// increase or decrease by Month value of Date object
Date.prototype.shiftMonth = function (month) {
	this.setMonth(this.getMonth() + month);
}
// convert date of Date object to YYYY-MM-DD format
Date.prototype.toDateInput = function () {
	var year = this.getFullYear(),
		month = this.getMonth() + 1,
		day = this.getDate();

	if (month < 10)
		month = "0" + month;
	if (day < 10)
		day = "0" + day

	var str = year + "-" + month + "-" + day;
	return str;
}
// convert time of Date object to HH:MM format
Date.prototype.toTimeInput = function () {
	var hour = this.getHours(),
		min = this.getMinutes();

	if (hour < 10)
		hour = '0' + hour;
	if (min < 10)
		min = '0' + min;

	//console.log(hour + ":" + min);
	return hour + ":" + min;
}

// object to manage sync with Google Calendar
var sync = {
	CLIENT_ID: '642165405561-i3955klb3np69upspeuakno68hg6adt0.apps.googleusercontent.com',
	SCOPES: ["https://www.googleapis.com/auth/calendar"],
	synced: false,
	$btnSync: $("#btn-sync"),

	//on start of sync
	syncStart: function () {
		sync.$btnSync.addClass("fa-spin");
	},
	//on end of sync
	syncEnd: function () {
		sync.$btnSync.removeClass("fa-spin");
		cal.getTodayEvents();
	},
	// handles auth click event
	handleAuthClick: function (event) {
		event.preventDefault();
		gapi.auth.authorize({
				client_id: sync.CLIENT_ID,
				scope: sync.SCOPES,
				immediate: false
			},
			sync.handleAuthResult);
		return false;
	},
	// reads and processes auth response
	handleAuthResult: function (authResult) {
		if (authResult && !authResult.error) {
			gapi.client.load('calendar', 'v3', function () {
				sync.synced = true;
				sync.syncEvents();
			});
		} else {
			console.log("Sync Failed");
		}
	},
	// add or edit event in google calendar
	addEditEvent: function (values) {
		if (!sync.synced)
			return;

		var event = {
			'summary': values.name,
			'location': values.location,
			'description': values.description,
			'start': {
				'dateTime': values.start,
				'timeZone': 'UTC'
			},
			'end': {
				'dateTime': values.end,
				'timeZone': 'UTC'
			}
		};

		if (values.allday) {
			delete event["start"]["dateTime"];
			event["start"]["date"] = (new Date(values.start)).toDateInput();

			delete event["end"]["dateTime"];
			event["end"]["date"] = (new Date(values.end)).toDateInput();
		}

		console.log("google add values", values, event);

		var request;
		if (values.action == "add") {
			request = gapi.client.calendar.events.insert({
				'calendarId': 'primary',
				'resource': event
			});
		} else if (values.action == "edit") {
			request = gapi.client.calendar.events.update({
				'calendarId': 'primary',
				'eventId': values.gid,
				'resource': event
			});
		} else {
			return;
		}

		request.execute(function (gevent) {
			console.log('Google Calendar Event created/edited ', gevent);
			cal.setSync(values.id, gevent.id);
			sync.syncEnd();
		});
	},
	// delete event from google calendar
	deleteEvent: function (gid) {
		if (!sync.synced)
			return;
		sync.syncStart();

		var request = gapi.client.calendar.events.delete({
			'calendarId': "primary",
			'eventId': gid
		});

		request.execute(function (resp) {
			console.log("google DELETED", resp);
			sync.syncEnd();
		});
	},
	// download events from google calendar for cal.gridDate month
	downEvents: function (callback) {
		if (!sync.synced)
			return;

		var start = new Date(cal.gridDate.getTime());
		start.setDate(1);
		var end = new Date(start.getTime());
		end.shiftMonth(1);

		var request = gapi.client.calendar.events.list({
			"calendarId": "primary",
			"timeMin": start.toISOString(),
			"timeMax": end.toISOString(),
			"timezone": "UTC",
			"showDeleted": false,
			'singleEvents': true,
			"orderBy": "updated"
		});

		request.execute(function (resp) {
			console.log(resp);
			var events = resp.items;
			//appendPre('Upcoming events:');

			if (events.length > 0) {

				for (var i = 0; i < events.length; i++) {
					var event = events[i];

					var gid = event.id;

					var name = event.summary ? event.summary : "";
					var location = event.location ? event.location : "";
					var allday = false;
					var sdate = event.start.dateTime;
					if (!sdate) {
						sdate = event.start.date;
						allday = true;
					}

					var edate = event.end.dateTime;
					if (!edate) {
						edate = event.end.date;
						allday = true;
					}

					var description = event.description ? event.description : "";

					var values = {
						gid: gid,
						action: "add",
						synced: true,
						name: name,
						location: location,
						start: sdate,
						end: edate,
						allday: allday,
						description: description,
						csrfmiddlewaretoken: csrf_token
					};

					if (cal.syncedGids.hasOwnProperty(values.gid)) {
						values.action = "edit";
						values.eid = cal.syncedGids[values.gid];
					}

					//console.log(values);
					cal.addEditEvent(values);
				}
			} else {
				console.log('No upcoming events found.');
			}

			if (callback !== undefined) {
				callback();
			}
		});
	},
	//upload usynced (event.sync=false) events to google calendar
	upEvents: function (callback) {
		$.each(cal.eventsById, function (id, event) {
			if (!event.synced) {
				var values = {
					name: event.name,
					location: event.location,
					start: event.start,
					end: event.end,
					allday: event.allday,
					description: event.description,
					eid: event.id,
					action: "add",
					synced: true
				};

				if (event.gid != "") {
					values.action = "edit";
					values.gid = event.gid;
				}

				sync.addEditEvent(values);
			}
		});

		if (callback !== undefined)
			callback();
	},
	//sync events
	syncEvents: function () {
		if (!sync.synced) {
			sync.syncEnd();
			return;
		}

		sync.syncStart();
		sync.upEvents(function () {
			sync.downEvents(function () {
				sync.syncEnd();
			});
		});
	},
	//initalization
	init: function () {
		sync.$btnSync.click(sync.handleAuthClick);
	}
}

cal.init();
sync.init();

//try auth on load of calendar
function tryauth() {
	//console.log("auth");
	gapi.auth.authorize({
			client_id: sync.CLIENT_ID,
			scope: sync.SCOPES,
			immediate: true
		},
		sync.handleAuthResult);
}
