"""Pillow-generated numeric labels; no Web or original graph images."""
from datetime import date
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import pytest
from collectors.pscube.graph import CONFIRMED_PROFILES, GraphProfile, estimate_graph
from collectors.pscube import axis_labels
from tests.test_graph import dashed_profile_fixture

DAY = date(2026, 10, 1)
TEMPLATES = json.loads((Path(__file__).parents[1] / "collectors/pscube/axis_templates.json").read_text())


def labeled_fixture(path, profile, *, missing=None, override=None, noise=False, unreadable=False, variant=0):
    dashed_profile_fixture(path, profile.top_medal // profile.step_medal, 400)
    with Image.open(path) as source:
        image = source.copy()
    for i, y in enumerate((20,129,238,348,457,567,676)):
        if i == missing:
            continue
        value = profile.top_medal-i*profile.step_medal
        if override and i in override:
            value = override[i]
        variants = TEMPLATES[str(value)]
        rows = min(variants, key=lambda rows: len(rows[0])) if variant == "plain" else variants[variant]
        mask = Image.new("L", (len(rows[0]), len(rows)))
        mask.putdata([255*int(bit) for row in rows for bit in row])
        image.paste("white", (65-mask.width, y-mask.height//2), mask)
    if noise:
        ImageDraw.Draw(image).rectangle((3, 124, 15, 133), fill="white")
    if unreadable:
        image = image.filter(ImageFilter.GaussianBlur(3))
    image.save(path)
    return path


@pytest.mark.parametrize("profile", CONFIRMED_PROFILES)
def test_all_profiles_and_a_d_disambiguation(tmp_path, profile):
    result = estimate_graph(labeled_fixture(tmp_path/"axis.png", profile), DAY, "0001")
    assert result.selected_profile == profile
    assert result.axis_recognition_confidence == "high"
    assert [label.recognized_value for label in result.axis_labels] == [profile.top_medal-i*profile.step_medal for i in range(7)]
    assert result.estimated_medal is not None


@pytest.mark.parametrize("kwargs", [
    {"missing": 1}, {"noise": True}, {"unreadable": True},
    {"override": {1: 1500}},  # repeated/nonuniform values
    {"override": {0: 5000}},  # one A label does not override D
])
def test_failures_return_none(tmp_path, kwargs):
    result = estimate_graph(labeled_fixture(tmp_path/"bad.png", CONFIRMED_PROFILES[3], **kwargs), DAY, "0001")
    assert result.selected_profile is None
    assert result.estimated_medal is None and result.confidence == "low"
    assert result.axis_recognition_confidence == "low"
    assert result.warnings


def test_zero_line_contradiction(tmp_path):
    path = labeled_fixture(tmp_path/"zero.png", CONFIRMED_PROFILES[3])
    with Image.open(path) as source:
        image = source.copy()
    draw = ImageDraw.Draw(image)
    draw.line((79,567,780,567), fill=(123,123,123))
    draw.line((79,348,780,348), fill="white")
    image.save(path)
    result = estimate_graph(path, DAY, "0001")
    assert result.selected_profile is None and result.estimated_medal is None
    assert "axis labels inconsistent" in result.warnings


def test_unknown_mathematically_consistent_profile(tmp_path):
    profile = GraphProfile(2000,-1000,500)
    result = estimate_graph(labeled_fixture(tmp_path/"unknown.png", profile), DAY, "0001")
    assert result.selected_profile is None and result.estimated_medal is None
    assert "axis profile ambiguous or unknown profile" in result.warnings


def test_plain_numeric_templates(tmp_path):
    # The narrowest label variant has no thousands separator.
    profile = CONFIRMED_PROFILES[3]
    result = estimate_graph(labeled_fixture(tmp_path/"plain.png", profile, variant="plain"), DAY, "0001")
    assert result.selected_profile == profile


def test_equal_template_scores_are_ambiguous(tmp_path, monkeypatch):
    path = labeled_fixture(tmp_path/"ambiguous.png", CONFIRMED_PROFILES[3])
    templates = axis_labels._templates()
    duplicate = next(mask for value, mask in templates if value == 2500)
    monkeypatch.setattr(axis_labels, "_templates", lambda: templates + ((5000, duplicate),))
    result = estimate_graph(path, DAY, "0001")
    assert result.axis_labels[0].recognized_value is None
    assert result.selected_profile is None and result.estimated_medal is None
