def _generate_pdf_especifico(self):
    attach_ids = []
    template_id = self.env.ref('snc_send_email_payslips.mail_template_new_payslip_especifico')

    mapped_reports = self.payslip_run_id.mapped('slip_ids')._get_pdf_reports()

    for report, payslips in mapped_reports.items():
        #for payslip in payslips:
        pdf_content, dummy = report.sudo()._render_qweb_pdf(payslips.ids)
        pdf_name = 'Nóminas unificadas.pdf'

        attachments_vals_list = self.env['ir.attachment'].create({
                'name': pdf_name,
                'type': 'binary',
                'raw': pdf_content,
                'res_model': payslips[0]._name,
                'res_id': payslips[0].id
        })

        if attachments_vals_list:
            attach_ids.append(attachments_vals_list.id)
    template_id.attachment_ids = [(6, 0, attach_ids)]
    template_id.send_mail(self.partner_id.user_id.id, force_send=True)