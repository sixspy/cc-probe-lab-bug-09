from pathlib import Path
from quart import Quart, jsonify, request, send_from_directory, redirect
from app import seed
from app.services import 目录, 装载, 结栏, 贯验, 夹具, 统计, 说明
from app.services import 栏号解析
from app.services import homonym as homonym_svc
from app.services import homonym_cutover as homonym_cut_svc
from app.services import homonym_dualwrite as homonym_dual_svc
from app.services import homonym_audit as homonym_audit_svc

_STATIC = Path(__file__).resolve().parent / "static"
app = Quart(__name__)


@app.before_serving
async def _boot():
    seed.初始化库()


@app.get("/login")
async def login_page():
    return await send_from_directory(_STATIC, "login.html")


@app.get("/")
async def index():
    return await send_from_directory(_STATIC, "index.html")


@app.get("/api/概览")
async def api_概览():
    return jsonify(目录.概览())


@app.get("/api/仓情")
async def api_仓情():
    return jsonify(说明.仓情())


@app.get("/api/栏规")
async def api_栏规_get():
    return jsonify(目录.栏规())


@app.post("/api/栏规")
async def api_栏规_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(目录.改栏规(body))


@app.get("/api/站点源")
async def api_站点():
    return jsonify(目录.站点列表())


@app.get("/api/观测报文")
async def api_报文():
    return jsonify(目录.报文列表())


@app.get("/api/入栏缓冲")
async def api_缓冲():
    return jsonify(目录.缓冲列表())


@app.get("/api/站点汇总账")
async def api_汇总():
    return jsonify(目录.汇总列表())


@app.get("/api/坏点匣")
async def api_坏点():
    return jsonify(目录.坏点列表())


@app.get("/api/栏贯验")
async def api_贯验列表():
    return jsonify(目录.贯验列表())


@app.get("/api/夹具")
async def api_夹具():
    return jsonify(夹具.列表())


@app.post("/api/观测报文/装载")
async def api_装载():
    body = await request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(装载.装一批(body, 解析指纹=body.get("解析指纹")))
    except (KeyError, ValueError, RuntimeError) as e:
        return jsonify({"错误": str(e), "拒绝": True}), 400


@app.post("/api/观测报文/夹具/<name>")
async def api_夹具装载(name: str):
    try:
        return jsonify(装载.装一批(夹具.读取(name)))
    except FileNotFoundError:
        return jsonify({"错误": name}), 404


@app.post("/api/结栏/跑")
async def api_结栏():
    return jsonify(结栏.结当前栏())


@app.get("/api/结栏/预览")
async def api_结栏预览():
    return jsonify(结栏.预览结栏())


@app.get("/api/栏贯验/快照")
async def api_贯验快照():
    return jsonify(贯验.只读快照())


@app.get("/api/夹具/预检")
async def api_夹具预检():
    return jsonify(夹具.全部预检())


@app.post("/api/栏贯验/跑")
async def api_贯验():
    return jsonify(贯验.跑一次())


@app.get("/api/统计/报文命运")
async def api_统计报文():
    return jsonify(统计.报文命运())


@app.get("/api/统计/缓冲命运")
async def api_统计缓冲():
    return jsonify(统计.缓冲命运())




@app.get("/api/装载批次")
async def api_装载批次():
    return jsonify(目录.装载批次列表())


@app.get("/api/结栏批次")
async def api_结栏批次():
    return jsonify(目录.结栏批次列表())


@app.get("/api/统计/按站点")
async def api_按站点():
    return jsonify(统计.按站点报文())


@app.get("/api/统计/按指标")
async def api_按指标():
    return jsonify(统计.按指标汇总())


@app.get("/api/统计/装载摘要")
async def api_装载摘要():
    return jsonify(统计.装载批次摘要())


@app.get("/api/统计/结栏摘要")
async def api_结栏摘要():
    return jsonify(统计.结栏批次摘要())

@app.get("/api/空桩")
async def api_空桩():
    root = Path(__file__).resolve().parent / "modules"
    out = []
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.is_dir() and p.name != "__pycache__" and (p / "__init__.py").is_file():
                out.append(p.name)
    return jsonify({"空桩": out, "条数": len(out)})


@app.get("/<path:name>")
async def static_page(name: str):
    p = _STATIC / name
    if not p.is_file():
        return redirect("/")
    return await send_from_directory(_STATIC, name)


@app.get("/api/homonym/看板")
async def api_homonym_board():
    return jsonify(homonym_svc.dashboard())


@app.post("/api/homonym/动作")
async def api_homonym_action():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(homonym_svc.commit_action(body))


@app.post("/api/homonym/半修展示")
async def api_homonym_half():
    return jsonify(homonym_svc.half_fix_display())


@app.get("/api/homonym/切流")
async def api_homonym_cut():
    return jsonify(homonym_cut_svc.board())


@app.post("/api/homonym/切流")
async def api_homonym_cut_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(homonym_cut_svc.append_cutover(int(body.get("ref_id") or 1), str(body.get("note") or "")))


@app.get("/api/homonym/双写")
async def api_homonym_dual():
    return jsonify(homonym_dual_svc.dual_board())


@app.post("/api/homonym/双写")
async def api_homonym_dual_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(homonym_dual_svc.apply_dualwrite(str(body.get("note") or "")))


@app.get("/api/homonym/审计")
async def api_homonym_audit():
    return jsonify(homonym_audit_svc.audit_summary())


@app.get("/api/栏号解析/真源卡")
async def api_解析真源卡():
    return jsonify(目录.解析真源卡())


@app.get("/api/栏号解析/齐套对账")
async def api_齐套对账():
    return jsonify(栏号解析.齐套对账())


@app.get("/api/栏号解析/映射")
async def api_站点栏映射():
    return jsonify(栏号解析.站点栏映射())


@app.get("/api/栏号解析/包")
async def api_历史包():
    return jsonify(栏号解析.历史包列表())


@app.get("/api/栏号解析/模糊归档")
async def api_模糊归档():
    return jsonify(栏号解析.模糊归档列表())


@app.post("/api/栏号解析/封包")
async def api_封包():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(栏号解析.封包(str(body.get("备注") or "")))


@app.post("/api/栏号解析/绑定")
async def api_绑定():
    body = await request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(栏号解析.绑定站点栏(str(body["站点键"]), str(body["栏号"])))
    except KeyError as e:
        return jsonify({"错误": str(e)}), 400


@app.post("/api/栏号解析/改名")
async def api_改名():
    body = await request.get_json(force=True, silent=True) or {}
    try:
        return jsonify(栏号解析.改站名(str(body["源键"]), str(body["新名称"])))
    except KeyError as e:
        return jsonify({"错误": str(e)}), 400


@app.post("/api/栏号解析/切流")
async def api_解析切流():
    return jsonify(栏号解析.切流())


@app.post("/api/栏号解析/模糊归档")
async def api_记模糊():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(栏号解析.记模糊归档(
        str(body.get("站名") or ""),
        list(body.get("候选栏") or []),
        str(body.get("模糊落点") or "只读归档"),
    ))


@app.post("/api/栏号解析/模糊回刷")
async def api_模糊回刷():
    body = await request.get_json(force=True, silent=True) or {}
    try:
        栏号解析.按站名模糊回刷(body)
    except ValueError as e:
        return jsonify({"错误": str(e), "拒绝": True}), 400
    return jsonify({"错误": "不应到达"}), 500
