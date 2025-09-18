/** @odoo-module **/
import {ConnectActiveCallsPopup} from "@connect/services/active_calls/active_calls_popup"

import {patch} from "@web/core/utils/patch"

patch(ConnectActiveCallsPopup.prototype, {
    _onClickLead(ev, lead) {
        if (lead === false) {
            return
        }
        ev.stopPropagation()
        this.action.doAction({
            res_id: lead[0],
            res_model: 'crm.lead',
            target: 'current',
            type: 'ir.actions.act_window',
            views: [[false, 'form']],
        })
    }
})
