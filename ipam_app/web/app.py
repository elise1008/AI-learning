"""
Web 主应用 - Flask 路由
调用各模块实现所有 PRD 功能
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flask import (
    Flask, render_template, request, jsonify,
    redirect, url_for, session, send_file, flash
)
from functools import wraps
import config
import abc_checker
import data_manager
import device_manager
import ip_manager
import importer
import nmap_report
import staff_compare
import topology
import backup
import auth
import logger
import uuid

if getattr(sys, "frozen", False):
    template_dir = os.path.join(sys._MEIPASS, "web", "templates")
    static_dir = os.path.join(sys._MEIPASS, "web", "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
else:
    app = Flask(__name__)
app.secret_key = "ipam-offline-secret-key-2026"

data_manager.initialize_data_files()
backup.start_auto_backup()


def login_required(f):
    """登录装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "role" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "admin":
            flash("需要管理员权限", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        password = request.form.get("password", "")
        result = auth.verify_password(password)
        if result["success"]:
            session["role"] = result["role"]
            session["user"] = "admin" if result["role"] == "admin" else "query"
            logger.log(session["user"], "登录系统")
            return redirect(url_for("index"))
        flash(result["message"], "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user" in session:
        logger.log(session["user"], "退出系统")
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/")
@login_required
def index():
    """首页仪表盘"""
    stats = {
        "devices": len(data_manager.get_all_devices()),
        "links": len(data_manager.get_router_links()),
        "loopbacks": len(data_manager.get_router_loopbacks()),
        "backups": len(backup.list_backups()),
    }
    role = session.get("role", "query")
    return render_template("index.html", stats=stats, role=role)


# ====== 设备管理 ======

@app.route("/devices")
@login_required
def devices_page():
    role = session.get("role")
    biz_name = request.args.get("biz", "")
    devices = data_manager.get_all_devices() if not biz_name else [
        d for d in data_manager.get_all_devices() if d.get("_业务") == biz_name
    ]
    businesses = list(config.BUSINESS_FILES.keys())
    if biz_name:
        columns = config.BUSINESS_COLUMNS.get(biz_name, [])
    else:
        columns = []
        for row in devices:
            for key in row.keys():
                if key.startswith("_") or key in columns:
                    continue
                columns.append(key)
    if role != "admin":
        columns = [col for col in columns if col != "密码"]
    return render_template("devices.html", devices=devices, businesses=businesses,
                           current_biz=biz_name, role=role, columns=columns,
                           business_columns=config.BUSINESS_COLUMNS)


@app.route("/api/devices/add", methods=["POST"])
@login_required
@admin_required
def api_add_device():
    data = request.json or {}
    biz_name = data.pop("_业务", "")
    result = device_manager.add_device(biz_name, data)
    if result["success"]:
        logger.log(session["user"], f"新增设备: {data.get('设备名称', '')}")
    return jsonify(result)


@app.route("/api/devices/update", methods=["POST"])
@login_required
@admin_required
def api_update_device():
    data = request.json or {}
    biz_name = data.pop("_业务", "")
    device_name = data.pop("_设备名称", "")
    result = device_manager.update_device(biz_name, device_name, data)
    if result["success"]:
        logger.log(session["user"], f"修改设备: {device_name}")
    return jsonify(result)


@app.route("/api/devices/delete", methods=["POST"])
@login_required
@admin_required
def api_delete_device():
    data = request.json or {}
    biz_name = data.get("_业务", "")
    device_name = data.get("设备名称", "")
    result = device_manager.delete_device(biz_name, device_name)
    if result["success"]:
        logger.log(session["user"], f"删除设备: {device_name}")
    return jsonify(result)


# ====== 查询 ======

@app.route("/query")
@login_required
def query_page():
    role = session.get("role")
    return render_template("query.html", role=role)


@app.route("/pcweb")
@login_required
def pcweb_page():
    accounts = data_manager.get_pcweb_accounts()
    role = session.get("role")
    return render_template("pcweb.html", accounts=accounts, role=role)


@app.route("/tools")
@login_required
def tools_page():
    role = session.get("role")
    return render_template("tools.html", role=role)


def _save_uploaded_file(file, allowed_suffixes):
    if not file or not file.filename:
        raise ValueError("请选择文件")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in allowed_suffixes:
        raise ValueError("仅支持 .xlsx / .csv 文件")
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EXPORT_DIR / f"upload_{uuid.uuid4().hex}{suffix}"
    file.save(str(path))
    return path


def _download_workbook(path: Path):
    return send_file(
        str(path),
        as_attachment=True,
        download_name=path.name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/tools/staff-compare", methods=["POST"])
@login_required
def api_staff_compare():
    active_path = accounts_path = None
    try:
        active_path = _save_uploaded_file(request.files.get("active"), {".xlsx", ".csv"})
        accounts_path = _save_uploaded_file(request.files.get("accounts"), {".xlsx", ".csv"})
        result = staff_compare.create_staff_compare_workbook(active_path, accounts_path, config.EXPORT_DIR)
    except (ValueError, staff_compare.StaffCompareError) as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.log(session["user"], f"在职与邮箱账号对比失败: {exc}")
        return jsonify({"success": False, "message": f"生成失败: {exc}"}), 500
    finally:
        for path in (active_path, accounts_path):
            if path and path.exists():
                path.unlink()

    logger.log(
        session["user"],
        f"在职与邮箱账号对比: 在职{result['active_count']}人, 邮箱{result['account_count']}条, 疑似{result['suspicious_count']}条"
    )
    return _download_workbook(result["output_path"])


@app.route("/api/tools/abc-check", methods=["POST"])
@login_required
def api_abc_check():
    a_path = b_path = c_path = None
    try:
        a_path = _save_uploaded_file(request.files.get("a"), {".xlsx", ".csv"})
        b_path = _save_uploaded_file(request.files.get("b"), {".xlsx", ".csv"})
        c_path = _save_uploaded_file(request.files.get("c"), {".xlsx", ".csv"})
        result = abc_checker.create_abc_check_workbook(a_path, b_path, c_path, config.EXPORT_DIR)
    except (ValueError, abc_checker.AbcCheckError) as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.log(session["user"], f"桌管/V10/合规性核查失败: {exc}")
        return jsonify({"success": False, "message": f"生成失败: {exc}"}), 500
    finally:
        for path in (a_path, b_path, c_path):
            if path and path.exists():
                path.unlink()

    logger.log(
        session["user"],
        f"桌管/V10/合规性核查: 总IP{result['total']}个, 合规{result['compliant']}个, 不合规{result['non_compliant']}个"
    )
    return _download_workbook(result["output_path"])


@app.route("/api/query", methods=["POST"])
@login_required
def api_query():
    data = request.json or {}
    query_type = data.get("type", "name")
    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"found": False, "results": [], "message": "请输入查询关键词"})

    if query_type == "name":
        result = device_manager.query_device_by_name(keyword)
    elif query_type == "ip":
        result = device_manager.query_device_by_ip(keyword)
    elif query_type == "account":
        if not auth.can_query_secret(session.get("role", "")):
            logger.log(session["user"], f"尝试查询密码: {keyword} (拒绝)")
            return jsonify({"found": False, "results": [], "message": "无权限查询密码"})
        logger.log(session["user"], f"查询密码: {keyword}")
        result = device_manager.query_account_password(keyword)
    else:
        result = {"found": False, "results": [], "message": "未知查询类型"}

    logger.log(session["user"], f"查询({query_type}): {keyword}")
    return jsonify(result)


@app.route("/api/query/batch", methods=["POST"])
@login_required
def api_batch_query():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "请选择文件"})

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "message": "请选择文件"})

    suffix = Path(file.filename).suffix.lower()
    if suffix == ".csv":
        rows = importer.read_csv_from_fileobj(file)
    elif suffix in (".xlsx", ".xls"):
        if not importer.HAS_OPENPYXL:
            return jsonify({"success": False, "message": "缺少 openpyxl 库"})
        rows = importer.read_excel_from_fileobj(file)
    else:
        return jsonify({"success": False, "message": "仅支持 xlsx/csv 格式"})

    if not rows:
        return jsonify({"success": False, "message": "文件中没有数据"})

    ip_list = []
    for row in rows:
        for val in row.values():
            txt = str(val).strip()
            if txt and ("." in txt or ":" in txt):
                ip_list.append(txt)

    if not ip_list:
        return jsonify({"success": False, "message": "未检测到 IP 地址"})

    results = device_manager.batch_query_ips(ip_list)
    used = sum(1 for r in results if r.get("备注") == "已分配")
    free = len(results) - used

    logger.log(session["user"], f"批量查询: {file.filename} ({len(ip_list)}个IP)")

    return jsonify({
        "success": True,
        "total": len(results),
        "used": used,
        "free": free,
        "results": results,
        "message": f"查询完成: {used} 已分配, {free} 未分配"
    })


@app.route("/api/query/nmap-risk", methods=["POST"])
@login_required
def api_nmap_risk_report():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "请选择 nmap txt 文件"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "message": "请选择 nmap txt 文件"}), 400

    suffix = Path(file.filename).suffix.lower()
    if suffix != ".txt":
        return jsonify({"success": False, "message": "仅支持 .txt 格式的 nmap 输出文件"}), 400

    raw = file.read()
    if not raw:
        return jsonify({"success": False, "message": "上传的 nmap 文件为空"}), 400

    try:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("gbk")
        report = nmap_report.create_nmap_risk_workbook(text, config.EXPORT_DIR)
    except nmap_report.NmapReportError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400
    except Exception as exc:
        logger.log(session["user"], f"Nmap高危端口归属分析失败: {file.filename} - {exc}")
        return jsonify({"success": False, "message": f"生成失败: {exc}"}), 500

    logger.log(
        session["user"],
        f"Nmap高危端口归属分析: {file.filename} "
        f"扫描主机{report['scanned_hosts']}个, 开放高危{report['open_risk_hosts']}个"
    )
    return send_file(
        str(report["output_path"]),
        as_attachment=True,
        download_name=report["output_path"].name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ====== IP 分配 ======

@app.route("/ip-assign")
@login_required
@admin_required
def ip_assign_page():
    businesses = list(config.BUSINESS_FILES.keys())
    master_pool = data_manager.get_master_pool()
    return render_template("ip_assign.html", businesses=businesses, master_pool=master_pool, role=session.get("role"))


@app.route("/api/ip/assign", methods=["POST"])
@login_required
@admin_required
def api_assign_ip():
    data = request.json or {}
    biz_name = data.get("biz", "")
    count = int(data.get("count", 1))
    subnet_mask = int(data.get("mask", 32))
    result = ip_manager.allocate_ips(biz_name, count, subnet_mask)
    if result["success"]:
        logger.log(session["user"], f"分配IP: {biz_name} x{count}")
    return jsonify(result)


@app.route("/api/ip/available", methods=["POST"])
@login_required
def api_available_ips():
    data = request.json or {}
    biz_name = data.get("biz", "")
    count = int(data.get("count", 20))
    return jsonify(ip_manager.get_available_ips(biz_name, count))


# ====== 导入 ======

@app.route("/import")
@login_required
@admin_required
def import_page():
    businesses = list(config.BUSINESS_FILES.keys())
    return render_template("import.html", businesses=businesses, role=session.get("role"))


@app.route("/api/import", methods=["POST"])
@login_required
@admin_required
def api_import():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "请选择文件"})

    file = request.files["file"]
    target_biz = request.form.get("biz", "")

    if not target_biz:
        return jsonify({"success": False, "message": "请选择目标业务"})

    upload_path = config.EXPORT_DIR / file.filename
    file.save(str(upload_path))

    try:
        result = importer.import_file(str(upload_path), target_biz)
        logger.log(session["user"], f"导入: {target_biz} ({file.filename}) - 成功{result['imported']}条")
    finally:
        if upload_path.exists():
            upload_path.unlink()

    return jsonify(result)


# ====== 拓扑图 ======

@app.route("/topology")
@login_required
def topology_page():
    links = data_manager.get_router_links()
    devices = set()
    for link in links:
        local = link.get("本端设备名", "").strip()
        remote = link.get("对端设备名", "").strip()
        if local:
            devices.add(local)
        if remote:
            devices.add(remote)
    role = session.get("role")
    return render_template("topology.html", links=links, devices=sorted(devices), role=role)


@app.route("/api/topology/generate")
@login_required
def api_generate_topology():
    result = topology.generate_topology_image()
    return jsonify(result)


@app.route("/api/topology/path", methods=["POST"])
@login_required
def api_path_analysis():
    data = request.json or {}
    source = data.get("source", "")
    target = data.get("target", "")
    if not source or not target:
        return jsonify({"success": False, "message": "请选择源和目标设备"})

    img_result = topology.generate_path_image(source, target)
    analysis = topology.analyze_path(source, target)
    logger.log(session["user"], f"链路分析: {source} -> {target}")

    return jsonify({
        "analysis": analysis,
        "image_path": img_result.get("path", ""),
        "success": img_result["success"]
    })


@app.route("/api/topology/image/<image_type>")
@login_required
def api_topology_image(image_type):
    if image_type == "topology":
        img_path = config.TOPOLOGY_OUTPUT
    elif image_type == "path":
        img_path = config.PATH_ANALYSIS_OUTPUT
    else:
        return "Invalid type", 400
    if img_path.exists():
        return send_file(str(img_path), mimetype="image/png")
    return "Image not found", 404


@app.route("/api/topology/download/<image_type>")
@login_required
def api_topology_download(image_type):
    if image_type == "topology":
        img_path = config.TOPOLOGY_OUTPUT
        download_name = "topology.png"
    elif image_type == "path":
        img_path = config.PATH_ANALYSIS_OUTPUT
        download_name = "path_analysis.png"
    else:
        return "Invalid type", 400

    if img_path.exists():
        return send_file(str(img_path), mimetype="image/png", as_attachment=True, download_name=download_name)
    return "Image not found", 404


# ====== 备份 ======

@app.route("/backup")
@login_required
@admin_required
def backup_page():
    backups_list = backup.list_backups()
    return render_template("backup.html", backups=backups_list, role=session.get("role"))


@app.route("/api/backup/manual", methods=["POST"])
@login_required
@admin_required
def api_manual_backup():
    name = backup.manual_backup()
    return jsonify({"success": True, "message": f"备份完成: {name}"})


@app.route("/api/backup/restore", methods=["POST"])
@login_required
@admin_required
def api_restore_backup():
    data = request.json or {}
    backup_name = data.get("name", "")
    if not backup_name:
        return jsonify({"success": False, "message": "请指定备份"})
    ok = backup.restore_backup(backup_name)
    if ok:
        logger.log(session["user"], f"恢复备份: {backup_name}")
        return jsonify({"success": True, "message": "恢复成功"})
    return jsonify({"success": False, "message": "备份不存在"})


# ====== 日志 ======

@app.route("/logs")
@login_required
@admin_required
def logs_page():
    logs_content = logger.get_logs(500)
    return render_template("logs.html", logs=logs_content, role=session.get("role"))


# ====== 路由器Loopback管理 ======

@app.route("/loopbacks")
@login_required
def loopbacks_page():
    loopbacks = data_manager.get_router_loopbacks()
    role = session.get("role")
    return render_template("loopbacks.html", loopbacks=loopbacks, role=role)


@app.route("/api/loopbacks/add", methods=["POST"])
@login_required
@admin_required
def api_add_loopback():
    data = request.json or {}
    result = device_manager.add_router_loopback(data)
    if result["success"]:
        logger.log(session["user"], f"新增Loopback: {data.get('设备名称', '')}")
    return jsonify(result)


@app.route("/api/loopbacks/update", methods=["POST"])
@login_required
@admin_required
def api_update_loopback():
    data = request.json or {}
    device_name = data.pop("_设备名称", "")
    result = device_manager.update_router_loopback(device_name, data)
    if result["success"]:
        logger.log(session["user"], f"修改Loopback: {device_name}")
    return jsonify(result)


# ====== 路由器链路管理 ======

@app.route("/links")
@login_required
def links_page():
    links = data_manager.get_router_links()
    role = session.get("role")
    return render_template("links.html", links=links, role=role)


@app.route("/api/links/add", methods=["POST"])
@login_required
@admin_required
def api_add_link():
    data = request.json or {}
    result = device_manager.add_router_link(data)
    if result["success"]:
        logger.log(session["user"], f"新增链路: {data.get('本端设备名', '')}-{data.get('对端设备名', '')}")
    return jsonify(result)


@app.route("/api/links/update", methods=["POST"])
@login_required
@admin_required
def api_update_link():
    data = request.json or {}
    local_device = data.pop("_本端设备名", "")
    local_intf = data.pop("_本端接口", "")
    result = device_manager.update_router_link(local_device, local_intf, data)
    return jsonify(result)


# ====== 地址总表管理 ======

@app.route("/master-pool")
@login_required
def master_pool_page():
    pool = data_manager.get_master_pool()
    role = session.get("role")
    return render_template("master_pool.html", pool=pool, role=role)


@app.route("/api/master-pool/add", methods=["POST"])
@login_required
@admin_required
def api_add_master_pool():
    data = request.json or {}
    result = device_manager.add_master_pool_row(data)
    if result["success"]:
        logger.log(session["user"], f"新增地址总表: {data.get('业务名称', '')}")
    return jsonify(result)


if __name__ == "__main__":
    print("IPAM 网络地址管理助手启动中...")
    print("打开浏览器访问: http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
