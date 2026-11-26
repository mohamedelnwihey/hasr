"""Tests for derived quantities (v0.3). Uses a small IFC built in-memory, no samples needed."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ifcopenshell = pytest.importorskip("ifcopenshell")
import ifcopenshell.api
import numpy as np
from openpyxl import load_workbook

from hasr.cli import main as cli_main


def _box(f, ctx, size, origin_z=0.0):
    x, y, z = size
    prof = f.createIfcRectangleProfileDef("AREA", None, f.createIfcAxis2Placement2D(
        f.createIfcCartesianPoint((x / 2, y / 2)), None), x, y)
    solid = f.createIfcExtrudedAreaSolid(prof, f.createIfcAxis2Placement3D(
        f.createIfcCartesianPoint((0.0, 0.0, origin_z)), None, None),
        f.createIfcDirection((0.0, 0.0, 1.0)), z)
    return f.createIfcShapeRepresentation(ctx, "Body", "SweptSolid", [solid])


def build(path):
    f = ifcopenshell.api.run("project.create_file", version="IFC4")
    proj = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcProject", name="T")
    ifcopenshell.api.run("unit.assign_unit", f, length={"is_metric": True, "raw": "METERS"})
    ctx = ifcopenshell.api.run("context.add_context", f, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", f, context_type="Model",
                                context_identifier="Body", target_view="MODEL_VIEW", parent=ctx)
    site = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSite", name="S")
    bld = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuilding", name="B")
    st = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcBuildingStorey", name="Ground")
    ifcopenshell.api.run("aggregate.assign_object", f, products=[site], relating_object=proj)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[bld], relating_object=site)
    ifcopenshell.api.run("aggregate.assign_object", f, products=[st], relating_object=bld)

    def add(cls, name, size, material=None):
        el = ifcopenshell.api.run("root.create_entity", f, ifc_class=cls, name=name)
        ifcopenshell.api.run("geometry.assign_representation", f, product=el,
                             representation=_box(f, body, size))
        ifcopenshell.api.run("spatial.assign_container", f, products=[el], relating_structure=st)
        if material:
            m = ifcopenshell.api.run("material.add_material", f, name=material)
            ifcopenshell.api.run("material.assign_material", f, products=[el], material=m)
        return el

    add("IfcWall", "W1", (5.0, 0.2, 3.0), "Brick masonry")        # faces 2*5*3 = 30
    add("IfcSlab", "S1", (4.0, 5.0, 0.2), "Reinforced concrete")  # vol 4, formwork 20+2*(9*0.2)=23.6
    add("IfcColumn", "C1", (0.3, 0.3, 3.0), "Concrete")           # vertical 4*0.3*3 = 3.6
    add("IfcSlab", "S2", (2.0, 2.0, 0.2))                         # no material: no formwork
    sp = ifcopenshell.api.run("root.create_entity", f, ifc_class="IfcSpace", name="R1")
    sp.LongName = "Room"
    ifcopenshell.api.run("geometry.assign_representation", f, product=sp,
                         representation=_box(f, body, (4.0, 5.0, 3.0)))
    ifcopenshell.api.run("aggregate.assign_object", f, products=[sp], relating_object=st)
    f.write(path)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    d = tmp_path_factory.mktemp("d")
    ifc, out = str(d / "t.ifc"), str(d / "t.xlsx")
    build(ifc)
    ratios = d / "r.csv"
    ratios.write_text("family,kg_per_m3\nslabs,100\ncolumns,\n")
    assert cli_main([ifc, "-o", out, "--rebar", str(ratios)]) == 0
    wb = load_workbook(out)
    rows = {}
    for r in wb["جدول الكميات"].iter_rows(min_row=6, values_only=True):
        if r[2]:
            rows[r[2]] = r[4]
    return wb, rows


def test_wall_faces_plaster_paint(run):
    _, rows = run
    assert rows["Wall faces, both sides (derived)"] == pytest.approx(30.0, abs=0.01)
    assert rows["Wall plaster (derived)"] == pytest.approx(30.0, abs=0.01)
    assert rows["Wall paint (derived)"] == pytest.approx(30.0, abs=0.01)


def test_formwork_only_for_concrete(run):
    _, rows = run
    assert rows["Formwork - Slabs"] == pytest.approx(23.6, abs=0.01)  # S2 has no material: excluded
    assert rows["Formwork - Columns"] == pytest.approx(3.6, abs=0.01)


def test_rebar_uses_only_user_ratio(run):
    _, rows = run
    # slabs 100 kg/m3 on the one concrete slab (4 m3) = 0.4 t; columns ratio blank: no row
    key = "Reinforcement steel - Slabs (user ratio)"
    assert rows[key] == pytest.approx(0.4, abs=0.001)
    assert not any("Columns (user ratio)" in k for k in rows)


def test_room_finishes(run):
    _, rows = run
    assert rows["Room floor finish"] == pytest.approx(20.0, abs=0.01)
    assert rows["Room skirting (perimeter)"] == pytest.approx(18.0, abs=0.01)
    assert rows["Room wall finish"] == pytest.approx(54.0, abs=0.01)


def test_extra_sheets_exist(run):
    wb, _ = run
    for name in ("الكميات حسب الدور", "جدول الغرف", "افتراضات الكميات المشتقة"):
        assert name in wb.sheetnames
    assert any(r[0] == "R1" for r in wb["جدول الغرف"].iter_rows(min_row=2, values_only=True))


def test_no_derived_flag(tmp_path):
    ifc, out = str(tmp_path / "t.ifc"), str(tmp_path / "t.xlsx")
    build(ifc)
    assert cli_main([ifc, "-o", out, "--no-derived"]) == 0
    assert "جدول الغرف" not in load_workbook(out).sheetnames


RAC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "samples", "rac-advanced-sample.ifc")


@pytest.mark.skipif(not os.path.exists(RAC), reason="sample not fetched")
def test_revit_sample_schedule_and_storeys(tmp_path):
    out = str(tmp_path / "r.xlsx")
    assert cli_main([RAC, "-o", out]) == 0
    wb = load_workbook(out)
    ops = list(wb["جدول الأبواب والشبابيك"].iter_rows(min_row=2, values_only=True))
    assert sum(r[5] for r in ops if r[0] == "Door") == 100
    assert sum(r[5] for r in ops if r[0] == "Window") == 24
    # per-storey totals add up to the BOQ total for doors
    ws = wb["الكميات حسب الدور"]
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[1] == "Doors":
            assert r[-1] == 100
