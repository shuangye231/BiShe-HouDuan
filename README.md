# BiShe-HouDuan

本科毕业设计后端服务仓库。

本项目为毕业设计 **《基于 Python 的 LCD1602 显示数据的 WEB 实时同步监控系统》** 的后端实现部分，主要负责设备数据接口提供以及 Web 端实时数据访问。

---

## 项目简介

本项目基于 **Python + Flask** 构建 Web 后端服务，用于接收设备端上传的数据，并向 Web 页面提供数据接口，实现设备数据的实时监控。

系统整体结构如下：

设备数据 → Python数据采集程序  
　　　　　　　　　　 ↓  
　　　　　　 Flask Web 后端  
　　　　　　　　　　 ↓  
　　　　　　 Web 页面实时查看

---

## 主要功能

本项目实现以下功能：

- 提供设备数据访问接口
- 实现 Web 页面数据获取
- 数据实时同步显示
- 提供简单的 REST API 服务

---

## 技术栈

- Python
- Flask
- REST API
- JSON 数据接口

---

## 项目结构


BiShe-HouDuan
│
├── app.py # Flask 主程序
├── api.py # 数据接口
├── data.py # 数据处理模块
├── templates # Web 页面模板
│
└── README.md


---

## 运行环境

- Python 3.8+
- Flask

---

## 安装依赖


pip install flask


---

## 运行项目

1. 克隆仓库


git clone https://github.com/shuangye231/BiShe-HouDuan.git


2. 进入项目目录


cd BiShe-HouDuan


3. 启动服务


python app.py


默认访问地址：


http://localhost:5000


---

## 项目说明

本项目为本科毕业设计项目的一部分，用于演示设备数据通过 Web 接口进行实时监控的基本实现方式。
