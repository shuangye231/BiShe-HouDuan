
# BiShe-HouDuan

本科毕业设计后端服务仓库。

本项目是毕业设计 **《基于 Python 的 LCD1602 显示数据的 Web 实时同步监控系统的设计与实现》** 的后端部分。
主要用于接收单片机发送的环境数据，并通过 Web 服务将数据提供给浏览器页面，实现实时监控功能。

---

# 项目简介

本系统采用 **Python + Flask** 构建后端服务，通过 **串口通信** 接收单片机发送的数据，并对数据进行解析和处理，然后通过 **WebSocket 和 HTTP 接口** 提供给前端页面进行展示。

系统整体数据流程如下：

```
单片机采集数据
        ↓
串口发送数据
        ↓
Python 串口接收程序
        ↓
Flask Web 后端处理
        ↓
Web 页面实时显示
```

通过该方式，可以实现环境数据的 **实时采集、实时更新以及历史数据查看**。

---

# 主要功能

本项目后端主要实现以下功能：

### 1 串口数据接收

通过 `pyserial` 监听串口数据，接收单片机发送的环境信息，包括：

* 温度数据
* 光照状态
* 传感器采样值

服务器会对串口数据进行解析，并转换为可处理的数据格式。

---

### 2 实时数据推送

系统使用 **Flask-SocketIO** 建立 WebSocket 连接，当新的传感器数据到达时，服务器会将数据实时推送到浏览器页面，从而实现数据的实时刷新。

---

### 3 数据接口提供

后端提供 HTTP 接口，用于前端页面获取系统数据，例如：

* 当前传感器数据
* 历史数据记录
* 数据趋势分析

所有接口均使用 **JSON 格式**进行数据传输。

---

### 4 用户系统

系统实现了简单的用户管理功能，包括：

* 用户注册
* 用户登录
* 验证码校验
* 修改密码

用于保证系统访问的基本安全性。

---

# 技术栈

本项目主要使用以下技术：

* **Python**
* **Flask**
* **Flask-SocketIO**
* **PySerial**
* **Eventlet**
* **HTML / JavaScript**

---

# 项目结构

```
BiShe-HouDuan
│
├── app.py              # Flask 主程序
├── requirements.txt    # 项目依赖
│
├── templates           # Web 页面
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── history_data.html
│   ├── trend_chart.html
│   └── change_pwd.html
│
└── README.md
```

---

# 运行环境

建议使用以下环境运行项目：

* Python 3.8 及以上
* Windows / Linux

---

# 安装依赖

进入项目目录后安装依赖：

```
pip install -r requirements.txt
```

依赖内容如下：



```
flask
pyserial
flask-socketio
python-socketio
eventlet
```

---

# 运行项目

### 1 克隆项目

```
git clone https://github.com/shuangye231/BiShe-HouDuan.git
```

### 2 进入项目目录

```
cd BiShe-HouDuan
```

### 3 启动后端服务

```
python app.py
```

---

# 访问系统

浏览器访问：

```
http://localhost:5000
```

即可进入系统登录页面。

---

# 项目说明

本项目为本科毕业设计项目，主要用于学习 **嵌入式系统与 Web 技术结合的应用开发**。
系统实现了从 **硬件数据采集 → Python 后端处理 → Web 页面展示** 的完整流程。
