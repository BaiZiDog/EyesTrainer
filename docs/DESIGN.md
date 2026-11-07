# EyesTrainer 设计方案

> 版本：0.5.0（2026-11-07）
> 状态：方向已确认，待开发
> 本文档描述产品定位、训练规则、测量口径、数据结构与验收标准，不包含实现代码。

## 0. 已确认的决策

| 日期 | 决策 | 说明 |
|---|---|---|
| 2026-11-06 | 技术栈：Python + pygame-ce 桌面应用 | 全屏、高刷新、相对鼠标瞄准、完全离线 |
| 2026-11-06 | 首批模块：甩枪反应 + 动态追踪 | 先验证手感与测量链路，再扩展其它模块 |
| 2026-11-06 | 追加模块：动态视敏 + 周边视野 | Landolt C 阶梯与周边检测；四个训练项目全部落地 |
| 2026-11-06 | 产品取向：数据优先 | 干净竞技界面、可靠指标、轻量音效 |
| 2026-11-06 | v1 不做 3D 场景 | 2D 屏幕平面便于标定和复现；3D 只可作为后续表现层 |
| 2026-11-06 | 瞄准方式：相对鼠标 + 自绘准星 | 贴近 FPS 肌肉记忆；菜单仍使用系统指针 |
| 待定 | 是否打包 exe、是否支持多档案 | 不阻塞首批开发，架构预留 |

---

## 1. 项目定位

EyesTrainer 是一个面向 FPS 玩家的本地视觉-运动训练器，训练并量化以下能力：

- 发现目标后的反应速度；
- 把准星快速、准确地移到目标上的能力（甩枪 / 目标切换）；
- 对移动目标的平滑追踪能力；
- 后续扩展：高速运动细节的辨识能力（动态视敏）、中央注视下的周边目标察觉能力。

**边界：**

- 不是医疗设备或视力矫正工具，不诊断、不治疗任何视力问题。
- 不做 3D FPS 模拟、武器、后坐力、地图；目标是可测量、可复现的视觉-运动任务。
- v1 只支持 Windows 10/11、键鼠、单显示器；不做手柄和触屏。
- 训练效果具有任务特异性。本项目提供稳定的测量环境和刻意练习条件，不承诺直接提升某款游戏的段位。

---

## 2. 设计原则

1. **测量优先**：每个指标都有明确公式，能从原始数据独立复算；不做不可解释的“综合战力分”。
2. **手感优先**：低延迟帧循环、高刷新率、相对鼠标瞄准，动作尽量接近 FPS。
3. **难度自适应**：把训练强度稳定在约 75% 成功率附近，既不过难也不无聊。
4. **可复现**：每个回合记录随机种子和完整配置，同配置下的结果可以纵向比较。
5. **克制反馈**：深色高对比、无动态背景、无遮挡特效；音效轻量，避免视觉疲劳。
6. **护眼**：内置累计训练时长与休息提醒，明确建议单次训练时长。

---

## 3. 能力模型与模块路线

| 能力 | FPS 场景 | 训练形式 | 主指标 | 阶段 |
|---|---|---|---|---|
| 简单反应 | 遭遇战先手 | 单目标随机延迟出现，点击 | 命中反应时、首动反应时 | 首批 |
| 甩枪 / 目标切换 | 快速转火 | 3 目标同屏，点掉即刷新 | 命中率、击杀间隔、路径效率、点击误差 | 首批 |
| 平滑追踪 | 跟枪 | 目标持续移动，按住左键保持覆盖 | 覆盖率 TO/T、平均偏离 | 首批 |
| 动态视敏 | 看清高速移动的敌人 | Landolt C 缺口方向判断，速度阶梯 | 可辨认速度阈值 | 已实现 |
| 周边视野 | 余光发现侧翼 / 小地图 | 中央注视点固定，周边闪现目标与干扰项 | 周边检出率、误报率、反应时 | 已实现 |
| 反应抑制 | 不误伤队友 | 红蓝目标 Go/No-Go | 误触率、遗漏率 | 可选后续 |

**四个训练模块均已实现**：甩枪反应（Flick）、动态追踪（Track）、动态视敏（DVA）、周边视野（Peripheral）。前两者为鼠标模块，后两者为键盘模块；详细规则见第 21 节。

---

## 4. 技术栈

| 项 | 选择 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ 64 位 | 使用 `perf_counter`、`sqlite3`、`tomllib` 等标准库 |
| 渲染 / 输入 | pygame-ce ≥ 2.5（SDL2） | 全屏、高刷新、相对鼠标模式 |
| 数据 | SQLite（标准库 `sqlite3`） | 本地单文件，支持事务、索引、导出 |
| 测试 | pytest | 纯逻辑单元测试 + 无头冒烟测试 |
| 打包 | PyInstaller（后续） | 优先 `onedir`，启动快、误报少 |
| 额外依赖 | 无（首批） | 不引入 NumPy；音频用 `array` 合成 |

**选择理由：** pygame-ce 能跑满显示器刷新率、支持 SDL 相对鼠标模式、单机离线、打包简单，与当前 Python 项目一致。Web 方案虽然易分享，但输入延迟和鼠标手感控制较弱，不适合作为测量型训练器。

**平台注意事项：**

- 启动时设置 Windows DPI 感知（per-monitor v2），避免系统缩放导致坐标和像素尺寸失真。
- 全屏使用桌面原生分辨率，不做分辨率缩放；窗口模式允许任意尺寸，但会提示全屏更利于测量。
- 静态背景（网格、边框）只预渲染一次；热路径不创建新 Surface。
- 中文字体优先使用系统 `Microsoft YaHei UI`，找不到时使用随包分发的 `Noto Sans SC`（OFL 许可），启动时缓存字体对象。

---

## 5. 总体架构

### 5.1 场景结构

```
main.py
└── eyestrainer.app.App
    ├── Window / FramePacer / FrameStats
    ├── InputState（相对鼠标 + 虚拟准星）
    ├── SceneManager
    │   ├── MenuScene
    │   ├── ModuleSelectScene
    │   ├── SessionScene ── SessionRunner ── TrainingModule
    │   │                                   ├── FlickModule
    │   │                                   └── TrackModule
    │   ├── ResultsScene
    │   ├── HistoryScene
    │   ├── SettingsScene
    │   └── CalibrationScene
    ├── Storage（SQLite 仓库）
    └── Audio
```

场景切换：启动 → 主菜单 → 模块选择 → 训练会话 → 结算 → 返回。历史、设置、校准从主菜单直接进入。

### 5.2 主循环与计时

```python
while running:
    now = time.perf_counter()
    real_dt = now - last_now
    last_now = now
    sim_dt = min(real_dt, 0.05)          # 模拟步长有上限，避免长帧穿模

    events = pygame.event.get()
    scene.handle_events(events, now)
    scene.update(sim_dt, real_dt, now)

    scene.draw(screen)
    present_ts = time.perf_counter()     # 本帧即将提交
    scene.commit_frame(present_ts)       # 给本帧新出现的刺激打时间戳
    pygame.display.flip()
    frame_stats.record(real_dt, present_ts - now)
    pacer.wait(next_deadline)
```

**计时规范：**

- 所有反应时使用基于 `time.perf_counter` 的“回合活跃时钟”，该时钟只在训练进行时累加，暂停、休息、倒计时期间停止。
- 刺激的时间戳在 `commit_frame` 中写入，取值为 `display.flip()` 之前的时刻，代表该刺激最早可见帧。
- 反应时分辨率为一个显示帧；在 144Hz 下约 7ms，在 240Hz 下约 4ms。结果页不显示超出该精度的伪小数。
- 显示链路本身有约 5–20ms 的固定延迟，因此绝对反应时偏高；所有结果保存配置快照，趋势和同配置对比有效，跨设备绝对值仅供参考。
- 模拟使用 `sim_dt`，回合计时使用 `real_dt`；单帧超过 2× 帧预算时记为 long frame，并在回合摘要中计数。
- 每个回合计时使用单调时钟，不依赖系统时间；数据库中的时间为回合相对秒数，另存会话开始时间。

### 5.3 帧率与延迟

- 启动时检测桌面刷新率，默认帧上限 = 刷新率；允许设置为 60 / 120 / 144 / 刷新率 / 无上限。
- 提供两种模式：
  - **低延迟模式（默认）**：关闭垂直同步，帧末最后约 1.5ms 忙等，追求最低输入延迟，可能轻微撕裂。
  - **稳定模式**：开启垂直同步，无撕裂，延迟略高。
- 性能目标：在 144Hz 显示器上，空载 5 分钟平均 FPS ≥ 135，p99 帧时 ≤ 1.5× 帧预算。
- 校准页提供 5 秒自检：平均 FPS、p99 帧时、掉帧数、当前显示模式；自检不通过时提示关闭垂直同步或降低分辨率。

---

## 6. 瞄准与输入

| 场景 | 输入方式 |
|---|---|
| 菜单、设置、历史 | 系统鼠标指针，正常点击 |
| 训练回合 | 隐藏系统指针，进入相对鼠标模式，使用自绘准星 |
| 暂停 / 结算 | 释放相对模式，系统指针回到准星最后位置 |

**相对瞄准：**

- 每帧读取 `pygame.mouse.get_rel()`，准星位置累加 `delta * sensitivity`，并限制在训练场内。
- 默认灵敏度 1.0，含义为 1 个鼠标原始计数移动 1 像素；设置页和模块选择页提供 0.1–5.0 滑杆，模块选择页可在开始训练前直接调整。
- 目标是在 Windows 下让相对模式绕过“增强指针精确度”；这是阶段 0 的实测项。若不满足，使用 `ctypes` 注册 Raw Input 作为后备实现。
- 准星可以更换样式（点 / 十字 / 点+十字）和颜色，默认亮绿色 `#39FF88`。
- 左键按下（LMB down）作为一次“射击”，不区分按下位置；命中判定使用虚拟准星位置。
- `Esc` 暂停；窗口失焦自动暂停；恢复时显示 3 秒倒计时，训练场遮蔽后重新显示，防止暂停期间预判。

**按键：**

- `Esc`：暂停 / 继续（由暂停菜单控制）。
- 训练中不绑定其它操作键，避免误触。
- 菜单支持键盘导航作为可选增强（方向键 + Enter），不阻塞首批。

---

## 7. 会话与回合流程

- **热身（可选，默认开启）**：15 秒低难度回合，标记为 warm-up，不计入趋势、不写入个人最佳。
- **正式回合**：默认 3 回合；甩枪 60 秒（可调），追踪 30 秒（可调），动态视敏 90 秒，周边视野 60 秒；回合间休息 15 秒，可调 0 / 10 / 15 / 30 秒。
- **开始前**：3 秒倒计时，期间显示本回合模式与目标数。
- **结束**：回合结束立即冻结，显示本回合概要；会话结束后进入结算页并写入数据库。
- **暂停**：冻结回合计时、刺激动画、音频；恢复后重新倒计时，不重置回合进度。
- **失焦**：自动暂停并释放鼠标；记录一次事件，结算页提示。
- **中途退出**：当前回合数据丢弃；已完成回合保留，会话状态标记为 incomplete。

---

## 8. 甩枪反应模块（Flick）

### 8.1 场地与目标

- 训练场为屏幕中央的矩形区域，四周留 5% 边距，深色背景 + 细网格 + 弱边框。
- 目标为实心圆，默认颜色 `#FF4F6D`，细描边增强边缘；无中心点、无动画。
- 目标半径、生成位置、生成顺序全部由固定种子的 `random.Random` 驱动，种子写入数据库。
- 点击反馈：白色小十字 hitmarker 持续 80ms；空点击时训练场边框闪红 60ms。音效可关闭。

### 8.2 连击模式（Chain）

**规则：**

- 场上始终维持 3 个目标；点中任意目标后该目标消失，在合法位置立即生成新目标。
- 生成候选点均匀采样于训练场；拒绝条件：
  - 与当前准星距离 < 180px；
  - 与其它目标圆心距离 < 两目标半径之和 + 40px。
  - 最多尝试 200 次，仍无合法点则放宽“距准星距离”至 100px。
- 没有目标存活时限；节奏由玩家自己驱动，记录每次击杀的时间与轨迹。
- 空点击记为 miss，不消灭目标，但计入射击总数和命中率。
- 统计以“点击”为单位，而不是以“目标”为单位。

**指标：**

- 命中率、每分钟击杀数、击杀间隔（IKI）中位数与 IQR；
- 点击误差（归一化到目标半径的中位值）；
- 路径效率（两次击杀之间准星实际移动距离与理想直线距离之比）；
- 当前难度等级与目标半径。

### 8.3 反应模式（Reaction）

**规则：**

- 场上同一时间只有 1 个目标。
- 每个试次：目标消失 → 0.6 秒间隔 → 随机延迟 U(0.8, 2.0)s → 目标出现。
- 目标与准星当前距离至少 250px，确保必须移动。
- 目标出现后 1.5 秒内未被击中记为 timeout，进入下一个试次。
- 目标出现前的左键点击记为 anticipation（预判错误），计为 miss，不计入反应时。
- 目标出现后 100ms 内的命中标记 anticipation，计入命中率但排除在反应时统计外（生理上过快）。

**指标：**

- 命中反应时：目标出现 → 命中点击，中位数、P25、P75；
- 首动反应时：目标出现 → 准星首次移动超过 `max(3px, 0.1×目标半径)` 的时间，中位数；
- 命中率、timeout 数、anticipation 数；
- 目标大小难度等级。

### 8.4 自适应难度

- 唯一难度变量：目标半径。范围 24–80px（连击）/ 28–90px（反应），步进 2px。
- **连击**：每 15 次射击评估最近 15 次的命中率。
  - 命中率 ≥ 90%：半径 −2px；
  - 命中率 ≤ 75%：半径 +2px；
  - 其它：不变。
- **反应**：每 12 个有效试次评估命中率，规则同上。
- 半径变化只影响之后新生成的目标，不改变已存在目标，避免不公平。
- 等级映射（0–100）：等级 0 = 该模式最大半径，等级 100 = 最小半径；公式在模块配置中定义，并记录到每次试次。
- 固定难度模式：关闭自适应时，使用设置页的 0–100 滑杆换算半径。

### 8.5 记录内容

每次射击一行：目标位置/半径、生成时间、点击时间、目标存在时长、命中/空点/超时/预判、点击位置、点击误差、路径长度、理想距离、准星位置、难度等级、首次入靶时间、入靶→点击、过冲、方向变化、峰值速度、曲率。预判点击没有目标，目标字段为空。

每回合额外保存压缩逐帧轨迹：准星位置、最近目标位置/半径、误差、鼠标速度、左键状态、等级和目标 id。轨迹用于结算页可视化与高级指标，不改变命中判定。

---

## 9. 动态追踪模块（Track）

### 9.1 场地与目标

- 训练场同甩枪模块，边距 40px。
- 目标为实心圆，默认半径固定 40px，颜色 `#FF4F6D`；目标不能移出场地。
- 准星与目标的距离只在“按住左键”时计入跟踪统计。

### 9.2 运动模型

首批实现两种轨迹，模块选择页可选：

1. **水平弹跳（bounce）**
   - 初始位置随机，速度方向与水平线夹角在 ±20° 内；
   - 碰到场地边界反射，速度大小不变；
   - 模拟横向拉枪/横向移动的敌人。
2. **航点转向（waypoint，默认）**
   - 每隔 0.8–1.6 秒在场内采样一个新航点（边距 60px）；
   - 目标以当前速度朝航点移动，航向最多按 300°/s 的角速度转向；
   - 到达航点 10px 内后按预设间隔选择下一个点；
   - 轨迹平滑，接近人类急停变向的跟枪场景。

两种模型都由回合种子决定；同种子 + 同配置可以复现完整轨迹。

### 9.3 射击与判定

- 按住左键进入“开火”状态；松开左键期间不累计任何跟踪统计。
- 每帧（dt 加权）记录：
  - 开火时长 `fired_ms`；
  - 准星到目标圆心的距离 ≤ 目标半径时的 `ontarget_ms`；
  - 距离误差 `err_px`。
- 覆盖率 TO/T = Σ ontarget_ms / Σ fired_ms。
- 触发覆盖率 = Σ fired_ms / 回合活跃时长；低于 70% 时结算页提示“本回合开火时间过短，结果参考性下降”。
- 目标移出场地时按反射/转向规则处理，不重置位置。

### 9.4 自适应难度

- 唯一难度变量：目标速度，范围 220–1100 px/s，默认初速 420 px/s。
- 每 5 秒一个评估窗口，用该窗口的 TO/T：
  - TO/T > 80%：速度 ×1.05；
  - TO/T < 55%：速度 ×0.95；
  - 其它：不变。
- 新速度在下一个 5 秒窗口生效，并在 0.4 秒内平滑过渡，避免瞬移。
- 等级映射（0–100）：`(speed − 220) / (1100 − 220) × 100`。
- 固定难度模式：滑杆直接指定速度，不再自动调整。

### 9.5 指标

- 覆盖率 TO/T（主指标），按开火时长加权；
- 平均偏离（px）与归一化偏离（平均偏离 / 目标半径）；
- 平均目标速度、最高目标速度、难度等级；
- 触发覆盖率；
- 长帧计数与无效窗口数。

### 9.6 记录内容

- 每个回合按 1 秒窗口写一行：窗口起止、开火毫秒、命中毫秒、平均误差、最大误差、目标速度、等级。
- 回合摘要包含总开火时长、总命中时长、加权 TO/T、加权平均偏离、速度区间、长帧数。
- 1 秒窗口用于聚合指标；同时每回合保存压缩后的准星/目标轨迹，用于过冲、入靶、修正、滞后等分析（见 12.4）。

---

## 10. 自适应难度总则

1. 只调整一个难度变量，避免多变量同时变化导致指标无法解释。
2. 使用滞回区间（hysteresis），避免在阈值附近来回抖动。
3. 评估窗口内样本不足时保持当前难度。
4. 参数变化只影响新目标或新窗口，不追溯修改已有数据。
5. 自适应开关、参数、起始等级都要写入会话配置快照。
6. 结算页明确展示“本次等级范围”和“是否触顶/触底”，而不是只给一个分数。

---

## 11. 指标定义与统计口径

| 指标 | 定义 / 公式 | 备注 |
|---|---|---|
| 命中反应时 RT | 目标出现 → 命中点击 | 仅反应模式；100–1500ms 有效；中位数 + P25/P75 |
| 首动反应时 | 目标出现 → 准星首次位移超过阈值 | 仅反应模式命中试次 |
| 命中率 | 命中数 / (命中 + 空点 + 超时) | 连击模式无超时；预判点击按空点计 |
| 击杀间隔 IKI | 相邻两次成功击杀的时间差 | 中位数；首杀不参与 |
| 每分钟击杀 | 击杀数 / 回合活跃分钟数 | 不含休息与暂停 |
| 点击误差 | 点击位置到目标圆心的距离 / 目标半径 | 0 = 圆心，1 = 边缘；仅命中 |
| 路径效率 | 理想直线距离 / 准星实际移动距离 | 两次击杀之间；截断到 [0, 1]；仅连击命中 |
| 覆盖率 TO/T | Σ ontarget_ms / Σ fired_ms | 追踪主指标；开火期间按 dt 加权 |
| 触发覆盖率 | Σ fired_ms / 回合活跃时长 | 低于 70% 提示参考性下降 |
| 平均偏离 | Σ(err_px × dt) / Σdt（开火期间） | 同时报告归一化值 |
| 长帧率 | long frame 数 / 回合帧数 | > 2× 帧预算记为 long frame |
| 可辨速度阈值 | 阶梯反转速度的中位数 | 动态视敏；px/s 与 deg/s 同时报告 |
| DVA 正确率 | 正确响应 / 全部试次 | 超时计为错误 |
| 周边检出率 | 命中 / 有目标试次 | 周边视野主指标 |
| 周边误报率 | 误报 / 无目标试次 | 越低越好；同时报告正确抑制 |
| 周边反应时 | 有目标命中试次的刺激→空格 | 中位数 + P25/P75 |
| 偏心角 | 目标像素距离换算的视角 | deg；同时报告最大值 |
| 首次入靶时间 | 目标出现 → 准星首次进入目标圆 | 仅命中试次；来自轨迹采样 |
| 入靶→点击 | 准星首次进入目标 → 命中点击 | 瞄准确认/修正时间；仅命中 |
| 过冲 | 首次入靶后超出目标边缘的最大距离 | px；同时记录过冲次数 |
| 方向变化 | 速度方向改变超过 40° 的次数 | 速度阈值 80px/s；反映修正动作 |
| 轨迹曲率 | 准星路径长度 / 起终点直线距离 | 越接近 1 越直接 |
| 峰值速度 | 准星单帧速度的最大值 | px/s；来自逐帧轨迹 |
| 跟踪滞后 | 准星与历史目标位置最匹配的时间差 | 0–300ms；按开火样本估计 |
| 速度波动 | 开火期间准星速度的标准差 | px/s；反映抖动 |
| 方向修正/秒 | 开火期间速度方向改变次数 / 秒 | 追踪平滑度指标 |

**统计规则：**

- 反应时、IKI、点击误差、路径效率使用中位数和 IQR，不用平均数。
- 会话汇总合并所有非热身回合的原始试次重新计算，不取“回合中位数的平均”。
- 追踪的会话 TO/T 用总命中毫秒 / 总开火毫秒，不平均各回合百分比。
- 显示时附带样本量 n；n 小于 10 的指标标注“样本不足”。
- 不做单一综合评分；结算页按指标分栏展示。
- 轨迹类指标只在完成一次新训练后产生；旧记录显示“暂无数据”，不从旧数据推断。

---

## 12. 数据模型与存储

### 12.1 路径

- 开发环境：`./data/eyestrainer.db`（加入 `.gitignore`）。
- 打包运行：`%APPDATA%/EyesTrainer/eyestrainer.db`。
- 可用环境变量 `EYESTRAINER_DATA_DIR` 覆盖，用于测试和便携模式。
- 日志：同目录 `logs/eyestrainer.log`，按大小轮转；记录版本、显示模式、长帧统计、异常。
- 不联网、不上传任何数据。

### 12.2 表结构

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE profiles (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL              -- UTC ISO 8601
);

CREATE TABLE sessions (
    id          INTEGER PRIMARY KEY,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id),
    app_version TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    config_json TEXT NOT NULL,             -- 显示/输入/模块/校准完整快照
    status      TEXT NOT NULL DEFAULT 'running'  -- running / completed / incomplete
);

CREATE TABLE rounds (
    id          INTEGER PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    module      TEXT NOT NULL,             -- flick / track
    mode        TEXT NOT NULL,             -- chain / reaction / bounce / waypoint
    round_idx   INTEGER NOT NULL,
    is_warmup   INTEGER NOT NULL DEFAULT 0,
    duration_s  REAL NOT NULL,
    seed        INTEGER NOT NULL,
    started_at  TEXT NOT NULL,
    summary_json TEXT NOT NULL
);

CREATE TABLE flick_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    outcome      TEXT NOT NULL,            -- hit / miss_click / timeout / anticipation
    spawn_t      REAL,                     -- 回合相对秒
    click_t      REAL,
    age_ms       REAL,                     -- 目标存在到点击/超时的时长
    first_move_ms REAL,                    -- 仅反应模式
    target_x     REAL, target_y REAL, target_r REAL,
    cross_x      REAL, cross_y REAL,
    click_err    REAL,                     -- 归一化点击误差
    path_px      REAL, ideal_px REAL,
    level        REAL,                     -- 0–100
    flags        TEXT,                     -- 逗号分隔：anticipation, long_frame 等
    target_id    INTEGER,                  -- 本次试次对应目标
    entry_ms     REAL,                     -- 首次入靶时间
    correction_ms REAL,                    -- 入靶到点击
    overshoot_px REAL,
    overshoot_count INTEGER,
    direction_changes INTEGER,
    peak_speed   REAL,
    curvature    REAL
);

CREATE TABLE track_windows (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    window_idx   INTEGER NOT NULL,
    t_start      REAL NOT NULL,
    t_end        REAL NOT NULL,
    fired_ms     REAL NOT NULL,
    ontarget_ms  REAL NOT NULL,
    mean_err_px  REAL,
    max_err_px   REAL,
    speed        REAL NOT NULL,
    level        REAL NOT NULL,
    lag_ms       REAL,
    jitter       REAL,
    dir_changes  REAL,
    peak_speed   REAL,
    error_std    REAL
);

CREATE TABLE round_motion (
    round_id     INTEGER PRIMARY KEY REFERENCES rounds(id) ON DELETE CASCADE,
    sample_count INTEGER NOT NULL,
    format       TEXT NOT NULL,            -- flick / track
    data         BLOB NOT NULL             -- zlib 压缩的逐帧轨迹
);

CREATE TABLE dva_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    speed_px_s   REAL NOT NULL,
    speed_deg_s  REAL NOT NULL,
    gap_dir      INTEGER NOT NULL,          -- 0右/1上/2左/3下
    response     INTEGER,                   -- 同上；空为超时
    correct      INTEGER NOT NULL,
    timeout      INTEGER NOT NULL,
    rt_ms        REAL,
    start_t      REAL NOT NULL,
    visible_end_t REAL NOT NULL,
    target_y     REAL NOT NULL,
    radius       REAL NOT NULL,
    level        REAL,
    reversal     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE peripheral_trials (
    id           INTEGER PRIMARY KEY,
    round_id     INTEGER NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,
    trial_idx    INTEGER NOT NULL,
    target_present INTEGER NOT NULL,
    responded    INTEGER NOT NULL,
    correct      INTEGER NOT NULL,
    false_alarm  INTEGER NOT NULL,
    miss         INTEGER NOT NULL,
    rt_ms        REAL,
    eccentricity_deg REAL NOT NULL,
    exposure_ms  REAL NOT NULL,
    stimulus_count INTEGER NOT NULL,
    target_angle REAL,
    level        REAL
);

CREATE INDEX idx_rounds_session ON rounds(session_id);
CREATE INDEX idx_flick_round ON flick_trials(round_id);
CREATE INDEX idx_track_round ON track_windows(round_id);
CREATE INDEX idx_sessions_started ON sessions(started_at);
```

- 使用 WAL 模式；`PRAGMA user_version` 记录 schema 版本（当前为 3），便于迁移。
- v2 迁移新增轨迹列与 `round_motion` 表，并把旧版 `track/chain`、`track/reaction` 记录归一化为 `track/waypoint`（旧版追踪模块实际执行的就是航点运动）。
- v3 迁移新增 `dva_trials` 与 `peripheral_trials` 表；旧数据不重算轨迹类指标。
- 默认创建一个名为 `default` 的本地档案；表结构已预留多档案能力。
- 回合摘要 `summary_json` 保存该回合所有派生指标及计算版本号；原始试次仍保留，可重算。
- 写入会话时使用事务：会话开始写 `sessions(status='running')`，每回合结束后写该回合和试次，正常结束时更新 `status='completed'`；异常退出下次启动时把遗留的 `running` 标记为 `incomplete`。

### 12.3 导出

- 历史页支持导出当前筛选结果为 CSV：`flick_trials.csv`、`track_windows.csv`、`dva_trials.csv`、`peripheral_trials.csv`、`rounds.csv`、`sessions.csv`，以及逐帧轨迹 `motion_samples.csv`。
- `motion_samples.csv` 包含每帧时间、准星坐标、目标坐标/半径、误差、鼠标速度、等级与标志位，便于外部做二次分析。
- 导出到 `<数据目录>/exports/`，文件名带时间戳；完成后显示完整路径，不弹系统文件对话框。
- CSV 使用 UTF-8 BOM，保证 Excel 直接打开中文不乱码。

### 12.4 轨迹数据格式

- 每回合保存一份 `round_motion` 记录，`format` 为 `flick` 或 `track`。
- `data` 是 zlib 压缩的二进制：12 字节头（magic `ETM1`、版本、格式、样本数）+ 每帧 42 字节固定结构。
- 每帧字段：时间 ms、准星 x/y、目标 x/y/半径、误差、鼠标速度、等级、目标 id、标志位（左键、在靶、有目标）。
- 编码/解码、抽样和高级指标计算集中在 `eyestrainer/core/motion.py`。修改格式必须递增版本号，并保留对旧版本的解码兼容或迁移方案。
- 逐帧轨迹只在本机数据库和用户主动导出的 CSV 中出现，不联网。

---

## 13. 界面与视觉

### 13.1 视觉规范

| 用途 | 颜色 |
|---|---|
| 背景 | `#0B0E14` |
| 面板 | `#121722` |
| 边框 / 网格 | `#1E2735` |
| 主文本 | `#E6EDF3` |
| 次文本 | `#8B98A9` |
| 强调 / 准星 | `#39FF88` |
| 目标 | `#FF4F6D` |
| 警告 | `#FFC857` |
| 命中标记 | `#FFFFFF` |

- 无渐变、无模糊、无动态背景；训练场只保留细网格和弱边框。
- 目标颜色提供色盲友好备选：蓝色 `#4FA3FF` + 准星黄色 `#FFD166`。
- UI 以 1080p 为基准按窗口高度缩放，范围 0.75–1.5；最小支持 1280×720。
- 字体：`Microsoft YaHei UI` / `Noto Sans SC`；标题 44 / 28px，正文 20px，辅助 16px，HUD 30px（1080p 基准）。
- 避免高于 3Hz 的闪烁；不使用全屏白闪。

### 13.2 主菜单

- 标题 `EyesTrainer` + 副标题“FPS 视觉与反应训练”。
- 菜单项：开始训练 / 历史记录 / 设置 / 校准 / 退出。
- 底部显示当前档案名、版本号、累计训练时长。

### 13.3 模块选择

- 四张模块卡片：甩枪反应、动态追踪、动态视敏、周边视野。
- 每个卡片选择模式、回合时长、自适应开关、固定难度滑杆。
- 页面直接提供“鼠标灵敏度”滑杆（仅鼠标模块显示），修改后写入设置并在开始训练时保存；固定难度滑杆仅在关闭自适应时显示。
- 动态视敏与周边视野标注为键盘模块，隐藏灵敏度滑杆，保留固定难度滑杆。
- 显示该模块个人最佳与最近一次成绩摘要。
- 大按钮“开始训练”，`Esc` 返回。

### 13.4 训练 HUD

- 顶部中央：回合剩余时间。
- 顶部右侧：当前难度等级（如“等级 42”），不显示实时分数。
- 默认不显示 FPS；调试快捷开关可在设置中开启 FPS / 帧时叠加。
- 命中反馈：hitmarker + 轻音效；空点反馈：边框短闪。
- 暂停菜单：继续 / 重新开始本回合 / 结束本次训练 / 设置 / 返回主菜单。

### 13.5 结算页

- 第一行指标卡片：主指标、命中率 / 覆盖率、等级范围、与上次和最佳值的差值。
- 第二行：反应时/IKI 分布直方图、覆盖率趋势、动态视敏速度阶梯或周边视野偏心角阶梯；鼠标模块可切换到“轨迹分析”查看准星/目标轨迹。
- 侧栏增加首次入靶、入靶→点击、过冲、方向变化、峰值速度、跟踪滞后、速度波动、阶梯反转、漏检/误报等高级指标。
- 数据质量提示：长帧数、无效窗口、触发覆盖率不足、暂停次数。
- 按钮：再来一次 / 返回模块选择 / 查看历史。
- 热身回合单独展示，标注“不计入统计”。

### 13.6 历史页

- 默认打开最近一次有正式回合的训练的模块/模式；也可手动切换筛选。
- 筛选：模块 + 模式；时间范围（最近 10 次 / 30 天 / 全部）。
- 指标切换：命中率、反应时中位数、IKI 中位数、TO/T、路径效率，以及首次入靶、过冲、跟踪滞后、方向修正、可辨速度阈值、周边检出率/误报率等指标。
- 折线图 + 个人最佳标记；每个点对应一次会话。
- 配置不一致的会话加提示图标（分辨率、灵敏度、刷新率、模块参数）。
- 会话列表：日期、模式、时长、关键指标、状态；支持导出 CSV。

### 13.7 设置页

- 显示：全屏、帧上限、垂直同步、低延迟模式、UI 缩放。
- 输入：灵敏度、准星样式/颜色/大小、指针加速说明。
- 音频：主音量、命中音、空点音、结束音。
- 训练：回合时长、回合数、组间休息、热身开关、自适应默认开关。
- 护眼：休息提醒间隔（15 / 25 / 40 分钟 / 关闭）。
- 数据：档案名、数据目录显示、导出位置、清空数据（二次确认）。
- 校准：屏幕对角线尺寸、观看距离、刷新率检测、5 秒性能自检。

### 13.8 校准页

- 自动检测桌面刷新率和当前显示模式；检测失败允许手动选择。
- 5 秒空载自检：平均 FPS、p99 帧时、掉帧数、建议。
- 像素视角换算：输入屏幕对角线英寸、宽高比、观看距离，计算 `px_per_deg`；动态视敏与周边视野直接使用它换算速度（deg/s）与偏心角。
- 灵敏度在设置页和模块选择页调整，校准页不再重复提供试移区。

---

## 14. 音频与护眼

**音频：**

- 全部由程序合成，无外部音频资源；采样率 44100，单声道，mixer buffer 512。
- 命中：880Hz 正弦波 25ms + 短噪声点击；空点：180Hz 60ms；倒计时：660Hz 60ms；回合结束：双音上行。
- 默认音量 0.3，可单独关闭命中/空点音效。
- 音频只做反馈，不参与计时。

**护眼：**

- 累计“训练活跃时长”，暂停和休息不计。
- 默认每 25 分钟弹出全屏休息层：20 秒倒计时 + 20-20-20 提示 + 建议远眺。
- 休息层不可被点击穿透；倒计时结束后可关闭。设置可改为 15 / 40 分钟或关闭。
- 每次会话结束提示休息 1–2 分钟。
- 首次启动显示简短免责声明：本工具不是医疗设备；如有眼痛、头痛、眩晕，请停止使用并咨询专业人士。

---

## 15. 目录结构

```
EyesTrainer/
├── main.py                      # 启动入口
├── pyproject.toml               # 项目元数据、依赖、pytest 配置
├── README.md
├── docs/
│   └── DESIGN.md                # 本文档
├── eyestrainer/
│   ├── __init__.py
│   ├── __main__.py              # python -m eyestrainer
│   ├── app.py                   # App、主循环、场景切换
│   ├── config.py                # 默认配置、加载/保存、迁移
│   ├── core/
│   │   ├── __init__.py
│   │   ├── timing.py            # FramePacer、FrameStats、回合时钟
│   │   ├── input.py             # InputState、相对鼠标、虚拟准星
│   │   ├── stats.py             # 中位数/IQR、滚动窗口、自适应控制器
│   │   ├── storage.py           # SQLite 仓库、schema、导出
│   │   ├── audio.py             # 合成音效
│   │   ├── font.py              # 中文字体解析与缓存
│   │   └── geometry.py          # 圆判定、路径长度、角度换算
│   ├── scenes/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── menu.py
│   │   ├── module_select.py
│   │   ├── session.py           # SessionRunner：回合、休息、暂停、写库
│   │   ├── results.py
│   │   ├── history.py
│   │   ├── settings.py
│   │   └── calibration.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── base.py              # TrainingModule 协议 / 基类
│   │   ├── flick.py
│   │   └── track.py
│   └── ui/
│       ├── __init__.py
│       ├── theme.py
│       ├── widgets.py           # 按钮、滑杆、卡片、标签页
│       ├── charts.py            # 折线图、直方图
│       └── hud.py
├── tests/
│   ├── test_stats.py
│   ├── test_adaptive.py
│   ├── test_geometry.py
│   ├── test_storage.py
│   ├── test_config.py
│   └── test_scene_smoke.py      # SDL_VIDEODRIVER=dummy
└── data/                        # 开发期数据库与导出（.gitignore）
```

---

## 16. 核心接口

```python
@dataclass
class InputFrame:
    crosshair: tuple[float, float]
    delta: tuple[float, float]
    lmb_down: bool
    lmb_pressed: bool
    lmb_released: bool
    events: list[pygame.event.Event]

@dataclass
class RoundResult:
    module_id: str
    mode: str
    round_idx: int
    is_warmup: bool
    duration_s: float
    seed: int
    summary: dict
    trials: list[dict]
    windows: list[dict]

class RoundResult:
    ...
    motion_blob: bytes | None
    motion_format: str
    motion_count: int
    arena: tuple[float, float, float, float] | None

class TrainingModule(Protocol):
    module_id: str

    def begin_round(self, cfg: ModuleConfig, seed: int) -> None: ...
    def handle_events(self, inp: InputFrame, t: float) -> None: ...
    def update(self, dt: float, t: float) -> None: ...
    def draw(self, surf: pygame.Surface, theme: Theme) -> None: ...
    def commit_frame(self, present_t: float) -> None: ...
    def end_round(self, t: float) -> RoundResult: ...
```

**职责边界：**

- `SessionRunner`：负责倒计时、回合时长、休息、暂停、热身标记、调用模块、写数据库；不关心目标生成和判定。
- `TrainingModule`：只负责本模块的刺激、判定、自适应、指标收集；不直接写数据库、不直接读键盘。
- `InputState`：把原始事件整理成 `InputFrame`；负责相对模式和系统指针切换。
- `Storage`：参数化 SQL，事务写入，导出；不包含业务判定。
- 所有时间参数由 `SessionRunner` 传入回合相对时间 `t`；模块不自己调用 `time.perf_counter()`，便于测试注入假时钟。

---

## 17. 默认参数

| 分组 | 参数 | 默认值 | 范围 / 备注 |
|---|---|---|---|
| 全局 | 刷新率 | 自动检测 | 失败时手动选择 |
| 全局 | 帧上限 | 刷新率 | 60 / 120 / 144 / 刷新率 / 无上限 |
| 全局 | 垂直同步 | 关闭 | 低延迟优先 |
| 全局 | 低延迟忙等 | 开启 | 最后约 1.5ms |
| 全局 | 倒计时 | 3s | 固定 |
| 全局 | 模拟 dt 上限 | 50ms | 固定 |
| 全局 | long frame 阈值 | 2× 帧预算 | 摘要统计 |
| 甩枪 | 训练场边距 | 5% 屏幕 | — |
| 甩枪-连击 | 同屏目标数 | 3 | 2–5 |
| 甩枪-连击 | 目标半径 | 48px | 24–80px，自适应 |
| 甩枪-连击 | 距准星最小生成距离 | 180px | 放宽下限 100px |
| 甩枪-连击 | 目标间距 | 两半径之和 + 40px | — |
| 甩枪-连击 | 自适应窗口 | 15 次射击 | — |
| 甩枪-连击 | 缩容 / 扩容阈值 | 90% / 75% | 步进 2px |
| 甩枪-反应 | 目标半径 | 56px | 28–90px |
| 甩枪-反应 | 预刺激延迟 | 0.8–2.0s 均匀 | — |
| 甩枪-反应 | 超时 | 1.5s | — |
| 甩枪-反应 | 试次间隔 | 0.6s | — |
| 甩枪-反应 | 距准星最小距离 | 250px | — |
| 甩枪-反应 | 自适应窗口 | 12 试次 | — |
| 追踪 | 目标半径 | 40px | 固定 |
| 追踪 | 初始速度 | 420px/s | 220–1100px/s |
| 追踪 | 自适应窗口 | 5s | — |
| 追踪 | 目标 TO/T 区间 | 55%–80% | 滞回 |
| 追踪 | 速度步进 | ×1.05 / ×0.95 | 每窗口最多一次 |
| 追踪 | 航点间隔 | 0.8–1.6s | waypoint 模式 |
| 追踪 | 最大转向速率 | 300°/s | waypoint 模式 |
| 回合 | 甩枪回合 | 60s × 3 | 可配置 30/60/90s，1–5 回合 |
| 回合 | 追踪回合 | 30s × 3 | 可配置 20/30/60s，1–5 回合 |
| 回合 | 组间休息 | 15s | 0/10/15/30s |
| 回合 | 热身 | 开启，15s | 不计入统计 |
| 音频 | 主音量 | 0.3 | 0–1 |
| 护眼 | 休息提醒 | 25 分钟 | 15/25/40/关闭 |
| 动态视敏 | 回合时长 | 90s | 固定，3 回合 |
| 动态视敏 | 速度范围 | 8–60 deg/s | 阶梯初始 20 deg/s，步进 6% |
| 周边视野 | 回合时长 | 60s | 固定，3 回合 |
| 周边视野 | 偏心角范围 | 8–25° | 自适应初始 12° |
| 周边视野 | 曝光 / 响应窗口 | 150ms / 900ms | 固定 |
| 轨迹 | 采样 | 每个训练活跃帧 | 单回合上限 120000 帧；zlib 压缩 |
| 轨迹 | 高级指标窗口 | 每 5 秒 / 每个命中试次 | 见 11、12.4 |

> 以上数值是初始默认值，实现后需通过实际试玩调参；调整必须记录在案，并体现在会话配置快照中。

---

## 18. 里程碑与验收标准

### 阶段 0：基础框架

**交付：**

- 项目骨架、pyproject、入口、场景管理器；
- 全屏窗口、DPI 感知、帧循环、帧统计、低延迟模式；
- 相对鼠标 + 虚拟准星 + 灵敏度设置；
- 中文字体、主题、基础按钮/滑杆控件；
- 设置加载/保存/迁移；
- 校准页：刷新率检测、5 秒性能自检。

**验收：**

- 144Hz 显示器、关闭垂直同步、帧上限 144 时，空载 5 分钟平均 FPS ≥ 135，p99 帧时 ≤ 1.5× 帧预算。
- 相对准星移动无漂移、无系统指针残留；暂停后系统指针出现在准星最后位置。
- 设置重启后保留；中文正常显示；无控制台异常。
- 相对鼠标是否绕过 Windows 指针加速有明确结论；不满足时有 Raw Input 后备方案记录。

### 阶段 1：甩枪反应模块

**交付：**

- 连击模式、反应模式；
- 自适应/固定难度；
- 回合、休息、暂停、热身流程；
- 结算页核心指标；
- SQLite 写入与读取；
- 基础音效。

**验收：**

- 60 秒连击回合可完整运行；命中、空点、超时、预判分类正确。
- 反应时只统计有效命中；预判与超时正确排除；结果页中位数/IQR 与独立复算一致。
- 数据库重启后保留数据，试次行数与游戏内计数一致。
- 开关自适应后，目标半径范围与步进符合本文档。
- 暂停期间反应时不累计；失焦自动暂停。

### 阶段 2：动态追踪模块

**交付：**

- 水平弹跳、航点转向两种轨迹；
- 按住左键的跟踪判定；
- 5 秒窗口自适应速度；
- 覆盖率、偏离、触发覆盖率指标；
- 窗口级数据写入。

**验收：**

- 同种子 + 同配置重复运行，轨迹完全一致。
- 回合 TO/T 与从窗口数据独立复算的结果误差 ≤ 0.5 个百分点。
- 自适应速度只在窗口边界调整，且不超过 220–1100px/s。
- 触发覆盖率 < 70% 时结算页出现提示。
- 长帧计数正确，且不影响回合计时。

### 阶段 3：数据与打磨

**交付：**

- 历史页趋势图、个人最佳、配置不一致提示；
- CSV 导出；
- 结算页与上次/最佳对比；
- 护眼休息提醒；
- 暂停菜单、异常退出恢复；
- 多档案（可选）；
- PyInstaller 打包（可选）。

**验收：**

- 历史图与数据库数据一致；筛选、指标切换正确。
- CSV 在 Excel 中打开无乱码，字段与表结构一致。
- 25 分钟累计训练后触发休息层，暂停期间不计时。
- 异常关闭后重启，遗留会话标记为 incomplete，不崩溃。

### 阶段 4：动态视敏 + 周边视野（已实现）

- 动态视敏：Landolt C、2-down-1-up 速度阶梯、可辨速度阈值（deg/s）。
- 周边视野：中央注视、周边目标/干扰项、自适应偏心角、检出率/误报率/反应时。
- 两个模块均为键盘操作；不产生鼠标轨迹。

---

## 19. 测试策略

**单元测试：**

- `stats`：中位数、IQR、滚动窗口、滞回控制器、分组聚合。
- `geometry`：圆命中、点击误差、路径效率截断、角度/像素换算。
- `storage`：建表、迁移、事务回滚、会话/回合/试次写入与查询、CSV 导出。
- `config`：默认值、缺字段兼容、版本迁移、损坏文件回退。
- 模块逻辑：用固定种子验证目标生成约束、限时、预判标记、自适应参数范围。

**轨迹测试：**

- 二进制轨迹编码/解码往返。
- 首次入靶、入靶→点击、过冲、方向变化、曲率等合成轨迹断言。
- 追踪滞后检测（已知延迟的合成轨迹）。
- v1→v2 数据库迁移：新增列/表、旧追踪模式归一化。
- 轨迹 CSV 导出与原始样本解码。

**新增模块测试：**

- 动态视敏：正确/错误/超时响应、固定难度速度、2-down-1-up 反转、阶梯阈值。
- 周边视野：命中、漏检、误报、正确抑制、自适应偏心角。
- schema v3 迁移与 `dva_trials` / `peripheral_trials` 写入。
- 模块选择、结算与历史页的新模块入口和指标聚合。

**无头集成测试：**

- `SDL_VIDEODRIVER=dummy`，启动 App、进入各场景、绘制一帧、退出，确保无异常。
- 用假时钟驱动 SessionRunner 的完整回合，验证计时、暂停、休息、结算数据。

**手动验收清单：**

- 1280×720 / 1920×1080 / 2560×1440 三种分辨率布局不重叠。
- 鼠标手感、灵敏度、准星位置、暂停恢复一致。
- 垂直同步开/关、帧上限各档位下的帧时表现。
- 音频开关、音量、护眼提示。
- 长时间（30 分钟）运行无内存增长、无句柄泄漏。

---

## 20. 风险与待验证项

| 风险 | 影响 | 应对 | 验证阶段 |
|---|---|---|---|
| SDL 相对模式在 Windows 下是否绕过指针加速 | 手感与跨设备一致性 | 实测；必要时用 `ctypes` 注册 Raw Input | 阶段 0 |
| 显示链路延迟未知 | 绝对反应时偏高 | 文档说明；固定配置比较；不宣传绝对毫秒排名 | 阶段 0 |
| Windows 合成器 / 无边框全屏帧节奏不稳 | 掉帧、反应时噪声 | 默认全屏 + 低延迟模式；p99 帧时监控；稳定模式备选 | 阶段 0 |
| 高 DPI 缩放导致坐标失真 | 点击偏移、目标尺寸错误 | 启动设置 per-monitor v2 DPI 感知；全屏原生分辨率 | 阶段 0 |
| 中文字体缺失 | 界面乱码 | 系统字体优先 + 内置 Noto Sans SC 后备 | 阶段 0 |
| 时间戳只有帧级精度 | 反应时量化误差 | 144Hz 以上推荐；文档披露；后续尝试读取 SDL 事件时间戳 | 阶段 1 |
| 设置变化导致历史不可比 | 趋势误读 | 快照配置；历史页标记不一致；同配置筛选 | 阶段 3 |
| 训练向 FPS 的迁移未经验证 | 用户预期过高 | 文案明确“任务特异性训练”；不承诺段位提升 | 全程 |
| PyInstaller 误报 / 启动慢 | 分发困难 | 优先 `onedir`；延迟到阶段 3 再处理 | 阶段 3 |
| 周边视野无法强制中央注视 | 偏心角数据可能偏乐观 | 中央十字与提示；无眼动仪时为行为要求，结果标注为自报注视 | 阶段 4 |
| DVA 速度依赖屏幕尺寸/校准 | 跨设备阈值不可直接比较 | 使用 `px_per_deg` 输出 deg/s，同时保存 px/s 与配置 | 阶段 4 |
| 长时间训练导致眼疲劳 | 健康风险 | 休息提醒、单次时长建议、免责声明 | 阶段 3 |

---

## 21. 动态视敏与周边视野（已实现）

### 21.1 动态视敏（DVA，Landolt C）

- 目标为带缺口的圆环（Landolt C），缺口朝上/下/左/右，4 选 1；缺口宽度约为外径的 1/3–1/5。
- 圆环从场地一侧水平匀速移动到另一侧，速度 `v` 为唯一难度变量；每试次随机起始侧与缺口方向。
- 玩家用方向键或 WASD 回答；回答窗口到圆环离场后 300ms，超时计为错误。
- 自适应：2-down-1-up 阶梯法（连续 2 次正确升速，1 次错误降速），步进 6%，速度范围 8–60 deg/s，初始 20 deg/s。阈值取最近反转速度的中位数，目标正确率约 70.7%。
- 回合时长 90 秒；热身使用 12 deg/s 固定速度；关闭自适应时由固定难度滑杆映射 8–60 deg/s。
- 指标：可辨速度阈值（deg/s 与 px/s）、正确率、反应时中位数、阶梯反转次数、平均/最终速度。
- 使用校准页的 `px_per_deg` 换算 deg/s；结果页显示速度阶梯与阈值参考线。

### 21.2 周边视野（Peripheral）

- 中央固定注视十字；每试次在左右两侧近水平方向闪现 3 个刺激，其中按 60% 概率有一个实心目标，其余为空心干扰项。
- 刺激曝光 150ms，响应窗口 900ms；玩家用空格报告“看到实心目标”，不移动鼠标。目标/干扰项位置避开中央注视区。
- 偏心角范围 8–25°（像素距离由 `px_per_deg` 换算并在场地内裁剪）；自适应窗口 8 个试次：检出率 ≥85% 且误报率 ≤10% 时偏心角 +1°，检出率 <60% 或误报率 >25% 时 −1°。
- 回合时长 60 秒；热身 8°；关闭自适应时由固定难度滑杆映射 8–25°。
- 指标：周边检出率、误报率、正确抑制、周边反应时中位数、平均/最大偏心角、曝光与刺激数。
- 依赖校准页的屏幕尺寸与观看距离；需要提示玩家保持头部和注视点不动。无眼动仪，中央注视为行为要求而非硬件强制。

### 21.3 反应抑制（Go/No-Go，可选）

- 红色目标点击，蓝色目标不点击；红蓝比例随机。
- 指标：误触率（commission error）、遗漏率（omission error）、正确反应时。
- 更贴近实战；当前四个训练项目已完成，Go/No-Go 作为可选扩展保留。

---

## 附录 A：用户设置草案

```json
{
  "version": 1,
  "profile": "default",
  "display": {
    "fullscreen": true,
    "fps_cap": 0,
    "vsync": false,
    "low_latency": true,
    "ui_scale": "auto"
  },
  "input": {
    "sensitivity": 1.0,
    "crosshair": {
      "style": "cross_dot",
      "color": "#39FF88",
      "size": 12
    }
  },
  "audio": {
    "volume": 0.3,
    "hit": true,
    "miss": true,
    "round_end": true
  },
  "training": {
    "warmup": true,
    "adaptive": true,
    "flick_round_s": 60,
    "track_round_s": 30,
    "rounds": 3,
    "rest_s": 15
  },
  "eye_care": {
    "reminder_min": 25
  },
  "calibration": {
    "screen_diagonal_in": 24.0,
    "view_distance_cm": 60.0
  }
}
```

- 模块级参数（目标半径、速度、窗口大小）不放入用户设置，由模块默认值 + 固定难度滑杆控制，并写入会话快照。
- 设置文件损坏时备份为 `settings.json.bad` 并回退默认值，不阻止启动。

---

## 附录 B：术语

| 术语 | 含义 |
|---|---|
| RT | Reaction Time，反应时 |
| 首动反应时 | 刺激出现到准星首次明显移动的时间 |
| IKI | Inter-Kill Interval，相邻两次击杀的间隔 |
| TO/T | Time on Target，开火期间准星覆盖目标的时间占比 |
| Landolt C | 带缺口圆环，用于视敏度测量 |
| 阶梯法 | 根据对错动态调整难度的心理物理阈值测量方法 |
| Long frame | 超过 2 倍帧预算的单帧 |
