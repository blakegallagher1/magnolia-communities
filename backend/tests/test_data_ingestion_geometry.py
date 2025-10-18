"""Unit tests for ArcGIS geometry helper conversions."""

import pytest
from geoalchemy2 import WKTElement

from app.jobs.data_ingestion import DataIngestionJob


class TestArcGISGeometryConversion:
    """Validate conversion of ArcGIS geometries to WKT."""

    def test_polygon_with_hole_conversion(self):
        feature = {
            "geometry": {
                "rings": [
                    # Outer ring (clockwise orientation for ArcGIS polygons)
                    [
                        [0, 0],
                        [0, 10],
                        [10, 10],
                        [10, 0],
                        [0, 0],
                    ],
                    # Hole (counter-clockwise)
                    [
                        [2, 2],
                        [4, 2],
                        [4, 4],
                        [2, 4],
                        [2, 2],
                    ],
                ]
            }
        }

        geom = DataIngestionJob._arcgis_polygon_geometry(feature)

        assert isinstance(geom, WKTElement)
        assert geom.srid == 4326
        wkt = geom.data.upper()
        assert "POLYGON" in wkt
        assert "0 0" in wkt
        assert "10 10" in wkt
        assert "2 2" in wkt

    def test_point_conversion_prefers_geometry_coordinates(self):
        feature = {"geometry": {"x": -91.1875, "y": 30.4583}, "attributes": {}}
        lon, lat, geom = DataIngestionJob._arcgis_point_geometry(feature)

        assert lon == pytest.approx(-91.1875)
        assert lat == pytest.approx(30.4583)
        assert isinstance(geom, WKTElement)
        assert geom.srid == 4326
        assert geom.data == "POINT (-91.1875 30.4583)"

    def test_point_conversion_falls_back_to_attributes(self):
        feature = {
            "geometry": {},
            "attributes": {"LONGITUDE": "-91.5", "LATITUDE": "30.1"},
        }
        lon, lat, geom = DataIngestionJob._arcgis_point_geometry(feature)

        assert lon == pytest.approx(-91.5)
        assert lat == pytest.approx(30.1)
        assert geom.data == "POINT (-91.5 30.1)"
