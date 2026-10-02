from datetime import date
from io import BytesIO
from unittest.mock import MagicMock
from PIL import Image, ImageDraw
import pytest
from collectors.pscube.graph import estimate_graph, annotate_graph, fetch_graph, GraphProfile
from collectors.pscube.client import PscubeClient
from common.exceptions import CollectorError
from jobs import inspect_pscube_graph as cli

DAY = date(2026,9,21)


def fixture(path, *, end_y=130, missing=False, unstable=False, line=True, early=False, size=1):
    im = Image.new("RGB", (400,380), "black")
    d = ImageDraw.Draw(im)
    d.line((40,20,40,320), fill=(140,140,140))
    for i in range(7):
        if missing and i==3: continue
        y=20+i*50+(15 if unstable and i==2 else 0)
        d.line((40,y,390,y), fill=(210,210,210) if i==5 else (120,120,120))
    if line:
        d.line([(40,270),(100,280),(160,210),(210 if early else 390,end_y)], fill=(245,115,220),width=2)
        d.point((385,60),fill=(255,100,240))  # isolated noise is not the endpoint
    if size != 1: im=im.resize((int(400*size),int(380*size)))
    im.save(path)
    return path


@pytest.mark.parametrize("scale", [1,2])
def test_positive_grid_and_endpoint(tmp_path, scale):
    p=fixture(tmp_path/'positive.png',size=scale)
    r=estimate_graph(p,DAY,'0272')
    assert len(r.horizontal_grid_y)==7
    assert r.zero_y == pytest.approx(270*scale, abs=1)
    assert r.step_px == pytest.approx(50*scale,abs=1)
    assert r.line_end_y == pytest.approx(130*scale,abs=2)
    assert r.estimated_medal == pytest.approx(2800,abs=40)
    assert r.confidence=='high'
    out=annotate_graph(r,tmp_path/'annotated')
    assert out.name=='20260921_0272.png'
    assert Image.open(out).size == Image.open(p).size


def test_negative(tmp_path):
    r=estimate_graph(fixture(tmp_path/'negative.png',end_y=300),DAY,'0272')
    assert r.estimated_medal == pytest.approx(-600,abs=20)


@pytest.mark.parametrize('kwargs',[{'missing':True},{'unstable':True},{'line':False}])
def test_unknown_returns_none(tmp_path,kwargs):
    r=estimate_graph(fixture(tmp_path/'bad.png',**kwargs),DAY,'0272')
    assert r.estimated_medal is None and r.confidence=='low'
    assert r.warnings


def test_early_end(tmp_path):
    r=estimate_graph(fixture(tmp_path/'early.png',early=True),DAY,'0272')
    assert r.confidence=='medium'
    assert r.line_end_x < r.plot_bounds[2]


def test_wrong_profile(tmp_path):
    r=estimate_graph(fixture(tmp_path/'wrong.png'),DAY,'0272',GraphProfile(4000,-2000))
    assert r.estimated_medal is None


def test_multiple_lines(tmp_path):
    path=fixture(tmp_path/'multi.png')
    im=Image.open(path);ImageDraw.Draw(im).line((100,70,350,70),fill=(255,100,230),width=2);im.save(path)
    assert estimate_graph(path,DAY,'0272').estimated_medal is None


def test_fetch_one_graph(monkeypatch,tmp_path):
    client=MagicMock(spec=PscubeClient)
    graph=MagicMock(business_date=DAY,src='20260921/sample.png?token=synthetic')
    detail=MagicMock(graphs=[graph],days=[MagicMock(unit_no='0272')])
    collect=MagicMock(return_value=detail)
    monkeypatch.setattr('collectors.pscube.graph.PscubeCollector.collect_unit',collect)
    stream=BytesIO();Image.new('RGB',(100,100)).save(stream,format='PNG')
    client.fetch_bytes.return_value=stream.getvalue()
    url='https://example.invalid/h/test/cgi-bin/nc-v06-001.php?cd_dai=0272'
    out=fetch_graph(client,url,DAY,'0272',tmp_path)
    assert out.name=='20260921_0272.png'
    client.fetch_bytes.assert_called_once_with('https://example.invalid/h/test/graph/20260921/sample.png?token=synthetic',headers={'Referer':url})
    graph.src='https://other.invalid/image.png'
    with pytest.raises(CollectorError):fetch_graph(client,url,DAY,'0272',tmp_path)
    assert client.fetch_bytes.call_count==1


def test_offline_cli(monkeypatch,tmp_path,capsys):
    path=fixture(tmp_path/'cli.png')
    monkeypatch.setattr(cli,'ROOT',tmp_path)
    monkeypatch.setattr(cli,'configure_logging',lambda:None)
    assert cli.main(['--unit','0272','--date','20260921','--image',str(path),'--annotate'])==0
    assert '"grid_line_count": 7' in capsys.readouterr().out


def test_no_grid(tmp_path):
    path=tmp_path/'blank.png';Image.new('RGB',(400,380)).save(path)
    assert estimate_graph(path,DAY,'0272').estimated_medal is None


@pytest.mark.parametrize("color", [(100, 60, 220), (30, 170, 230)])
def test_symmetric_profile_and_color(tmp_path, color):
    path = fixture(tmp_path / 'symmetric.png', line=False)
    with Image.open(path) as im:
        draw = ImageDraw.Draw(im)
        draw.line((40,270,390,270), fill=(120,120,120))
        draw.line((40,170,390,170), fill=(210,210,210))
        draw.line([(40,170),(120,210),(250,100),(389,30)], fill=color, width=2)
        im.save(path)
    result = estimate_graph(path, DAY, '0272')
    assert result.selected_profile == GraphProfile(1500,-1500,500)
    assert result.zero_y == 170
    assert result.estimated_medal == pytest.approx(1400, abs=15)


def test_ambiguous_axis_requires_explicit_profile(tmp_path):
    path = fixture(tmp_path / 'ambiguous.png', line=False)
    with Image.open(path) as im:
        ImageDraw.Draw(im).line((40,270,390,270), fill=(120,120,120))
        ImageDraw.Draw(im).line([(40,280),(150,210),(389,130)], fill=(245,115,220), width=2)
        im.save(path)
    assert estimate_graph(path, DAY, '0272').estimated_medal is None
    assert estimate_graph(path, DAY, '0272', GraphProfile()).estimated_medal is not None


def test_original_geometry_regression(tmp_path):
    path = tmp_path / 'original.png'
    im = Image.new('RGB', (800,730), 'black')
    draw = ImageDraw.Draw(im)
    draw.line((79,20,79,676), fill=(140,140,140))
    for y in (20,129,238,348,457,567,676):
        draw.line((79,y,780,y), fill=(210,210,210) if y==567 else (120,120,120))
    draw.line([(79,567),(250,590),(500,400),(779,211)],fill=(245,115,220))
    im.save(path)
    assert estimate_graph(path, DAY, '0272').estimated_medal == 3256


@pytest.mark.parametrize('values', [(True,-1000,1000),(5000,-1000,False),(5000.0,-1000,1000)])
def test_profile_rejects_nonintegers(values):
    with pytest.raises(ValueError):
        GraphProfile(*values)
