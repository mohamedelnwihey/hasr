"""Automated tests for hasr v0.1.2 — run: python3 -m pytest tests/ -v

Sample files are NOT bundled (third-party licenses unclear); tests that need
them skip when absent. See samples/README.md for fetch commands and provenance.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openpyxl import load_workbook

from hasr.cli import main as cli_main
from hasr.extract import (
    STATUS_GEOMETRY,
    STATUS_NO_QUANTITY,
    STATUS_OK,
    STATUS_UNCLASSIFIED,
    ElementRecord,
    _unit_factors,
    aggregate,
    extract,
    summarize_issues,
)
from hasr.items import UNITS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
SAMPLE_2X3 = os.path.join(SAMPLES, "building-architecture.ifc")
SAMPLE_4 = os.path.join(SAMPLES, "wall-with-opening-and-window.ifc")
SAMPLE_RAC = os.path.join(SAMPLES, "rac-advanced-sample.ifc")


def _rec(status, value, item=("حوائط", "Walls", "m3")):
    return ElementRecord(
        guid="g", ifc_type="IfcWall", name="", storey="", material="",
        item_ar=item[0], item_en=item[1], unit_key=item[2],
        status=status, value=value,
    )


def test_provenance_breakdown():
    lines = aggregate([
        _rec(STATUS_OK, 1.5),
        _rec(STATUS_OK, 2.5),
        _rec(STATUS_GEOMETRY, 4.0),
        _rec(STATUS_NO_QUANTITY, None),
        _rec(STATUS_UNCLASSIFIED, 9.9),  # must never appear
    ])
    stats = list(lines.values())[0]
    assert stats["qty"] == 8.0 and stats["file_qty"] == 4.0 and stats["geo_qty"] == 4.0
    assert stats["file_n"] == 2 and stats["geo_n"] == 1 and stats["missing_n"] == 1
    from hasr.excel import _coverage_label, _source_label
    assert _source_label(stats).startswith("مختلط")
    assert _coverage_label(stats) == "3/4"
    only_file = aggregate([_rec(STATUS_OK, 1.0)])[("حوائط", "Walls", "m3")]
    assert _source_label(only_file).startswith("ملف")
    only_geo = aggregate([_rec(STATUS_GEOMETRY, 1.0)])[("حوائط", "Walls", "m3")]
    assert _source_label(only_geo).startswith("هندسي")
    print("OK provenance: mixed/file/geometry labels + coverage math, unclassified excluded")


def test_extract_ifc2x3():
    if not os.path.exists(SAMPLE_2X3):
        pytest.skip("ifc2x3 sample missing (see samples/README.md)")
    project, schema, unit_note, records = extract(SAMPLE_2X3)
    assert schema == "IFC2X3"
    assert len(records) == 13
    unclassified, no_qty, geometry = summarize_issues(records)
    assert len(unclassified) == 5
    assert all(r.status == STATUS_UNCLASSIFIED for r in unclassified)
    lines = aggregate(records)
    assert not any(k[1] == "Other items" for k in lines), "proxies leaked into totals"
    kinds = {(k[1], k[2]) for k in lines}
    assert ("Masonry works - Walls", "m3") in kinds, kinds
    assert ("Gypsum board walls", "m2") in kinds, kinds
    # file quantities dominate this sample; every row's coverage is complete or flagged
    for stats in lines.values():
        have = stats["file_n"] + stats["geo_n"]
        assert have > 0
    print(f"OK ifc2x3: {len(records)} elements, {len(lines)} rows, "
          f"unclassified={len(unclassified)}, no_qty={len(no_qty)}, geo={len(geometry)}")


def test_extract_ifc4():
    if not os.path.exists(SAMPLE_4):
        pytest.skip("ifc4 sample missing (see samples/README.md)")
    project, schema, unit_note, records = extract(SAMPLE_4)
    assert schema.startswith("IFC4"), schema
    types = {r.ifc_type for r in records}
    assert types == {"IfcWall", "IfcWindow"}, types
    windows = [r for r in records if r.ifc_type == "IfcWindow"]
    assert windows[0].value == 1.0 and windows[0].unit_key == "count"
    walls = [r for r in records if r.ifc_type == "IfcWall"]
    assert walls[0].status != STATUS_OK, "quantity-less wall must not read as a file quantity"
    lines = aggregate(records)
    win_stats = [s for k, s in lines.items() if k[1] == "Windows"][0]
    assert win_stats["qty"] == 1.0 and win_stats["file_n"] == 1
    print(f"OK ifc4: window counted, wall flagged/estimated, {len(lines)} rows")


def test_unit_conversion_factors():
    import ifcopenshell

    # mixed project: lengths in mm, areas and volumes already in m2/m3
    f = ifcopenshell.file(schema="IFC2X3")
    units = [
        f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE"),
        f.create_entity("IfcSIUnit", UnitType="AREAUNIT", Name="SQUARE_METRE"),
        f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE"),
    ]
    f.create_entity("IfcUnitAssignment", Units=units)
    lf, af, vf, _ = _unit_factors(f)
    assert abs(lf - 0.001) < 1e-12 and af == 1.0 and vf == 1.0, (lf, af, vf)
    # uniform metre project
    f2 = ifcopenshell.file(schema="IFC2X3")
    si2 = f2.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    f2.create_entity("IfcUnitAssignment", Units=[si2])
    lf2, af2, vf2, _ = _unit_factors(f2)
    assert (lf2, af2, vf2) == (1.0, 1.0, 1.0), (lf2, af2, vf2)
    if os.path.exists(SAMPLE_2X3):
        _, _, _, records = extract(SAMPLE_2X3)
        vols = {r.name: r.value for r in records if r.item_en == "Reinforced concrete - Slabs"}
        assert vols and max(vols.values()) > 1.0, f"volumes look wrongly downscaled: {vols}"
    print("OK unit factors: mm-length + m2/m3 project handled")


def test_classification_honesty():
    from hasr.items import UNCLASSIFIED as UNCL, classify
    assert classify("IfcSlab", "concrete_reinforced_in-situ")[1] == "Reinforced concrete - Slabs"
    assert classify("IfcSlab", "concrete")[1] == "Concrete - Slabs"   # plain concrete stays neutral
    assert classify("IfcSlab", "")[1] == "Slabs"                       # no material: no assertion
    assert classify("IfcBeam", "concrete")[1] == "Concrete - Beams"
    assert classify("IfcBuildingElementProxy", "anything") == UNCL
    print("OK classification: RC needs explicit reinforced, plain concrete neutral")


def test_per_quantity_unit_override_ifc4():
    import ifcopenshell
    import ifcopenshell.guid

    f = ifcopenshell.file(schema="IFC4")
    project_length = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE")
    f.create_entity("IfcUnitAssignment", Units=[project_length])
    milli = f.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Prefix="MILLI", Name="METRE")
    q = f.create_entity("IfcQuantityLength", Name="Length", Unit=milli, LengthValue=500.0)
    qto = f.create_entity("IfcElementQuantity", Name="Qto", Quantities=[q])
    wall = f.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="w")
    f.create_entity("IfcRelDefinesByProperties",
                    GlobalId=ifcopenshell.guid.new(),
                    RelatedObjects=[wall], RelatingPropertyDefinition=qto)
    from hasr.extract import _read_quantities
    lf, af, vf, _ = _unit_factors(f)
    quantities = _read_quantities(wall, (lf, af, vf))
    assert abs(quantities["Length"] - 0.5) < 1e-9, quantities  # 500mm -> 0.5m despite m project
    print("OK per-quantity unit override: 500mm quantity honored over m project unit")


def test_duplicate_quantity_never_summed():
    import ifcopenshell
    import ifcopenshell.guid

    f = ifcopenshell.file(schema="IFC2X3")
    si = f.create_entity("IfcSIUnit", UnitType="VOLUMEUNIT", Name="CUBIC_METRE")
    f.create_entity("IfcUnitAssignment", Units=[si])
    wall = f.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="w")
    for vol in (1.0, 2.0):
        q = f.create_entity("IfcQuantityVolume", Name="NetVolume", VolumeValue=vol)
        qto = f.create_entity("IfcElementQuantity", Name="Qto", Quantities=[q])
        f.create_entity("IfcRelDefinesByProperties",
                        GlobalId=ifcopenshell.guid.new(),
                        RelatedObjects=[wall], RelatingPropertyDefinition=qto)
    from hasr.extract import _read_quantities
    factors = _unit_factors(f)[:3]
    quantities = _read_quantities(wall, factors)
    assert quantities["NetVolume"] == 2.0, quantities  # last wins, never 3.0
    print("OK duplicate quantity sets: last wins, no double counting")


def test_workbook(tmp_path):
    if not os.path.exists(SAMPLE_2X3):
        pytest.skip("workbook sample missing (see samples/README.md)")
    tmp_out = str(tmp_path / "hasr-boq.xlsx")
    rc = cli_main([SAMPLE_2X3, "-o", tmp_out])
    assert rc == 0 and os.path.exists(tmp_out)
    wb = load_workbook(tmp_out)
    assert wb.sheetnames == ["جدول الكميات", "تفاصيل العناصر"]
    ws = wb["جدول الكميات"]
    assert ws.sheet_view.rightToLeft is True
    header = [ws.cell(row=5, column=c).value for c in range(1, 8)]
    assert header == ["م", "البند (عربي)", "Item (English)", "الوحدة", "الكمية الإجمالية",
                      "المصدر", "التغطية"], header
    row = 6
    seen = 0
    while ws.cell(row=row, column=1).value is not None and isinstance(
        ws.cell(row=row, column=1).value, int
    ):
        unit_cell = ws.cell(row=row, column=4).value or ""
        assert any(f"({en})" in unit_cell for _, en in UNITS.values()), unit_cell
        assert isinstance(ws.cell(row=row, column=5).value, (int, float))
        source_cell = str(ws.cell(row=row, column=6).value or "")
        assert any(tag in source_cell for tag in ("ملف", "هندسي", "مختلط")), source_cell
        coverage = str(ws.cell(row=row, column=7).value or "")
        have, _, total = coverage.partition("/")
        assert have.isdigit() and total.isdigit() and 0 < int(have) <= int(total), coverage
        seen += 1
        row += 1
    assert seen >= 3, f"expected >=3 BOQ rows, got {seen}"
    texts = []
    for r in range(row, row + 7):
        v = ws.cell(row=r, column=1).value
        if v:
            texts.append(str(v))
    joined = "\n".join(texts)
    assert "ملاحظات" in joined, "notes heading missing"
    assert "غير مصنّفة" in joined or "unclassified" in joined.lower()
    ws2 = wb["تفاصيل العناصر"]
    assert ws2.cell(row=1, column=9).value == "الحالة"
    assert ws2.cell(row=2, column=10).value, "GUID column empty"
    statuses = [ws2.cell(row=r, column=9).value for r in range(2, 15)]
    assert any("غير مصنّف" in str(s) for s in statuses), statuses
    print(f"OK workbook: {seen} rows, per-row source + coverage, notes flag exclusions")


def test_real_revit_export_geometry_fallback():
    if not os.path.exists(SAMPLE_RAC):
        pytest.skip("rac sample missing (see samples/README.md)")
    import ifcopenshell

    project, schema, unit_note, records = extract(SAMPLE_RAC)
    unclassified, no_qty, geometry = summarize_issues(records)
    lines = aggregate(records)
    # independent ground truth: entity counts straight from the file
    model = ifcopenshell.open(SAMPLE_RAC)
    assert len(model.by_type("IfcDoor")) == 100
    assert len(model.by_type("IfcWindow")) == 24
    door_stats = [s for k, s in lines.items() if k[1] == "Doors"][0]
    win_stats = [s for k, s in lines.items() if k[1] == "Windows"][0]
    assert door_stats["qty"] == 100 and win_stats["qty"] == 24
    # geometry fallback estimates real volumes/areas for structural elements
    assert len(geometry) > 100, f"geometry fallback too small: {len(geometry)}"
    vol_lines = {k[1]: s["qty"] for k, s in lines.items() if k[2] == "m3"}
    assert vol_lines, "no volumetric BOQ rows on a real building"
    # plausible magnitudes for a real two-story house, in meters
    assert all(0.1 < v < 10000 for v in vol_lines.values()), vol_lines
    # every geometry value is labeled estimated, none reads as a file quantity
    assert all(r.status == STATUS_GEOMETRY for r in geometry)
    geo_rows = [k[1] for k, s in lines.items() if s["geo_n"] > 0]
    assert geo_rows, "no geometry-sourced rows"
    print(f"OK real Revit export: doors=100 windows=24 match entity counts, "
          f"{len(geometry)} geometry-estimated, rows={len(lines)}")


def test_missing_file():
    rc = cli_main(["/nonexistent/model.ifc"])
    assert rc == 2
    print("OK missing-file handling (exit 2)")


if __name__ == "__main__":
    test_provenance_breakdown()
    test_extract_ifc2x3()
    test_extract_ifc4()
    test_unit_conversion_factors()
    test_classification_honesty()
    test_per_quantity_unit_override_ifc4()
    test_duplicate_quantity_never_summed()
    test_workbook("/tmp/hasr-test-boq.xlsx")
    test_real_revit_export_geometry_fallback()
    test_missing_file()
    print("ALL TESTS PASSED")
