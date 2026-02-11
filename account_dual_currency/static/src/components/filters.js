/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { AccountReport } from "@account_reports/components/account_report/account_report";
import { AccountReportFilters } from "@account_reports/components/account_report/filters/filters";

export class AccountReportFiltersDual extends AccountReportFilters {

    setup() {
        super.setup();
        this.controller = useState(this.env.controller);
    }

    async updateDualCurrency(optionKey, optionValue) {
        await this.controller.updateOption(optionKey, optionValue, true);
    }

}

AccountReport.registerCustomComponent(AccountReportFiltersDual);
