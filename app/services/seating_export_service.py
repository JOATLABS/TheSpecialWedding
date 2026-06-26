"""
Seating Chart PDF Export Service

Generates printable PDF seating charts with visual floor plan layout
for wedding venue display.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.database import mongo

logger = logging.getLogger(__name__)


class SeatingExportService:
    """Service for generating seating chart PDF exports."""

    def __init__(self):
        self.tables_collection = mongo.db["tables"]
        self.guests_collection = mongo.db["guests"]
        self.layouts_collection = mongo.db["seating_layouts"]

    async def generate_seating_chart_pdf(
        self,
        wedding_id: str,
        wedding_name: str = "Wedding",
        layout_style: str = "visual",
        paper_size: str = "poster",
    ) -> bytes:
        """
        Generate a printable seating chart PDF.

        Args:
            wedding_id: The wedding ID to generate chart for
            wedding_name: Display name for the wedding (couple names)
            layout_style: "visual" for floor plan, "list" for table-by-table list
            paper_size: "poster" (24x18) or "tabloid" (11x17)

        Returns:
            PDF file as bytes
        """
        try:
            from weasyprint import HTML
        except ImportError:
            logger.error("WeasyPrint not installed. Run: pip install weasyprint")
            raise

        # Fetch tables for wedding
        tables = await self.tables_collection.find({"wedding_id": wedding_id}).to_list(
            length=None
        )

        # Fetch guests for wedding
        guests = await self.guests_collection.find({"wedding_id": wedding_id}).to_list(
            length=None
        )
        seating_layout = await self.layouts_collection.find_one(
            {"wedding_id": wedding_id}
        )

        # Build guest lookup by table_id (T5: normalize ObjectId → string consistently)
        guests_by_table: Dict[str, List[dict]] = {}
        unseated_guests: List[dict] = []

        for guest in guests:
            table_id = guest.get("table_id")
            if table_id:
                # Normalize to string — table_id may be stored as ObjectId or string
                table_id_str = str(table_id)
                if table_id_str not in guests_by_table:
                    guests_by_table[table_id_str] = []
                guests_by_table[table_id_str].append(guest)
            else:
                unseated_guests.append(guest)

        # Also index by string _id for tables (some guests may reference table by _id string)
        # This ensures guests stored with ObjectId("abc") match table _id ObjectId("abc")
        # since both are converted via str()

        # Generate HTML based on layout style
        if layout_style == "visual":
            html = self._generate_visual_layout(
                tables,
                guests_by_table,
                unseated_guests,
                wedding_name,
                paper_size,
                seating_layout,
            )
        else:
            html = self._generate_list_layout(
                tables, guests_by_table, unseated_guests, wedding_name, paper_size
            )

        # Convert to PDF
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes

    def _generate_visual_layout(
        self,
        tables: List[dict],
        guests_by_table: Dict[str, List[dict]],
        unseated_guests: List[dict],
        wedding_name: str,
        paper_size: str = "poster",
        seating_layout: Optional[dict] = None,
    ) -> str:
        """Generate visual floor plan layout with positioned tables."""

        # Paper size configuration
        page_sizes = {"poster": "24in 18in landscape", "tabloid": "11in 17in landscape"}
        font_scales = {
            "poster": {
                "title": "36pt",
                "table": "14pt",
                "guest": "10pt",
                "small": "8pt",
            },
            "tabloid": {
                "title": "24pt",
                "table": "11pt",
                "guest": "8pt",
                "small": "7pt",
            },
        }
        page_size = page_sizes.get(paper_size, page_sizes["poster"])
        fonts = font_scales.get(paper_size, font_scales["poster"])

        # Calculate canvas bounds from the venue outline and table positions.
        layout_width = int((seating_layout or {}).get("canvas_width", 800))
        layout_height = int((seating_layout or {}).get("canvas_height", 600))
        if tables:
            max_x = max((t.get("x", 0) + 180 for t in tables), default=800)
            max_y = max((t.get("y", 0) + 180 for t in tables), default=600)
        else:
            max_x, max_y = 800, 600
        max_x = max(max_x, layout_width)
        max_y = max(max_y, layout_height)

        # Scale factor for tabloid size
        scale = 0.5 if paper_size == "tabloid" else 1.0

        floor_plan_html = self._render_floor_plan_layers(
            seating_layout, max_x, max_y, scale
        )

        # Generate table cards
        tables_html = ""
        for table in sorted(tables, key=lambda t: t.get("name", "")):
            table_id = str(table.get("_id", ""))
            table_guests = guests_by_table.get(table_id, [])
            tables_html += self._render_table_card(table, table_guests, fonts, scale)

        # Build complete HTML
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: {page_size};
            margin: 0.5in;
        }}
        * {{
            box-sizing: border-box;
        }}
        body {{
            font-family: 'Georgia', 'Times New Roman', serif;
            margin: 0;
            padding: 0;
            color: #1e293b;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 3px solid #d4af37;
        }}
        .header h1 {{
            color: #1e3a5f;
            font-size: {fonts["title"]};
            margin: 0 0 8px 0;
            font-weight: normal;
            letter-spacing: 2px;
        }}
        .header .subtitle {{
            color: #64748b;
            font-size: {fonts["table"]};
            font-style: italic;
        }}
        .canvas {{
            position: relative;
            width: {int((max_x + 100) * scale)}px;
            height: {int((max_y + 100) * scale)}px;
            margin: 0 auto;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            overflow: visible;
        }}
        .floor-plan {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
        }}
        .floor-plan-image {{
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            opacity: 0.34;
            pointer-events: none;
        }}
        .fixture-card {{
            position: absolute;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px dashed #60a5fa;
            border-radius: 8px;
            background: rgba(239, 246, 255, 0.74);
            color: #1e40af;
            font-family: 'Helvetica Neue', Arial, sans-serif;
            font-size: {fonts["small"]};
            font-weight: 700;
            text-align: center;
            padding: 4px 8px;
        }}
        .table-card {{
            position: absolute;
            text-align: center;
            background: white;
            border: 2px solid #d4af37;
            padding: 12px 15px;
            min-width: {int(130 * scale)}px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        }}
        .table-card.round {{
            border-radius: 50%;
            min-height: {int(130 * scale)}px;
        }}
        .table-card.rectangle {{
            border-radius: 8px;
        }}
        .table-name {{
            font-weight: bold;
            color: #1e3a5f;
            font-size: {fonts["table"]};
            margin-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 6px;
        }}
        .guest-list {{
            font-size: {fonts["guest"]};
            color: #475569;
            line-height: 1.4;
        }}
        .guest-name {{
            margin: 3px 0;
        }}
        .capacity-info {{
            font-size: {fonts["small"]};
            color: #94a3b8;
            margin-top: 8px;
            font-style: italic;
        }}
        .unseated-section {{
            margin-top: 40px;
            padding: 20px 25px;
            background: #fef2f2;
            border: 1px solid #fecaca;
            border-radius: 8px;
        }}
        .unseated-section h3 {{
            color: #dc2626;
            font-size: {fonts["table"]};
            margin: 0 0 12px 0;
        }}
        .unseated-section p {{
            color: #7f1d1d;
            font-size: {fonts["guest"]};
            line-height: 1.6;
            margin: 0;
        }}
        .summary {{
            margin-top: 30px;
            text-align: center;
            padding: 15px;
            background: #f8fafc;
            border-radius: 8px;
        }}
        .summary p {{
            margin: 0;
            font-size: {fonts["table"]};
            color: #475569;
        }}
        .summary strong {{
            color: #1e3a5f;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #94a3b8;
            font-size: {fonts["small"]};
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{self._escape_html(wedding_name)}</h1>
        <p class="subtitle">Seating Chart &bull; {datetime.now(timezone.utc).strftime("%B %d, %Y")}</p>
    </div>

    <div class="canvas">
        {floor_plan_html}
        {tables_html}
    </div>

    {self._render_unseated_section(unseated_guests, fonts) if unseated_guests else ""}

    <div class="summary">
        <p>
            <strong>{len(tables)}</strong> Tables &bull;
            <strong>{sum(len(g) for g in guests_by_table.values())}</strong> Seated Guests &bull;
            <strong>{len(unseated_guests)}</strong> Unseated
        </p>
    </div>

    <div class="footer">
        <p>Generated by The Special Wedding</p>
    </div>
</body>
</html>
"""
        return html

    def _render_floor_plan_layers(
        self, seating_layout: Optional[dict], width: int, height: int, scale: float
    ) -> str:
        """Render the saved venue context under table cards for visual PDF exports."""
        if not seating_layout:
            return ""

        layers: list[str] = []
        background_image = seating_layout.get("background_image_data_url")
        if background_image:
            layers.append(
                f'<img class="floor-plan-image" src="{self._escape_html(background_image)}" alt="" />'
            )

        points = seating_layout.get("outline") or []
        if len(points) >= 3:
            safe_points: list[str] = []
            for point in points:
                try:
                    x = float(point.get("x", 0))
                    y = float(point.get("y", 0))
                except (TypeError, ValueError):
                    continue
                safe_points.append(f"{x:.1f},{y:.1f}")

            if len(safe_points) >= 3:
                points_attr = " ".join(safe_points)
                layers.append(
                    f"""
        <svg class="floor-plan" viewBox="0 0 {width} {height}" aria-hidden="true">
            <polygon points="{points_attr}" fill="#3b82f6" fill-opacity="0.06" stroke="#3b82f6" stroke-opacity="0.7" stroke-width="6" stroke-linejoin="round" stroke-dasharray="18 12" />
        </svg>
        """
                )

        for fixture in seating_layout.get("fixtures") or []:
            try:
                x = int(float(fixture.get("x", 0)) * scale)
                y = int(float(fixture.get("y", 0)) * scale)
                fixture_width = int(float(fixture.get("width", 160)) * scale)
                fixture_height = int(float(fixture.get("height", 90)) * scale)
            except (TypeError, ValueError):
                continue
            label = self._escape_html(fixture.get("label", "Fixture"))
            layers.append(
                f"""
        <div class="fixture-card" style="left: {x}px; top: {y}px; width: {fixture_width}px; height: {fixture_height}px;">
            {label}
        </div>
        """
            )

        return "".join(layers)

    def _render_table_card(
        self, table: dict, guests: List[dict], fonts: dict, scale: float = 1.0
    ) -> str:
        """Render a single table as positioned HTML card."""
        x = int(table.get("x", 0) * scale)
        y = int(table.get("y", 0) * scale)
        name = self._escape_html(table.get("name", "Table"))
        shape = table.get("shape", "round")
        capacity = table.get("capacity", 8)

        # Sort guests alphabetically
        sorted_guests = sorted(guests, key=lambda g: g.get("name", "").lower())

        guest_names = "".join(
            f'<div class="guest-name">{self._escape_html(g.get("name", "Guest"))}</div>'
            for g in sorted_guests[:capacity]
        )

        shape_class = "round" if shape == "round" else "rectangle"

        return f"""
        <div class="table-card {shape_class}" style="left: {x}px; top: {y}px;">
            <div class="table-name">{name}</div>
            <div class="guest-list">{guest_names if guest_names else '<em style="color: #94a3b8;">Empty</em>'}</div>
            <div class="capacity-info">{len(guests)}/{capacity} seats</div>
        </div>
        """

    def _render_unseated_section(self, unseated_guests: List[dict], fonts: dict) -> str:
        """Render list of unseated guests."""
        sorted_guests = sorted(unseated_guests, key=lambda g: g.get("name", "").lower())
        guest_names = ", ".join(
            self._escape_html(g.get("name", "Guest")) for g in sorted_guests
        )
        return f"""
    <div class="unseated-section">
        <h3>Unseated Guests ({len(unseated_guests)})</h3>
        <p>{guest_names}</p>
    </div>
        """

    def _generate_list_layout(
        self,
        tables: List[dict],
        guests_by_table: Dict[str, List[dict]],
        unseated_guests: List[dict],
        wedding_name: str,
        paper_size: str = "poster",
    ) -> str:
        """Generate table-by-table list format (alternative layout)."""

        # Paper size configuration
        page_sizes = {"poster": "letter landscape", "tabloid": "letter portrait"}
        page_size = page_sizes.get(paper_size, "letter landscape")

        # Generate table sections
        tables_html = ""
        for table in sorted(tables, key=lambda t: t.get("name", "")):
            table_id = str(table.get("_id", ""))
            table_guests = guests_by_table.get(table_id, [])
            table_name = self._escape_html(table.get("name", "Table"))
            capacity = table.get("capacity", 8)

            guest_rows = ""
            for guest in sorted(table_guests, key=lambda g: g.get("name", "").lower()):
                guest_name = self._escape_html(guest.get("name", "Guest"))
                group_id = self._escape_html(guest.get("group_id", ""))
                guest_rows += f"<tr><td>{guest_name}</td><td>{group_id}</td></tr>"

            if not guest_rows:
                guest_rows = '<tr><td colspan="2" style="color: #94a3b8; font-style: italic;">No guests assigned</td></tr>'

            tables_html += f"""
            <div class="table-section">
                <h3>{table_name} <span class="capacity">({len(table_guests)}/{capacity})</span></h3>
                <table>
                    <thead><tr><th>Guest Name</th><th>Group</th></tr></thead>
                    <tbody>{guest_rows}</tbody>
                </table>
            </div>
            """

        # Unseated section
        unseated_html = ""
        if unseated_guests:
            rows = ""
            for guest in sorted(
                unseated_guests, key=lambda g: g.get("name", "").lower()
            ):
                guest_name = self._escape_html(guest.get("name", "Guest"))
                group_id = self._escape_html(guest.get("group_id", ""))
                rows += f"<tr><td>{guest_name}</td><td>{group_id}</td></tr>"

            unseated_html = f"""
            <div class="table-section unseated">
                <h3>Unseated Guests <span class="capacity">({len(unseated_guests)})</span></h3>
                <table>
                    <thead><tr><th>Guest Name</th><th>Group</th></tr></thead>
                    <tbody>{rows}</tbody>
                </table>
            </div>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        @page {{
            size: {page_size};
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
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 2px solid #d4af37;
        }}
        .header h1 {{
            color: #1e3a5f;
            font-size: 20pt;
            margin: 0 0 5px 0;
        }}
        .header p {{
            color: #64748b;
            font-size: 9pt;
            margin: 0;
        }}
        .tables-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }}
        .table-section {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            break-inside: avoid;
        }}
        .table-section.unseated {{
            background: #fef2f2;
            border-color: #fecaca;
        }}
        .table-section h3 {{
            color: #1e3a5f;
            font-size: 12pt;
            margin: 0 0 10px 0;
            padding-bottom: 8px;
            border-bottom: 1px solid #e2e8f0;
        }}
        .table-section.unseated h3 {{
            color: #dc2626;
            border-bottom-color: #fecaca;
        }}
        .capacity {{
            font-weight: normal;
            color: #64748b;
            font-size: 9pt;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th, td {{
            text-align: left;
            padding: 5px 8px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 9pt;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            color: #475569;
        }}
        .summary {{
            margin-top: 25px;
            text-align: center;
            padding: 12px;
            background: #f8fafc;
            border-radius: 8px;
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
        <h1>{self._escape_html(wedding_name)} - Seating List</h1>
        <p>Generated on {datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")}</p>
    </div>

    <div class="tables-grid">
        {tables_html}
        {unseated_html}
    </div>

    <div class="summary">
        <p>
            <strong>{len(tables)}</strong> Tables &bull;
            <strong>{sum(len(g) for g in guests_by_table.values())}</strong> Seated &bull;
            <strong>{len(unseated_guests)}</strong> Unseated
        </p>
    </div>

    <div class="footer">
        <p>Generated by The Special Wedding</p>
    </div>
</body>
</html>
"""
        return html

    @staticmethod
    def _escape_html(text: Optional[str]) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )


# Singleton instance
seating_export_service = SeatingExportService()
