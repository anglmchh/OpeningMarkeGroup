/** @odoo-module **/

import { session } from 'web.session'; // Uso correcto de la importación

(function() {
    // Array de selectores a ocultar
    const selectors = [
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > button",
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > div",
        "body > div.o_action_manager > div > div > div.o_control_panel.d-flex.flex-column.gap-3.gap-lg-1.px-3.pt-2.pb-3 > div > div.o_control_panel_breadcrumbs.d-flex.align-items-center.gap-1.order-0.h-lg-100 > div.o_breadcrumb.d-flex.flex-row.flex-md-column.align-self-stretch.justify-content-between.min-w-0 > div > div.o_control_panel_breadcrumbs_actions.d-inline-flex > div > div > div > span.dropdown-item.text-truncate.o_menu_item.focus"
    ];

    // Función que oculta los elementos que coinciden con los selectores
    function hideActionButtons() {
        selectors.forEach(selector => {
            const element = document.querySelector(selector);
            if (element) {
                console.log(`[ConditionalActions] Ocultando elemento con selector "${selector}"`);
                element.style.display = "none";
            } else {
                console.log(`[ConditionalActions] No se encontró elemento con selector "${selector}"`);
            }
        });
    }

    // Esperar a que el DOM esté listo y verificar el grupo del usuario
    document.addEventListener("DOMContentLoaded", function() {
        session.user_has_group('conditional_invoice_actions.group_enable_action_button').then(function(userHasGroup) {
            console.log("[ConditionalActions] Resultado de user_has_group:", userHasGroup);
            if (!userHasGroup) {
                console.log("[ConditionalActions] Usuario NO autorizado: ocultando botones de acciones.");
                hideActionButtons();
                // Configurar un MutationObserver para detectar cambios en el DOM
                const observer = new MutationObserver(() => {
                    hideActionButtons();
                });
                observer.observe(document.body, { childList: true, subtree: true });
            } else {
                console.log("[ConditionalActions] Usuario autorizado: se mostrará el botón de acciones.");
            }
        });
    });
})();
