# Harness 引擎及飞书集成优化记录

**日期**: 2026-04-17
**目标**: 解决 Harness 本地运行环境双依赖冲突、优化飞书互动卡片交互体验、规范化 AI 智能体生成产物路径及 Web 面板同步。

---

## 1. 统一 Harness 与飞书机器人的 Python 虚拟环境
### 问题背景
由于 `start.sh` 脚本维护了主控引擎（`.venv`）和飞书机器人（`feishu-claude-code/.venv`）两个独立的虚拟环境，导致主环境运行 `feishu_notifier.py` 时缺少 `python-dotenv`，以及后续容易发生依赖错位和重复安装的问题。此外，根目录遗失了核心依赖清单 `requirements/runtime.txt`。
### 修改指引
- 将飞书项目特有依赖合并至 `requirements/runtime.txt`。
- 修改启动脚本，废弃子环境，让整个工程统一使用 `$VENV` 运行，减少环境碎片化。
- 安全清理了废弃的 `feishu-claude-code/requirements.txt` 和 `feishu-claude-code/.venv`。
### 涉及文件
- `start.sh`
- `requirements/runtime.txt`
- `feishu-claude-code/requirements.txt` (已删除)
- `feishu-claude-code/.venv` (已删除)

---

## 2. 增强并重构飞书交互卡片体验
### 问题背景
- 当发生 `NEED_HUMAN` 挂起时，原卡片的交互是：点击某一选项后，其他选项全部消失，且底部有生硬的文字提示。
- 处理人 ID 均为 `ou_xxx`，难以辨认具体操作者。
- 用户想要附写一段补充说明时，必须被迫同时选择某个选项。
### 修改指引
- **按钮交互留痕**：改用正式的 Feishu Button `disabled` 属性，发生点击后，保留所有按钮但将其全部“置灰”，并在被选中的按钮打上 `(已处理)` 的高亮标记，完美还原决策现场。
- **发送机制优化**：在卡片挂起选项中注入一个专用的 **“📤 仅发送说明”** 的按键，支持用户只用文本框做纯文字反馈。去除了原先生硬的 `**操作区状态**` 文本行。
- **人员实名展示**：解析卡片回调信息，当识别到操作者前缀为 `ou_` / `oc_` 时，自动转为包含 `<at id="ou_xxx"></at>` 的飞书标准 At 标签语法，使得端侧自然展示处理人的花名（如：@张三）。
### 涉及文件
- `feishu-claude-code/main.py`
- `engine/feishu_notifier.py`

---

## 3. 全局规范产物输出目录及底层卡片摘要策略
### 问题背景
- **产物散落问题**：AI 会直接在项目主根目录下建立形如 `design/`、`src/`、`docs/` 的目录及文件。我们希望所有的生成成果都能被统一内聚到 `output/` 这个顶级文件夹下。
- **摘要遭截断与风险项不清**：AI 找出的“6 个高风险/待确认项”在飞书卡片里由于 500 字符限制和默认 `summary` 的编写要求，未被详细罗列。
- **Web 面板文件“表里不一”**：Web 面板上挂载的产物仅仅是大模型的聊天嘴炮过程，而非落地在硬盘上的真实深度内容文件。
### 修改指引
- **输出约束**：在底层 `pipeline_runner.py` 拼接的 Global Prompt 中注入最高级强校验指令（`CRITICAL REQUIREMENT`），强制所有阶段的 AI 将包含代码、架构等物理文件直接写入加了 `output/` 前缀的绝对路径下。
- **优化 Git 屏蔽区**：在 `.gitignore` 抹去原来的各类松散规约，统一屏蔽 `output/` 文件夹。
- **挂起报告要求具象化**：修改 AI 的告警指令：触发 `NEED_HUMAN` 挂起请求时，必需将具体的高风险点用条目列表展现在 `<summary>` 中。同时调大了正则匹配卡片摘要的截断上限（从 500 放宽到 3000 字符）。
- **统一真假产物源**：重构 `_materialize_stage_artifacts` 挂载及打包归档方法，使其不再用聊天文本强行覆盖写入附件，而是准确地挂载 `output/` 对应子目录中由各种工具（Read/Write/Glob）直接落地出来的包含真材实料的文件。
### 涉及文件
- `engine/pipeline_runner.py`
- `.gitignore`

---

## 4. 事件流与底层日志净化策略
### 问题背景
- **满屏的思考过程与冗长代码**：大模型执行时的 `Thinking Process` 或 `<thought>` 标签会完整输出到前端页面，以及使用工具生成巨长代码（或 `shell` 脚本）时全部原文会被当作事件抛出，导致用户的 Web 面板变得极其杂乱，无法正常阅读执行轨迹。
- **底层引擎和 CLI 排版符号泄漏**：强制指定 `--json` 格式的环境下，Copilot/Claude 底层 CLI 会强制输出一些面向终端的排版符号、搜索进度提示（如 `● Create...`, `│ mkdir -p ...`, `└ 1 line...`, `└ No matches found`），这些内容因无法解析为 JSON 被当作未格式化的纯文本事件泄漏。

### 修改指引
- **去除模型内部对话内容**：在 `pipeline_runner.py` 中运用正则表达式过滤掉大模型所有的 `Thinking Process` 和 `<thought>...</thought>` 内容。并将工具反馈内容做阈值截断、或在大量输出时仅显示简单结论 `● [输出了一段代码/预置数据]` 等字样。
- **底层调度拦截与正则净化**：在调用飞书卡片的 `claude_runner.py` 和支撑 Web 面板运行回调的 `integrations.py` 中，增加了对 `JSONDecodeError` 的拦截处理。遇到文本输出时，移除 ANSI 颜色码后，对以制表符或状态符（`│`, `└`, `┌`, `├`, `┤`, `┼`, `┴`, `┬`, `─`, `●`）打头、或以 `line...` 结尾、或包含 `no matches found` 的垃圾命令行日志打上标记并直接静默抛弃，极大提升 Web 日志的纯净度。

### 涉及文件
- `engine/pipeline_runner.py`
- `engine/integrations.py`
- `feishu-claude-code/claude_runner.py`

---

## 5. Web 面板前端 UI 样式修复
### 问题背景
- **卡片溢出堆叠**：用户发现在 Web 面板（Dashboard）的“产物查看”页面侧边栏选取任务时，原来应该单排列表显示的任务变成了两两一行挤在一起并发生换行，严重影响交互体验。

### 修改指引
- **重构输出布局 CSS**：排查发现 `dashboard.css` 中 `.outputs-task-list` 样式被不慎配为了 `display: grid; gap: 10px;`，导致内部卡片宽度适配错误。将其更正为 `display: flex; flex-direction: column;` 后强制垂直堆叠，页面布局恢复正常。

### 涉及文件
- `dashboard/assets/css/dashboard.css`

---

## 6. 飞书卡片文本框输入丢失与表单回传修复
### 问题背景
- **输入截断与发送丢失**：用户发现在飞书卡片中输入补充说明并点击“仅发送说明”时，大模型和后端收到的都是“未提供”。
- **表单未封装**：根据飞书最新的卡片规范，未包含在 `<form>` 组件内的乱序输入框如果不按回车失去焦点，直接点击按钮时输入值不会随事件（`value`）携带回传。
- **发送按钮冗余导致的交互混淆**：原来的输入框末尾默认带有一个冗余的回车提交/发送行为配置，当用户点击发送按钮本身，和点击下方的“仅发送说明”、“批准业务”等按钮存在明显的逻辑割裂与状态机碰撞。
- **审批类型状态误判**：对于 `Approval` 审批流状态下的“仅发送文本”操作，回调函数里缺失了 `"comment_only"` 的判定，错误跌入了 `else` 导致后端将纯解释操作当作了“拒绝继续”。

### 修改指引
- **组件表单化合并设计**：在 `feishu_client.py` 中重构卡片打包逻辑，当卡片设定了 `use_input=True` 时，强制将输入框与底部的决策按钮组封入一个完整的 `"tag": "form"` 结构内，并将业务按钮的类型调整为 `"action_type": "form_submit"`。
- **彻底去除独立发送逻辑**：移除了输入框自备的零碎发送行为。现行业务要求所有附言的提交必须与其执行决策（如批准放行、尝试修复、或仅仅发送说明）建立显式捆绑。用户必须点击下方的某一业务按钮，利用统一的 Form Submit 机制连同文本内容打包发往大模型，防止只发了文字丢了操作的误导情况发生。
- **防止空值吞噬**：在 `feishu_notifier.py` 中，将“仅发送说明”按钮的底座传值变更为 `"仅提供附件或补充说明，请继续执行"`，彻底杜绝回传时因全部为空导致被过滤的问题。
- **填补审批态漏洞**：更新了 `main.py` 的回调校验，在审批卡片的标签匹配时补充判别了 `elif resolution == "comment_only"`，正确区分“批准”、“拒绝”与“附言”三种独立行为逻辑。

### 涉及文件
- `feishu-claude-code/feishu_client.py`
- `engine/feishu_notifier.py`
- `feishu-claude-code/main.py`

---

## 7. CLI Adapter 缓冲区排空并发漏洞修复 (Race Condition)
### 问题背景
- **部分阶段产物为空（如 Planning 阶段）**：大模型执行完毕并成功退出（`return_code=0`），但落盘文件内没有任何有效的思考或 JSON 输出痕迹，只有干瘪的空壳文档标题。
- **原因分析**：在 `integrations.py` 的主备进程读取机制中存在微妙的 Race Condition。由于大模型在终端下是非实时 TTY 环境，其标准输出会在结束运行时在一瞬间集中 Flush 到管道。此时主线程 `process.poll()` 探测到进程退出直接触发 `break`，导致负责日志录入的专门读取子线程 (`reader_thread`) 还未来得及将管道塞入 `output_queue` 的海量输出物进行消费，最终导致上千字符的有效生成内容被提前退出的主循环所丢弃。

### 修改指引
- **安全排空机制**：在主动读取判断逻辑中，将原来的 `if process.poll() is not None: break` 修改为附加存活状态检测的 `if process.poll() is not None and not reader_thread.is_alive(): break`。确保进程退出后，依然留出余量让后台读取线程将其管道中残存的最后一大波关键输出消化掉，待线程完满死掉后才放行主循环停止，保证 AI 输出物零丢失。

### 涉及文件
- `engine/integrations.py`

---

## 8. 生成产物物理覆盖写入漏洞修复 (Artifact Overwrite Bug)
### 问题背景
- **实体文件生成物诡异失踪**：AI Agents 兢兢业业通过内部 Tool 建好的数十页乃至数百行的 `development.md`、代码片段等关键实体报告。但在后续检查及前端面板展示时，被剥夺成了仅仅剩下几行字的摘要或者仅保留一个单薄的 `# Implementation \n` 大标题骨架。
- **原因分析**：`pipeline_runner.py` 中分装归档用的 `_materialize_stage_artifacts` 存在漏配参数的致命 Bug。在前期的 `intake`、`planning` 分支具有 `preserve=True` 防止暴力覆写早已落实的实体文件，但 `development` 和所有的兜底 `else` 阶段分支却均未传入该保护参数。这就导致任务临结束归档时，引擎简单粗暴地拿着大模型聊天记录里的摘要“缩写”去毫无顾忌地替换甚至清空掉已经存在的复杂交付文件。

### 修改指引
- **补齐引擎级保护参数**：在 `development` 后续开发及 `else` 的一切兜底分支内的 `self._save_text()` 方法调用里补齐缺失的 `preserve=True` 选项。以此规定和尊重：凡是大模型的 Agent 工具能够主动且完好创建的高质量阶层产物文件，系统不能再擅自用其干涩单薄的简聊记录去做盲目的复写截断。

### 涉及文件
- `engine/pipeline_runner.py`

---

## 9. 任务状态彻底清除机制漏洞与自动化测试修复 
### 问题背景
- **任务清除崩溃 (DELETE API)**：试图清理处于 Wait/Pause 等状态的陈旧 Task 导致系统报 `TypeError: _path_normpath: not NoneType` 错误。
- **基线测试常年失败**：现有仓库自动化测试 `test_pipeline_runner_delete.py` 内部因为缺乏虚拟运行环境配置，一直处于报错状态，掩盖了其他的错误。

### 修改指引
- **防空指针环境清理加固**：在 `pipeline_runner` 执行 `delete_task` 方法抹除文件结构中，针对偶尔因流转缺失而变为空（`None`）的沙盒/任务录入目录对象实施额外的检测控制（`if not path or not root: continue`），以此防范目录层级合并时的 Python Type 打断。
- **Mock 环境补齐**：修补自动化测试用例，为 `PipelineRunner` mock 实例注入虚拟的 `tasks_dir` 与 `runs_dir`，修复由于状态不全导致的属性存取错误，让基线测试完全恢复绿色通过状态。

### 涉及文件
- `engine/pipeline_runner.py`
- `tests/test_pipeline_runner_delete.py`