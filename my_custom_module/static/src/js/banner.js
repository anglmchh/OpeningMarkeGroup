odoo.define('my_custom_module.banner', function (require) {
    "use strict";

    const { Component } = require('web.Component');
    const session = require('web.session');
    const { _lt } = require('web.core');

    function loadBanner() {
        console.log("Consultando si el banner debe mostrarse...");
        
        // Realizamos la llamada RPC al controlador
        session.rpc('/banner/status')
            .then(function(response) {
                // Verificamos si la respuesta indica que debemos mostrar el banner
                if (response.show_banner) {
                    console.log("El banner debe mostrarse. Creando el banner...");
                    const banner = document.createElement('div');
                    banner.id = 'account_closure_banner';
                    banner.style = 'background: #ffc107; padding: 10px; text-align: center;';
                    banner.innerHTML = `
                        <strong style="display:block; font-size: 16px; margin-bottom: 5px; color: red;">
                            🚨 ${_lt('ADVERTENCIA:')} <span style="color: black; font-weight: bold;">${_lt(response.message)}</span>
                        </strong>
                        <span style="color: #333; font-weight: 600;">
                            ${_lt('Antes de iniciar un nuevo periodo, debe cerrarse correctamente el periodo anterior.')}
                            <br/>
                            ${_lt('Por favor, revise y complete el cierre correspondiente para evitar inconsistencias en los registros.')}
                        </span>
                    `;

                    // Insertamos el banner antes del header
                    const header = document.querySelector("body > header");
                    if (header) {
                        document.body.insertBefore(banner, header);
                    } else {
                        document.body.insertBefore(banner, document.body.firstChild);
                    }
                }
            })
            .catch(function(error) {
                console.error("Error al consultar el estado del banner", error);
            });
    }

    // Llamamos a la función loadBanner cuando el DOM se cargue
    loadBanner();
});
