"""
Guest Export Service

Generates QR codes for RSVP links, guest list PDFs, and bulk QR code ZIP files.
Used by planners for physical invitations and printable guest lists.
"""

import base64
import logging
import os
import zipfile
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from typing import Dict, List, Optional
from urllib.parse import quote

from app.core.database import mongo

logger = logging.getLogger(__name__)


class GuestExportService:
    """
    Service for exporting guest data in various formats.

    - QR codes linking to RSVP pages
    - PDF guest lists for printing
    - ZIP archives of QR codes for bulk printing
    """

    def __init__(self):
        self.guest_collection = mongo.get_guest_collection()
        self.rsvp_collection = mongo.db["rsvps"]
        self.wedding_collection = mongo.db["weddings"]

    def generate_qr_code(self, url: str, box_size: int = 10, border: int = 4) -> bytes:
        """
        Generate a QR code PNG for a given URL.

        Args:
            url: The URL to encode in the QR code
            box_size: Size of each box in pixels
            border: Border size in boxes

        Returns:
            PNG image bytes
        """
        try:
            from io import BytesIO

            import qrcode  # type: ignore
            from qrcode.constants import ERROR_CORRECT_L  # type: ignore

            qr = qrcode.QRCode(
                version=1,
                error_correction=ERROR_CORRECT_L,
                box_size=box_size,
                border=border,
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, kind="PNG")
            buffer.seek(0)
            return buffer.getvalue()

        except ImportError:
            logger.error(
                "qrcode or pillow not installed. Run: pip install qrcode[pil] pillow"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to generate QR code: {str(e)}")
            raise

    def build_rsvp_url(self, slug: str, token: str) -> str:
        """
        Build the RSVP URL for a guest.

        Args:
            slug: Wedding slug
            token: Guest's unique token

        Returns:
            Full RSVP URL
        """
        frontend_url = (
            os.getenv("FRONTEND_URL") or "https://thespecialwedding.io"
        ).rstrip("/")
        return (
            f"{frontend_url}/otp/verify"
            f"?slug={quote(slug, safe='')}"
            f"&token={quote(token, safe='')}"
        )

    async def get_guest_with_rsvp(self, guest: Dict, rsvp_map: Dict[str, Dict]) -> Dict:
        """
        Combine guest data with their RSVP status.

        Args:
            guest: Guest document
            rsvp_map: Map of guest_id to RSVP data

        Returns:
            Guest dict with RSVP status
        """
        guest_id = str(guest.get("_id", guest.get("id", "")))
        rsvp = rsvp_map.get(guest_id, {})

        attending = rsvp.get("attending", [])
        if attending:
            status = "Attending"
        elif rsvp.get("submitted_at"):
            status = "Declined"
        else:
            status = "Pending"

        return {**guest, "rsvp_status": status, "dietary": rsvp.get("dietary", "")}

    async def generate_guest_list_pdf(
        self, wedding_id: str, wedding_name: str = "Wedding"
    ) -> bytes:
        """
        Generate a PDF of the guest list table.

        Args:
            wedding_id: Wedding ID
            wedding_name: Name to display on the PDF

        Returns:
            PDF file bytes
        """
        try:
            from weasyprint import HTML

            # Fetch all guests for the wedding
            guests = await self.guest_collection.find(
                {"wedding_id": wedding_id}
            ).to_list(length=None)

            # Fetch all RSVPs for the wedding
            rsvps = await self.rsvp_collection.find({"wedding_id": wedding_id}).to_list(
                length=None
            )

            # Create RSVP lookup map
            rsvp_map = {str(r.get("guest_id", "")): r for r in rsvps}

            # Build guest rows with RSVP status
            rows_html = ""
            total = len(guests)
            attending_count = 0
            pending_count = 0
            declined_count = 0

            for guest in sorted(guests, key=lambda g: g.get("name", "").lower()):
                guest_with_rsvp = await self.get_guest_with_rsvp(guest, rsvp_map)

                status = guest_with_rsvp["rsvp_status"]
                if status == "Attending":
                    attending_count += 1
                    status_class = "status-attending"
                elif status == "Declined":
                    declined_count += 1
                    status_class = "status-declined"
                else:
                    pending_count += 1
                    status_class = "status-pending"

                phone = guest.get("phone", "") or "-"
                email = guest.get("email", "") or "-"
                group = guest.get("group_id", "") or "-"
                dietary = guest_with_rsvp.get("dietary", "") or "-"

                rows_html += f"""
                <tr>
                    <td>{guest.get("name", "Unknown")}</td>
                    <td>{phone}</td>
                    <td>{email}</td>
                    <td>{group}</td>
                    <td class="{status_class}">{status}</td>
                    <td>{dietary}</td>
                </tr>
                """

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    @page {{
                        size: letter landscape;
                        margin: 0.5in;
                    }}
                    body {{
                        font-family: 'Helvetica Neue', Arial, sans-serif;
                        font-size: 10pt;
                        line-height: 1.4;
                        color: #1e293b;
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 20px;
                        padding-bottom: 15px;
                        border-bottom: 2px solid #e11d48;
                    }}
                    .header h1 {{
                        color: #e11d48;
                        margin: 0 0 5px 0;
                        font-size: 20pt;
                    }}
                    .header p {{
                        color: #64748b;
                        margin: 0;
                        font-size: 9pt;
                    }}
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                    }}
                    table th, table td {{
                        padding: 8px 10px;
                        text-align: left;
                        border-bottom: 1px solid #e2e8f0;
                    }}
                    table th {{
                        background: #f8fafc;
                        font-weight: 600;
                        color: #475569;
                        font-size: 9pt;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    }}
                    table tr:hover {{
                        background: #f8fafc;
                    }}
                    .status-attending {{
                        color: #16a34a;
                        font-weight: 600;
                    }}
                    .status-declined {{
                        color: #dc2626;
                        font-weight: 600;
                    }}
                    .status-pending {{
                        color: #ca8a04;
                        font-weight: 600;
                    }}
                    .summary {{
                        margin-top: 20px;
                        padding-top: 15px;
                        border-top: 1px solid #e2e8f0;
                        display: flex;
                        justify-content: space-between;
                    }}
                    .summary-item {{
                        text-align: center;
                        padding: 10px 20px;
                        background: #f8fafc;
                        border-radius: 8px;
                    }}
                    .summary-item .number {{
                        font-size: 18pt;
                        font-weight: bold;
                        color: #1e293b;
                    }}
                    .summary-item .label {{
                        font-size: 8pt;
                        color: #64748b;
                        text-transform: uppercase;
                    }}
                    .summary-item.attending .number {{
                        color: #16a34a;
                    }}
                    .summary-item.pending .number {{
                        color: #ca8a04;
                    }}
                    .summary-item.declined .number {{
                        color: #dc2626;
                    }}
                    .footer {{
                        margin-top: 20px;
                        text-align: center;
                        color: #94a3b8;
                        font-size: 8pt;
                    }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>{wedding_name} - Guest List</h1>
                    <p>Generated on {datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")}</p>
                </div>

                <table>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Phone</th>
                            <th>Email</th>
                            <th>Group</th>
                            <th>RSVP Status</th>
                            <th>Dietary</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>

                <div class="summary">
                    <div class="summary-item">
                        <div class="number">{total}</div>
                        <div class="label">Total Guests</div>
                    </div>
                    <div class="summary-item attending">
                        <div class="number">{attending_count}</div>
                        <div class="label">Attending</div>
                    </div>
                    <div class="summary-item pending">
                        <div class="number">{pending_count}</div>
                        <div class="label">Pending</div>
                    </div>
                    <div class="summary-item declined">
                        <div class="number">{declined_count}</div>
                        <div class="label">Declined</div>
                    </div>
                </div>

                <div class="footer">
                    <p>Generated by The Special Wedding</p>
                </div>
            </body>
            </html>
            """

            pdf_bytes = HTML(string=html).write_pdf()
            return pdf_bytes

        except ImportError:
            logger.error("WeasyPrint not installed. Run: pip install weasyprint")
            raise
        except Exception as e:
            logger.error(f"Failed to generate guest list PDF: {str(e)}")
            raise

    async def generate_guests_qr_zip(self, guests: List[Dict], slug: str) -> bytes:
        """
        Generate a ZIP file containing QR codes for multiple guests.

        Args:
            guests: List of guest documents
            slug: Wedding slug for URL generation

        Returns:
            ZIP file bytes
        """
        try:
            buffer = BytesIO()

            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for guest in guests:
                    token = guest.get("token")
                    if not token:
                        logger.warning(
                            f"Guest {guest.get('name')} has no token, skipping"
                        )
                        continue

                    # Build URL and generate QR
                    url = self.build_rsvp_url(slug, token)
                    qr_bytes = self.generate_qr_code(url)

                    # Create safe filename
                    name = guest.get("name", "Unknown")
                    safe_name = "".join(
                        c if c.isalnum() or c in " -_" else "_" for c in name
                    )
                    safe_name = safe_name.replace(" ", "_")[:50]

                    # Add short token suffix for uniqueness
                    filename = f"{safe_name}_{token[:6]}.png"

                    zf.writestr(filename, qr_bytes)

            buffer.seek(0)
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Failed to generate QR ZIP: {str(e)}")
            raise

    async def generate_guest_memories_sign_pdf(
        self,
        *,
        couple_names: str,
        upload_url: str,
        qr_png_bytes: bytes,
        upload_closes_at: Optional[datetime] = None,
    ) -> bytes:
        """
        Generate a printable sign that invites guests to upload photos and videos.

        Args:
            couple_names: Couple names shown on the sign
            upload_url: Active guest memories upload URL
            qr_png_bytes: QR code PNG bytes for the upload URL
            upload_closes_at: Optional close date shown as a reminder on the sign

        Returns:
            PDF bytes for download/printing
        """
        try:
            from weasyprint import HTML

            escaped_couple_names = escape(couple_names or "Wedding")
            escaped_upload_url = escape(upload_url)
            close_label = (
                upload_closes_at.astimezone(timezone.utc).strftime("%B %d, %Y")
                if upload_closes_at
                else "After the celebration"
            )
            qr_base64 = base64.b64encode(qr_png_bytes).decode("ascii")

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    @page {{
                        size: letter portrait;
                        margin: 0.5in;
                    }}
                    body {{
                        margin: 0;
                        font-family: 'Helvetica Neue', Arial, sans-serif;
                        color: #0f172a;
                        background: #f8fafc;
                    }}
                    .poster {{
                        min-height: 9.5in;
                        border: 2px solid #e2e8f0;
                        border-radius: 28px;
                        background:
                            radial-gradient(circle at top left, rgba(99, 102, 241, 0.12), transparent 32%),
                            radial-gradient(circle at bottom right, rgba(225, 29, 72, 0.12), transparent 30%),
                            #ffffff;
                        padding: 34px 34px 28px;
                        box-sizing: border-box;
                    }}
                    .eyebrow {{
                        display: inline-block;
                        padding: 8px 14px;
                        border-radius: 999px;
                        background: rgba(99, 102, 241, 0.09);
                        color: #4338ca;
                        font-size: 11px;
                        font-weight: 700;
                        letter-spacing: 0.18em;
                        text-transform: uppercase;
                    }}
                    h1 {{
                        margin: 20px 0 8px;
                        font-size: 33px;
                        line-height: 1.05;
                        letter-spacing: -0.04em;
                    }}
                    .subhead {{
                        margin: 0;
                        font-size: 16px;
                        line-height: 1.6;
                        color: #475569;
                    }}
                    .names {{
                        margin-top: 18px;
                        font-size: 18px;
                        font-weight: 700;
                        color: #e11d48;
                    }}
                    .grid {{
                        margin-top: 28px;
                        display: table;
                        width: 100%;
                    }}
                    .column {{
                        display: table-cell;
                        vertical-align: top;
                    }}
                    .column.instructions {{
                        padding-right: 26px;
                    }}
                    .step {{
                        margin-bottom: 16px;
                        padding: 16px 18px;
                        border-radius: 18px;
                        background: #f8fafc;
                        border: 1px solid #e2e8f0;
                    }}
                    .step-label {{
                        margin: 0 0 6px;
                        font-size: 11px;
                        font-weight: 700;
                        letter-spacing: 0.16em;
                        text-transform: uppercase;
                        color: #6366f1;
                    }}
                    .step-copy {{
                        margin: 0;
                        font-size: 15px;
                        line-height: 1.5;
                    }}
                    .qr-card {{
                        text-align: center;
                        border-radius: 22px;
                        border: 1px solid #e2e8f0;
                        background: #ffffff;
                        padding: 20px;
                    }}
                    .qr-card img {{
                        width: 245px;
                        height: 245px;
                        object-fit: contain;
                        border-radius: 18px;
                        border: 1px solid #e2e8f0;
                        padding: 14px;
                        background: #ffffff;
                    }}
                    .qr-caption {{
                        margin: 16px 0 8px;
                        font-size: 14px;
                        font-weight: 700;
                        color: #111827;
                    }}
                    .url {{
                        margin: 0;
                        font-size: 11px;
                        line-height: 1.5;
                        color: #64748b;
                        word-break: break-word;
                    }}
                    .footer {{
                        margin-top: 26px;
                        padding-top: 18px;
                        border-top: 1px solid #e2e8f0;
                        font-size: 12px;
                        color: #64748b;
                        display: flex;
                        justify-content: space-between;
                        gap: 16px;
                    }}
                    .footer strong {{
                        color: #0f172a;
                    }}
                </style>
            </head>
            <body>
                <div class="poster">
                    <div class="eyebrow">Guest memories</div>
                    <h1>Share your photos and videos from tonight</h1>
                    <p class="subhead">
                        Help us capture the full celebration. Scan the QR code, enter your name,
                        and upload the moments you catch throughout the event.
                    </p>
                    <p class="names">{escaped_couple_names}</p>

                    <div class="grid">
                        <div class="column instructions">
                            <div class="step">
                                <p class="step-label">Step 1</p>
                                <p class="step-copy">Scan the QR code with your phone camera.</p>
                            </div>
                            <div class="step">
                                <p class="step-label">Step 2</p>
                                <p class="step-copy">Tell us your name so the couple knows who shared each memory.</p>
                            </div>
                            <div class="step">
                                <p class="step-label">Step 3</p>
                                <p class="step-copy">Upload photos or videos from any part of the celebration. If you are not sure which event it belongs to, that is okay.</p>
                            </div>
                        </div>
                        <div class="column">
                            <div class="qr-card">
                                <img src="data:image/png;base64,{qr_base64}" alt="Guest memories upload QR code" />
                                <p class="qr-caption">Scan to upload instantly</p>
                                <p class="url">{escaped_upload_url}</p>
                            </div>
                        </div>
                    </div>

                    <div class="footer">
                        <span><strong>Uploads close:</strong> {escape(close_label)}</span>
                        <span>Powered by The Special Wedding</span>
                    </div>
                </div>
            </body>
            </html>
            """

            return HTML(string=html).write_pdf()
        except ImportError:
            logger.error("WeasyPrint not installed. Run: pip install weasyprint")
            raise
        except Exception as e:
            logger.error(f"Failed to generate guest memories sign PDF: {str(e)}")
            raise

    async def get_single_guest_qr(
        self, guest_id: str, wedding_id: str
    ) -> Optional[tuple]:
        """
        Get QR code for a single guest.

        Args:
            guest_id: Guest ID
            wedding_id: Wedding ID for verification

        Returns:
            Tuple of (qr_bytes, filename) or None if not found
        """
        from bson import ObjectId

        try:
            guest = await self.guest_collection.find_one(
                {"_id": ObjectId(guest_id), "wedding_id": wedding_id}
            )

            if not guest:
                return None

            # Get wedding slug
            wedding = await self.wedding_collection.find_one({"_id": wedding_id})
            if not wedding:
                return None

            slug = wedding.get("slug", "")
            token = guest.get("token", "")

            if not slug or not token:
                return None

            url = self.build_rsvp_url(slug, token)
            qr_bytes = self.generate_qr_code(url)

            # Create filename
            name = guest.get("name", "Unknown")
            safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in name)
            safe_name = safe_name.replace(" ", "_")[:50]
            filename = f"{safe_name}_qr.png"

            return (qr_bytes, filename)

        except Exception as e:
            logger.error(f"Failed to get guest QR: {str(e)}")
            return None


# Singleton instance
guest_export_service = GuestExportService()
