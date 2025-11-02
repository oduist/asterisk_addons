/** @odoo-module **/
"use strict"
import {useService} from "@web/core/utils/hooks"
import {uid} from "web.session"
import {Calls} from "@asterisk_plus_phone/components/calls/calls"
import {Favorites} from "@asterisk_plus_phone/components/favorites/favorites"
import {Contacts} from "@asterisk_plus_phone/components/contacts/contacts"
import {browser, dialTone, setFocus, maskNumber} from "@asterisk_plus_phone/js/utils"

const {Component} = owl
const {useState, useRef, onWillStart, onMounted} = owl.hooks
const {loadJS} = owl.utils

export class Phone extends Component {
    static template = 'asterisk_plus_phone.phone'
    static components = {Calls, Favorites, Contacts}

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
        this.callStatus = {
            NoAnswer: 'noanswer',
            Busy: 'busy',
            Rejected: 'busy',
            Answered: 'answered',
            Terminated: 'hangup',
            Canceled: 'canceled',
            Failed: 'failed'
        }
        this.tabs = {
            phone: 'phone',
            contacts: 'contacts',
            calls: 'calls',
            favorites: 'favorites'
        }
        this.status = {
            incoming: 'incoming',
            outgoing: 'outgoing',
            connecting: 'connecting',
            accepted: 'accepted',
            ended: 'ended'
        }
        this.title = 'Phone'
        this.state = useState({
            isActive: true,
            isDisplay: false,
            isDisplayLastState: false,
            isMicrophoneMute: false,
            isSoundMute: localStorage.getItem('asterisk_plus_phone_is_sound_mute') === 'true',
            isKeypad: true,
            isContacts: false,
            isFavorites: false,
            isCalls: false,
            isPartner: false,
            isTransfer: false,
            isForward: false,
            isCallForwarded: false,
            isDialingPanel: false,
            inCall: false,
            inIncoming: false,
            isContactList: false,
            phoneNumber: '',
            callPhoneNumber: '',
            contact_search_query: '',
            user_search_query: '',
            partnerName: '',
            partnerId: '',
            partnerUrl: '',
            partnerIconUrl: '',
            users: [],
            activeTab: this.tabs.phone,
            callDurationTime: '',
            callerId: {},
            xTransferTo: '',
            xTransferInfo: '',
            xTransferPartner: false,
            phone_status: this.status.ended,
            calls: [],
        })
        this.callDuration = 0
        this.callDurationTimerInstance = null
        this.phoneInput = useRef('phone-input')
        this.enterPhoneNumberTimer = null
        this.userInput = useRef('user-input')
        this.user = uid
        this.phone_configs = {
            phone_sip_protocol: '',
            phone_sip_proxy: '',
            sip_password: '',
            sip_user: '',
            phone_stun_server: '',
            phone_websocket: '',
            phone_realm: '',
            sip_auth_user: ''
        }
        this.sipRegistered = false
        this.lastActiveTab = this.tabs.phone
        this.session = null
        this.userAgent = null
        this.call_id = null
        this.call_popup_is_enabled = false
        this.call_popup_is_sticky = false
        this.phone_ring_volume = 70
        this.isMaskCallNumber = false
        this.attended_transfer_sequence = '*7'
        this.disconnect_call_sequence = '**'
        this.trace_sip = false
        // Move Phone
        this.mousePosition = {}
        this.offset = [0, 0]
        this.isDown = false
        this.phoneRoot = useRef("phone-root")
        this.phoneHeader = useRef("phone-header")
        // BroadcastChannel
        this.bc = new BroadcastChannel("phone")
        this.contactSearch = 'all'
        this.id = Math.floor(Math.random() * 1000000);
        this.windows = [this.id]
        this.sipSessions = []
        this.supressBroadcastChannel = false
        this.browser = navigator.userAgent.includes("Firefox") ? browser.firefox : browser.chrome
    }

    setup() {
        super.setup()
        this.orm = useService('orm')
        this.action = useService('action')
        this.notification = useService("notification")

        this.notify = (message, {title = 'Phone', sticky = null, type = 'info', messageIsHtml = false}) => {
            if (sticky === null) {
                sticky = this.call_popup_is_sticky
            }
            if (this.call_popup_is_enabled) {
                this.notification.add(message, {title, sticky, type, messageIsHtml})
            }
        }

        onWillStart(async () => {
            await loadJS('/asterisk_plus_phone/static/src/lib/jssip.min.js')

            this.testPlayer = new Audio()
            this.testPlayer.src = "/asterisk_plus_phone/static/src/sounds/mute.mp3"
            this.testPlayer.volume = 0.5

            // EVENTS
            this.bus.on('busPhoneMakeCall', this, this.prepareCall)

            this.bus.on('busPhoneMakeTransfer', this, this._busPhoneMakeTransfer)

            this.bus.on('busPhoneMakeForward', this, this._busPhoneMakeForward)

            this.bus.on('busPhoneToggleDisplay', this, this._busPhoneToggleDisplay)

            this.bus.on('busPhoneHangUp', this, this._busPhoneHangUp)

            this.bus.on('busBugReport', this, this._busBugReport)

            // Get USER configs
            const {user_config, phone_config} = await this.orm.call('res.users', 'get_sip_user_config', [uid])
            this.call_popup_is_enabled = phone_config.call_popup_is_enabled
            this.call_popup_is_sticky = phone_config.call_popup_is_sticky
            this.phone_ring_volume = phone_config.phone_ring_volume
            this.isMaskCallNumber = phone_config.mask_call_number

            if (user_config) {
                delete user_config['id']
                Object.assign(this.phone_configs, user_config)
            }

            // Get WebRTC configs
            const phone_pbx_configs = await this.orm.call("asterisk_plus.settings", "get_settings")
            this.attended_transfer_sequence = phone_pbx_configs['attended_transfer_sequence']
            this.disconnect_call_sequence = phone_pbx_configs['disconnect_call_sequence']
            this.trace_sip = phone_pbx_configs['trace_sip']
            this.phone_sip_auth_user_enabled = phone_pbx_configs['phone_sip_auth_user_enabled']
            this.contactSearch = phone_pbx_configs['transfer_contact_search']
            Object.assign(this.phone_configs, phone_pbx_configs.user_agent)

            this.dialPlayer = document.createElement("audio")
            this.dialPlayer.volume = this.phone_ring_volume / 100
            this.dialPlayer.setAttribute("src", "/asterisk_plus_phone/static/src/sounds/outgoing-call.mp3")

            this.autoAnswerPlayer = document.createElement("audio")
            this.autoAnswerPlayer.volume = this.phone_ring_volume / 100
            this.autoAnswerPlayer.setAttribute("src", "/asterisk_plus_phone/static/src/sounds/beep.mp3")

            this.incomingPlayer = document.createElement("audio")
            this.incomingPlayer.setAttribute("src", "/asterisk_plus_phone/static/src/sounds/incoming-call-2.mp3")
            this.incomingPlayer.loop = true
            this.setIncomingVolume()

            window.addEventListener("beforeunload", (event) => {
                if (this.session) {
                    event = event || window.event
                    const message = "You're in call! Are you sure you want to close?"
                    if (event) {
                        event.returnValue = message
                    }
                    return message
                }
            })

            window.addEventListener("unload", (event) => {
                if (this.session) {
                    const params = {id: this.id, action: 'pop'}
                    this.bc.postMessage({event: 'bcSipSession', params})
                    this.bc.postMessage({event: "bcCloseTab", params: {id: this.id}})
                    this.session.terminate()
                }
            })
        })

        onMounted(() => {
            for (let key in this.phone_configs) {
                if (key !== 'sip_auth_user' && !this.phone_configs[key]) {
                    console.error(`Missing config: "${key}" for Phone!`)
                    this.state.isActive = false
                }
            }
            this.initUserAgent()

            const phoneRoot = this.phoneRoot.el
            this.phoneHeader.el.addEventListener("mousedown", function (e) {
                self.isDown = true
                self.offset = [
                    phoneRoot.offsetLeft - e.clientX,
                    phoneRoot.offsetTop - e.clientY
                ]
            }, true)

            document.addEventListener("mouseup", function () {
                self.isDown = false
            }, true)

            document.addEventListener("mousemove", function (event) {
                if (self.isDown) {
                    event.preventDefault()
                    self.mousePosition = {
                        x: event.clientX,
                        y: event.clientY
                    }
                    const px = self.mousePosition.x + self.offset[0]
                    const py = self.mousePosition.y + self.offset[1]
                    const cx = document.documentElement.clientWidth
                    const cy = document.documentElement.clientHeight

                    let left = px < 10 ? 0 : px
                    left = left + 310 > cx ? cx - 300 : left
                    let top = py < 10 ? 0 : py
                    top = top + 530 > cy ? cy - 520 : top

                    phoneRoot.style.left = left + "px"
                    phoneRoot.style.top = top + "px"
                }
            }, true)
            // BroadcastChannel Events
            const self = this
            this.bc.onmessage = ({data: {event, params}}) => {
                // console.log('bc.onMessage', {event, params})
                const localStartCall = () => {
                    if (self.session) return
                    // console.log('bcStartCall -> ... INIT')
                    const {callerId, isPartner} = params
                    self.state.isPartner = isPartner
                    self.state.callerId = callerId

                    self.state.inIncoming = true
                    self.state.isDialingPanel = true
                    self.startCall()
                }
                if (event === 'bcStartCall') {
                    // console.log('bcStartCall', params)
                    if (!self.session && !self.state.inIncoming) {
                        self.state.isDisplayLastState = self.state.isDisplay
                    }
                    localStartCall()
                    if (self.id === self.windows.at(-1) && !self.session) {
                        const ringParams = {id: self.sipSessions[0]}
                        self.bc.postMessage({event: "bcRing", params: ringParams})
                    }
                } else if (event === 'bcAnswerCall') {
                    // console.log('bcAnswerCall', params)
                    if (self.session && params.id === self.id) {
                        self.session.answer()
                    }
                    localStartCall()
                    self.state.inIncoming = false
                    self.state.phone_status = self.status.accepted
                    if (self.session) {
                        setTimeout(() => {
                            localStartCall()
                            self.state.inIncoming = false
                            self.state.phone_status = self.status.accepted
                        }, 500)
                    }

                } else if (event === "bcEndCall") {
                    // console.log("bcEndCall")
                    if (self.session) {
                        self.supressBroadcastChannel = true
                        self.session.terminate()
                    }
                    self.state.phone_status = self.status.ended
                    self.endCall().then()
                } else if (event === 'bcNewTab') {
                    // console.log('bcNewTab', params)
                    self.windows.push(params.id)
                    if (self.session) {
                        const syncParams = self.getJsonCallData()
                        self.bc.postMessage({event: "bcSync", params: syncParams})
                    }
                } else if (event === 'bcCloseTab') {
                    // console.log('bcCloseTab', params)
                    const index = self.windows.indexOf(params.id)
                    if (index > -1) {
                        self.windows.splice(index, 1)
                        if (self.id === self.windows.at(-1)) {
                            self.userAgent.register()
                        }
                    }
                } else if (event === 'bcDtmf') {
                    // console.log('bcDtmf', params)
                    if (self.session) {
                        self.sendDTMF(params.key)
                    }
                } else if (event === 'bcTransfer') {
                    // console.log('bcTransfer', params)
                    if (self.session) {
                        self.session.refer(params.phoneNumber)
                    }
                } else if (event === 'bcForward') {
                    // console.log('bcForward', params)
                    this.state.isCallForwarded = true
                    if (self.session) {
                        this.session.sendDTMF(`${this.attended_transfer_sequence}${params.phoneNumber}#`)
                    }
                } else if (event === 'bcMicrophoneMute') {
                    // console.log('bcMicrophoneMute')
                    if (self.session) {
                        if (params.mute === true) {
                            self.session.mute()
                        } else {
                            self.session.unmute()
                        }
                    }
                    self.state.isMicrophoneMute = params.mute
                } else if (event === 'bcSoundMute') {
                    // console.log('bcSoundMute')
                    self.state.isSoundMute = params.mute
                    self.setIncomingVolume()
                } else if (event === 'bcCancelForward') {
                    // console.log('bcCancelForward')
                    self.state.isCallForwarded = false
                    if (self.session) {
                        self.session.sendDTMF(self.disconnect_call_sequence)
                    }
                } else if (event === 'bcSync') {
                    // console.log('bcSync', params)
                    if (self.state.inCall === false) {
                        self.state.callerId = params.callerId
                        self.state.isPartner = params.isPartner
                        self.state.inCall = true
                        self.state.phone_status = params.phoneStatus
                        self.startCall()
                    }
                } else if (event === 'bcSipSession') {
                    // console.log('bcSipSession', params)
                    const {action} = params
                    if (action === 'push') {
                        self.sipSessions.push(params.id)
                    } else if (action === 'clear') {
                        self.sipSessions = []
                    } else if (action === 'pop') {
                        const index = self.sipSessions.indexOf(params.id);
                        if (index > -1) {
                            self.sipSessions.splice(index, 1);
                        }
                        if (self.sipSessions.length === 0) {
                            self.state.phone_status = self.status.ended
                            self.endCall().then()
                        }
                    }
                } else if (event === 'bcRing') {
                    if (params.id === self.id) self.incomingPlayer.play().catch()
                }
            }
            this.bc.postMessage({event: "bcNewTab", params: {id: this.id}})
        })
    }

    _busPhoneToggleDisplay() {
        this.state.isDisplayLastState = !this.state.isDisplay
        this.toggleDisplay()
    }

    async _busPhoneMakeTransfer(phoneNumber) {
        if (this.session) {
            this.session.refer(phoneNumber)
        } else {
            this.bc.postMessage({event: "bcTransfer", params: {phoneNumber}})
        }
        this.state.phone_status = self.status.ended
        await this.endCall()
    }

    async _busPhoneHangUp() {
        await this._onClickEndCall()
    }

    _busBugReport() {
        const state = JSON.stringify(this.state)
        console.log(`[PHONE]:\n {state: ${state}}\n\nthis:${this}`)
    }

    async _busPhoneMakeForward(phoneNumber, model, id, name) {
        if (this.session) {
            this.session.sendDTMF(`${this.attended_transfer_sequence}${phoneNumber}#`)
        }
        this.bc.postMessage({event: "bcForward", params: {phoneNumber}})
        this.state.isDialingPanel = true
        this.state.isCallForwarded = true
        this.state.isForward = false
        this.state.isContacts = false

        let mask = maskNumber(phoneNumber)
        const displayNumber = this.isMaskCallNumber ? mask : phoneNumber
        const partnerIconUrl = model === 'partner' ? this.computePartnerIconUrl(id) : this.computeUserIconUrl(id)
        if (model !== '' && id !== '') {
            this.state.xTransferPartner = {
                partnerName: name,
                partnerIconUrl: partnerIconUrl,
                phoneNumber,
                displayNumber,
            }
        } else {
            this.state.xTransferInfo = {
                xTransferInfo: displayNumber
            }
        }
    }

    async prepareCall(props) {
        if (!this.state.inCall) {
            if (!this.sipRegistered) {
                this.notify('Not registered to the SIP server!', {title: 'Phone', sticky: false})
                return
            }
            this.state.isContactList = false
            this.state.callPhoneNumber = props.phone
            await this.searchPartner(props.phone)
            this.makeCall(props)
        }
    }

    async setCallStatus(status) {
        const currentCallStatus = this.callStatus[status] ? this.callStatus[status] : this.callStatus.Failed
        this.notify(currentCallStatus.toUpperCase(), {title: 'Phone', sticky: false})
    }

    initUserAgent() {
        const self = this
        if (!self.state.isActive) {
            return
        }

        const {
            sip_user,
            sip_auth_user,
            sip_password,
            phone_sip_proxy,
            phone_sip_protocol,
            phone_websocket,
            phone_stun_server,
            phone_realm,
        } = self.phone_configs

        try {
            self.socket = new JsSIP.WebSocketInterface(phone_websocket)
        } catch (e) {
            console.error(e)
            this.state.isActive = false
            return
        }
        self.socket.via_transport = phone_sip_protocol
        self.configuration = {
            sockets: [self.socket],
            ws_servers: phone_websocket,
            realm: phone_realm,
            display_name: sip_user,
            uri: `sip:${sip_user}@${phone_sip_proxy}`,
            password: sip_password,
            contact_uri: `sip:${sip_user}@${phone_sip_proxy}`,
            register: true,
            stun_server: phone_stun_server,
            ...(this.phone_sip_auth_user_enabled && sip_auth_user ? { authorization_user: sip_auth_user } : {})
        }

        try {
            self.userAgent = new JsSIP.UA(self.configuration)
        } catch (e) {
            console.error('-> ERROR! Agent initialization: ', e)
            this.state.isActive = false
            return
        }

        if (this.trace_sip) {
            JsSIP.debug.enable('JsSIP:*')
        } else {
            JsSIP.debug.disable('JsSIP:*')
        }

        self.userAgent.start()

        self.userAgent.on('registered', function (e) {
            self.sipRegistered = true
            console.log('SIP Registered')
        })

        // HANDLE RTCSession
        self.userAgent.on("newRTCSession", async function ({session}) {
            if (session.direction === "outgoing") {
                session.connection.addEventListener("track", (e) => {
                    const remoteAudio = document.createElement('audio')
                    remoteAudio.srcObject = e.streams[0]
                    remoteAudio.play()
                    self.session = session
                })
            }

            if (session.direction === "incoming") {
                const phoneNumber = session._request.from._uri._user

                if (self.session === null) {
                    self.session = session
                    self.sipSessions.push(self.id)
                    const params = {id: self.id, action: 'push'}
                    self.bc.postMessage({event: 'bcSipSession', params})
                } else {
                    session.terminate()
                    self.getCalls()
                    return
                }
                // console.log('Windows-> ', self.id, self.windows)
                session.on("failed", async function (data) {
                    // console.log('incoming -> failed: ', data)
                    self.incomingPlayer.pause()
                    self.incomingPlayer.currentTime = 0
                    self.state.phone_status = self.status.ended
                    await self.failProcessing(data.cause)
                    const index = self.sipSessions.indexOf(self.id);
                    self.sipSessions.splice(index, 1);
                    const params = {id: self.id, action: 'pop'}
                    self.bc.postMessage({event: 'bcSipSession', params})
                    self.session = null
                    await self.endCall()
                })

                session.on('peerconnection', function (data) {
                    data.peerconnection.addEventListener('addstream', function (e) {
                        const remoteAudio = document.createElement('audio')
                        remoteAudio.srcObject = e.stream
                        remoteAudio.play()
                        self.state.phone_status = self.status.connecting
                    })
                })
                // incoming call here
                session.on("accepted", async function (data) {
                    // console.log('incoming -> accepted: ', data)
                    self.incomingPlayer.pause()
                    self.incomingPlayer.currentTime = 0
                    self.createCallCounter(phoneNumber)
                    self.state.phone_status = self.status.accepted
                    await self.setCallStatus("Answered")
                })
                session.on("ended", async function (data) {
                    // console.log('incoming -> ended: ', data)
                    self.state.phone_status = self.status.ended
                    await self.setCallStatus(data.cause)
                    await self.endCall()
                    self.session = null
                    if (self.supressBroadcastChannel) {
                        self.supressBroadcastChannel = false
                    } else {
                        self.bc.postMessage({event: "bcEndCall"})
                    }
                })

                const xTransferInfo = session._request.headers['X-Transfer-Info']
                self.state.xTransferInfo = xTransferInfo ? xTransferInfo[0].raw : ''

                let xTransferTo = session._request.headers['X-Transfer-To']
                xTransferTo = xTransferTo ? xTransferTo[0].raw : ''
                self.state.xTransferTo = xTransferTo
                if (xTransferTo) {
                    const partner = await self.getPartner(xTransferTo)
                    self.state.xTransferPartner = self.computePartnerData(partner, xTransferTo)
                } else {
                    self.state.xTransferPartner = false
                }

                self.state.isContactList = false


                self.state.callPhoneNumber = phoneNumber
                await self.searchPartner(phoneNumber)

                self.state.isDisplayLastState = self.state.isDisplay

                let answerMode = session._request.headers['Answer-Mode']
                answerMode = answerMode ? answerMode[0].raw : false
                if (answerMode === 'Auto') {
                    // console.log('Auto Answer', answerMode)
                    self._onClickAcceptIncoming()
                    self.state.inIncoming = false
                    self.autoAnswerPlayer.play().then()
                    return
                } else {
                    if (self.id === self.windows.at(-1)) {
                        self.incomingPlayer.play().catch((error) => {
                            console.error('Failed to play local media')
                            console.error(error.message)
                        })
                    }
                }
                try {
                    const callInfo = session._request.headers['Call-Info']
                    const autoAnswer = callInfo ? callInfo[0].raw : ''
                    if (autoAnswer.includes("Answer-After")) {
                        const delay = parseInt(autoAnswer.split('=')[1])
                        setTimeout(() => self._onClickAcceptIncoming(), delay * 1000)
                    }
                } catch (e) {
                    console.log(e)
                }

                self.state.isDisplayLastState = self.state.isDisplay
                if (!self.state.isDisplay) {
                    self.toggleDisplay()
                }
                const params = self.getJsonCallData()
                self.bc.postMessage({event: "bcStartCall", params})

                self.state.inIncoming = true
                self.state.isDialingPanel = true
                self.startCall()
            }
        })
    }

    async failProcessing(cause = null) {
        let sound, microphone = false
        // Check sound permission
        this.testPlayer.play().then(async () => {
            sound = true
            microphone = await this.checkMicrophonePermissions()
            this.failNotify(sound, microphone, cause)
        }).catch(async (e) => {
            microphone = await this.checkMicrophonePermissions()
            this.failNotify(sound, microphone, cause)
        })
    }

    failNotify(sound, microphone, cause) {
        if (sound && microphone) {
            this.notify(cause, {title: 'Failed', sticky: false, type: 'danger'})
        } else {
            let message = `${cause}<br/>Check permission for:`
            message += sound ? '' : '<br/>&emsp; - Sound'
            message += microphone ? '' : '<br/>&emsp; - Microphone'
            this.notification.add(message, {title: 'Phone', sticky: true, type: 'danger', message_is_html: true})
        }
    }

    async checkMicrophonePermissions() {
        if (this.browser === browser.chrome) {
            const permissionStatus = await navigator.permissions.query({name: 'microphone'})
            if (permissionStatus.state === "granted") {
                return true
            }
            // Check microphone permission for Firefox
        } else if (this.browser === browser.firefox) {
            console.log(this.browser)
            try {
                const stream = await navigator.mediaDevices.getUserMedia({video: false, audio: true})
                stream.getTracks().forEach(function (track) {
                    track.stop()
                })
                return true
            } catch (e) {
                console.error(`you got an error: ${e}`)
            }
        }
        return false
    }

    setIncomingVolume() {
        this.incomingPlayer.volume = this.state.isSoundMute ? 0 : this.phone_ring_volume / 100
    }

    getJsonCallData() {
        return {
            id: this.session ? this.id : this.sipSessions[0],
            isPartner: this.state.isPartner,
            phoneStatus: this.state.phone_status,
            callerId: JSON.parse(JSON.stringify(this.state.callerId)),
        }
    }

    makeCall(props) {
        const self = this
        const phoneNumber = props.phone
        self.startCall()

        const syncParams = self.getJsonCallData()
        self.bc.postMessage({event: "bcSync", params: syncParams})
        self.eventHandlers = {
            'connecting': function (data) {
                // console.log('outgoing -> connecting: ', data)
                self.dialPlayer.play()
                self.dialPlayer.loop = true
                self.state.phone_status = self.status.connecting
            },
            'confirmed': function (data) {
                // console.log('outgoing -> confirmed: ', data)
            },
            'accepted': async function (data) {
                // console.log('outgoing -> accepted: ', data)
                self.dialPlayer.pause()
                self.dialPlayer.currentTime = 0
                self.createCallCounter(phoneNumber)
                self.state.phone_status = self.status.accepted
                await self.setCallStatus("Answered")
                const params = self.getJsonCallData()
                self.bc.postMessage({event: "bcAnswerCall", params})
            },
            'ended': async function (data) {
                // console.log('outgoing -> ended: ', data)
                self.dialPlayer.pause()
                self.dialPlayer.currentTime = 0
                self.state.phone_status = self.status.ended
                await self.setCallStatus(data.cause)
                await self.endCall()
                self.session = null
                if (self.supressBroadcastChannel) {
                    self.supressBroadcastChannel = false
                } else {
                    self.bc.postMessage({event: "bcEndCall"})
                }
            },
            'failed': async function (data) {
                // console.log('outgoing -> failed: ', data)
                self.dialPlayer.pause()
                self.dialPlayer.currentTime = 0
                self.state.phone_status = self.status.ended
                await self.failProcessing(data.cause)
                self.session = null
                await self.endCall()
            }
        }

        const options = {
            'eventHandlers': self.eventHandlers,
            'mediaConstraints': {'audio': true, 'video': false}
        }

        self.session = self.userAgent.call(`sip:${phoneNumber}`, options)
    }

    startCall() {
        this.state.inCall = true
        this.state.isDialingPanel = true
        this.state.isContacts = false
        this.state.isFavorites = false
        this.state.isCalls = false
        this.state.isDisplay = true
        this.state.isKeypad = false
        this.bus.trigger('busTraySetState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
    }

    async endCall() {
        this.state.isDisplay = this.state.isDisplayLastState
        this.state.isContactList = false
        this.state.isDialingPanel = false
        this.state.inCall = false
        this.state.inIncoming = false
        this.state.isKeypad = this.lastActiveTab === this.tabs.phone
        this.state.isContacts = this.lastActiveTab === this.tabs.contacts
        this.state.isFavorites = this.lastActiveTab === this.tabs.favorites
        this.state.isCalls = this.lastActiveTab === this.tabs.calls
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCallForwarded = false
        this.state.isMicrophoneMute = false
        this.state.isPartner = false
        this.state.phoneNumber = ''
        this.state.xPhoneInfoDisplay = ''
        this.phoneInput.el.value = this.state.phoneNumber
        this.bus.trigger('busTraySetState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
        this.state.activeTab = this.lastActiveTab
        if (this.lastActiveTab === this.tabs.calls) {
            this.getCalls()
        }
        this.destroyCallCounter()
        this.sipSessions = []
        this.state.xTransferTo = ''
        this.state.xTransferInfo = ''
        this.state.xTransferPartner = false
    }

    async getPartner(phoneNumber) {
        const partner = await this.orm.call("res.partner", 'get_partner_by_number', [phoneNumber])
        return partner.id ? partner : false
    }

    _openPartner(id) {
        if (id) {
            this.action.doAction({
                res_id: id,
                res_model: 'res.partner',
                target: 'current',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            })
        }
    }

    async searchPartner(phoneNumber) {
        const partner = await this.getPartner(phoneNumber)
        if (partner) {
            this.state.isPartner = true
            this.state.callerId = this.computePartnerData(partner, phoneNumber)
        } else {
            this.state.isPartner = false
            const pbxUser = await this.getUser(phoneNumber)
            if (pbxUser) {
                this.state.callerId = this.computeUserData(pbxUser, phoneNumber)
            } else {
                this.state.callerId = {phoneNumber, displayNumber: phoneNumber}
            }
        }
        return partner
    }

    computePartnerData(partner, phoneNumber) {
        let mask = maskNumber(phoneNumber)
        const displayNumber = this.isMaskCallNumber ? mask : phoneNumber
        return {
            partnerId: partner.id,
            partnerName: partner.name,
            partnerIconUrl: this.computePartnerIconUrl(partner.id),
            partnerUrl: this.computePartnerUrl(partner.id),
            phoneNumber,
            displayNumber,
        }
    }

    computePartnerUrl(partnerId) {
        return `/web#id=${partnerId}&model=res.partner&view_type=form`
    }

    computePartnerIconUrl(partnerId) {
        return `/web/image?model=res.partner&field=avatar_128&id=${partnerId}`
    }

    async getUser(phoneNumber) {
        return await this.orm.call("asterisk_plus.user", 'get_user_by_number', [phoneNumber])
    }

    computeUserData(user, phoneNumber) {
        return {
            partnerId: user.id,
            partnerName: user.name,
            partnerIconUrl: this.computeUserIconUrl(user.user[0]),
            phoneNumber: phoneNumber,
            displayNumber: phoneNumber
        }
    }

    computeUserIconUrl(userId) {
        return `/web/image?model=res.users&field=avatar_128&id=${userId}`
    }

    createCallCounter(phoneNumber) {
        const self = this
        self.callDuration = 0
        self.state.callDurationTime = '00:00:00'
        self.callDurationTimerInstance = setInterval(() => {
            self.callDuration += 1
            if (self.state.callerId.phoneNumber === phoneNumber) {
                self.state.callDurationTime = new Date((self.callDuration) * 1000).toISOString().substring(11, 19)
            }
        }, 1000)
    }

    destroyCallCounter() {
        const self = this
        self.state.callDurationTime = ''
        clearInterval(self.callDurationTimerInstance)
    }

    setLastActiveTab() {
        this.lastActiveTab = this.state.activeTab
    }

    toggleDisplay() {
        if (this.state.isActive) {
            this.state.isDisplay = !this.state.isDisplay
            if (this.state.inCall) {
                this.state.isKeypad = false
                this.state.isDialingPanel = true
                this.state.isContacts = false
                this.state.isCalls = false
                this.state.activeTab = this.tabs.phone
                this.bus.trigger('busTraySetState', {isDisplay: this.state.isDisplay, inCall: this.state.inCall})
            } else {
                setFocus(this.phoneInput.el)
            }
        } else {
            this.notify('Missing configs! Check "User / Preferences"!', {sticky: false})
        }
    }

    getCalls() {
        this.bus.trigger('busCallsGetCalls')
    }

    _onClickMakeCall(ev) {
        if (this.state.phoneNumber) {
            if (!this.sipRegistered) {
                this.notify('Not registered to the SIP server!', {title: 'Phone', sticky: false})
                return
            }
            this.state.callPhoneNumber = this.state.phoneNumber.replace(/\(|\)|-| /gm, '')
            this.state.phoneNumber = ''
            this.phoneInput.el.value = this.state.phoneNumber
            this.prepareCall({phone: this.state.callPhoneNumber})
        } else {
            this.notify("The phone call has no number!", {sticky: false})
        }
    }

    _onClickContactCall(phoneNumber) {
        this.prepareCall({phone: phoneNumber})
    }

    _onClickPhone(ev) {
        this.state.activeTab = this.tabs.phone
        this.setLastActiveTab()
        if (this.state.inCall) {
            this.state.isKeypad = false
            this.state.isDialingPanel = true
        } else {
            this.state.isKeypad = true
            this.state.isDialingPanel = false
        }
        this.state.isContacts = false
        this.state.isCalls = false
        this.state.isFavorites = false
        setFocus(this.phoneInput.el)
    }

    _onClickContacts(ev) {
        this.state.activeTab = this.tabs.contacts
        this.setLastActiveTab()
        this.state.isKeypad = false
        this.state.isContacts = true
        this.state.isContactList = false
        this.state.isFavorites = false
        this.state.isCalls = false
        this.state.isDialingPanel = false
    }

    _onClickFavorites(ev) {
        this.state.activeTab = this.tabs.favorites
        this.setLastActiveTab()
        this.state.isKeypad = false
        this.state.isContacts = false
        this.state.isContactList = false
        this.state.isFavorites = true
        this.state.isCalls = false
        this.state.isDialingPanel = false
    }

    _onClickHistory(ev) {
        this.state.activeTab = this.tabs.calls
        this.setLastActiveTab()
        this.state.isKeypad = false
        this.state.isContacts = false
        this.state.isFavorites = false
        this.state.isCalls = true
        this.state.isDialingPanel = false
        this.getCalls()
    }

    _onClickDialingPanel(ev) {
        this.state.activeTab = this.tabs.phone
        this.state.isContacts = false
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = false
        this.state.isDialingPanel = true
    }

    _onClickKeypad(ev) {
        this.state.activeTab = this.tabs.phone
        this.state.isContacts = false
        this.state.isTransfer = false
        this.state.isForward = false
        this.state.isCalls = false
        this.state.isKeypad = true
        this.state.isDialingPanel = false
        setFocus(this.phoneInput.el)
    }

    _onClickTransfer(ev) {
        if (this.state.isTransfer) return
        this.state.isForward = false
        this.state.isKeypad = false
        this.state.isDialingPanel = false
        this.state.isContacts = true
        this.state.isTransfer = true
        this.bus.trigger('busContactSetState', {isTransfer: true})
    }

    _onClickForward(ev) {
        if (this.state.isForward) return
        this.state.isTransfer = false
        this.state.isKeypad = false
        this.state.isDialingPanel = false
        this.state.isForward = true
        this.state.isContacts = true
        this.bus.trigger('busContactSetState', {isForward: true, isContactMode: true})
    }

    _onClickMicrophoneMute(ev) {
        if (this.session) {
            if (this.state.isMicrophoneMute) {
                this.session.unmute()
            } else {
                this.session.mute()
            }
        }
        this.state.isMicrophoneMute = !this.state.isMicrophoneMute
        this.bc.postMessage({event: "bcMicrophoneMute", params: {mute: this.state.isMicrophoneMute}})
    }

    _onClickSoundMute(ev) {
        this.state.isSoundMute = !this.state.isSoundMute
        localStorage.setItem('asterisk_plus_phone_is_sound_mute', `${this.state.isSoundMute}`)
        this.bc.postMessage({event: "bcSoundMute", params: {mute: this.state.isSoundMute}})
        this.setIncomingVolume()
    }


    async _onClickEndCall(ev) {
        if (this.session) {
            this.supressBroadcastChannel = true
            this.session.terminate()
        }
        this.bc.postMessage({event: "bcEndCall"})
        this.state.phone_status = this.status.ended
        await this.endCall()
        if (this.lastActiveTab === this.tabs.phone) {
            setFocus(this.phoneInput.el)
        }
    }

    _onClickAcceptIncoming() {
        if (this.session) {
            this.session.answer()
        }
        const params = this.getJsonCallData()
        this.bc.postMessage({event: "bcAnswerCall", params})
        this.state.phone_status = this.status.accepted
        this.state.inIncoming = false
        this.startCall()
    }

    async _onClickRejectIncoming(ev) {
        if (this.session) {
            this.supressBroadcastChannel = true
            this.session.terminate()
        }
        this.bc.postMessage({event: "bcEndCall"})
        this.state.inIncoming = false
        await this.endCall()
        if (this.lastActiveTab === this.tabs.phone) {
            setFocus(this.phoneInput.el)
        }
    }

    _onClickClose(ev) {
        this.state.isDisplayLastState = !this.state.isDisplay
        this.toggleDisplay()
    }

    _onClickKeypadButton(ev) {
        if (this.state.inCall) {
            if (this.session) {
                this.sendDTMF(ev.target.textContent)
            } else {
                this.bc.postMessage({event: "bcDtmf", params: {key: ev.target.textContent}})
            }
        } else {
            this.state.phoneNumber += ev.target.textContent
            this.phoneInput.el.value = this.state.phoneNumber
        }
        this.phoneInput.el.focus()
    }

    _onClickBackSpace(ev) {
        setFocus(this.phoneInput.el)
        this.state.phoneNumber = this.state.phoneNumber.slice(0, -1)
        this.phoneInput.el.value = this.state.phoneNumber
        if (this.state.isContactList) {
            this.bus.trigger('busContactSearchQuery', {searchQuery: this.phoneInput.el.value})
        }
        if (this.state.phoneNumber === '') this.state.isContactList = false
    }

    sendDTMF(key) {
        const validDTMF = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '#']
        if (validDTMF.includes(key)) {
            dialTone(key)
            this.session.sendDTMF(key)
        }
    }

    _onEnterPhoneNumber(ev) {
        const self = this
        clearTimeout(this.enterPhoneNumberTimer)
        self.enterPhoneNumberTimer = setTimeout(() => {
            if (self.state.inCall) {
                self.sendDTMF(ev.key)
            } else {
                if (ev.key === "Enter") {
                    self._onClickMakeCall()
                } else {
                    self.state.phoneNumber = self.phoneInput.el.value
                    self.state.isContactList = self.state.phoneNumber !== ''
                    self.bus.trigger('busContactSetState', {isContact: true})
                    self.bus.trigger('busContactSearchQuery', {searchQuery: self.phoneInput.el.value})
                }
            }
        }, 400)
    }

    _createPartner() {
        const context = {
            default_phone: this.state.callerId.phoneNumber,
            call_id: this.call_id,
            default_name: `Partner ${this.state.callerId.phoneNumber}`
        }
        this.action.doAction({
            context,
            res_model: 'res.partner',
            target: 'new',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        })
    }

    _cancelForward() {
        this.state.isCallForwarded = false
        if (this.session) {
            this.session.sendDTMF(this.disconnect_call_sequence)
        }
        this.bc.postMessage({event: "bcCancelForward"})
    }
}
