document.addEventListener("DOMContentLoaded", function (event) {
    const init_soft_phone = (params) => {
        let _enabledButton = true
        for (let key in params) {
            if (!params[key]) {
                console.warn(`Missing config: "${key}" for Talk Button!`)
                _enabledButton = false
            }
        }
        if (!_enabledButton) {
            return
        }
        const talkButton = document.querySelector("#talk_btn")
        let talkButtonText = talkButton
        let flag = true
        while (flag) {
            if (talkButtonText.firstElementChild) {
                talkButtonText = talkButtonText.firstElementChild
            } else {
                flag = false
            }
        }
        const initTalkButtonText = talkButtonText.innerText

        let soundPlayer = document.createElement("audio")
        soundPlayer.volume = 0.7
        soundPlayer.src = "/asterisk_plus_website/static/src/sounds/outgoing-call.mp3"

        const {
            talkbtn_sip_user,
            talkbtn_sip_secret,
            talkbtn_exten,
            talkbtn_sip_proxy,
            talkbtn_sip_protocol,
            talkbtn_websocket
        } = params

        var socket = null
        try {
            socket = new JsSIP.WebSocketInterface(`${talkbtn_websocket}`)
        } catch (e) {
            console.error(e)
            return
        }

        socket.via_transport = talkbtn_sip_protocol
        var configuration = {
            sockets: [socket],
            ws_servers: `${talkbtn_websocket}`,
            realm: "AsteriskPlus",
            display_name: `${talkbtn_sip_user}`,
            uri: `sip:${talkbtn_sip_user}@${talkbtn_sip_proxy}`,
            password: `${talkbtn_sip_secret}`,
            contact_uri: `sip:${talkbtn_sip_user}@${talkbtn_sip_proxy}`,
            register: false,
        }
        var userAgent = new JsSIP.UA(configuration)
        // JsSIP.debug.enable("JsSIP:*")
        // JsSIP.debug.disable("JsSIP:*")
        userAgent.start()

        userAgent.on("registered", function (e) {
            console.log("SIP Registered")
        })

        userAgent.on("newRTCSession", function ({ session }) {
            if (session.direction === "outgoing") {
                session.connection.addEventListener("track", (e) => {
                    const remoteAudio = document.createElement("audio")
                    remoteAudio.srcObject = e.streams[0]
                    remoteAudio.play()
                })
            }
        })

        var eventHandlers = {
            connecting: function (data) {
                talkButton.classList.add("btn-warning")
                talkButtonText.innerText = "Calling ..."
                soundPlayer.play()
                soundPlayer.loop = true
            },
            confirmed: function (data) {
                talkButton.classList.add("btn-danger")
                talkButtonText.innerText = "Hangup"
            },
            accepted: function (data) {
                soundPlayer.pause()
                soundPlayer.currentTime = 0
            },
            ended: function (data) {
                talkButton.classList.remove("btn-danger", "btn-warning")
                talkButtonText.innerText = initTalkButtonText
                soundPlayer.pause()
                soundPlayer.currentTime = 0
            },
            failed: function (data) {
                talkButton.classList.remove("btn-danger", "btn-warning")
                talkButtonText.innerText = initTalkButtonText
                soundPlayer.pause()
                soundPlayer.currentTime = 0
            }
        }

        var options = {
            eventHandlers: eventHandlers,
            mediaConstraints: { audio: true, video: false }
        }

        var callSession = null
        talkButton.addEventListener("click", function () {
            if (talkButton.classList.contains("btn-danger") || talkButton.classList.contains("btn-warning")) {
                callSession.terminate()
            } else {
                callSession = userAgent.call(`sip:${talkbtn_exten}`, options)
            }
        })
    }

    fetch("/get_talk_param/", {
        headers: {
            "Accept": "application/json",
            "Content-Type": "application/json"
        },
        method: "POST",
        body: JSON.stringify({})
    })
        .then(res => res.json())
        .then(res => init_soft_phone(res.result))
})