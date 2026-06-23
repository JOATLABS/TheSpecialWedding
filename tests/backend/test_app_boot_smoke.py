def _collect_route_paths(app) -> set[str]:
    """Collect concrete route paths across eager and lazy FastAPI routers."""
    route_paths: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if path is not None:
            route_paths.add(path)
            continue

        effective_route_contexts = getattr(route, "effective_route_contexts", None)
        if effective_route_contexts is None:
            continue

        route_paths.update(
            context.path
            for context in effective_route_contexts()
            if getattr(context, "path", None) is not None
        )
    return route_paths


def test_main_app_imports_under_python_311():
    from importlib import reload

    import app.main as main_module

    reload(main_module)

    route_paths = _collect_route_paths(main_module.app)

    assert "/health/livez" in route_paths
    assert "/health" in route_paths
    assert "/admin/form-templates" in route_paths
