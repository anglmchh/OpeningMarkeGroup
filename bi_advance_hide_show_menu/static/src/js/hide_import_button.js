/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ImportRecords } from "@base_import/import_records/import_records";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useSubEnv, useState, useRef,useEffect } from "@odoo/owl";
import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";

let import_group = false;

const letListControllerHideButtons = {

    setup() {
    super.setup();
    this.userService = useService('user')
    var def_import = this.userService.hasGroup('bi_advance_hide_show_menu.group_import_btn_access').then(function (has_import_group) {
        if(has_import_group){
            import_group = has_import_group;
            }
            
        });
    }
}

export const patchImportMenuHide = {
    setup() {
        this.action = useService("action");
        if (import_group==true){
            
            this.hasimportmenu=false
        }
        else{
            this.hasimportmenu=true
        }
       
    }
}

patch(ListRenderer.prototype,  letListControllerHideButtons);
patch(ImportRecords.prototype, patchImportMenuHide);

