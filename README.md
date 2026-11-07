# EyesTrainer

面向 FPS 玩家的本地视觉-运动训练器：甩枪反应、动态追踪、动态视敏与周边视野。数据优先、完全离线。

## 下载与安装

从 [GitHub Releases](https://github.com/BaiZiDog/EyesTrainer/releases) 下载 `EyesTrainer-Setup-0.5.0.exe`，双击安装。安装包由 Inno Setup 6 生成，支持开始菜单和可选桌面快捷方式。

- 安装版数据保存在 `%APPDATA%\EyesTrainer\`，升级和卸载都不会删除训练记录。
- 安装向导会显示中英双语 MIT 许可协议。
- 设置页“数据”标签提供“打开数据目录”按钮。
- 安装包和 EXE 未做代码签名，Windows SmartScreen 可能提示；可选择“更多信息 → 仍要运行”。

## 源码运行

需要 Python 3.11+（当前开发环境为 3.13）与 Windows。

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe main.py
```

无全屏调试：

```bash
.venv/Scripts/python.exe main.py --windowed
```

数据目录默认在项目的 `data/`；打包运行时使用 `%APPDATA%/EyesTrainer/`。可用 `--data-dir` 或环境变量 `EYESTRAINER_DATA_DIR` 覆盖。

## 训练模块

- **甩枪反应 · 连击**：3 个目标同屏，点掉立即刷新；记录命中率、每分钟击杀、击杀间隔、点击误差和路径效率。
- **甩枪反应 · 反应**：单目标随机延迟出现，限时点击；记录命中反应时、首动反应时、命中率和预判失误。
- **动态追踪 · 航点 / 弹跳**：按住左键让准星覆盖移动目标；记录覆盖率 TO/T、平均偏离、触发覆盖率和速度等级。
- **动态视敏 · 阶梯**：带缺口圆环横向高速移动，用方向键/WASD 判断缺口方向；2-down-1-up 阶梯自动调整速度，输出可辨速度阈值（deg/s）。
- **周边视野 · 自适应**：注视中央十字，周边闪现实心目标与空心干扰项；按空格报告实心目标，自动调整偏心角，统计检出率、误报率与周边反应时。
- **轨迹分析**：鼠标模块逐帧采集准星与目标位置，结算页可查看轨迹，并统计首次入靶、入靶→点击、过冲、方向变化、峰值速度、跟踪滞后和速度波动。
- **自定义灵敏度**：设置页和模块选择页均可调整鼠标灵敏度，立即作用于鼠标训练准星；键盘模块不涉及灵敏度。

训练中按 `Esc` 暂停，`F3` 显示帧率信息。菜单和结算页使用系统指针，训练回合使用隐藏光标 + 自绘准星 + 相对鼠标。

## 数据

每回合写入 SQLite（`eyestrainer.db`）：会话、回合、甩枪试次、追踪 1 秒窗口、动态视敏试次、周边视野试次和压缩后的逐帧轨迹。历史页默认打开最近一次训练，可查看趋势并导出指标/轨迹 CSV。所有数据本地保存，不联网。

## 打包 EXE 与安装包

```bat
build_exe.bat
build_installer.bat
```

`build_exe.bat` 使用 Nuitka onefile 模式生成 `dist\EyesTrainer.exe`；`build_installer.bat` 调用 Inno Setup 6 生成 `dist\EyesTrainer-Setup-0.5.0.exe`。构建使用 Zig 作为 C 编译器（Nuitka 4.x 在 Python 3.13 下不再支持 MinGW64）；需要本机有 `zig` 或让 Nuitka 下载，且 `.venv` 内已安装 Nuitka：

```bash
.venv/Scripts/python.exe -m pip install -e ".[build]"
```

EXE 启动时会把运行文件解压到临时目录，首次启动会比源码运行慢几秒。打包运行的数据目录是 `%APPDATA%\EyesTrainer\`，不会写入项目目录。想在 EXE 中继续使用源码版数据，可把 `data\eyestrainer.db` 和 `data\settings.json` 复制到 `%APPDATA%\EyesTrainer\`，或直接运行 `dist\EyesTrainer.exe --data-dir D:\PythonProject\EyesTrainer\data`。onefile 产物可能被杀毒软件误报，必要时改用 `--mode=standalone` 生成文件夹版本。

安装包使用 Inno Setup 6，默认按当前用户安装到 `%LOCALAPPDATA%\Programs\EyesTrainer`，可在安装向导中修改。`[Dirs]` 预创建 `%APPDATA%\EyesTrainer` 并标记为 `uninsneveruninstall`，训练数据不会随卸载删除。

## 开发

```bash
.venv/Scripts/python.exe -m pytest -q
SDL_VIDEODRIVER=dummy .venv/Scripts/python.exe -m pytest tests/test_scene_smoke.py -q
```

设计与测量口径见 [docs/DESIGN.md](docs/DESIGN.md)。工程约定见 [CLAUDE.md](CLAUDE.md)。

## 许可协议

项目采用 [MIT 许可协议](LICENSE)。[中文参考译文](LICENSE.zh-CN.md) 仅供阅读；如中英文文本存在歧义，以英文文本为准。安装向导中的许可页同时包含中英文，便携版许可文本随 Release 资产提供。

## 定位与免责

本工具是 FPS 视觉-运动训练器，不是医疗设备，不诊断或治疗视力问题。训练效果具有任务特异性；如出现眼痛、头痛或眩晕，请停止使用并咨询专业人士。
