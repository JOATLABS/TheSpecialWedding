# ADR-002: Use FastAPI for Backend API Framework

## Status
Accepted

## Context
We need a backend API framework that can:
- Handle high concurrent load for multiple weddings
- Provide automatic API documentation
- Support async operations for database and external service calls
- Offer strong typing and validation
- Integrate well with Python ecosystem

## Decision
We will use FastAPI as our backend API framework with Python 3.11+.

## Consequences

### Positive
- **Performance**: One of the fastest Python frameworks, built on Starlette and Pydantic
- **Automatic Documentation**: OpenAPI (Swagger) and ReDoc documentation generated automatically
- **Type Safety**: Full type hints support with runtime validation via Pydantic
- **Async Support**: Native async/await support for high concurrency
- **Developer Experience**: Excellent IDE support with autocompletion
- **Standards-based**: Built on OpenAPI, JSON Schema, and OAuth2 standards
- **Testing**: Easy to test with built-in TestClient
- **WebSocket Support**: Real-time capabilities when needed

### Negative
- **Maturity**: Younger than Django/Flask with smaller ecosystem
- **ORM**: No built-in ORM, requires separate solution (we use Motor for MongoDB)
- **Admin Interface**: No built-in admin panel like Django
- **Learning Curve**: Async programming can be complex for developers new to it

### Neutral
- **Minimalist**: Provides core API functionality, requires additional libraries for full features
- **Community Size**: Growing rapidly but smaller than Django/Flask

## Alternatives Considered
1. **Django + DRF**: More features but heavier and slower
2. **Flask**: More mature but requires more setup for similar features
3. **Tornado**: Good async support but less modern API design
4. **Sanic**: Similar async capabilities but less feature-rich

## Implementation Details
```python
# Example FastAPI endpoint with automatic validation
@app.post("/api/weddings", response_model=Wedding)
async def create_wedding(
    wedding: WeddingCreate,  # Pydantic model for validation
    current_user: User = Depends(get_current_user),  # Dependency injection
    db: AsyncIOMotorDatabase = Depends(get_database)  # Async database
) -> Wedding:
    # Automatic request validation and serialization
    return await wedding_service.create(db, wedding, current_user)
```

## References
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [FastAPI Performance Benchmarks](https://www.techempower.com/benchmarks/)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)