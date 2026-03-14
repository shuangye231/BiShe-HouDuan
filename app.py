from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_sock import Sock
import serial
import threading
import time
import hashlib
import random
import string
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import queue
import json
import math
from datetime import datetime
import copy

app = Flask(__name__)
app.secret_key = 'sensor_monitor_bishe_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:123456@localhost:3306/sensor_monitor'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# 串口配置
SERIAL_CONFIG = {
    "port": "COM3",
    "baudrate": 9600,
    "timeout": 0.1
}

# 数据库配置
MAX_DATA_ROWS = 10000
BATCH_SAVE_COUNT = 100
BATCH_SAVE_TIMEOUT = 5

sock = Sock(app)
db = SQLAlchemy(app)

# 全局队列
data_queue = queue.Queue(maxsize=0)


# 工具函数：获取毫秒级时间
def get_current_time_ms():
    now = datetime.now()
    return now.strftime("%H:%M:%S.%f")[:-3]


# 全局变量
latest_sensor_data = {
    "adj": 0,
    "ntc": 0,
    "light": 0,
    "status": "Dark",
    "temp": 0.0,
    "update_time": get_current_time_ms()
}

ws_connections = []
ws_lock = threading.Lock()
data_cache = []
DATA_CACHE_MAX_SIZE = 600
cache_lock = threading.Lock()
last_collect_time = 0
COLLECT_INTERVAL = 1.0  # ✅ 固定为1秒采集一次，保证每秒一条
last_second = None  # ✅ 记录上一条数据的秒数，用于按秒去重


# ===================== 数据库模型（前置定义，避免报错） =====================
class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(64), nullable=False)
    create_time = db.Column(db.DateTime, default=datetime.now)


class SensorData(db.Model):
    __tablename__ = 'sensor_data'
    id = db.Column(db.Integer, primary_key=True)
    adj = db.Column(db.Integer, nullable=False)
    ntc = db.Column(db.Integer, nullable=False)
    light = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    temp = db.Column(db.Float, nullable=False, default=0.0)
    create_time = db.Column(db.DateTime, default=datetime.now, nullable=False)


# ===================== 工具函数 =====================
def md5_encrypt(text):
    """MD5加密"""
    return hashlib.md5(text.encode()).hexdigest()


def generate_captcha():
    """生成验证码图片"""
    captcha_text = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    img = Image.new('RGB', (120, 45), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype('simhei.ttf', 28)
    except:
        font = ImageFont.load_default()
    draw.text((15, 5), captcha_text, font=font, fill=(0, 51, 102))
    for _ in range(6):
        x1, y1 = random.randint(0, 120), random.randint(0, 45)
        x2, y2 = random.randint(0, 120), random.randint(0, 45)
        draw.line((x1, y1, x2, y2), fill=(100, 150, 200), width=1)
    buf = BytesIO()
    img.save(buf, 'PNG')
    buf.seek(0)
    session['captcha'] = captcha_text.lower()
    return buf


def calculate_volatility(data_list, period_minutes):
    """计算波动率"""
    if not isinstance(data_list, list) or len(data_list) < 2:
        return 0.0
    max_items = int(period_minutes * 60)
    period_data = data_list[-max_items:] if len(data_list) >= max_items else data_list
    period_data = [x for x in period_data if isinstance(x, (int, float)) and not math.isnan(x)]
    if len(period_data) < 2:
        return 0.0
    avg = sum(period_data) / len(period_data)
    if avg == 0 or math.isnan(avg):
        return 0.0
    variance = sum([(x - avg) ** 2 for x in period_data]) / len(period_data)
    std_dev = math.sqrt(variance) if variance >= 0 else 0.0
    volatility = (std_dev / avg) * 100
    return round(volatility, 2)


def clean_old_data():
    """清理旧数据"""
    try:
        total_count = SensorData.query.count()
        if total_count <= MAX_DATA_ROWS:
            return
        delete_count = total_count - MAX_DATA_ROWS
        old_data = SensorData.query.order_by(SensorData.create_time.asc()).limit(delete_count).all()
        for d in old_data:
            db.session.delete(d)
        db.session.commit()
    except:
        db.session.rollback()


def push_data_to_all_clients(data):
    """推送数据到所有WebSocket客户端"""
    with ws_lock:
        safe_data = copy.deepcopy(data)
        js = json.dumps(safe_data, ensure_ascii=False)
        for ws in list(ws_connections):
            try:
                ws.send(js)
            except:
                if ws in ws_connections:
                    ws_connections.remove(ws)


def update_data_cache(data):
    """更新数据缓存"""
    with cache_lock:
        try:
            item = {
                'timestamp': time.time(),
                'adj': int(data.get('adj', 0)),
                'ntc': int(data.get('ntc', 0)),
                'light': int(data.get('light', 0)),
                'temp': float(data.get('temp', 0.0))
            }
            data_cache.append(item)
            if len(data_cache) > DATA_CACHE_MAX_SIZE:
                data_cache.pop(0)
        except:
            pass


# ===================== 核心线程 =====================
def serial_read_thread():
    """串口读取线程（稳定+1秒间隔+按秒去重）"""
    global latest_sensor_data, last_collect_time, last_second
    ser = None
    while True:
        try:
            # 串口重连
            if ser is None or not ser.is_open:
                try:
                    ser = serial.Serial(**SERIAL_CONFIG)
                    ser.flushInput()
                    print("串口已成功打开")
                except Exception as e:
                    print(f"串口打开失败，重试中：{e}")
                    time.sleep(2)
                    continue

            # ✅ 严格1秒采集间隔
            current_time = time.time()
            if current_time - last_collect_time < COLLECT_INTERVAL:
                time.sleep(0.01)
                continue

            # 读取串口数据
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                ser.flushInput()
                if not line:
                    continue

                # 解析数据
                parts = line.split('|')
                parsed = {}
                for p in parts:
                    if ':' in p:
                        k, v = p.split(':', 1)
                        parsed[k.strip().lower()] = v.strip()

                # 验证数据完整性
                req = ['adj', 'ntc', 'light', 'status', 'temp']
                if all(k in parsed for k in req):
                    try:
                        new_data = {
                            "adj": int(parsed['adj']),
                            "ntc": int(parsed['ntc']),
                            "light": int(parsed['light']),
                            "status": parsed['status'],
                            "temp": float(parsed['temp']),
                            "update_time": get_current_time_ms()
                        }

                        # ✅ 按秒去重：同一秒只保留一条数据
                        current_second = new_data['update_time'].split('.')[0]
                        if current_second == last_second:
                            continue  # 同一秒内的重复数据，直接丢弃
                        last_second = current_second

                        # 更新全局数据
                        latest_sensor_data = new_data
                        update_data_cache(new_data)
                        push_data_to_all_clients(new_data)
                        data_queue.put(new_data.copy())
                        last_collect_time = current_time
                    except Exception as e:
                        print(f"数据解析错误：{e}")
        except Exception as e:
            print(f"串口线程异常：{e}")
            try:
                ser.close()
            except:
                pass
            ser = None
            time.sleep(1)


def db_save_thread():
    """数据库保存线程"""
    with app.app_context():
        batch = []
        last_save = time.time()
        while True:
            try:
                # 读取队列数据
                try:
                    d = data_queue.get(timeout=1)
                    ct = datetime.now()
                    batch.append(SensorData(
                        adj=d['adj'], ntc=d['ntc'], light=d['light'],
                        status=d['status'], temp=d['temp'], create_time=ct
                    ))
                    data_queue.task_done()
                except queue.Empty:
                    pass

                # 批量保存
                if len(batch) >= BATCH_SAVE_COUNT or time.time() - last_save >= BATCH_SAVE_TIMEOUT:
                    if batch:
                        try:
                            db.session.bulk_save_objects(batch)
                            db.session.commit()
                            clean_old_data()
                            print(f"批量保存{len(batch)}条数据成功")
                        except Exception as e:
                            print(f"数据库保存失败：{e}")
                            db.session.rollback()
                        batch = []
                        last_save = time.time()
            except Exception as e:
                print(f"数据库线程异常：{e}")
                db.session.rollback()
                batch = []
                time.sleep(1)


# ===================== WebSocket路由 =====================
@sock.route('/ws/sensor')
def ws_sensor(ws):
    """WebSocket实时数据推送"""
    if 'user_id' not in session:
        ws.close()
        return
    with ws_lock:
        ws_connections.append(ws)
    try:
        # 推送最新数据
        ws.send(json.dumps(copy.deepcopy(latest_sensor_data), ensure_ascii=False))
        # 保持连接
        while True:
            ws.receive(timeout=30)
    except:
        pass
    finally:
        with ws_lock:
            if ws in ws_connections:
                ws_connections.remove(ws)


# ===================== HTTP路由 =====================
@app.before_request
def check_login():
    """登录校验"""
    allow = ['/login', '/register', '/captcha', '/static']
    if request.method != 'OPTIONS' and not any(request.path.startswith(p) for p in allow):
        if 'user_id' not in session:
            return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        c = request.form.get('captcha', '').strip().lower()
        if session.get('captcha') != c:
            return render_template('login.html', msg='验证码错误')
        user = User.query.filter_by(username=u, password=md5_encrypt(p)).first()
        if not user:
            return render_template('login.html', msg='用户名或密码错误')
        session['user_id'] = user.id
        session['username'] = user.username
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """注册页面"""
    if request.method == 'POST':
        u = request.form.get('username', '').strip()
        p = request.form.get('password', '').strip()
        cp = request.form.get('confirm_pwd', '').strip()
        c = request.form.get('captcha', '').strip().lower()
        if session.get('captcha') != c:
            return render_template('register.html', msg='验证码错误')
        if p != cp:
            return render_template('register.html', msg='两次密码不一致')
        if User.query.filter_by(username=u).first():
            return render_template('register.html', msg='用户名已存在')
        new_user = User(username=u, password=md5_encrypt(p))
        db.session.add(new_user)
        db.session.commit()
        return render_template('login.html', msg='注册成功')
    return render_template('register.html')


# 新增：修改密码路由
@app.route('/change_pwd', methods=['GET', 'POST'])
def change_pwd():
    """修改密码页面"""
    if request.method == 'POST':
        # 获取表单数据
        old_pwd = request.form.get('old_pwd', '').strip()
        new_pwd = request.form.get('new_pwd', '').strip()
        confirm_pwd = request.form.get('confirm_pwd', '').strip()

        # 验证数据
        if not old_pwd or not new_pwd or not confirm_pwd:
            return render_template('change_pwd.html', msg='所有字段都不能为空', success=False)

        if new_pwd != confirm_pwd:
            return render_template('change_pwd.html', msg='两次输入的新密码不一致', success=False)

        if len(new_pwd) < 6 or len(new_pwd) > 20:
            return render_template('change_pwd.html', msg='新密码长度必须在6-20位之间', success=False)

        # 验证原密码
        user_id = session.get('user_id')
        user = User.query.get(user_id)
        if not user or user.password != md5_encrypt(old_pwd):
            return render_template('change_pwd.html', msg='原密码错误', success=False)

        # 修改密码
        try:
            user.password = md5_encrypt(new_pwd)
            db.session.commit()
            return render_template('change_pwd.html', msg='密码修改成功！请重新登录', success=True)
        except Exception as e:
            db.session.rollback()
            print(f"修改密码失败：{e}")
            return render_template('change_pwd.html', msg='密码修改失败，请重试', success=False)

    # GET请求显示页面
    return render_template('change_pwd.html', username=session.get('username'))


@app.route('/captcha')
def captcha():
    """验证码接口"""
    buf = generate_captcha()
    res = make_response(buf.getvalue())
    res.headers['Content-Type'] = 'image/png'
    return res


@app.route('/logout')
def logout():
    """退出登录"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@app.route('/index')
def index():
    """实时监控页面"""
    return render_template('index.html', username=session.get('username'))


@app.route('/history_data')
def history_data():
    """历史数据页面（最新数据在第一行+按秒去重）"""
    limit = request.args.get('limit', 20, type=int)
    is_ajax = request.args.get('ajax', 0) == '1'

    # 按创建时间降序查询（最新的在前）
    lst = SensorData.query.order_by(SensorData.create_time.desc()).limit(limit).all()
    out = []
    for item in lst:
        out.append({
            'id': item.id,
            'time': item.create_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],  # 毫秒级时间
            'adj': item.adj,
            'ntc': item.ntc,
            'light': item.light,
            'status': item.status,
            'temp': round(item.temp, 1)
        })

    # AJAX请求返回JSON，普通请求返回页面
    if is_ajax:
        return jsonify(out)
    return render_template('history_data.html', username=session.get('username'), data_list=out, current_limit=limit)


@app.route('/trend_chart')
def trend_chart():
    """趋势图页面"""
    return render_template('trend_chart.html', username=session.get('username'))


@app.route('/api/realtime')
def api_realtime():
    """实时数据API"""
    return jsonify(copy.deepcopy(latest_sensor_data))


@app.route('/api/history')
def api_history():
    """历史数据API"""
    limit = request.args.get('limit', 300, type=int)
    lst = SensorData.query.order_by(SensorData.create_time.desc()).limit(limit).all()
    ret = {
        "time": [int(dt.timestamp() * 1000) for dt in [i.create_time for i in lst]],
        "adj": [i.adj for i in lst],
        "ntc": [i.ntc for i in lst],
        "light": [i.light for i in lst],
        "temp": [i.temp for i in lst]
    }
    return jsonify(ret)


@app.route('/api/volatility')
def api_volatility():
    """波动率API"""
    with cache_lock:
        cp = copy.deepcopy(data_cache)
    adj = [x['adj'] for x in cp]
    ntc = [x['ntc'] for x in cp]
    light = [x['light'] for x in cp]
    temp = [x['temp'] for x in cp]
    data = {
        "adj": {"1min": calculate_volatility(adj, 1), "5min": calculate_volatility(adj, 5),
                "10min": calculate_volatility(adj, 10)},
        "ntc": {"1min": calculate_volatility(ntc, 1), "5min": calculate_volatility(ntc, 5),
                "10min": calculate_volatility(ntc, 10)},
        "light": {"1min": calculate_volatility(light, 1), "5min": calculate_volatility(light, 5),
                  "10min": calculate_volatility(light, 10)},
        "temp": {"1min": calculate_volatility(temp, 1), "5min": calculate_volatility(temp, 5),
                 "10min": calculate_volatility(temp, 10)},
        "update_time": get_current_time_ms()
    }
    return jsonify(data)


@app.after_request
def cors(res):
    """跨域处理"""
    res.headers['Access-Control-Allow-Origin'] = '*'
    res.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    res.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return res


# ===================== 启动程序 =====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print("数据库表创建成功")
    # 启动串口线程
    threading.Thread(target=serial_read_thread, daemon=True).start()
    # 启动数据库线程
    threading.Thread(target=db_save_thread, daemon=True).start()
    # 启动Flask服务
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)