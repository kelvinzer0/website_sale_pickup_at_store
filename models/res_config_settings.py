# -*- coding: utf-8 -*-
"""Settings: konfigurasi Pickup At Store.

Akses: Settings > Website > Pickup At Store
"""

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Field Text TIDAK boleh pakai config_parameter= (Odoo 17
    # _get_classified_fields hanya menerima boolean/integer/float/char/
    # selection/many2one/datetime). Persistence manual di get/set_values.
    pickup_store_address = fields.Text(
        string='Pickup Store Address',
        help='Alamat toko untuk pickup. Default = alamat company utama.',
    )
    pickup_business_hours_display = fields.Text(
        string='Business Hours (fetched from Evolution API)',
        readonly=True,
        help='Jam buka toko hasil fetch dari Evolution API. '
             'Cache 24 jam. Klik Refresh untuk update.',
    )
    pickup_business_hours_fetched_at = fields.Char(
        string='Business Hours Last Fetched At',
        readonly=True,
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICP = self.env['ir.config_parameter'].sudo()
        # Default alamat = company address
        company = self.env.company
        default_addr = ''
        if company and company.partner_id:
            p = company.partner_id
            parts = []
            if p.street: parts.append(p.street)
            if p.street2: parts.append(p.street2)
            if p.city: parts.append(p.city)
            if p.zip: parts.append(p.zip)
            if p.state_id: parts.append(p.state_id.name)
            default_addr = ', '.join(parts)
        addr = ICP.get_param('website_sale_pickup_at_store.store_address', '') or default_addr
        bh_raw = ICP.get_param('website_sale_pickup_at_store.business_hours_json', '')
        bh_fetched = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_fetched_at', '')
        # Format human-readable
        bh_display = ''
        if bh_raw:
            try:
                import json
                bh = json.loads(bh_raw)
                bh_display = self.env['sale.order']._format_business_hours_human(bh)
            except Exception:
                bh_display = '(gagal parse)'
        res.update(
            pickup_store_address=addr,
            pickup_business_hours_display=bh_display,
            pickup_business_hours_fetched_at=bh_fetched,
        )
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICP = self.env['ir.config_parameter'].sudo()
        ICP.set_param('website_sale_pickup_at_store.store_address',
                      self.pickup_store_address or '')

    def action_refresh_business_hours(self):
        """Fetch business hours dari Evolution API (manual refresh)."""
        self.ensure_one()
        bh = self.env['sale.order']._fetch_business_hours_from_evolution()
        if bh:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Berhasil',
                    'message': 'Jam buka berhasil di-refresh dari Evolution API.',
                    'type': 'success',
                    'sticky': False,
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Gagal',
                'message': 'Tidak bisa fetch jam buka. Cek konfigurasi Evolution API di menu WhatsApp Evolution API Settings.',
                'type': 'danger',
                'sticky': True,
            },
        }
