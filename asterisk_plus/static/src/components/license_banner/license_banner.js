/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class LicenseBanner extends Component {
    static template = "oduist.LicenseBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            visible: false,
            status: null,
            message: "",
            type: "info", // info, warning, danger
        });

        onWillStart(async () => {
            await this.loadLicenseStatus();
        });
    }

    async loadLicenseStatus() {
        try {
            const result = await this.orm.call(
                "oduist.license",
                "get_oduist_license_banner",
                []
            );

            if (result) {
                this.state.visible = true;
                this.state.status = result.status;
                this.state.message = result.message;
                this.state.type = result.type;
            }
        } catch (error) {
            console.error("Failed to load license status:", error);
        }
    }

    get bannerClass() {
        const baseClass = "oduist-license-banner";
        return `${baseClass} ${baseClass}-${this.state.type}`;
    }

    async openSettings() {
        const action = await this.orm.call(
            "oduist.license",
            "open_license_form",
            []
        );
        this.env.services.action.doAction(action);
    }
}

// Register as a systray item to appear in navbar
export const systrayItem = {
    Component: LicenseBanner,
};

registry.category("systray").add("oduist.LicenseBanner", systrayItem, { sequence: 1 });
