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
    r=estimate_graph(p,DAY,'0272',GraphProfile())
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
    r=estimate_graph(fixture(tmp_path/'negative.png',end_y=300),DAY,'0272',GraphProfile())
    assert r.estimated_medal == pytest.approx(-600,abs=20)


@pytest.mark.parametrize('kwargs',[{'missing':True},{'unstable':True},{'line':False}])
def test_unknown_returns_none(tmp_path,kwargs):
    r=estimate_graph(fixture(tmp_path/'bad.png',**kwargs),DAY,'0272',GraphProfile())
    assert r.estimated_medal is None and r.confidence=='low'
    assert r.warnings


def test_early_end(tmp_path):
    r=estimate_graph(fixture(tmp_path/'early.png',early=True),DAY,'0272',GraphProfile())
    assert r.confidence=='medium'
    assert r.line_end_x < r.plot_bounds[2]


def test_wrong_profile(tmp_path):
    r=estimate_graph(fixture(tmp_path/'wrong.png'),DAY,'0272',GraphProfile(4000,-2000))
    assert r.estimated_medal is None


def test_multiple_lines(tmp_path):
    path=fixture(tmp_path/'multi.png')
    im=Image.open(path);ImageDraw.Draw(im).line((100,70,350,70),fill=(255,100,230),width=2);im.save(path)
    assert estimate_graph(path,DAY,'0272',GraphProfile()).estimated_medal is None


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
    assert cli.main(['--unit','0272','--date','20260921','--image',str(path),'--annotate',
                     '--top-medal','5000','--bottom-medal','-1000','--step-medal','1000'])==0
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
    result = estimate_graph(path, DAY, '0272', GraphProfile(1500,-1500,500))
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
    assert estimate_graph(path, DAY, '0272', GraphProfile()).estimated_medal == 3256


@pytest.mark.parametrize('values', [(True,-1000,1000),(5000,-1000,False),(5000.0,-1000,1000)])
def test_profile_rejects_nonintegers(values):
    with pytest.raises(ValueError):
        GraphProfile(*values)


def profile_c_fixture(path, *, emphasized=(6,), end_y=646):
    image = Image.new('RGB', (800, 730), 'black')
    draw = ImageDraw.Draw(image)
    draw.line((79, 20, 79, 676), fill=(140, 140, 140))
    for index, y in enumerate((20, 129, 238, 348, 457, 567, 676)):
        draw.line((79, y, 780, y), fill=(255, 255, 255) if index in emphasized else (123, 123, 123))
    draw.line([(79, 675), (250, 600), (500, 560), (779, end_y)], fill=(100, 60, 220))
    image.save(path)
    return path


@pytest.mark.parametrize('unit,day', [('0100', date(2026, 10, 1)), ('0042', DAY)])
def test_profile_c_boundary_zero(tmp_path, unit, day):
    result = estimate_graph(profile_c_fixture(tmp_path / 'c.png'), day, unit, GraphProfile(3000,0,500))
    assert result.selected_profile == GraphProfile(3000, 0, 500)
    assert result.zero_y == 676
    assert result.step_px == pytest.approx(656 / 6)
    assert (result.line_end_x, result.line_end_y) == (779, 646)
    # Derive expected medals from generated geometry, not a supplied comparison value.
    assert result.estimated_medal == round((676 - 646) / (656 / 6) * 500)
    assert result.confidence == 'high'


@pytest.mark.parametrize('emphasized', [(), (3, 6), (5, 6), (0, 6), (0,)])
def test_profile_c_ambiguous_or_unsupported_zero(tmp_path, emphasized):
    result = estimate_graph(profile_c_fixture(tmp_path / 'ambiguous_c.png', emphasized=emphasized), DAY, '0100')
    assert result.estimated_medal is None and result.confidence == 'low'
    assert result.selected_profile is None
    assert result.warnings


def test_profile_c_explicit_and_wrong_profile(tmp_path):
    path = profile_c_fixture(tmp_path / 'explicit_c.png')
    result = estimate_graph(path, DAY, '0100', GraphProfile(3000, 0, 500))
    assert result.estimated_medal is not None
    for profile in (GraphProfile(), GraphProfile(1500, -1500, 500)):
        result = estimate_graph(path, DAY, '0100', profile)
        assert result.estimated_medal is None and result.confidence == 'low'


def dashed_profile_fixture(path, zero_index, end_y):
    image = Image.new('RGB', (800, 730), 'black')
    draw = ImageDraw.Draw(image)
    draw.line((79, 20, 79, 676), fill=(140, 140, 140))
    for i, y in enumerate((20, 129, 238, 348, 457, 567, 676)):
        for x in range(79, 780, 10):
            draw.line((x, y, min(x + 5, 780), y), fill=(255,255,255) if i == zero_index else (123,123,123))
    draw.line((79,676,780,676), fill=(255,255,255))
    draw.line([(79,350),(300,400),(500,450),(779,end_y)], fill=(100,60,220))
    image.save(path)
    return path


@pytest.mark.parametrize('profile,zero_index,end_y', [
    (GraphProfile(2500,-500,500),5,162),
    (GraphProfile(1000,-2000,500),2,588),
    (GraphProfile(1500,-1500,500),3,626),
])
def test_profiles_d_e_and_b_regression(tmp_path, profile, zero_index, end_y):
    path = dashed_profile_fixture(tmp_path / 'profile.png', zero_index, end_y)
    result = estimate_graph(path, DAY, '0042', profile)
    grid = [20,129,238,348,457,567,676]
    assert result.selected_profile == profile
    assert result.estimated_medal == round((grid[zero_index]-end_y)/(656/6)*500)
    assert result.confidence == 'high'
    auto = estimate_graph(path, DAY, '0042')
    assert auto.selected_profile is None
    assert auto.estimated_medal is None and auto.confidence == 'low'


def test_a_d_collision_returns_none(tmp_path):
    path = fixture(tmp_path / 'collision.png')
    result = estimate_graph(path, DAY, '0272')
    assert result.selected_profile is None
    assert result.estimated_medal is None and result.confidence == 'low'
    a = estimate_graph(path, DAY, '0272', GraphProfile())
    d = estimate_graph(path, DAY, '0272', GraphProfile(2500,-500,500))
    assert a.estimated_medal == d.estimated_medal * 2


def test_unknown_zero_position(tmp_path):
    path = dashed_profile_fixture(tmp_path / 'unknown.png', 4, 500)
    result = estimate_graph(path, DAY, '0042')
    assert result.estimated_medal is None and result.confidence == 'low'
