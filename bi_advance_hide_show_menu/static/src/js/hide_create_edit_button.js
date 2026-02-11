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
import { ExportAll } from "@web/views/list/export_all/export_all";
export const STATIC_ACTIONS_GROUP_NUMBER = 1;
export const ACTIONS_GROUP_NUMBER = 100;
import { KanbanRenderer } from '@web/views/kanban/kanban_renderer';
import { FormController } from "@web/views/form/form_controller";

let create_group = false;
let export_group = false;
let edit_group = false;
let admin_group = false;
let export_group_btn = false;


const letListControllerHideButtons = {

    setup() {
    super.setup();
    this.userService = useService('user')

  
    var def_export_btn = this.userService.hasGroup('bi_advance_hide_show_menu.group_export_btn_access').then(function (has_export_btn_group) {
        if(has_export_btn_group){
            export_group_btn = has_export_btn_group;
        }
      
        });

    var def_usergroup = this.userService.hasGroup('base.group_system').then(function (has_duplicate_group) {
        if(has_duplicate_group){
            admin_group = has_duplicate_group;

            }
           
            });
    }
}

export const patchImportMenuHide = {
    setup() {
        this.action = useService("action");
        if (export_group_btn==true){
            this.hasimportmenu=false
        }
        else{
            this.hasimportmenu=true
        }
       
    }
}

patch(ListRenderer.prototype,  letListControllerHideButtons);
patch(ExportAll.prototype, patchImportMenuHide);
