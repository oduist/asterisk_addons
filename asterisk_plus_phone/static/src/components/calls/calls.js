/** @odoo-module **/

import {useService} from "@web/core/utils/hooks"
import {uid} from "web.session"
import {maskNumber} from "@asterisk_plus_phone/js/utils"

const {Component, useState} = owl
const {onWillStart} = owl.hooks

class CallDetail extends Component {
    static template = 'asterisk_plus_phone.call_detail'

    constructor() {
        super(...arguments)
        this.state = useState({
            call: this.props.call,
        })
        this.isMaskCallNumber = false
    }

    setup() {
        super.setup()
        this.orm = useService('orm')
        this.action = useService('action')
        this.user = uid
    }

    async _createPartner() {
        if (this.state.call.partner) {
            this.action.doAction({
                res_id: this.state.call.partner[0],
                res_model: "res.partner",
                target: 'new',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            })
        } else {
            let context = {
                call_id: this.state.call.id,
                default_phone: this.state.call.caller_number,
                default_name: `Partner ${this.state.call.display_caller_number}`
            }
            this.action.doAction({
                context,
                res_model: 'res.partner',
                target: 'new',
                type: 'ir.actions.act_window',
                views: [[false, 'form']],
            })
        }
    }

    _OpenInCallHistory() {
        this.action.doAction({
            res_id: this.state.call.id,
            res_model: 'asterisk_plus.call',
            target: 'new',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        })
    }
}

export class Calls extends Component {
    static template = 'asterisk_plus_phone.calls'
    static components = {CallDetail}

    constructor() {
        super(...arguments)
        this.bus = this.props.bus
    }

    setup() {
        super.setup()
        this.orm = useService('orm')
        this.action = useService('action')
        this.notification = useService('notification')
        this.user = uid
        this.favorites = []
        this.isMaskCallNumber = false
        this.state = useState({
            calls: [],
            call: null,
        })

        onWillStart(async () => {
            this.bus.on('busCallsGetCalls', this, this._getCalls)
            this.bus.on('busCallsGetFavorites', this, this._getFavorites)
            this.bus.on('busBugReport', this, this._busBugReport)
            await this._getFavorites()
            this.isMaskCallNumber = await this.orm.call('asterisk_plus.user', 'get_param', ['mask_call_number'])
        })
    }

    async _getCalls() {
        this.state.calls = []
        const domain = ["|", ["calling_user", "=", this.user], ["called_users", "=", this.user]]
        const records = await this.orm.call("asterisk_plus.call", "get_widget_calls", [domain, 20])
        for (const item of records) {
            const call_number = item.calling_user[0] === this.user ? item.called_number : item.calling_number
            item.direction = item.calling_user[0] === this.user ? 'out' : 'in'
            item.caller_number = call_number
            item.display_caller_number = this.isMaskCallNumber ? maskNumber(call_number) : call_number
            item.favorite = this.favorites.includes(call_number)
            const local_time = new Date(`${item.started} UTC`).toLocaleTimeString("en-GB")
            item.started = `${item.started.split(' ')[0]} ${local_time}`
        }
        this.state.calls = records
    }

    async _getFavorites() {
        this.favorites = []
        const favorites = await this.orm.searchRead('asterisk_plus_phone.favorite', [], ['phone_number'])
        favorites.forEach((el) => this.favorites.push(el.phone_number))
        this.state.calls.forEach(item => {
            const call_number = item.calling_user[0] === this.user ? item.called_number : item.calling_number
            item.display_caller_number = this.isMaskCallNumber ? maskNumber(call_number) : call_number
            item.favorite = this.favorites.includes(call_number)
        })
    }

    _busBugReport() {
        const state = JSON.stringify(this.state)
        console.log(`[CALLS]:\n {state: ${state}}`)
    }

    _onClickContactCall(phoneNumber) {
        this.bus.trigger('busPhoneMakeCall', {phone: phoneNumber})
    }

    async _onClickFavorite(call) {
        const kwargs = {}
        const isCalling = call.calling_user[0] === this.user
        kwargs.phone_number = isCalling ? call.called_number : call.calling_number
        if (call.partner) {
            kwargs.partner = call.partner[0]
        } else {
            if (call.calling_user && isCalling) {
                kwargs.user = call.called_users[0]
            } else if (call.called_users.length > 0 && !isCalling) {
                kwargs.user = call.calling_user[0]
            } else {
                kwargs.name = kwargs.phone_number
            }
        }

        const domain = [["phone_number", "=", kwargs.phone_number]]
        const favorite = await this.orm.search('asterisk_plus_phone.favorite', domain)

        if (favorite.length === 0) {
            await this.orm.create('asterisk_plus_phone.favorite', kwargs)
            this.notification.add('Added to Favorite!', {title: 'Phone', type: 'info'})
            await this._getFavorites()
        } else {
            await this.orm.unlink("asterisk_plus_phone.favorite", favorite, {})
            await this._getFavorites()
            this.notification.add('Removed from Favorite!', {title: 'Phone', type: 'info'})
        }
    }

    _openDetail(call) {
        this.state.call = call
    }

    _closeCallDetail() {
        this.state.call = null
        this._getCalls()
    }
}
