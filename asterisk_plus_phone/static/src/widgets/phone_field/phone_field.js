/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {session} from "@web/session"
import {registry} from "@web/core/registry"

patch(PhoneField.prototype, "asterisk_plus_phone.PhoneField", {
    setup() {
        this._super.apply()
        this.mainPhone = registry.category("main_components").get('mainPhone', null)
    },

    async _onClickCallButton(e) {
        e.preventDefault()
        const [asterisk_user] = await this.env.model.orm.searchRead(
            'asterisk_plus.user',
            [["user", "=", session.uid]],
            ["originate_type"]
        )
        if (this.mainPhone && asterisk_user && asterisk_user.originate_type === 'client') {
            let props = {phone: this.props.record.data[this.props.name]}
            this.mainPhone.props.bus.trigger('busPhoneMakeCall', props)
        } else {
            const {resModel, data} = this.props.record
            const args = [this.props.value, resModel, data.id]
            this.env.model.orm.call("asterisk_plus.server", "originate_call", args, {})
        }
    }
})
