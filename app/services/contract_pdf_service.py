"""
Contract PDF Service

Generates PDF snapshots of signed contracts using WeasyPrint.
Uploads to cloud storage (R2/S3) and returns the document URL.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import logging
import io
from app.core.settings import settings
from app.core.database import mongo

logger = logging.getLogger(__name__)


class ContractPDFService:
    """
    Service for generating and storing contract PDFs.

    Uses WeasyPrint for HTML-to-PDF conversion and uploads
    to Cloudflare R2 for storage.
    """

    def __init__(self):
        self.contracts = mongo.db["contracts"]
        self._s3_client = None

    def _get_s3_client(self):
        """Get or create S3 client for R2 uploads."""
        if self._s3_client is None:
            try:
                import boto3
                self._s3_client = boto3.client(
                    's3',
                    endpoint_url=settings.s3_endpoint_url,
                    aws_access_key_id=settings.s3_access_key_id,
                    aws_secret_access_key=settings.s3_secret_access_key,
                    region_name='auto'
                )
            except Exception as e:
                logger.error(f"Failed to create S3 client: {str(e)}")
                raise
        return self._s3_client

    def _generate_html(self, contract: Dict) -> str:
        """Generate HTML content for the contract PDF."""
        package = contract.get("package_snapshot", {})
        couple = contract.get("couple", {})
        signature = contract.get("signature", {})

        # Format currency
        total = package.get("total_amount", 0)
        currency = package.get("currency", "usd").upper()

        # Format dates
        def format_date(date_val):
            if not date_val:
                return "TBD"
            if isinstance(date_val, str):
                try:
                    date_val = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                except:
                    return date_val
            return date_val.strftime("%B %d, %Y")

        wedding_date = format_date(contract.get("wedding_date"))
        signed_at = format_date(contract.get("signed_at"))

        # Build services list
        services_html = ""
        for service in package.get("services", []):
            if service.get("included"):
                services_html += f"""
                <div class="service-item">
                    <span class="checkmark">✓</span>
                    <div>
                        <strong>{service.get('name', 'Service')}</strong>
                        {f"<br><small>{service.get('description')}</small>" if service.get('description') else ""}
                    </div>
                </div>
                """

        # Build payment schedule
        schedule_html = ""
        for i, payment in enumerate(package.get("payment_schedule", []), 1):
            amount = payment.get("amount") or (total * payment.get("percentage", 0) / 100)
            trigger = payment.get("trigger", "")
            trigger_label = {
                "on_signing": "Due on signing",
                "days_after_signing": f"{payment.get('days_after', 0)} days after signing",
                "days_before_wedding": f"{payment.get('days_before', 0)} days before wedding",
                "fixed_date": "Fixed date"
            }.get(trigger, trigger)

            schedule_html += f"""
            <tr>
                <td>{payment.get('name', f'Payment {i}')}</td>
                <td>{trigger_label}</td>
                <td style="text-align: right;">${amount:,.2f}</td>
            </tr>
            """

        # Build terms section
        terms_html = ""
        if package.get("cancellation_policy"):
            terms_html += f"""
            <div class="term-section">
                <h4>Cancellation Policy</h4>
                <p>{package.get('cancellation_policy')}</p>
            </div>
            """
        if package.get("late_payment_policy"):
            terms_html += f"""
            <div class="term-section">
                <h4>Late Payment Policy</h4>
                <p>{package.get('late_payment_policy')}</p>
            </div>
            """
        if package.get("custom_terms"):
            terms_html += f"""
            <div class="term-section">
                <h4>Additional Terms</h4>
                <p>{package.get('custom_terms')}</p>
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: letter;
                    margin: 1in;
                }}
                body {{
                    font-family: 'Helvetica Neue', Arial, sans-serif;
                    font-size: 11pt;
                    line-height: 1.5;
                    color: #1e293b;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    padding-bottom: 20px;
                    border-bottom: 2px solid #6366f1;
                }}
                .header h1 {{
                    color: #6366f1;
                    margin: 0 0 5px 0;
                    font-size: 24pt;
                }}
                .header p {{
                    color: #64748b;
                    margin: 0;
                }}
                .section {{
                    margin-bottom: 25px;
                }}
                .section h2 {{
                    color: #334155;
                    font-size: 14pt;
                    border-bottom: 1px solid #e2e8f0;
                    padding-bottom: 8px;
                    margin-bottom: 15px;
                }}
                .info-grid {{
                    display: table;
                    width: 100%;
                }}
                .info-row {{
                    display: table-row;
                }}
                .info-label {{
                    display: table-cell;
                    width: 120px;
                    color: #64748b;
                    padding: 4px 0;
                }}
                .info-value {{
                    display: table-cell;
                    font-weight: 500;
                    padding: 4px 0;
                }}
                .total-box {{
                    background: #f8fafc;
                    border: 2px solid #6366f1;
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin: 20px 0;
                }}
                .total-box .label {{
                    color: #64748b;
                    font-size: 10pt;
                    text-transform: uppercase;
                    letter-spacing: 1px;
                }}
                .total-box .amount {{
                    font-size: 28pt;
                    font-weight: bold;
                    color: #1e293b;
                }}
                .service-item {{
                    display: flex;
                    align-items: flex-start;
                    gap: 10px;
                    padding: 8px 0;
                    border-bottom: 1px solid #f1f5f9;
                }}
                .checkmark {{
                    color: #22c55e;
                    font-weight: bold;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                table th, table td {{
                    padding: 10px;
                    text-align: left;
                    border-bottom: 1px solid #e2e8f0;
                }}
                table th {{
                    background: #f8fafc;
                    font-weight: 600;
                    color: #475569;
                }}
                .term-section {{
                    margin-bottom: 15px;
                }}
                .term-section h4 {{
                    color: #475569;
                    margin: 0 0 5px 0;
                    font-size: 11pt;
                }}
                .term-section p {{
                    color: #64748b;
                    margin: 0;
                    font-size: 10pt;
                }}
                .signature-box {{
                    background: #f0fdf4;
                    border: 1px solid #86efac;
                    border-radius: 8px;
                    padding: 20px;
                    margin-top: 30px;
                }}
                .signature-box h3 {{
                    color: #166534;
                    margin: 0 0 15px 0;
                }}
                .signature-name {{
                    font-family: 'Brush Script MT', cursive;
                    font-size: 24pt;
                    color: #1e293b;
                    margin: 10px 0;
                }}
                .signature-meta {{
                    color: #64748b;
                    font-size: 9pt;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e2e8f0;
                    text-align: center;
                    color: #94a3b8;
                    font-size: 9pt;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>{package.get('name', 'Wedding Planning Agreement')}</h1>
                <p>Wedding Planning Agreement</p>
            </div>

            <div class="section">
                <h2>Client Information</h2>
                <div class="info-grid">
                    <div class="info-row">
                        <div class="info-label">Client</div>
                        <div class="info-value">{couple.get('name', 'N/A')}{f" & {couple.get('partner_name')}" if couple.get('partner_name') else ""}</div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Email</div>
                        <div class="info-value">{couple.get('email', 'N/A')}</div>
                    </div>
                    <div class="info-row">
                        <div class="info-label">Wedding Date</div>
                        <div class="info-value">{wedding_date}</div>
                    </div>
                    {f'<div class="info-row"><div class="info-label">Venue</div><div class="info-value">{contract.get("venue")}</div></div>' if contract.get("venue") else ""}
                </div>
            </div>

            <div class="total-box">
                <div class="label">Total Investment</div>
                <div class="amount">${total:,.2f} {currency}</div>
            </div>

            {f'''
            <div class="section">
                <h2>Services Included</h2>
                {services_html}
            </div>
            ''' if services_html else ""}

            {f'''
            <div class="section">
                <h2>Payment Schedule</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Payment</th>
                            <th>Due</th>
                            <th style="text-align: right;">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        {schedule_html}
                    </tbody>
                </table>
            </div>
            ''' if schedule_html else ""}

            {f'''
            <div class="section">
                <h2>Terms & Conditions</h2>
                {terms_html}
            </div>
            ''' if terms_html else ""}

            <div class="signature-box">
                <h3>Digital Signature</h3>
                <div class="signature-name">{signature.get('signed_by', 'N/A')}</div>
                <div class="signature-meta">
                    Signed on {signed_at}
                    {f"<br>IP: {signature.get('ip_address')}" if signature.get('ip_address') else ""}
                </div>
            </div>

            <div class="footer">
                <p>This document was digitally signed and is legally binding.</p>
                <p>Contract ID: {contract.get('id', 'N/A')} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</p>
            </div>
        </body>
        </html>
        """

        return html

    async def generate_pdf(self, contract_id: str) -> Optional[str]:
        """
        Generate PDF for a signed contract and upload to storage.

        Args:
            contract_id: The contract ID

        Returns:
            URL of the uploaded PDF or None if generation failed
        """
        try:
            from bson import ObjectId
            from weasyprint import HTML

            # Get contract data
            contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
            if not contract:
                logger.error(f"Contract not found: {contract_id}")
                return None

            # Serialize for HTML generation
            contract_data = {
                "id": str(contract["_id"]),
                "couple": contract.get("couple", {}),
                "wedding_date": contract.get("wedding_date"),
                "venue": contract.get("venue"),
                "package_snapshot": contract.get("package_snapshot", {}),
                "signature": contract.get("signature", {}),
                "signed_at": contract.get("signed_at"),
                "status": contract.get("status")
            }

            # Generate HTML and convert to PDF
            html_content = self._generate_html(contract_data)
            pdf_bytes = HTML(string=html_content).write_pdf()

            # Upload to S3/R2
            filename = f"contracts/{contract_id}/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_signed.pdf"

            s3 = self._get_s3_client()
            s3.put_object(
                Bucket=settings.s3_bucket_name,
                Key=filename,
                Body=pdf_bytes,
                ContentType='application/pdf'
            )

            # Build the URL
            if settings.media_domain:
                document_url = f"https://{settings.media_domain}/{filename}"
            else:
                document_url = f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{filename}"

            # Update contract with document URL
            await self.contracts.update_one(
                {"_id": ObjectId(contract_id)},
                {
                    "$set": {
                        "document_url": document_url,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )

            logger.info(f"Generated PDF for contract {contract_id}: {document_url}")
            return document_url

        except ImportError:
            # C14: Fallback — store the HTML as a signed document instead of PDF
            logger.warning("WeasyPrint not installed. Falling back to HTML document storage.")
            try:
                from bson import ObjectId

                contract = await self.contracts.find_one({"_id": ObjectId(contract_id)})
                if contract:
                    contract_data = {
                        "id": str(contract["_id"]),
                        "couple": contract.get("couple", {}),
                        "wedding_date": contract.get("wedding_date"),
                        "venue": contract.get("venue"),
                        "package_snapshot": contract.get("package_snapshot", {}),
                        "signature": contract.get("signature", {}),
                        "signed_at": contract.get("signed_at"),
                        "status": contract.get("status")
                    }
                    html_content = self._generate_html(contract_data)
                    html_bytes = html_content.encode("utf-8")

                    filename = f"contracts/{contract_id}/{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_signed.html"
                    s3 = self._get_s3_client()
                    s3.put_object(
                        Bucket=settings.s3_bucket_name,
                        Key=filename,
                        Body=html_bytes,
                        ContentType='text/html'
                    )

                    if settings.media_domain:
                        document_url = f"https://{settings.media_domain}/{filename}"
                    else:
                        document_url = f"{settings.s3_endpoint_url}/{settings.s3_bucket_name}/{filename}"

                    await self.contracts.update_one(
                        {"_id": ObjectId(contract_id)},
                        {"$set": {"document_url": document_url, "updated_at": datetime.now(timezone.utc)}}
                    )
                    logger.info(f"Stored HTML fallback for contract {contract_id}: {document_url}")
                    return document_url
            except Exception as fallback_err:
                logger.error(f"HTML fallback also failed for contract {contract_id}: {str(fallback_err)}")
            return None
        except Exception as e:
            logger.error(f"Failed to generate PDF for contract {contract_id}: {str(e)}")
            return None


# Singleton instance
contract_pdf_service = ContractPDFService()
