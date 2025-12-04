"""
Security audit service for logging and monitoring security events
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from app.core.database import mongo
import os

logger = logging.getLogger(__name__)

class SecurityEventType(str, Enum):
    """Security event types for audit logging"""

    # Authentication events
    LOGIN_ATTEMPT = "login_attempt"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    TOKEN_VALIDATION_FAILURE = "token_validation_failure"

    # Authorization events
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    PERMISSION_DENIED = "permission_denied"
    PRIVILEGE_ESCALATION_ATTEMPT = "privilege_escalation_attempt"

    # Form security events
    FORM_CREATION = "form_creation"
    FORM_ACCESS = "form_access"
    FORM_MODIFICATION = "form_modification"
    FORM_DELETION = "form_deletion"
    FORM_SUBMISSION = "form_submission"
    INVALID_FORM_DATA = "invalid_form_data"
    PUBLIC_FORM_ACCESS = "public_form_access"

    # Input validation events
    XSS_ATTEMPT = "xss_attempt"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    MALICIOUS_INPUT = "malicious_input"
    INVALID_INPUT_FORMAT = "invalid_input_format"

    # Rate limiting events
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Data access events
    SENSITIVE_DATA_ACCESS = "sensitive_data_access"
    DATA_EXPORT = "data_export"
    BULK_OPERATION = "bulk_operation"


class SecuritySeverity(str, Enum):
    """Security event severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityEvent:
    """Security event data structure"""
    event_type: SecurityEventType
    severity: SecuritySeverity
    user_email: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    resource: Optional[str]
    action: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime
    success: bool
    error_message: Optional[str] = None
    session_id: Optional[str] = None
    wedding_id: Optional[str] = None
    form_id: Optional[str] = None


class SecurityAuditService:
    """Service for security audit logging and monitoring"""

    def __init__(self):
        self.audit_collection = mongo.db["security_audit_logs"]
        self.enable_db_logging = True
        self.enable_file_logging = True
        self.log_file_path = os.getenv("SECURITY_LOG_FILE", "/var/log/wedding_app_security.log")

        # Setup file logging if enabled
        if self.enable_file_logging:
            self._setup_file_logging()

    def _setup_file_logging(self):
        """Setup security-specific file logging"""
        try:
            # Create security logger
            security_logger = logging.getLogger("security_audit")
            security_logger.setLevel(logging.INFO)

            # Create file handler
            handler = logging.FileHandler(self.log_file_path)
            handler.setLevel(logging.INFO)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - SECURITY - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)

            # Add handler to logger
            if not security_logger.handlers:
                security_logger.addHandler(handler)

        except Exception as e:
            logger.warning(f"Failed to setup security file logging: {str(e)}")

    def log_security_event(
        self,
        event_type: SecurityEventType,
        severity: SecuritySeverity,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        session_id: Optional[str] = None,
        wedding_id: Optional[str] = None,
        form_id: Optional[str] = None
    ):
        """
        Log a security event

        Args:
            event_type: Type of security event
            severity: Severity level
            user_email: User email if applicable
            ip_address: Client IP address
            user_agent: Client user agent
            resource: Resource being accessed
            action: Action being performed
            details: Additional event details
            success: Whether the action was successful
            error_message: Error message if applicable
            session_id: Session identifier
            wedding_id: Wedding ID if applicable
            form_id: Form ID if applicable
        """
        try:
            # Create security event
            event = SecurityEvent(
                event_type=event_type,
                severity=severity,
                user_email=user_email,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=resource,
                action=action,
                details=details or {},
                timestamp=datetime.utcnow(),
                success=success,
                error_message=error_message,
                session_id=session_id,
                wedding_id=wedding_id,
                form_id=form_id
            )

            # Log to database
            if self.enable_db_logging:
                self._log_to_database(event)

            # Log to file
            if self.enable_file_logging:
                self._log_to_file(event)

            # Log critical events to application logger
            if severity in [SecuritySeverity.HIGH, SecuritySeverity.CRITICAL]:
                logger.warning(f"SECURITY ALERT: {event_type.value} - {details}")

        except Exception as e:
            logger.error(f"Failed to log security event: {str(e)}")

    def _log_to_database(self, event: SecurityEvent):
        """Log security event to database"""
        try:
            event_doc = asdict(event)
            # Convert enum values to strings
            event_doc['event_type'] = event.event_type.value
            event_doc['severity'] = event.severity.value

            self.audit_collection.insert_one(event_doc)

        except Exception as e:
            logger.error(f"Failed to log security event to database: {str(e)}")

    def _log_to_file(self, event: SecurityEvent):
        """Log security event to file"""
        try:
            security_logger = logging.getLogger("security_audit")

            log_message = (
                f"EVENT={event.event_type.value} "
                f"SEVERITY={event.severity.value} "
                f"USER={event.user_email or 'anonymous'} "
                f"IP={event.ip_address or 'unknown'} "
                f"RESOURCE={event.resource or 'none'} "
                f"ACTION={event.action or 'none'} "
                f"SUCCESS={event.success} "
                f"DETAILS={json.dumps(event.details)}"
            )

            if event.error_message:
                log_message += f" ERROR={event.error_message}"

            # Log with appropriate level based on severity
            if event.severity == SecuritySeverity.CRITICAL:
                security_logger.critical(log_message)
            elif event.severity == SecuritySeverity.HIGH:
                security_logger.error(log_message)
            elif event.severity == SecuritySeverity.MEDIUM:
                security_logger.warning(log_message)
            else:
                security_logger.info(log_message)

        except Exception as e:
            logger.error(f"Failed to log security event to file: {str(e)}")

    def get_security_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        event_types: Optional[List[SecurityEventType]] = None,
        severity: Optional[SecuritySeverity] = None,
        user_email: Optional[str] = None,
        ip_address: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve security events based on filters

        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            event_types: List of event types to filter
            severity: Severity level to filter
            user_email: User email to filter
            ip_address: IP address to filter
            limit: Maximum number of results

        Returns:
            List of security events
        """
        try:
            query = {}

            # Date range filter
            if start_date or end_date:
                query['timestamp'] = {}
                if start_date:
                    query['timestamp']['$gte'] = start_date
                if end_date:
                    query['timestamp']['$lte'] = end_date

            # Event type filter
            if event_types:
                query['event_type'] = {'$in': [et.value for et in event_types]}

            # Severity filter
            if severity:
                query['severity'] = severity.value

            # User filter
            if user_email:
                query['user_email'] = user_email

            # IP filter
            if ip_address:
                query['ip_address'] = ip_address

            # Execute query
            events = list(
                self.audit_collection
                .find(query)
                .sort('timestamp', -1)
                .limit(limit)
            )

            # Convert ObjectId to string
            for event in events:
                if '_id' in event:
                    event['_id'] = str(event['_id'])

            return events

        except Exception as e:
            logger.error(f"Failed to retrieve security events: {str(e)}")
            return []

    def get_security_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get security events summary

        Args:
            start_date: Start date for summary
            end_date: End date for summary

        Returns:
            Security summary statistics
        """
        try:
            query = {}

            # Date range filter
            if start_date or end_date:
                query['timestamp'] = {}
                if start_date:
                    query['timestamp']['$gte'] = start_date
                if end_date:
                    query['timestamp']['$lte'] = end_date

            # Aggregate statistics
            pipeline = [
                {'$match': query},
                {
                    '$group': {
                        '_id': {
                            'event_type': '$event_type',
                            'severity': '$severity'
                        },
                        'count': {'$sum': 1}
                    }
                }
            ]

            results = list(self.audit_collection.aggregate(pipeline))

            # Process results
            summary = {
                'total_events': 0,
                'by_severity': {
                    'critical': 0,
                    'high': 0,
                    'medium': 0,
                    'low': 0
                },
                'by_event_type': {},
                'failed_events': 0
            }

            for result in results:
                count = result['count']
                event_type = result['_id']['event_type']
                severity = result['_id']['severity']

                summary['total_events'] += count
                summary['by_severity'][severity] += count

                if event_type not in summary['by_event_type']:
                    summary['by_event_type'][event_type] = 0
                summary['by_event_type'][event_type] += count

            # Get failed events count
            failed_query = dict(query)
            failed_query['success'] = False
            summary['failed_events'] = self.audit_collection.count_documents(failed_query)

            return summary

        except Exception as e:
            logger.error(f"Failed to generate security summary: {str(e)}")
            return {}

    def detect_suspicious_activity(
        self,
        ip_address: str,
        time_window_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        Detect suspicious activity from an IP address

        Args:
            ip_address: IP address to analyze
            time_window_minutes: Time window for analysis

        Returns:
            Suspicious activity analysis
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

            query = {
                'ip_address': ip_address,
                'timestamp': {'$gte': cutoff_time}
            }

            events = list(self.audit_collection.find(query))

            analysis = {
                'ip_address': ip_address,
                'time_window_minutes': time_window_minutes,
                'total_events': len(events),
                'failed_attempts': sum(1 for e in events if not e.get('success', True)),
                'event_types': {},
                'severity_levels': {},
                'suspicious_indicators': []
            }

            # Analyze event patterns
            for event in events:
                event_type = event.get('event_type', 'unknown')
                severity = event.get('severity', 'low')

                analysis['event_types'][event_type] = analysis['event_types'].get(event_type, 0) + 1
                analysis['severity_levels'][severity] = analysis['severity_levels'].get(severity, 0) + 1

            # Detect suspicious patterns
            if analysis['failed_attempts'] > 10:
                analysis['suspicious_indicators'].append('High number of failed attempts')

            if analysis['total_events'] > 100:
                analysis['suspicious_indicators'].append('Unusually high activity volume')

            if analysis['severity_levels'].get('critical', 0) > 0:
                analysis['suspicious_indicators'].append('Critical security events detected')

            return analysis

        except Exception as e:
            logger.error(f"Failed to detect suspicious activity: {str(e)}")
            return {}


# Global security audit service instance
security_audit = SecurityAuditService()