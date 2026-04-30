def test_main_app_imports_under_python_311():
    from importlib import reload

    import app.main as main_module

    reload(main_module)

    route_paths = {
        route.path for route in main_module.app.routes if hasattr(route, "path")
    }

    assert "/health/livez" in route_paths
    assert "/health" in route_paths
    assert "/admin/form-templates" in route_paths
