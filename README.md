系统框架图：

设备数据
   │
   ▼
Python 数据采集程序
   │
   ├── LCD1602 显示
   │
   └── Flask Web API
            │
            ▼
        Web 页面


        
代码结构目录：

lcd-web-monitor/
│
├─ app.py           # Flask服务
├─ lcd.py           # LCD1602控制
├─ data.py          # 数据采集
├─ templates/       # Web页面
│
├─ static/
│
└─ README.md


系统功能：

- LCD1602 实时显示设备数据
- Web 页面远程查看数据
- Flask API 提供数据接口
