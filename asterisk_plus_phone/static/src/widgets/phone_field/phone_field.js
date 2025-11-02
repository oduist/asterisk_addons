/** @odoo-module **/
import basic_fields from 'web.basic_fields'
import {registry} from "@web/core/registry"
import {uid} from "web.session"

const Phone = basic_fields.FieldPhone

Phone.include({

    init() {
        this._super.apply(this, arguments)
        this.enableCall = 'enable_call' in this.attrs.options ? this.attrs.options.enable_call : true
        this.attrs.options.enable_call = this.enableCall
        this.mainPhone = registry.category("main_components").get('mainPhone', null)
    },

    _onClickPhone: async function (ev) {
        ev.preventDefault()
        ev.stopPropagation()

        const [asterisk_user] = await this._rpc({
            model: 'asterisk_plus.user',
            method: 'search_read',
            args: [[["user", "=", uid]], ['id', 'originate_type']],
        })

        if (this.mainPhone && asterisk_user && asterisk_user.originate_type === 'client') {
            let props = {phone: this.value}
            this.mainPhone.props.bus.trigger('busPhoneMakeCall', props)
        } else {
            return this._rpc({
                model: 'asterisk_plus.server',
                method: 'originate_call',
                args: [this.value, this.model, parseInt(this.res_id)],
            })
        }
    },

})
