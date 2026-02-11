/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
const { Component, onWillStart, useState } = owl;
import { session } from "@web/session";

class TRM extends Component {
    setup() {
        super.setup(...arguments);
        this.state = useState({ trm: 0 });
        var company_id = session.company_id;
        this.orm = useService('orm');
        onWillStart(async () => {
            var trm = await this.orm.call('res.currency', 'get_trm_systray', [company_id]);
            this.state.trm = trm;
        });
    }

    get trm() {
        return this.state.trm;
    }
    _onClick() {

    }
}

TRM.template = "trm_menu";
export const trmItem = { Component: TRM};

registry.category("systray").add("TRM", trmItem, {sequence: 1});
