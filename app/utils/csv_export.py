"""
CSV Export Utilities for Wedding WebApp

Provides secure and efficient CSV export functionality for form responses
with proper data sanitization and CSV injection protection.
"""

import csv
import io
import html
import re
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from app.utils.security_utils import InputSanitizer
import logging

logger = logging.getLogger(__name__)


class CSVSecurityError(Exception):
    """Raised when CSV data contains potential security issues"""
    pass


class CSVExportUtils:
    """Utility class for secure CSV export operations"""
    # Patterns that could indicate CSV injection attempts
    DANGEROUS_CSV_PATTERNS = [
        r'^[=@+\-]',  # Formulas starting with =, @, +, -
        r'^\s*[=@+\-]',  # Formulas with leading whitespace
        r'cmd\s*\|',  # Command injection attempts
        r'powershell',  # PowerShell commands
        r'<script',  # Script tags
        r'javascript:',  # JavaScript URLs
    ]
    @classmethod
    def sanitize_csv_value(cls, value: Any) -> str:
        """
        Sanitize a single value for CSV export to prevent injection attacks.

        Args:
            value: The value to sanitize

        Returns:
            str: The sanitized string value

        Raises:
            CSVSecurityError: If dangerous patterns are detected
        """
        if value is None:
            return ""
        # Convert to string
        if isinstance(value, bool):
            return "Yes" if value else "No"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, list):
            # Handle arrays by joining with semicolon
            sanitized_items = [cls.sanitize_csv_value(item) for item in value]
            return "; ".join(sanitized_items)
        elif isinstance(value, dict):
            # Handle objects by converting to JSON-like string
            items = []
            for k, v in value.items():
                sanitized_key = cls.sanitize_csv_value(k)
                sanitized_value = cls.sanitize_csv_value(v)
                items.append(f"{sanitized_key}: {sanitized_value}")
            return "; ".join(items)

        # Convert to string and sanitize
        str_value = str(value).strip()

        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_CSV_PATTERNS:
            if re.search(pattern, str_value, re.IGNORECASE):
                logger.warning(f"Potential CSV injection attempt detected: {str_value[:100]}")
                # Prefix with single quote to neutralize formula
                str_value = "'" + str_value
                break

        # Remove or escape problematic characters
        str_value = str_value.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        str_value = str_value.replace('"', '""')  # Escape quotes for CSV

        # Limit length to prevent DoS
        if len(str_value) > 32767:  # Excel cell limit
            str_value = str_value[:32764] + "..."
            logger.warning("CSV value truncated due to length")

        return str_value

    @classmethod
    def generate_csv_content(
        cls,
        headers: List[str],
        data_rows: List[List[Any]],
        include_bom: bool = True
    ) -> str:
        """
        Generate CSV content with proper sanitization.
        Args:
            headers: List of column headers
            data_rows: List of data rows (each row is a list of values)
            include_bom: Whether to include BOM for Excel compatibility
        Returns:
            str: The CSV content as a string
        """
        try:
            output = io.StringIO()

            # Add BOM for Excel compatibility if requested
            if include_bom:
                output.write('\ufeff')

            writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\n')

            # Sanitize and write headers
            sanitized_headers = [cls.sanitize_csv_value(header) for header in headers]
            writer.writerow(sanitized_headers)

            # Sanitize and write data rows
            for row in data_rows:
                sanitized_row = [cls.sanitize_csv_value(value) for value in row]
                writer.writerow(sanitized_row)

            content = output.getvalue()
            output.close()

            return content

        except Exception as e:
            logger.error(f"Error generating CSV content: {str(e)}")
            raise CSVSecurityError(f"Failed to generate CSV: {str(e)}")

    @classmethod
    def generate_form_response_csv(
        cls,
        form_data: Dict[str, Any],
        responses: List[Dict[str, Any]],
        include_metadata: bool = True,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None
    ) -> str:
        """
        Generate CSV content for form responses.
        Args:
            form_data: The form definition with fields
            responses: List of form responses
            include_metadata: Whether to include submission metadata
            date_from: Optional start date filter
            date_to: Optional end date filter
        Returns:
            str: The CSV content
        """
        try:
            # Filter responses by date if provided
            filtered_responses = responses
            if date_from or date_to:
                filtered_responses = []
                for response in responses:
                    submitted_at = response.get('submitted_at')
                    if isinstance(submitted_at, str):
                        try:
                            submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
                        except ValueError:
                            continue
                    if date_from and submitted_at < date_from:
                        continue
                    if date_to and submitted_at > date_to:
                        continue

                    filtered_responses.append(response)

            if not filtered_responses:
                # Return empty CSV with headers if no responses
                headers = cls._build_csv_headers(form_data, include_metadata)
                return cls.generate_csv_content(headers, [])

            # Build headers
            headers = cls._build_csv_headers(form_data, include_metadata)

            # Build data rows
            data_rows = []
            for response in filtered_responses:
                row = cls._build_csv_row(form_data, response, include_metadata)
                data_rows.append(row)

            return cls.generate_csv_content(headers, data_rows)

        except Exception as e:
            logger.error(f"Error generating form response CSV: {str(e)}")
            raise CSVSecurityError(f"Failed to generate form CSV: {str(e)}")

    @classmethod
    def _build_csv_headers(cls, form_data: Dict[str, Any], include_metadata: bool) -> List[str]:
        """Build CSV headers based on form structure"""
        headers = []
        if include_metadata:
            headers.extend([
                "Response ID",
                "Submission Date",
                "Submitted By (Name)",
                "Submitted By (Email)",
                "IP Address",
                "Completion Status"
            ])

        # Add field headers
        for field in form_data.get('fields', []):
            field_label = field.get('label', field.get('id', 'Unknown Field'))
            headers.append(field_label)

        return headers

    @classmethod
    def _build_csv_row(
        cls,
        form_data: Dict[str, Any],
        response: Dict[str, Any],
        include_metadata: bool
    ) -> List[Any]:
        """Build a CSV row for a single response"""
        row = []
        if include_metadata:
            # Add metadata columns
            row.extend([
                response.get('id', ''),
                response.get('submitted_at', ''),
                response.get('submitted_by_name', ''),
                response.get('submitted_by_email', ''),
                response.get('ip_address', ''),
                cls._calculate_completion_status(form_data, response)
            ])
        # Add field values
        responses_data = response.get('responses', {})
        for field in form_data.get('fields', []):
            field_id = field.get('id')
            field_type = field.get('type', 'text')
            field_value = responses_data.get(field_id)

            # Format value based on field type
            formatted_value = cls._format_field_value(field_type, field_value, field)
            row.append(formatted_value)

        return row

    @classmethod
    def _format_field_value(cls, field_type: str, value: Any, field_config: Dict[str, Any]) -> Any:
        """Format a field value based on its type"""
        if value is None or value == '':
            return ''
        if field_type == 'rating':
            try:
                rating = int(value)
                return f"{rating}/5"
            except (ValueError, TypeError):
                return value
        elif field_type == 'scale':
            try:
                scale = int(value)
                return f"{scale}/10"
            except (ValueError, TypeError):
                return value

        elif field_type in ['checkbox', 'select'] and isinstance(value, list):
            return '; '.join(str(v) for v in value)

        elif field_type == 'date':
            if isinstance(value, str):
                try:
                    # Try to parse and reformat date
                    date_obj = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return date_obj.strftime('%Y-%m-%d')
                except ValueError:
                    return value
            return value
        elif field_type == 'file_upload':
            if isinstance(value, list):
                return '; '.join(str(v) for v in value)
            elif isinstance(value, dict):
                return value.get('filename', str(value))
            return value

        return value

    @classmethod
    def _calculate_completion_status(cls, form_data: Dict[str, Any], response: Dict[str, Any]) -> str:
        """Calculate completion status for a response"""
        required_fields = [
            field.get('id') for field in form_data.get('fields', [])
            if field.get('required', False)
        ]

        if not required_fields:
            return 'Complete'

        responses_data = response.get('responses', {})
        completed_required = 0

        for field_id in required_fields:
            if field_id in responses_data and responses_data[field_id] not in [None, '', []]:
                completed_required += 1

        if completed_required == len(required_fields):
            return 'Complete'
        else:
            return f'Partial ({completed_required}/{len(required_fields)})'

    @classmethod
    def generate_filename(
        cls,
        form_name: str,
        export_type: str = "responses",
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Generate a safe filename for CSV export.

        Args:
            form_name: The name of the form
            export_type: Type of export (e.g., "responses", "analytics")
            timestamp: Optional timestamp (defaults to now)

        Returns:
            str: Safe filename for the CSV export
        """
        if timestamp is None:
            timestamp = datetime.utcnow()
        # Sanitize form name for filename
        safe_name = re.sub(r'[^\w\-_\. ]', '', form_name)
        safe_name = safe_name.strip()[:50]  # Limit length
        safe_name = safe_name.replace(' ', '_')

        if not safe_name:
            safe_name = "form"

        # Format timestamp
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')

        return f"{safe_name}_{export_type}_{timestamp_str}.csv"


class FormResponseCSVExporter:
    """Specialized CSV exporter for form responses"""

    def __init__(self):
        self.utils = CSVExportUtils()

    def export_responses(
        self,
        form_data: Dict[str, Any],
        responses: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Export form responses to CSV format.
        Args:
            form_data: The form definition
            responses: List of responses to export
            options: Export options (metadata, date filters, etc.)
        Returns:
            Dict containing CSV content and metadata
        """
        try:
            if options is None:
                options = {}

            include_metadata = options.get('include_metadata', True)
            date_from = options.get('date_from')
            date_to = options.get('date_to')

            # Parse date strings if provided
            if isinstance(date_from, str):
                try:
                    date_from = datetime.fromisoformat(date_from.replace('Z', '+00:00'))
                except ValueError:
                    date_from = None
            if isinstance(date_to, str):
                try:
                    date_to = datetime.fromisoformat(date_to.replace('Z', '+00:00'))
                except ValueError:
                    date_to = None
            # Generate CSV content
            csv_content = self.utils.generate_form_response_csv(
                form_data=form_data,
                responses=responses,
                include_metadata=include_metadata,
                date_from=date_from,
                date_to=date_to
            )

            # Generate filename
            form_name = form_data.get('name', 'Unknown Form')
            filename = self.utils.generate_filename(form_name, "responses")

            # Calculate statistics
            total_responses = len(responses)
            filtered_count = len([r for r in responses
                                if FormResponseCSVExporter._passes_date_filter(r, date_from, date_to)])

            return {
                'content': csv_content,
                'filename': filename,
                'content_type': 'text/csv; charset=utf-8',
                'size': len(csv_content.encode('utf-8')),
                'total_responses': total_responses,
                'exported_count': filtered_count,
                'export_timestamp': datetime.utcnow().isoformat(),
                'options': options
            }

        except Exception as e:
            logger.error(f"Error exporting form responses: {str(e)}")
            raise CSVSecurityError(f"Export failed: {str(e)}")

    @staticmethod
    def _passes_date_filter(
        response: Dict[str, Any],
        date_from: Optional[datetime],
        date_to: Optional[datetime]
    ) -> bool:
        """Check if response passes date filter"""
        if not date_from and not date_to:
            return True

        submitted_at = response.get('submitted_at')
        if not submitted_at:
            return False

        if isinstance(submitted_at, str):
            try:
                submitted_at = datetime.fromisoformat(submitted_at.replace('Z', '+00:00'))
            except ValueError:
                return False
        if date_from and submitted_at < date_from:
            return False
        if date_to and submitted_at > date_to:
            return False
        return True


# Convenience function for quick exports
def export_form_responses_to_csv(
    form_data: Dict[str, Any],
    responses: List[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Convenience function to export form responses to CSV.
    Args:
        form_data: The form definition
        responses: List of responses to export
        **options: Export options
    Returns:
        Dict with CSV content and metadata
    """
    exporter = FormResponseCSVExporter()
    return exporter.export_responses(form_data, responses, options)