from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import serial
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 全局数据：新增ADJ、NTC字段
current_data = {
    'adj_value': 0,
    'ntc_value': 0,
    'light_value': 0,
    'status': 'Waiting',
    'line1': 'Light: ----',
    'line2': 'Status: --',
    'timestamp': time.strftime('%H:%M:%S')
}

def read_serial_data():
    global current_data
    ser = None
    # 清理残留串口连接
    try:
        ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
        if ser.is_open:
            ser.close()
    except:
        pass

    try:
        ser = serial.Serial(port='COM3', baudrate=9600, timeout=1)
        print(f"✅ 串口连接成功：{ser.port}")
    except Exception as e:
        print(f"❌ 串口连接失败：{e}")
        print("请检查：1.单片机是否已连接 2.串口号是否正确 3.波特率是否匹配")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                print(f"收到数据：{line}")

                # 解析ADJ、NTC、LIGHT、STATUS（适配单片机新格式）
                if 'ADJ:' in line and 'NTC:' in line and 'LIGHT:' in line:
                    # 拆分各字段
                    adj_match = [x for x in line.split('|') if x.startswith('ADJ:')]
                    ntc_match = [x for x in line.split('|') if x.startswith('NTC:')]
                    light_match = [x for x in line.split('|') if x.startswith('LIGHT:')]
                    status_match = [x for x in line.split('|') if x.startswith('STATUS:')]

                    # 解析数值
                    if adj_match:
                        current_data['adj_value'] = int(adj_match[0].split(':')[1])
                    if ntc_match:
                        current_data['ntc_value'] = int(ntc_match[0].split(':')[1])
                    if light_match:
                        current_data['light_value'] = int(light_match[0].split(':')[1])
                    if status_match:
                        current_data['status'] = status_match[0].split(':')[1]

                    # 更新LCD显示文本
                    current_data['line1'] = f"ADJ:{current_data['adj_value']:4d}"
                    current_data['line2'] = f"NTC:{current_data['ntc_value']:4d}"
                    current_data['timestamp'] = time.strftime('%H:%M:%S')

                    # 推送所有数据到前端
                    socketio.emit('sensor_update', current_data)
                    print(f"已推送数据：{current_data}")

        except Exception as e:
            print(f"数据处理错误：{e}")

        time.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html', initial_data=current_data)

@socketio.on('connect')
def handle_connect():
    print("✅ 客户端已连接")
    emit('sensor_update', current_data)

if __name__ == '__main__':
    print("=" * 50)
    print("LCD监控系统后端服务启动中...")
    print("=" * 50)

    serial_thread = threading.Thread(target=read_serial_data, daemon=True)
    serial_thread.start()
    print("✅ 串口读取线程已启动")

    print("🚀 Web服务启动，请访问：http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)

    socketio.run(app, debug=False, host='0.0.0.0', port=5000)