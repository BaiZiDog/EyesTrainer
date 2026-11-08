# EyesTrainer v1.0.0

面向 FPS 玩家的本地视觉-运动训练器，首个正式版。

## 下载

- `EyesTrainer-Setup-1.0.0.exe` — Inno Setup 安装包（推荐）
- `EyesTrainer.exe` — Nuitka onefile 便携版
- `SHA256SUMS.txt` — 产物校验值
- `EyesTrainer-Portable-README.txt` — 便携版数据目录说明
- `EyesTrainer-LICENSE.txt` — 中英双语 MIT 许可协议

## 安装

1. 运行 `EyesTrainer-Setup-1.0.0.exe`。
2. 阅读并接受中英双语 MIT 许可协议。
3. 按向导选择安装位置；默认按当前用户安装到 `%LOCALAPPDATA%\Programs\EyesTrainer`。
4. 安装完成后可直接启动。

安装包未做代码签名，Windows SmartScreen 可能提示；可选择“更多信息 → 仍要运行”。

## 首个正式版内容

- **中文 / English 界面切换**：设置页新增“语言 / Language”标签，切换立即生效并保存。
- 主菜单、模块选择、训练提示、暂停/休息、结算、历史、校准、护眼提醒和 Windows 系统通知同步切换语言。
- 英文界面针对窄窗口压缩指标标签；小尺寸窗口下隐藏模块选择页的个人记录面板，避免文字重叠。
- 保留 v0.5.0 的中英双语许可、系统托盘通知、四训练模块和 SQLite schema v3。
- 版本号正式升级到 v1.0.0，作为首个正式版。

## 数据目录

训练数据、设置和日志保存在：

```text
%APPDATA%\EyesTrainer\
```

- 设置页“数据”标签提供“打开数据目录”。
- 升级、重装和卸载都不会删除该目录。
- 安装版不会自动读取源码目录的 `data\`。如需沿用源码版数据，可把 `data\eyestrainer.db` 与 `data\settings.json` 复制到上述目录，或运行 `EyesTrainer.exe --data-dir "D:\PythonProject\EyesTrainer\data"`。

## 环境

- Windows 10/11 x64
- 单文件版首次启动会解压到临时目录，可能需要几秒
- 需要系统自带的 Universal C Runtime（Windows 10/11 默认具备）

## 验证

- 74 项自动化测试通过
- 中英文界面在 1600×900 与 960×540 下完成布局检查
- onefile EXE 在临时数据目录下启动成功
- Inno Setup 安装包执行安装、安装版启动、静默卸载验收
- 安装/卸载前后 `%APPDATA%\EyesTrainer\eyestrainer.db` 哈希一致
- 安装包、便携版、双语许可和校验值随 Release 上传
