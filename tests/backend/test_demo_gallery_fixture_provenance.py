from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = ROOT / "docs" / "marketing" / "demo-gallery-fixture-provenance.md"
GALLERY = ROOT / "public" / "demo-gallery"

FIXTURES = {
    "sofia-daniel-terrace.webp": {
        "sha256": "b0c1ae45b2d377618a518a999b0599fbf33d37d36442c2842e5cce6c9b05f453",
        "source": "exec-3e5fcdf3-d2a0-4ab0-b469-f631e2eb9bfb.png",
        "source_sha256": (
            "f87e365ddbad216ae1a9315e9d388ad17d4fc62ea138b178ece3ae1e33bc1294"
        ),
        "source_size": "1586x992",
    },
    "sofia-daniel-ceremony.webp": {
        "sha256": "d56ac91b101c697bce3b23d60e5d9dd6b58386e40c56b7ed8b67c813794d1f0c",
        "source": "exec-2dc68bfc-29a2-4071-b679-2024e20f4f9f.png",
        "source_sha256": (
            "59f8f18984ca3706f28c7c54a8c3488fe210cab63dc5e09cc30ddaf4d35a4f83"
        ),
        "source_size": "1536x1024",
    },
    "sofia-daniel-reception.webp": {
        "sha256": "829bb93d0538cb772b402c22b275f94eeb3a8fc9562039ddcbad9e736c1bb661",
        "source": "exec-3ab19a4d-08cd-4d40-9578-6191858588cc.png",
        "source_sha256": (
            "71615b2518ac10c0b817e371c980280c5608c5d6cdbea7d7befef666f78d7550"
        ),
        "source_size": "1536x1024",
    },
}


def test_committed_demo_gallery_fixtures_match_the_provenance_ledger():
    source = PROVENANCE.read_text()

    for filename, record in FIXTURES.items():
        path = GALLERY / filename

        assert path.is_file()
        assert sha256(path.read_bytes()).hexdigest() == record["sha256"]
        with Image.open(path) as image:
            assert image.format == "WEBP"
            assert image.size == (1600, 1000)

        assert filename in source
        assert record["sha256"] in source
        assert record["source"] in source
        assert record["source_sha256"] in source
        assert record["source_size"] in source


def test_provenance_records_generation_conversion_and_privacy_contracts():
    source = PROVENANCE.read_text()

    required_evidence = (
        "image_gen.imagegen",
        'resize(1600, 1000, { fit: "cover", position: "centre" })',
        ".webp({ quality: 92 })",
        "overwritten by the Sharp outputs",
        "no identifiable faces are visible",
        "No people.",
        "No stock or third-party photography was used or incorporated.",
        "Fictional capture fixture generated for The Special Wedding",
    )

    for evidence in required_evidence:
        assert evidence in source
