odoo.define("asterisk_plus.intercom", function (require) {
    "use strict";

    // TODO: Update event List
    const eventList = [
        {model: "asterisk_plus.server", post_id: 8927457},
        {model: "asterisk_plus.recording", post_id: 8989865},
    ]

    var ajax = require('web.ajax');
    var WebClient = require('web.WebClient');

    WebClient.include({
        start: function () {
            this._super()
            let url = location.href
            const self = this
            this.getSession().user_has_group('asterisk_plus.group_asterisk_admin').then(function (has_group) {
                if (has_group) {

                    ajax.rpc('/web/dataset/call_kw/asterisk_plus', {
                        "model": "asterisk_plus.settings",
                        "method": "get_instance_support_data",
                        "args": [],
                        "kwargs": {}
                    }).then(function (support_data) {
                        self.manageIntercom(location.href, support_data)
                        if (window.navigation) {
                            navigation.addEventListener("navigate", (event) => {
                                self.manageIntercom(event.destination.url, support_data)
                            })
                        } else {
                            setInterval(() => {
                                if (url !== location.href) {
                                    url = location.href
                                    self.manageIntercom(location.href, support_data)
                                }
                            }, 1000)
                        }
                    })
                }
            })
        },

        manageIntercom: function (url, support_data) {
            eventList.forEach((event) => {
                if (url.includes(event.model)) {
                    let asterisk_plus_setup = localStorage.getItem('asterisk_plus_setup')
                    asterisk_plus_setup = asterisk_plus_setup ? JSON.parse(asterisk_plus_setup) : []
                    if (!asterisk_plus_setup.includes(event.post_id)) {
                        asterisk_plus_setup.push(event.post_id)
                        localStorage.setItem('asterisk_plus_setup', JSON.stringify(asterisk_plus_setup))
                        window.Intercom('showArticle', event.post_id)
                    }
                }
            })
            if (url.includes('model=asterisk_plus')) {
                if (!window.intercomStatus) {
                    window.intercomStatus = true
                    this.intercomStart(support_data, {show: false})
                }
            } else {
                if (window.intercomStatus && typeof window.Intercom === "function") {
                    window.intercomStatus = false
                    window.Intercom('shutdown')
                }
            }
        },

        intercomStart: function (support_data, {show = false}) {
            const {user_id, user_hash, name, email, created_at} = support_data
            window.intercomSettings = {
                api_base: "https://api-iam.intercom.io",
                app_id: "qijhupkn",
                name, // Full name
                user_id, // a UUID for your user
                email, // the email for your user
                created_at, // Signup date as a Unix timestamp
                user_hash,
            };

            // We pre-filled your app ID in the widget URL: 'https://widget.intercom.io/widget/qijhupkn'
            (function () {
                var w = window;
                var ic = w.Intercom;
                if (typeof ic === "function") {
                    ic('reattach_activator');
                    ic('update', w.intercomSettings);
                    if (show) w.Intercom('show')
                } else {
                    var d = document;
                    var i = function () {
                        i.c(arguments);
                    };
                    i.q = [];
                    i.c = function (args) {
                        i.q.push(args);
                    };
                    w.Intercom = i;
                    var l = function () {
                        var s = d.createElement('script');
                        s.type = 'text/javascript';
                        s.async = true;
                        s.src = 'https://widget.intercom.io/widget/qijhupkn';
                        var x = d.getElementsByTagName('script')[0];
                        x.parentNode.insertBefore(s, x)
                        if (show) w.Intercom('show')
                    };
                    if (document.readyState === 'complete') {
                        l();
                    } else if (w.attachEvent) {
                        w.attachEvent('onload', l);
                    } else {
                        w.addEventListener('load', l, false);
                    }
                }
            })();
        }
    })
})
