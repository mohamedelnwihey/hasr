"""Tests for X-RAY (finishing systems -> purchase list). Small in-memory IFC, hand-computed answers."""

import copy
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytest.importorskip("ifcopenshell")
from openpyxl import load_workbook

from hasr.cli import main as cli_main
from hasr.derived import derive
from hasr.extract import extract
from hasr.xray import GREEN, ORANGE, RED, analyze, load_systems, read_boq_rows
from test_derived import build


@pytest.fixture(scope="module")
def rooms(tmp_path_factory):
    d = tmp_path_factory.mktemp("x")
    ifc = str(d / "t.ifc")
    build(ifc)  # one room R1 / Room, 4 x 5 m, height 3 m
    _, _, _, recs = extract(ifc)
    _, extras = derive(ifc, recs)
    return extras["rooms"], str(d), ifc


def _approved(cfg):
    cfg = copy.deepcopy(cfg)
    for s in cfg["systems"].values():
        for c in s["components"]:
            c["approved"] = True
    return cfg


def test_purchase_math_with_declared_waste(rooms):
    res = analyze(rooms[0], _approved(load_systems()))
    p = {(x["system_en"], x["en"]): x for x in res["purchase"]}
    t = p[("Porcelain floor 60x60", "Porcelain tiles 60x60")]
    assert t["net"] == pytest.approx(20 / 0.36)
    assert t["gross"] == pytest.approx(20 / 0.36 * 1.10)
    assert t["packs"] == 16            # ceil(61.11 / 4)
    a = p[("Porcelain floor 60x60", "Tile adhesive")]
    assert a["net"] == pytest.approx(100.0) and a["packs"] == 5   # 105 kg / 25
    paint = p[("Wall paint (putty + primer + 2 coats)", "Paint, 2 coats")]
    assert paint["net"] == pytest.approx(54 * 0.25) and paint["packs"] == 1


def test_green_only_when_every_rate_is_approved(rooms):
    approved = analyze(rooms[0], _approved(load_systems()))
    assert all(s["status"] == GREEN for s in approved["scopes"])
    example = analyze(rooms[0], load_systems())
    assert all(s["status"] == ORANGE for s in example["scopes"])
    assert not any(c["approved"] for c in example["evidence"])


def test_unassigned_scope_is_red(rooms):
    cfg = load_systems()
    cfg["assignments"] = [a for a in cfg["assignments"] if a["scope"] != "ceiling"]
    res = analyze(rooms[0], cfg)
    ceil = [s for s in res["scopes"] if s["scope"] == "ceiling"][0]
    assert ceil["status"] == RED
    assert any(m["status"] == RED and "ceiling" in m["en"].lower() for m in res["missing"])


def test_required_item_missing_is_red(rooms):
    cfg = _approved(load_systems())
    cfg["required_items"] = [{"room_match": "room", "tags": ["waterproofing"],
                              "labels": {"waterproofing": ["العزل المائي", "Waterproofing"]}}]
    res = analyze(rooms[0], cfg)  # the plain floor system has no waterproofing component
    assert any(m["status"] == RED and "Waterproofing" in m["en"] for m in res["missing"])


def test_boq_double_counting_warning(rooms, tmp_path):
    boq = tmp_path / "b.csv"
    boq.write_text("م,وصف\n1,سقف جبس بورد معلق شامل الهيكل المعدني\n", encoding="utf-8")
    res = analyze(rooms[0], load_systems(), read_boq_rows(str(boq)))
    texts = [m["en"] for m in res["missing"] if m["where"].startswith("BOQ")]
    assert any("Metal framing channels" in t and "already mentions" in t for t in texts)
    assert any("Hangers" in t and "Check whether" in t for t in texts)
    # floor and paint have no BOQ row: red
    assert any("No item in your BOQ covers 'Porcelain floor 60x60'" in t for t in texts)


def test_no_rooms_is_red():
    res = analyze([], load_systems())
    assert res["missing"][0]["status"] == RED and not res["purchase"]


def test_evidence_row_explains_the_number(rooms):
    res = analyze(rooms[0], load_systems())
    e = [x for x in res["evidence"] if x["component_en"] == "Porcelain tiles 60x60"][0]
    assert e["base"] == pytest.approx(20.0) and "0.36" in e["formula"] and e["guid"]


def test_cli_writes_sheets(rooms, tmp_path):
    out = str(tmp_path / "o.xlsx")
    plan = str(tmp_path / "p.png")
    assert cli_main([rooms[2], "-o", out, "--xray", "--xray-plan", plan]) == 0
    wb = load_workbook(out)
    for n in ("X-RAY إيه اللي ناقص", "X-RAY قائمة المشتريات", "X-RAY دليل الأرقام"):
        assert n in wb.sheetnames
    assert os.path.getsize(plan) > 5000
