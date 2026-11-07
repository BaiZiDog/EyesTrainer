# EyesTrainer v0.5.0

面向 FPS 玩家的本地视觉-运动训练器，首个可安装发行版。

## 下载

- `EyesTrainer-Setup-0.5.0.exe` — Inno Setup 安装包（推荐）
- `EyesTrainer.exe` — Nuitka onefile 便携版
- `SHA256SUMS.txt` — 产物校验值
- `使用说明.txt` — 便携版数据目录说明

## 安装

1. 运行 `EyesTrainer-Setup-0.5.0.exe`。
2. 按向导选择安装位置；默认按当前用户安装到 `%LOCALAPPDATA%\Programs\EyesTrainer`。
3. 可选创建桌面快捷方式；开始菜单会提供程序和“数据目录”快捷方式。
4. 安装完成后可直接启动。

安装包未做代码签名，Windows SmartScreen 可能提示；可选择“更多信息 → 仍要运行”。

## 数据目录

训练数据、设置和日志保存在：

```text
%APPDATA%\EyesTrainer\
```

- 设置页“数据”标签提供“打开数据目录”。
- 升级、重装和卸载都不会删除该目录。
- 安装版不会自动读取源码目录的 `data\`。如需沿用源码版数据，可把 `data\eyestrainer.db` 与 `data\settings.json` 复制到上述目录，或运行 `EyesTrainer.exe --data-dir "D:\PythonProject\EyesTrainer\data"`。

## 本版内容

- 四个训练模块：甩枪反应、动态追踪、动态视敏（Landolt C 阶梯）、周边视野。
- 鼠标模块逐帧轨迹采集、结算轨迹图、首次入靶/入靶→点击/过冲/方向变化/峰值速度/跟踪滞后/速度波动等指标。
- 历史趋势、个人最佳、CSV 导出（含 `motion_samples.csv`）。
- SQLite schema v3，完整保留既有训练记录。
- 历史默认打开最近一次训练；模块选择默认上次使用模块。
- 鼠标灵敏度可在设置页和模块选择页调整。

## 环境

- Windows 10/11 x64
- 单文件版首次启动会解压到临时目录，可能需要几秒
- 需要系统自带的 Universal C Runtime（Windows 10/11 默认具备）

## 验证

- 69 项自动化测试通过
- onefile EXE 在临时数据目录和默认 `%APPDATA%` 数据目录下均启动成功
- Inno Setup 安装包执行安装、安装版启动、静默卸载验收
- 安装包、便携版和校验值随 Release 上传
