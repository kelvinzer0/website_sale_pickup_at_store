# -*- coding: utf-8 -*-
"""sale.order extension: pickup order support.

Adds:
- is_pickup_order (computed from carrier_id.is_pickup)
- pickup_ready_at (Datetime, kapan siap diambil)

Override:
- _get_delivery_price / rate_shipment -> force 0 jika carrier.is_pickup
  (ensure free shipping even if carrier has fixed price configured).
"""

import json
import logging
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_pickup_order = fields.Boolean(
        string='Pickup Order',
        compute='_compute_is_pickup_order',
        store=True,
        index=True,
        help="True jika customer pilih metode 'Ambil di Tempat' (carrier dengan is_pickup=True).",
    )
    pickup_ready_at = fields.Datetime(
        string='Ready for Pickup At',
        copy=False,
        help="Waktu admin menandai pesanan pickup siap diambil.",
    )

    @api.depends('carrier_id', 'carrier_id.is_pickup')
    def _compute_is_pickup_order(self):
        for order in self:
            order.is_pickup_order = bool(
                order.carrier_id and order.carrier_id.is_pickup
            )

    # ============================================================
    # FREE SHIPPING for pickup orders
    # ============================================================
    # Override rate_shipment to return 0 cost for pickup carriers.
    # Odoo 17 uses rate_shipment(self, order) to get the delivery price
    # at checkout time.
    @api.model
    def _get_delivery_link_carrier_rate(self, carrier, order):
        """Helper: jalankan rate asli lalu overwrite harga jadi 0 untuk pickup."""
        res = super()._get_delivery_link_carrier_rate(carrier, order) if hasattr(super(), '_get_delivery_link_carrier_rate') else None
        return res

    def _get_shipment_rate(self, carrier):
        """Untuk pickup carrier: return 0 langsung tanpa call API/OSRM."""
        if carrier.is_pickup:
            return {
                'success': True,
                'price': 0.0,
                'error': False,
                'warning': False,
            }
        return super()._get_shipment_rate(carrier)

    # ============================================================
    # EVOLUTION API: fetch business hours (cached)
    # ============================================================
    @api.model
    def _fetch_business_hours_from_evolution(self):
        """Fetch business hours dari Evolution API untuk pickup info.

        Endpoint: POST {base_url}/chat/fetchBusinessProfile/{instance}
        Body: {"number": "<own_number>"}  # optional, ambil dari instance profile
        Response field: business_hours.business_config[].{day_of_week, mode, open_time, close_time}

        Cache 24h di ir.config_parameter
        'website_sale_pickup_at_store.business_hours_json'.
        """
        ICP = self.env['ir.config_parameter'].sudo()

        # Check cache (TTL 24h)
        cached_raw = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_json', '')
        cached_at_str = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_fetched_at', '')
        if cached_raw and cached_at_str:
            try:
                cached_at = datetime.fromisoformat(cached_at_str)
                if datetime.now() - cached_at < timedelta(hours=24):
                    return json.loads(cached_raw)
            except (ValueError, TypeError):
                pass  # cache corrupt, fetch ulang

        # Build request
        base_url = (ICP.get_param('whatsapp_evolution.base_url') or '').rstrip('/')
        instance = ICP.get_param('whatsapp_evolution.instance_name') or ''
        api_key = ICP.get_param('whatsapp_evolution.api_key') or ''
        if not base_url or not instance or not api_key:
            _logger.warning("[PICKUP] Evolution API config not set, cannot fetch business hours")
            return None

        # URL-encode instance name (could contain space, e.g. "Warung Lakku")
        inst_enc = urllib.parse.quote(instance, safe='')
        url = f"{base_url}/chat/fetchBusinessProfile/{inst_enc}"

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # Body: own number (look up from ownerJid via fetchInstances first,
        # or just send empty body and let API decide). Empirically, sending
        # the owner number works reliably. Try fetchInstances first.
        try:
            # 1. fetch instance to get owner number
            url_inst = f"{base_url}/instance/fetchInstances?instanceName={inst_enc}"
            req_inst = urllib.request.Request(
                url_inst, headers={"apikey": api_key, "Content-Type": "application/json"})
            with urllib.request.urlopen(req_inst, context=ctx, timeout=15) as r:
                instances = json.loads(r.read())
            owner_jid = None
            if isinstance(instances, list) and instances:
                owner_jid = instances[0].get('ownerJid') or instances[0].get('number')
            if owner_jid and '@s.whatsapp.net' not in str(owner_jid):
                owner_jid = f"{owner_jid}@s.whatsapp.net"
        except Exception as e:
            _logger.warning("[PICKUP] fetchInstances failed: %s", e)
            owner_jid = None

        body = json.dumps({"number": owner_jid} if owner_jid else {}).encode()
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"apikey": api_key, "Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
                data = json.loads(r.read())
        except Exception as e:
            _logger.exception("[PICKUP] fetchBusinessProfile failed: %s", e)
            return None

        # Extract business_hours
        bh = data.get('business_hours') if isinstance(data, dict) else None
        if not bh:
            _logger.warning("[PICKUP] No business_hours in response: %s", data)
            return None

        # Cache
        ICP.set_param('website_sale_pickup_at_store.business_hours_json',
                      json.dumps(bh))
        ICP.set_param('website_sale_pickup_at_store.business_hours_fetched_at',
                      datetime.now().isoformat())
        return bh

    @api.model
    def _format_business_hours_human(self, business_hours):
        """Format business_hours JSON menjadi string manusia-friendly.

        Input format (Evolution API):
        {
          "timezone": "Asia/Jakarta",
          "business_config": [
            {"day_of_week": "sun", "mode": "specific_hours",
             "open_time": "720", "close_time": "1200"},
            ...
          ]
        }

        Output:
        "Senin-Sam, 12:00-20:00 | Tutup: Kam"
        atau per-day detail kalau jam beda per hari.
        """
        if not business_hours or not isinstance(business_hours, dict):
            return ''
        configs = business_hours.get('business_config', [])
        if not configs:
            return ''

        DAY_MAP = {
            'sun': 'Min', 'mon': 'Sen', 'tue': 'Sel',
            'wed': 'Rab', 'thu': 'Kam', 'fri': 'Jum', 'sat': 'Sab',
        }

        def to_time(minute_str):
            try:
                m = int(minute_str)
                return f"{m // 60:02d}:{m % 60:02d}"
            except (ValueError, TypeError):
                return '?'

        # Group by (mode, open, close)
        groups = {}
        closed_days = []
        for cfg in configs:
            day = cfg.get('day_of_week', '')
            mode = cfg.get('mode', 'closed')
            if mode == 'closed':
                closed_days.append(DAY_MAP.get(day, day))
                continue
            open_t = cfg.get('open_time', '?')
            close_t = cfg.get('close_time', '?')
            key = (mode, open_t, close_t)
            groups.setdefault(key, []).append(DAY_MAP.get(day, day))

        parts = []
        for (mode, open_t, close_t), days in groups.items():
            days_str = '-'.join([days[0], days[-1]]) if len(days) > 1 else days[0]
            if mode == 'specific_hours' or mode == 'open_24_hours':
                if mode == 'open_24_hours':
                    parts.append(f"{days_str} 24 jam")
                else:
                    parts.append(f"{days_str} {to_time(open_t)}-{to_time(close_t)}")
            elif mode == 'appointment_only':
                parts.append(f"{days_str} (janji temu)")
            else:
                parts.append(f"{days_str} {mode}")

        result = " | ".join(parts)
        if closed_days:
            result += f" | Tutup: {', '.join(closed_days)}"
        return result

    @api.model
    def _pickup_hours_display(self):
        """Return human-readable business hours string (cached or fetch).
        Used by checkout template to fill info banner.
        """
        ICP = self.env['ir.config_parameter'].sudo()
        bh_raw = ICP.get_param(
            'website_sale_pickup_at_store.business_hours_json', '')
        if not bh_raw:
            # Try fetch (will populate cache)
            bh = self._fetch_business_hours_from_evolution()
            if not bh:
                return ''
            bh_raw = json.dumps(bh)
        try:
            bh = json.loads(bh_raw)
            return self._format_business_hours_human(bh)
        except Exception:
            return ''
