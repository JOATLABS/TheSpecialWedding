"""
Dependency Injection Container for better testability and loose coupling
"""
from typing import Dict, Any, Type, TypeVar, Optional, Callable
from abc import ABC, abstractmethod
import asyncio
import logging
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')


class Lifetime(Enum):
    """Service lifetime scopes"""
    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


class ServiceDescriptor:
    """Describes how a service should be created and managed"""
    
    def __init__(
        self,
        service_type: Type,
        implementation: Type = None,
        factory: Callable = None,
        instance: Any = None,
        lifetime: Lifetime = Lifetime.TRANSIENT
    ):
        self.service_type = service_type
        self.implementation = implementation or service_type
        self.factory = factory
        self.instance = instance
        self.lifetime = lifetime
        self.created_instance = None


class DependencyContainer:
    """Dependency injection container"""
    
    def __init__(self):
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._scoped_services: Dict[str, Dict[Type, Any]] = {}
        self._current_scope: Optional[str] = None
    
    def register_singleton(self, service_type: Type[T], implementation: Type[T] = None) -> 'DependencyContainer':
        """Register a singleton service"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=Lifetime.SINGLETON
        )
        return self
    
    def register_scoped(self, service_type: Type[T], implementation: Type[T] = None) -> 'DependencyContainer':
        """Register a scoped service"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=Lifetime.SCOPED
        )
        return self
    
    def register_transient(self, service_type: Type[T], implementation: Type[T] = None) -> 'DependencyContainer':
        """Register a transient service"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=implementation,
            lifetime=Lifetime.TRANSIENT
        )
        return self
    
    def register_instance(self, service_type: Type[T], instance: T) -> 'DependencyContainer':
        """Register a service instance"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=Lifetime.SINGLETON
        )
        return self
    
    def register_factory(
        self, 
        service_type: Type[T], 
        factory: Callable[[], T],
        lifetime: Lifetime = Lifetime.TRANSIENT
    ) -> 'DependencyContainer':
        """Register a service factory"""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime
        )
        return self
    
    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance"""
        if service_type not in self._services:
            raise ValueError(f"Service {service_type.__name__} not registered")
        
        descriptor = self._services[service_type]
        
        # Handle different lifetime scopes
        if descriptor.lifetime == Lifetime.SINGLETON:
            return self._get_singleton(descriptor)
        elif descriptor.lifetime == Lifetime.SCOPED:
            return self._get_scoped(descriptor)
        else:  # TRANSIENT
            return self._create_instance(descriptor)
    
    def _get_singleton(self, descriptor: ServiceDescriptor):
        """Get singleton instance"""
        if descriptor.created_instance is None:
            descriptor.created_instance = self._create_instance(descriptor)
        return descriptor.created_instance
    
    def _get_scoped(self, descriptor: ServiceDescriptor):
        """Get scoped instance"""
        if self._current_scope is None:
            raise ValueError("No active scope for scoped service")
        
        if self._current_scope not in self._scoped_services:
            self._scoped_services[self._current_scope] = {}
        
        scope_services = self._scoped_services[self._current_scope]
        
        if descriptor.service_type not in scope_services:
            scope_services[descriptor.service_type] = self._create_instance(descriptor)
        
        return scope_services[descriptor.service_type]
    
    def _create_instance(self, descriptor: ServiceDescriptor):
        """Create a new service instance"""
        if descriptor.instance is not None:
            return descriptor.instance
        
        if descriptor.factory is not None:
            return descriptor.factory()
        
        # Use dependency injection to create instance
        return self._create_with_dependencies(descriptor.implementation)
    
    def _create_with_dependencies(self, implementation_type: Type):
        """Create instance with dependency injection"""
        try:
            # Get constructor parameters
            import inspect
            signature = inspect.signature(implementation_type.__init__)
            parameters = {}
            
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Check if parameter has type annotation
                if param.annotation and param.annotation != inspect.Parameter.empty:
                    if param.annotation in self._services:
                        parameters[param_name] = self.resolve(param.annotation)
                    elif param.default != inspect.Parameter.empty:
                        parameters[param_name] = param.default
                    else:
                        logger.warning(f"Cannot resolve dependency {param.annotation} for {implementation_type}")
            
            return implementation_type(**parameters)
            
        except Exception as e:
            logger.error(f"Failed to create instance of {implementation_type}: {str(e)}")
            # Fallback to parameterless constructor
            return implementation_type()
    
    def create_scope(self, scope_id: str = None) -> 'ServiceScope':
        """Create a new service scope"""
        if scope_id is None:
            scope_id = f"scope_{id(object())}"
        
        return ServiceScope(self, scope_id)
    
    def _enter_scope(self, scope_id: str):
        """Enter a service scope"""
        self._current_scope = scope_id
        if scope_id not in self._scoped_services:
            self._scoped_services[scope_id] = {}
    
    def _exit_scope(self, scope_id: str):
        """Exit a service scope"""
        if scope_id in self._scoped_services:
            # Dispose scoped services if they implement IDisposable
            scope_services = self._scoped_services[scope_id]
            for service in scope_services.values():
                if hasattr(service, 'dispose'):
                    try:
                        service.dispose()
                    except Exception as e:
                        logger.error(f"Error disposing service: {str(e)}")
            
            del self._scoped_services[scope_id]
        
        if self._current_scope == scope_id:
            self._current_scope = None


class ServiceScope:
    """Service scope context manager"""
    
    def __init__(self, container: DependencyContainer, scope_id: str):
        self.container = container
        self.scope_id = scope_id
    
    def __enter__(self):
        self.container._enter_scope(self.scope_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.container._exit_scope(self.scope_id)
    
    async def __aenter__(self):
        self.container._enter_scope(self.scope_id)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.container._exit_scope(self.scope_id)


# Service interfaces
class IEmailService(ABC):
    """Email service interface"""
    
    @abstractmethod
    async def send_email(self, to: str, subject: str, body: str) -> bool:
        pass


class ISMSService(ABC):
    """SMS service interface"""
    
    @abstractmethod
    async def send_sms(self, to: str, message: str) -> bool:
        pass


class ISubscriptionService(ABC):
    """Subscription service interface"""
    
    @abstractmethod
    async def check_usage_limits(self, user_id: str, resource_type: str, amount: int) -> Dict[str, Any]:
        pass


class INotificationService(ABC):
    """Notification service interface"""
    
    @abstractmethod
    async def send_notification(self, user_id: str, message: str, notification_type: str) -> bool:
        pass


# Global container instance
container = DependencyContainer()


def setup_services():
    """Setup service registrations"""
    from app.services.email_service_resend import EmailService
    from app.services.subscription_service import SubscriptionService
    from app.core.settings import settings
    from app.core.cache import cache
    from app.core.events import event_bus
    
    # Register singleton services
    container.register_singleton(settings.__class__, lambda: settings)
    container.register_singleton(cache.__class__, lambda: cache)
    container.register_singleton(event_bus.__class__, lambda: event_bus)
    
    # Register scoped services (per request)
    container.register_scoped(IEmailService, EmailService)
    container.register_scoped(ISubscriptionService, SubscriptionService)
    
    # Register factories for complex services
    def create_notification_service():
        from app.services.notification_service import NotificationService
        email_service = container.resolve(IEmailService)
        return NotificationService(email_service)
    
    container.register_factory(INotificationService, create_notification_service, Lifetime.SCOPED)
    
    logger.info("Service container setup complete")


# Dependency injection decorator
def inject(*dependencies):
    """Decorator for dependency injection"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # Create a new scope for this request
            async with container.create_scope():
                # Resolve dependencies and add to kwargs
                for dep_type in dependencies:
                    if dep_type not in kwargs:
                        kwargs[dep_type.__name__.lower().replace('i', '')] = container.resolve(dep_type)
                
                return await func(*args, **kwargs)
        
        return wrapper
    return decorator


# FastAPI dependency provider
def get_service(service_type: Type[T]) -> Callable[[], T]:
    """Create FastAPI dependency provider"""
    def provider() -> T:
        return container.resolve(service_type)
    
    return provider