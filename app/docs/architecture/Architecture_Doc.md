# Wedding WebApp Architecture Documentation

## Overview

This is a full-stack wedding planning and management application built with a **hybrid architecture** combining:
- **Backend**: FastAPI (Python) - SaaS multi-tenant wedding management platform
- **Frontend**: Next.js (TypeScript/React) - Wedding websites and admin dashboard
- **Database**: MongoDB with async driver (Motor)
- **Caching**: Redis (optional)
- **Deployment**: Backend on DigitalOcean, Frontend on Vercel

## Architecture Patterns

### 1. Modular Monolith with Clean Architecture
```
app/
 core/ # Infrastructure & configuration
 models/ # Domain entities (Pydantic)
 services/ # Business logic layer
 api/ # API endpoints (FastAPI routers)
 middleware/ # Cross-cutting concerns
 dependencies/ # Dependency injection
 utils/ # Shared utilities
```

### 2. Event Sourcing & Domain Events
- **Event Store**: Persists all domain events for audit trails
- **Event Bus**: Publishes events to subscribers (async handlers)
- **Snapshots**: Performance optimization for aggregate reconstruction
- **Use Cases**: Subscription tracking, audit logging, notifications

### 3. Multi-Tenant SaaS Model (COMPLETED)
- **Tenant Isolation**: Wedding planners manage their own weddings with data separation
- **Subscription Tiers**: Enterprise plans with unlimited features, usage tracking
- **Access Control**: Role-based permissions (ROOT_ADMIN, PLANNER, VENDOR)
- **Wedding Assignment**: Automatic planner assignment with access control
- **Dual Role Support**: Users can have both ROOT_ADMIN and PLANNER capabilities

## Core Components

### Application Entry Points
- `main.py` - Legacy application setup
- `main_optimized.py` - **Primary entry point** with enhanced middleware stack

### Settings & Configuration (`core/settings.py`)
- **Pydantic Settings**: Type-safe configuration with validation
- **Environment Support**: Development, staging, production, testing
- **Feature Flags**: Toggle features per environment
- **Security Configuration**: Centralized security settings

### Database Layer
- **Sync**: `core/database.py` - Legacy MongoDB connector
- **Async**: `core/database_async.py` - **Primary** async Motor driver
- **Collections**: Users, weddings, guests, RSVPs, subscriptions, forms, etc.

### Caching Strategy (`core/cache.py`)
- **Redis Backend**: Async Redis with connection pooling
- **Serialization**: JSON for simple types, pickle for complex objects
- **Key Management**: Prefixed keys with application namespace
- **Cache Patterns**: get_or_set, expiration, pattern clearing
- **Decorators**: `@cached` for automatic function result caching

### Event System (`core/events.py`)
- **Domain Events**: User registration, wedding creation, RSVP submissions
- **Event Store**: MongoDB persistence with versioning
- **Event Bus**: Async pub/sub with concurrent handler execution
- **Factory Pattern**: Standardized event creation
- **Handlers**: Security logging, usage tracking, notifications

## Middleware Stack (Order Matters)

The middleware is applied in a specific order from outermost to innermost:

1. **ErrorHandlerMiddleware** - Global exception handling with standardized responses
2. **SecurityHeadersMiddleware** - HSTS, CSP, X-Frame-Options, etc.
3. **CSRFProtectionMiddleware** - Cross-site request forgery protection
4. **AuditLoggingMiddleware** - Security event logging to DB and files
5. **PerformanceMonitoringMiddleware** - Request timing and metrics
6. **RateLimitMiddleware** - Sliding window rate limiting per IP
7. **CORSMiddleware** - Cross-origin resource sharing
8. **GZipMiddleware** - Response compression

### Security Features
- **Content Security Policy**: Restricts resource loading
- **Rate Limiting**: 100 requests/min general, 10/min for auth endpoints
- **CSRF Protection**: Token-based with cookie/header validation
- **Audit Logging**: All security events logged with metadata
- **Security Headers**: Comprehensive protection headers

## API Structure

### Route Organization
```
/ - Root and info endpoints
/health - Health checks and monitoring
/guest - Public guest operations (invite, search)
/rsvp - Public RSVP submissions
/wedding - Public wedding information
/forms - Public form submissions
/vendor-form/* - Public vendor form access (token-based)
/admin/* - All authenticated admin operations
 /admin/weddings - Multi-tenant wedding management
 /admin/planner/* - Wedding planner specific endpoints
 /admin/vendor-forms - Vendor form builder and management
 /admin/users - User management with role filtering
 /admin/forms - Form builder management
```

### Authentication Patterns
- **Public Routes**: No authentication required (wedding sites, vendor forms)
- **Admin Routes**: JWT-based authentication under `/admin` prefix
- **Token-Based Access**: Secure vendor form access via email tokens
- **Role-Based Access**: Different permissions for ROOT_ADMIN vs. wedding planners
- **Multi-Tenant Access Control**: Planners restricted to assigned weddings
- **Dual Role Support**: Users can have multiple roles (ROOT_ADMIN + PLANNER)

### Error Handling
- **Standardized Responses**: Consistent error format across all endpoints
- **Custom Exceptions**: `WeddingAppException` for application-specific errors
- **Validation Errors**: Detailed field-level validation feedback
- **Logging**: All errors logged with context and stack traces

## Data Models & Domain

### Core Entities (Pydantic Models)
- **Wedding**: Events, themes, privacy settings, RSVP config
- **Guest**: Contact info, RSVP status, verification tokens
- **User**: Planners, vendors with role-based permissions
- **Subscription**: Plans, usage tracking, feature limits
- **Form**: Custom form builder with dynamic fields

### Business Rules
- **Subscription Limits**: Features gated by subscription tier
- **Wedding Privacy**: Private, password-protected, or public modes
- **Guest Verification**: Phone/name verification for security
- **RSVP Flow**: Token-based guest authentication

## Frontend Architecture (Next.js)

### Page Structure
```
app/
 [slug]/ # Dynamic wedding websites
 admin/ # Admin dashboard
 weddings/ # Multi-wedding management with search/filtering
 vendors/ # Vendor form builder and submission management
 planner/ # Wedding planner dashboard
 forms/ # Form builder and responses
 vendor-form/ # Public vendor forms (no login required)
 components/ # Reusable UI components
 contexts/ # State management
```

### Key Patterns
- **Dynamic Routing**: Wedding sites accessible via slug
- **Protected Routes**: Admin areas require authentication with role-based access
- **Multi-Tenant Dashboard**: Role-based views (ROOT_ADMIN vs Wedding Planner)
- **Public Form Access**: Vendor forms accessible via secure tokens (no login)
- **Component Library**: Reusable UI components with consistent styling
- **State Management**: React Context for global state and user profiles

## Multi-Tenant Features (Phase 3 - COMPLETED)

### Phase 3.1: Core Wedding Management
- **Multi-Wedding Dashboard**: Role-based filtering and assignment management
- **Wedding Creation Interface**: Planner assignment with auto-assignment for planners
- **Enhanced Permission System**: Fixed ObjectId handling, proper access control
- **Subscription Integration**: Enterprise plans with usage limit enforcement

### Phase 3.2: Wedding Organization & Archiving
- **Advanced Status Management**: 8-status workflow (Draft → Planning → Active → Confirmed → Completed → Archived → Cancelled → Postponed)
- **Search & Filtering System**: Multi-field search, status filters, date range filtering
- **Bulk Operations**: Multi-select with bulk status updates and deletion
- **Wedding Templates**: Pre-built templates for quick wedding setup (Traditional Nigerian, Simple Ceremony, Destination, Court Wedding)

### Phase 3.3: Simplified Vendor Management
- **Email-Based Vendor Forms**: No vendor accounts required, secure token access
- **Vendor Form Builder**: Type-specific templates with smart field generation
- **Professional Email System**: Branded vendor outreach with wedding context
- **Submission Management**: Approval workflow with print/PDF export capabilities
- **Instant Notifications**: Email alerts to planners on vendor submissions

### Key Technical Achievements
- **Role-Based Access Control**: Planners restricted to assigned weddings, ROOT_ADMIN platform oversight
- **Token-Based Security**: Secure vendor form access without authentication complexity
- **Professional Vendor Experience**: Mobile-optimized forms with clear wedding context
- **Automated Workflows**: Email notifications and status tracking throughout vendor process

## Development Workflow

### Code Quality
- **Type Safety**: Python with type hints, TypeScript for frontend
- **Pydantic Models**: Runtime validation and serialization
- **Error Handling**: Comprehensive exception handling
- **Logging**: Structured logging with different levels per environment

### Testing Strategy
- **Unit Tests**: Service layer testing with pytest
- **Integration Tests**: API endpoint testing
- **E2E Tests**: Playwright for frontend flows
- **Factories**: Test data generation

### Deployment
- **Backend**: DigitalOcean Ubuntu droplet with manual deployment script
- **Frontend**: Vercel with automatic GitHub integration
- **Database**: MongoDB with backup scripts
- **Environment**: Separate staging (local) and production configs

## Performance Considerations

### Caching Strategy
- **Redis Caching**: Optional Redis layer for performance
- **Database Optimization**: Proper indexing and connection pooling
- **Static Assets**: CDN-friendly cache headers
- **API Response Caching**: Conditional caching based on endpoint type

### Monitoring
- **Performance Metrics**: Request timing and slow query detection
- **Health Checks**: Endpoint monitoring and status reporting
- **Error Tracking**: Centralized error logging and alerting
- **Usage Analytics**: Subscription and feature usage tracking

## Security Architecture

### Authentication & Authorization
- **JWT Tokens**: Stateless authentication with configurable expiration
- **Role-Based Access**: Granular permissions system
- **Session Management**: Optional Redis-based session storage

### Data Protection
- **Input Validation**: Pydantic model validation on all inputs
- **SQL Injection Prevention**: MongoDB with proper query construction
- **XSS Protection**: Content Security Policy and output encoding
- **CSRF Protection**: Token-based protection for state-changing operations

### Compliance & Auditing
- **Audit Trail**: All security events logged with context
- **Data Privacy**: Guest data protection and access controls
- **Backup & Recovery**: Automated MongoDB backups

## Operational Patterns

### Configuration Management
- **Environment Variables**: All secrets and config via env vars
- **Feature Flags**: Runtime feature toggling
- **Settings Validation**: Type-safe configuration with defaults

### Error Recovery
- **Graceful Degradation**: Cache failures don't break functionality
- **Connection Resilience**: Automatic reconnection for database/cache
- **Fallback Behavior**: Default responses when external services fail

### Scalability Considerations
- **Async Operations**: Non-blocking I/O throughout the stack
- **Connection Pooling**: Efficient database connection management
- **Horizontal Scaling**: Stateless design allows multiple instances

## Development Guidelines

### Code Organization
- **Domain-Driven Design**: Clear separation between business logic and infrastructure
- **Dependency Injection**: Clean architecture with inverted dependencies
- **Single Responsibility**: Each module has a clear, focused purpose

### Best Practices
- **Type Safety**: Always use type hints and Pydantic models
- **Error Handling**: Comprehensive exception handling with proper logging
- **Testing**: Write tests for all business logic
- **Documentation**: Keep this file updated with architectural changes

### Common Patterns
- **Service Layer**: Business logic encapsulated in service classes
- **Repository Pattern**: Data access abstraction (via database collections)
- **Factory Pattern**: Consistent object creation (events, models)
- **Decorator Pattern**: Cross-cutting concerns (caching, authentication)

## Technology Stack Summary

**Backend:**
- FastAPI with async/await patterns
- Pydantic for data validation and serialization
- Motor for async MongoDB operations
- Redis for caching and session storage
- JWT for authentication

**Frontend:**
- Next.js 13+ with App Router
- TypeScript for type safety
- Tailwind CSS for styling
- React Context for state management

**Infrastructure:**
- MongoDB for primary data storage
- Redis for caching (optional)
- DigitalOcean for backend hosting
- Vercel for frontend hosting
- GitHub for source control and CI/CD triggers

This architecture provides a solid foundation for a scalable, secure, and maintainable wedding management SaaS platform with clear separation of concerns and robust error handling throughout the stack.