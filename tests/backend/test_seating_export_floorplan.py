from app.services.seating_export_service import SeatingExportService


def test_visual_pdf_layout_includes_floor_plan_backdrop_and_fixtures():
    service = SeatingExportService.__new__(SeatingExportService)

    html = service._generate_visual_layout(
        tables=[
            {
                "_id": "table-1",
                "name": "Table 1",
                "shape": "round",
                "capacity": 8,
                "x": 360,
                "y": 260,
            }
        ],
        guests_by_table={"table-1": [{"name": "Ada Lovelace"}]},
        unseated_guests=[],
        wedding_name="Ava and Noah",
        paper_size="poster",
        seating_layout={
            "canvas_width": 1600,
            "canvas_height": 1000,
            "background_image_data_url": "data:image/png;base64,abc123",
            "scale_pixels": 100,
            "scale_distance": 10,
            "scale_unit": "ft",
            "outline": [
                {"x": 120, "y": 100},
                {"x": 1480, "y": 100},
                {"x": 1480, "y": 900},
                {"x": 120, "y": 900},
            ],
            "fixtures": [
                {
                    "id": "dance-floor-1",
                    "type": "dance_floor",
                    "label": "Dance Floor",
                    "x": 500,
                    "y": 420,
                    "width": 260,
                    "height": 180,
                    "rotation": 15,
                }
            ],
        },
    )

    assert 'class="floor-plan-image"' in html
    assert 'src="data:image/png;base64,abc123"' in html
    assert 'points="120.0,100.0 1480.0,100.0 1480.0,900.0 120.0,900.0"' in html
    assert 'class="fixture-card"' in html
    assert "rotate(15deg)" in html
    assert 'class="scale-ruler"' in html
    assert "10ft" in html
    assert "Dance Floor" in html
    assert "Ada Lovelace" in html
