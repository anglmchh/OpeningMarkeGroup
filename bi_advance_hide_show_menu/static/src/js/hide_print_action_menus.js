/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ImportRecords } from "@base_import/import_records/import_records";
import { useService } from "@web/core/utils/hooks";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";
import { ListRenderer } from "@web/views/list/list_renderer";
import { useSubEnv, useState, useRef,useEffect } from "@odoo/owl";
import { Component,onWillPatch, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { ExportAll } from "@web/views/list/export_all/export_all";
export const STATIC_ACTIONS_GROUP_NUMBER = 1;
export const ACTIONS_GROUP_NUMBER = 100;
import { KanbanRenderer } from '@web/views/kanban/kanban_renderer';
import { FormController } from "@web/views/form/form_controller";
import { ListController } from "@web/views/list/list_controller";
//import { useArchiveEmployee } from "@hr/views/archive_employee_hook";
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import {CogMenu} from "@web/search/cog_menu/cog_menu";
import {
    deleteConfirmationMessage,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
let export_group = false;
let delete_group = false;
let print_group = false;
let duplicate_group = false;
let action_group = false;
let export_group_btn=false;


const letListControllerHideButtons = {

    setup() {
    super.setup();
    this.userService = useService('user')

   
    var def_print = this.userService.hasGroup('bi_advance_hide_show_menu.group_hide_print_btn').then(function (has_print_group) {
        if(has_print_group){
            print_group = has_print_group;
            
        }
        
        });
    

    var def_action = this.userService.hasGroup('bi_advance_hide_show_menu.group_hide_action_btn').then(function (has_action_group) {
        if(has_action_group){
            action_group = has_action_group;
        }
        
        });

    
    var def_export_action = this.userService.hasGroup('bi_advance_hide_show_menu.group_hide_export_action').then(function (has_export_action_group) {
        if(has_export_action_group){
            export_group = has_export_action_group;
        }
        
        });

    var def_export_btn = this.userService.hasGroup('bi_advance_hide_show_menu.group_export_btn_access').then(function (has_export_btn_group) {
        if(has_export_btn_group){
            export_group_btn = has_export_btn_group;
            
        }
        
        });

    var def_delete = this.userService.hasGroup('bi_advance_hide_show_menu.group_hide_delete_action').then(function (has_delete_group) {
        if(has_delete_group){
            delete_group = has_delete_group;
        }
        
        });

    var def_duplicate = this.userService.hasGroup('bi_advance_hide_show_menu.group_hide_duplicate_action').then(function (has_duplicate_group) {
        if(has_duplicate_group){
            duplicate_group = has_duplicate_group;
        }
        
        });

    }
}

export const patchActionMenu = {

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        onWillStart(async () => {
            this.actionItems = [];
            if (action_group == true){
                this.actionItems.length = 0;
            }else{
                this.actionItems = await this.getActionItems(this.props);
            }
            
        });
        onWillUpdateProps(async (nextProps) => {
            this.actionItems = [];

            if (action_group == true){
                this.actionItems.length = 0;

            }else{
                this.actionItems = await this.getActionItems(nextProps);
            }
            
        });
       
    },

    get printItems() {
        const printActions = this.props.items.print || [];
        if(print_group == true){
            printActions.length = 0;
        }
        return printActions.map((action) => ({
            action,
            description: action.name,
            key: action.id,
        }));
    },
} 

patch(FormController.prototype,{

    setup() {
        super.setup()
        this.orm = useService("orm");
        this.user = useService("user");
//        this.archiveEmployee = useArchiveEmployee();

    },

    getStaticActionMenuItems() {
        const { activeActions } = this.archInfo;
        const menuItems = super.getStaticActionMenuItems();
//        menuItems.archive.callback = this.archiveEmployee.bind(this, this.model.root.resId);
        return menuItems;

        if(duplicate_group == true){
            activeActions.duplicate = false
            var dupli = {   
                isAvailable: () => activeActions.create && activeActions.duplicate,
                sequence: 30,
                icon: "fa fa-clone",
                description: _t("Duplicate"),
                callback: () => this.duplicateRecord(),
            
            }
        }
        else{
            var dupli = {   
                isAvailable: () => activeActions.create && activeActions.duplicate,
                sequence: 30,
                icon: "fa fa-clone",
                description: _t("Duplicate"),
                callback: () => this.duplicateRecord(),
            }
        }

        if(delete_group == true){
            activeActions.delete = false
            var del = {   
                isAvailable: () => activeActions.delete && !this.model.root.isNew,
                sequence: 40,
                icon: "fa fa-trash-o",
                description: _t("Delete"),
                callback: () => this.deleteRecord(),
                skipSave: true,
            }
        }
        else{
            var del = {   
                isAvailable: () => activeActions.delete && !this.model.root.isNew,
                sequence: 40,
                icon: "fa fa-trash-o",
                description: _t("Delete"),
                callback: () => this.deleteRecord(),
                skipSave: true,
            }
        }
        return {duplicate : dupli , delete : del}
        
    },
});


patch(CogMenu.prototype,{

    setup() {
        super.setup();
        onWillStart(async () => {
            this.registryItems = await this._registryItems();
        });
        onWillUpdateProps(async () => {
            this.registryItems = await this._registryItems();
        });
    },

    get hasItems() {
        if (action_group == true){
            this.cogItems.length = 0;
        }
        if (print_group == true){
            this.printItems.length = 0;
        }
        return this.cogItems.length || this.printItems.length;
    }
});



function createAction(icon, description, callback, isAvailable) {
  return {
    isAvailable: isAvailable,
    sequence: 40,
    icon: icon,
    description: _t(description),
    callback: callback,
  };
}

patch(ListController.prototype, {
    setup() {
      super.setup();
      this.actionService = useService("action");
      this.userService = useService("user");
    },
  
    getStaticActionMenuItems() {
      const { activeActions } = this.archInfo;
      const list = this.model.root;
      const isM2MGrouped = list.groupBy.some((groupBy) => list.fields[groupBy.split(":")[0]].type === "many2many");
  
      const exp = createAction("fa fa-upload", "Export", () => this.onExportData(), () => this.isExportEnable && !export_group);
      
      const archive = createAction("oi oi-archive", "Archive", () => {
        this.dialogService.add(ConfirmationDialog, this.archiveDialogProps);
      }, () => this.archiveEnabled && !isM2MGrouped);
  
      const unarchive = createAction("oi oi-unarchive", "Unarchive", () => {
        this.toggleArchiveState(false);
      }, () => this.archiveEnabled && !isM2MGrouped);

      const duplicate = createAction("fa fa-clone", "Duplicate", () => this.duplicateRecords(), () => activeActions.duplicate && !isM2MGrouped && !duplicate_group);
      const demo = createAction("fa fa-trash-o", "Delete", () => this.onDeleteSelectedRecords(), () => activeActions.delete && !isM2MGrouped && !delete_group);
  
      return { export: exp, archive, unarchive, duplicate, delete: demo };
    },
});



patch(ListRenderer.prototype,  letListControllerHideButtons);
patch(ActionMenus.prototype, patchActionMenu);

















