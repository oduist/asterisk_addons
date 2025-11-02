/** @odoo-module **/
"use strict"

import {patch} from "@web/core/utils/patch"
import {PhoneField} from "@web/views/fields/phone/phone_field"
import {session} from "@web/session"
import {registry} from "@web/core/registry"

patch(PhoneField.prototype, {
    setup() {
        super.setup()
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
            super._onClickCallButton(e)
        }
    }
})
