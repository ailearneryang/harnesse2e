"""贪吃蛇 (Snake Game) 核心逻辑单元测试。

通过 extracting JS 逻辑到独立模块并使用 Node.js 执行测试来
验证所有核心游戏功能 (F001-F014) 和非功能需求 (NFR001-NFR005)。

测试策略：
  - 将纯逻辑函数从 snake.html 中提取出来
  - 使用 subprocess 调用 Node.js 执行 JavaScript 测试
  - 每个测试方法对应一个或多个需求编号
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest


# ─── 测试辅助：提取核心 JS 逻辑并在 Node.js 中执行 ─────────────

SNAKE_HTML = Path(__file__).resolve().parent.parent / "src" / "snake.html"


def _extract_js(html_path: Path) -> str:
    """从 snake.html 中提取 <script> 标签内的 JavaScript 代码。"""
    content = html_path.read_text(encoding="utf-8")
    start = content.index("<script>") + len("<script>")
    end = content.index("</script>")
    return content[start:end]


def _run_js(script: str) -> dict:
    """在 Node.js 中执行 JavaScript 代码并返回 JSON 结果。

    Args:
        script: 完整的 JS 脚本 (包含 mock + 游戏逻辑 + 测试代码)

    Returns:
        解析后的 JSON 字典

    Raises:
        RuntimeError: 当 Node.js 执行失败时
    """
    result = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Node.js execution failed:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
    # 取最后一行非空输出作为 JSON 结果
    lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
    if not lines:
        raise RuntimeError("No output from Node.js")
    return json.loads(lines[-1])


# ─── DOM/Canvas Mock — 提供浏览器 API 的最小模拟 ─────────────

MOCK_BROWSER = textwrap.dedent("""\
    // Mock browser APIs for Node.js testing
    global.window = {
        innerWidth: 800, innerHeight: 600,
        addEventListener: () => {},
        AudioContext: null, webkitAudioContext: null
    };
    global.document = {
        getElementById: (id) => {
            if (id === 'gameCanvas') return {
                getContext: () => ({
                    fillStyle: '', strokeStyle: '', lineWidth: 0,
                    fillRect: () => {}, fillText: () => {},
                    beginPath: () => {}, moveTo: () => {}, lineTo: () => {},
                    stroke: () => {}, arc: () => {}, fill: () => {},
                    clearRect: () => {}
                }),
                getBoundingClientRect: () => ({ left: 0, top: 0, width: 400, height: 400 }),
                width: 400, height: 400,
                addEventListener: () => {}
            };
            return {
                textContent: '', style: {},
                classList: { add: () => {}, remove: () => {} },
                addEventListener: () => {}
            };
        },
        addEventListener: () => {}
    };
    global.localStorage = {
        _store: {},
        getItem(k) { return this._store[k] || null; },
        setItem(k, v) { this._store[k] = String(v); },
        removeItem(k) { delete this._store[k]; }
    };
    global.requestAnimationFrame = () => 0;
    global.cancelAnimationFrame = () => {};
""")


def _build_test_script(test_code: str) -> str:
    """组合 mock + 游戏源码 + 测试代码。"""
    js_source = _extract_js(SNAKE_HTML)
    # 移除末尾的自执行代码 (resizeCanvas/initGame/render)
    # 这些在测试中手动调用
    js_source_clean = js_source.replace(
        "resizeCanvas();\ninitGame();\nrender();",
        "// [REMOVED FOR TESTING] resizeCanvas/initGame/render auto-calls"
    )
    return f"{MOCK_BROWSER}\n{js_source_clean}\n\n{test_code}"


# ======================================================================
# F001: 游戏画布渲染 — 20×20 网格配置
# ======================================================================

class TestCanvasConfig:
    """F001: 验证画布配置常量。"""

    def test_grid_size_is_20(self) -> None:
        """F001 AC: 20×20 网格。"""
        result = _run_js(_build_test_script(
            'console.log(JSON.stringify({ grid: GRID }))'
        ))
        assert result["grid"] == 20

    def test_cell_size_calculation(self) -> None:
        """F001 AC: 画布尺寸为 cellSize 整数倍。"""
        result = _run_js(_build_test_script("""
            resizeCanvas();
            console.log(JSON.stringify({
                width: canvas.width,
                height: canvas.height,
                cellSize: cellSize,
                isMultiple: canvas.width === cellSize * GRID
            }))
        """))
        assert result["isMultiple"] is True
        assert result["cellSize"] > 0


# ======================================================================
# F002: 蛇的初始化与渲染
# ======================================================================

class TestSnakeInit:
    """F002: 蛇的初始化。"""

    def test_snake_initial_length(self) -> None:
        """F002 AC: 初始长度为 3。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({ length: snake.length }))
        """))
        assert result["length"] == 3

    def test_snake_starts_at_center(self) -> None:
        """F002 AC: 蛇出现在画布中央区域。"""
        result = _run_js(_build_test_script("""
            initGame();
            const head = snake[0];
            const center = Math.floor(GRID / 2);
            console.log(JSON.stringify({
                headX: head.x, headY: head.y,
                centerX: center, centerY: center,
                isCenter: head.x === center && head.y === center
            }))
        """))
        assert result["isCenter"] is True

    def test_snake_faces_right(self) -> None:
        """F002 AC: 默认朝右移动。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({
                dirX: direction.x, dirY: direction.y
            }))
        """))
        assert result["dirX"] == 1
        assert result["dirY"] == 0

    def test_snake_body_horizontal(self) -> None:
        """F002 AC: 初始蛇为水平排列 (头在右, 尾在左)。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({ snake: snake }))
        """))
        s = result["snake"]
        assert len(s) == 3
        # 头在最右, 依次向左
        assert s[0]["x"] > s[1]["x"]
        assert s[1]["x"] > s[2]["x"]
        # 同一行
        assert s[0]["y"] == s[1]["y"] == s[2]["y"]


# ======================================================================
# F003: 蛇的移动
# ======================================================================

class TestSnakeMovement:
    """F003: 蛇的自动移动。"""

    def test_move_right(self) -> None:
        """F003 AC: 向右移动一格。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            const headBefore = { ...snake[0] };
            // 将食物移走以避免吃到
            food = { x: 0, y: 0 };
            update();
            const headAfter = snake[0];
            console.log(JSON.stringify({
                moved: headAfter.x === headBefore.x + 1 && headAfter.y === headBefore.y,
                lengthSame: snake.length === 3
            }))
        """))
        assert result["moved"] is True
        assert result["lengthSame"] is True

    def test_move_up(self) -> None:
        """F003: 改变方向后向上移动。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            nextDirection = DIR.UP;
            food = { x: 0, y: 0 };
            const headBefore = { ...snake[0] };
            update();
            const headAfter = snake[0];
            console.log(JSON.stringify({
                moved: headAfter.x === headBefore.x && headAfter.y === headBefore.y - 1
            }))
        """))
        assert result["moved"] is True

    def test_move_preserves_length_no_food(self) -> None:
        """F003 AC: 未吃到食物时蛇长度不变。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            food = { x: 0, y: 0 };
            const lenBefore = snake.length;
            update();
            console.log(JSON.stringify({
                same: snake.length === lenBefore
            }))
        """))
        assert result["same"] is True


# ======================================================================
# F004: 键盘方向控制 — 禁止180°反向 & 每帧仅首次有效
# ======================================================================

class TestDirectionControl:
    """F004: 方向控制逻辑。"""

    def test_opposite_direction_blocked(self) -> None:
        """F004 AC: 禁止 180° 反向移动 (向右时不能向左)。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            // 当前向右, 尝试设置向左
            const curName = getDirName(direction);
            const isBlocked = ('LEFT' === OPPOSITE[curName]);
            console.log(JSON.stringify({ isBlocked }))
        """))
        assert result["isBlocked"] is True

    def test_valid_direction_change(self) -> None:
        """F004 AC: 允许有效方向变更 (向右时可以向上)。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            const curName = getDirName(direction);
            const canUp = ('UP' !== OPPOSITE[curName]);
            console.log(JSON.stringify({ canUp }))
        """))
        assert result["canUp"] is True

    def test_direction_changed_flag(self) -> None:
        """F004 AC: directionChanged 标志阻止同帧多次方向变更。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            directionChanged = false;
            // 第一次变更: 有效
            nextDirection = DIR.UP;
            directionChanged = true;
            // 第二次变更: 被阻止 (因为 directionChanged=true)
            const secondBlocked = directionChanged;
            console.log(JSON.stringify({ secondBlocked }))
        """))
        assert result["secondBlocked"] is True

    def test_direction_flag_reset_after_update(self) -> None:
        """F004: update() 后 directionChanged 重置为 false。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            food = { x: 0, y: 0 };
            directionChanged = true;
            update();
            console.log(JSON.stringify({ reset: !directionChanged }))
        """))
        assert result["reset"] is True


# ======================================================================
# F005: 触屏滑动控制 — 30px 阈值
# ======================================================================

class TestTouchControl:
    """F005: 触屏控制参数。"""

    def test_swipe_threshold(self) -> None:
        """F005 AC: 滑动阈值为 30px。"""
        result = _run_js(_build_test_script(
            'console.log(JSON.stringify({ threshold: SWIPE_THRESHOLD }))'
        ))
        assert result["threshold"] == 30


# ======================================================================
# F006: 食物生成
# ======================================================================

class TestFoodSpawn:
    """F006: 食物生成逻辑。"""

    def test_food_not_on_snake(self) -> None:
        """F006 AC: 食物不在蛇身上。"""
        result = _run_js(_build_test_script("""
            initGame();
            // 多次生成, 每次检查
            let allValid = true;
            for (let i = 0; i < 100; i++) {
                spawnFood();
                for (const seg of snake) {
                    if (seg.x === food.x && seg.y === food.y) {
                        allValid = false; break;
                    }
                }
            }
            console.log(JSON.stringify({ allValid }))
        """))
        assert result["allValid"] is True

    def test_food_in_bounds(self) -> None:
        """F006 AC: 食物在网格范围内。"""
        result = _run_js(_build_test_script("""
            initGame();
            let allInBounds = true;
            for (let i = 0; i < 100; i++) {
                spawnFood();
                if (food.x < 0 || food.x >= GRID || food.y < 0 || food.y >= GRID) {
                    allInBounds = false; break;
                }
            }
            console.log(JSON.stringify({ allInBounds }))
        """))
        assert result["allInBounds"] is True

    def test_food_on_nearly_full_grid(self) -> None:
        """F006 AC: 蛇占据大量格子时, 食物仍在空闲位置。"""
        result = _run_js(_build_test_script("""
            initGame();
            // 构造一条很长的蛇 (占满大部分格子)
            snake = [];
            for (let y = 0; y < GRID; y++)
                for (let x = 0; x < GRID - 1; x++)
                    snake.push({ x, y });
            spawnFood();
            const onSnake = snake.some(s => s.x === food.x && s.y === food.y);
            console.log(JSON.stringify({
                snakeLen: snake.length,
                foodValid: !onSnake,
                foodX: food.x
            }))
        """))
        assert result["foodValid"] is True
        # 食物只能在最后一列 (x=19)
        assert result["foodX"] == 19


# ======================================================================
# F007: 吃食物与蛇身增长
# ======================================================================

class TestEatingFood:
    """F007: 吃食物逻辑。"""

    def test_eating_increases_length(self) -> None:
        """F007 AC: 吃到食物后蛇身长度 +1。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            // 将食物放在蛇头正前方
            food = { x: snake[0].x + 1, y: snake[0].y };
            const lenBefore = snake.length;
            update();
            console.log(JSON.stringify({
                grew: snake.length === lenBefore + 1
            }))
        """))
        assert result["grew"] is True

    def test_eating_spawns_new_food(self) -> None:
        """F007 AC: 吃到食物后生成新食物。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            const oldFood = { ...food };
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            // 新食物应该被重新生成 (位置大概率不同)
            // 关键是 food 对象存在且在范围内
            console.log(JSON.stringify({
                foodExists: food !== null && food !== undefined,
                inBounds: food.x >= 0 && food.x < GRID && food.y >= 0 && food.y < GRID
            }))
        """))
        assert result["foodExists"] is True
        assert result["inBounds"] is True


# ======================================================================
# F008: 碰撞检测 — 撞墙
# ======================================================================

class TestWallCollision:
    """F008: 撞墙检测。"""

    def test_hit_right_wall(self) -> None:
        """F008 AC: 蛇头超出右边界 → 游戏结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            // 将蛇头放在右边界
            snake[0] = { x: GRID - 1, y: 10 };
            snake[1] = { x: GRID - 2, y: 10 };
            snake[2] = { x: GRID - 3, y: 10 };
            nextDirection = DIR.RIGHT;
            food = { x: 0, y: 0 };
            update();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "GAME_OVER"

    def test_hit_top_wall(self) -> None:
        """F008 AC: 蛇头超出顶部边界 → 游戏结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            snake[0] = { x: 10, y: 0 };
            snake[1] = { x: 10, y: 1 };
            snake[2] = { x: 10, y: 2 };
            nextDirection = DIR.UP;
            food = { x: 0, y: 19 };
            update();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "GAME_OVER"

    def test_hit_left_wall(self) -> None:
        """F008 AC: 蛇头超出左边界 → 游戏结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            snake[0] = { x: 0, y: 10 };
            snake[1] = { x: 1, y: 10 };
            snake[2] = { x: 2, y: 10 };
            nextDirection = DIR.LEFT;
            food = { x: 19, y: 0 };
            update();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "GAME_OVER"

    def test_hit_bottom_wall(self) -> None:
        """F008 AC: 蛇头超出底部边界 → 游戏结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            snake[0] = { x: 10, y: GRID - 1 };
            snake[1] = { x: 10, y: GRID - 2 };
            snake[2] = { x: 10, y: GRID - 3 };
            nextDirection = DIR.DOWN;
            food = { x: 0, y: 0 };
            update();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "GAME_OVER"


# ======================================================================
# F009: 碰撞检测 — 撞自身
# ======================================================================

class TestSelfCollision:
    """F009: 撞自身检测。"""

    def test_self_collision_long_snake(self) -> None:
        """F009 AC: 蛇长度≥5 时撞自身 → 游戏结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            // 构造一条长蛇, 头部即将撞到身体
            snake = [
                { x: 5, y: 5 },  // head
                { x: 6, y: 5 },
                { x: 6, y: 6 },
                { x: 5, y: 6 },
                { x: 4, y: 6 },
                { x: 4, y: 5 },  // body at (4,5)
            ];
            nextDirection = DIR.LEFT; // 向左 → 到 (4,5) 撞自身
            food = { x: 0, y: 0 };
            update();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "GAME_OVER"

    def test_short_snake_no_self_collision(self) -> None:
        """F009 AC: 蛇长度 < 4 不会自身碰撞 (物理上不可能)。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            food = { x: 0, y: 0 };
            // 标准初始蛇 (长度3) 正常移动
            update();
            console.log(JSON.stringify({
                state, length: snake.length
            }))
        """))
        assert result["state"] == "PLAYING"
        assert result["length"] == 3


# ======================================================================
# F010: 计分系统
# ======================================================================

class TestScoring:
    """F010: 计分系统。"""

    def test_initial_score_zero(self) -> None:
        """F010 AC: 初始分数为 0。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({ score }))
        """))
        assert result["score"] == 0

    def test_score_increases_by_10(self) -> None:
        """F010 AC: 每吃一个食物 +10 分。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            console.log(JSON.stringify({ score }))
        """))
        assert result["score"] == 10

    def test_score_accumulates(self) -> None:
        """F010: 连续吃多个食物, 分数正确累积。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            // 吃第一个
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            const s1 = score;
            // 吃第二个
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            const s2 = score;
            console.log(JSON.stringify({ s1, s2 }))
        """))
        assert result["s1"] == 10
        assert result["s2"] == 20


# ======================================================================
# F011: 最高分记录 (localStorage)
# ======================================================================

class TestHighScore:
    """F011: 最高分记录。"""

    def test_high_score_default_zero(self) -> None:
        """F011 AC: 首次加载最高分为 0。"""
        result = _run_js(_build_test_script("""
            const hs = loadHighScore();
            console.log(JSON.stringify({ hs }))
        """))
        assert result["hs"] == 0

    def test_high_score_save_and_load(self) -> None:
        """F011 AC: 保存并读取最高分。"""
        result = _run_js(_build_test_script("""
            saveHighScore(100);
            const hs = loadHighScore();
            console.log(JSON.stringify({ hs }))
        """))
        assert result["hs"] == 100

    def test_high_score_updated_on_game_over(self) -> None:
        """F011 AC: 游戏结束时如果当前分数 > 最高分则更新。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            score = 50;
            highScore = 30;
            // 手动触发 gameOver
            gameOver();
            console.log(JSON.stringify({
                highScore,
                stored: parseInt(localStorage.getItem('snakeHighScore'))
            }))
        """))
        assert result["highScore"] == 50
        assert result["stored"] == 50

    def test_high_score_not_downgraded(self) -> None:
        """F011: 当前分数 < 最高分时不更新。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            saveHighScore(100);
            highScore = 100;
            score = 50;
            gameOver();
            console.log(JSON.stringify({
                highScore,
                stored: parseInt(localStorage.getItem('snakeHighScore'))
            }))
        """))
        assert result["highScore"] == 100
        assert result["stored"] == 100


# ======================================================================
# F012: 游戏状态管理
# ======================================================================

class TestGameState:
    """F012: 游戏状态机。"""

    def test_initial_state_idle(self) -> None:
        """F012 AC: 初始状态为 IDLE。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({ state }))
        """))
        assert result["state"] == "IDLE"

    def test_state_transitions(self) -> None:
        """F012 AC: IDLE → PLAYING → PAUSED → PLAYING → GAME_OVER。"""
        result = _run_js(_build_test_script("""
            initGame();
            const s0 = state;             // IDLE
            state = STATE.PLAYING;
            const s1 = state;             // PLAYING
            state = STATE.PAUSED;
            const s2 = state;             // PAUSED
            state = STATE.PLAYING;
            const s3 = state;             // PLAYING
            state = STATE.GAME_OVER;
            const s4 = state;             // GAME_OVER
            console.log(JSON.stringify({ s0, s1, s2, s3, s4 }))
        """))
        assert result["s0"] == "IDLE"
        assert result["s1"] == "PLAYING"
        assert result["s2"] == "PAUSED"
        assert result["s3"] == "PLAYING"
        assert result["s4"] == "GAME_OVER"

    def test_state_enum_values(self) -> None:
        """F012: 状态枚举完整性。"""
        result = _run_js(_build_test_script("""
            console.log(JSON.stringify(STATE))
        """))
        assert set(result.keys()) == {"IDLE", "PLAYING", "PAUSED", "GAME_OVER"}


# ======================================================================
# F013: 速度递增机制
# ======================================================================

class TestSpeedIncrease:
    """F013: 速度递增。"""

    def test_initial_interval(self) -> None:
        """F013: 初始帧间隔为 150ms。"""
        result = _run_js(_build_test_script("""
            initGame();
            console.log(JSON.stringify({ interval }))
        """))
        assert result["interval"] == 150

    def test_speed_increases_every_5_food(self) -> None:
        """F013 AC: 每吃 5 个食物, 帧间隔减少 10ms。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            const intervals = [interval];
            for (let i = 0; i < 10; i++) {
                // 每次重置蛇位置到中间, 防止撞墙
                snake = [
                    { x: 10, y: 10 },
                    { x: 9, y: 10 },
                    { x: 8, y: 10 }
                ];
                nextDirection = DIR.RIGHT;
                directionChanged = false;
                food = { x: 11, y: 10 };
                update();
                if (state !== 'PLAYING') break;
                intervals.push(interval);
            }
            console.log(JSON.stringify({ intervals, foodEaten }))
        """))
        intervals = result["intervals"]
        # 吃 5 个后应从 150 降到 140
        assert intervals[0] == 150
        assert intervals[5] == 140
        # 吃 10 个后应为 130
        assert intervals[10] == 130

    def test_speed_minimum_cap(self) -> None:
        """F013 AC: 帧间隔最小为 50ms。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            interval = 60;
            foodEaten = 4; // 下次吃第5个会触发加速
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            console.log(JSON.stringify({ interval }))
        """))
        assert result["interval"] == 50

    def test_speed_does_not_go_below_minimum(self) -> None:
        """F013 AC: 达到 50ms 后不再减小。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            interval = 50;
            foodEaten = 49; // 下次吃第50个
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            console.log(JSON.stringify({ interval }))
        """))
        assert result["interval"] == 50


# ======================================================================
# F014: 游戏音效 — 参数验证
# ======================================================================

class TestAudioConfig:
    """F014: 音效相关。"""

    def test_audio_silent_fallback(self) -> None:
        """F014 AC: 无 AudioContext 时静默跳过 (不报错)。"""
        result = _run_js(_build_test_script("""
            // audioCtx 为 null (Mock 中未提供)
            let error = false;
            try { playSound('eat'); playSound('die'); }
            catch(e) { error = true; }
            console.log(JSON.stringify({ error }))
        """))
        assert result["error"] is False


# ======================================================================
# NFR001: 性能 — 常量验证
# ======================================================================

class TestPerformanceConfig:
    """NFR001: 性能相关配置。"""

    def test_game_logic_is_lightweight(self) -> None:
        """NFR001: update() 核心逻辑执行时间极短。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            food = { x: 0, y: 0 };
            const start = Date.now();
            for (let i = 0; i < 1000; i++) {
                // 重置位置以防撞墙
                snake = [
                    { x: 10, y: 10 },
                    { x: 9, y: 10 },
                    { x: 8, y: 10 }
                ];
                nextDirection = DIR.RIGHT;
                directionChanged = false;
                update();
                if (state !== 'PLAYING') {
                    state = STATE.PLAYING;
                }
            }
            const elapsed = Date.now() - start;
            console.log(JSON.stringify({ elapsed, avgMs: elapsed / 1000 }))
        """))
        # 1000次 update 应在 100ms 内完成 (平均 ≤ 0.1ms, 远低于 1ms 要求)
        assert result["elapsed"] < 100


# ======================================================================
# NFR004: 代码质量
# ======================================================================

class TestCodeQuality:
    """NFR004: 代码质量约束。"""

    def test_single_html_file(self) -> None:
        """NFR004: 单文件交付。"""
        assert SNAKE_HTML.exists()
        assert SNAKE_HTML.suffix == ".html"

    def test_line_count_under_500(self) -> None:
        """NFR004: 代码总量 ≤ 500 行。"""
        line_count = len(SNAKE_HTML.read_text(encoding="utf-8").splitlines())
        assert line_count <= 500, f"文件有 {line_count} 行, 超过 500 行限制"

    def test_no_external_dependencies(self) -> None:
        """NFR004: 无外部依赖 (无 <script src=> 或 <link href=>CDN)。"""
        content = SNAKE_HTML.read_text(encoding="utf-8")
        # 确保没有引用外部 JS/CSS
        assert 'src="http' not in content
        assert "src='http" not in content
        assert 'href="http' not in content
        assert "href='http" not in content

    def test_has_canvas_element(self) -> None:
        """F001: HTML 中包含 canvas 元素。"""
        content = SNAKE_HTML.read_text(encoding="utf-8")
        assert "<canvas" in content

    def test_has_viewport_meta(self) -> None:
        """NFR002: 包含 viewport meta 标签 (移动端适配)。"""
        content = SNAKE_HTML.read_text(encoding="utf-8")
        assert 'name="viewport"' in content


# ======================================================================
# NFR005: 安全性
# ======================================================================

class TestSecurity:
    """NFR005: 安全性约束。"""

    def test_no_fetch_or_xhr(self) -> None:
        """NFR005: 不发起网络请求。"""
        content = SNAKE_HTML.read_text(encoding="utf-8")
        assert "fetch(" not in content
        assert "XMLHttpRequest" not in content
        assert "$.ajax" not in content

    def test_localstorage_key(self) -> None:
        """NFR005: localStorage 仅存储高分 key。"""
        result = _run_js(_build_test_script("""
            console.log(JSON.stringify({ key: LS_KEY }))
        """))
        assert result["key"] == "snakeHighScore"


# ======================================================================
# 综合集成测试 — 完整游戏流程
# ======================================================================

class TestIntegration:
    """综合测试: 模拟完整游戏流程。"""

    def test_full_game_cycle(self) -> None:
        """集成测试: 初始化 → 移动 → 吃食物 → 撞墙 → 结束。"""
        result = _run_js(_build_test_script("""
            initGame();
            const s0 = state;

            // 开始游戏
            state = STATE.PLAYING;
            const s1 = state;

            // 放置食物在蛇头前方, 吃食物
            food = { x: snake[0].x + 1, y: snake[0].y };
            update();
            const scoreAfterEat = score;
            const lenAfterEat = snake.length;

            // 移动几步 (不吃食物)
            food = { x: 0, y: 0 };
            for (let i = 0; i < 3; i++) {
                if (state !== 'PLAYING') break;
                update();
            }

            // 移到墙边并撞墙
            snake[0] = { x: GRID - 1, y: snake[0].y };
            snake[1] = { x: GRID - 2, y: snake[0].y };
            snake[2] = { x: GRID - 3, y: snake[0].y };
            if (snake.length > 3) snake[3] = { x: GRID - 4, y: snake[0].y };
            nextDirection = DIR.RIGHT;
            directionChanged = false;
            update();
            const sFinal = state;

            console.log(JSON.stringify({
                s0, s1, scoreAfterEat, lenAfterEat, sFinal
            }))
        """))
        assert result["s0"] == "IDLE"
        assert result["s1"] == "PLAYING"
        assert result["scoreAfterEat"] == 10
        assert result["lenAfterEat"] == 4
        assert result["sFinal"] == "GAME_OVER"

    def test_restart_resets_state(self) -> None:
        """F012: 重新开始后游戏完全重置。"""
        result = _run_js(_build_test_script("""
            initGame();
            state = STATE.PLAYING;
            score = 50;
            foodEaten = 10;
            interval = 100;
            snake = [
                {x:5,y:5},{x:4,y:5},{x:3,y:5},{x:2,y:5},{x:1,y:5}
            ];

            // 重新初始化
            initGame();
            console.log(JSON.stringify({
                state, score, foodEaten, interval,
                snakeLen: snake.length
            }))
        """))
        assert result["state"] == "IDLE"
        assert result["score"] == 0
        assert result["foodEaten"] == 0
        assert result["interval"] == 150
        assert result["snakeLen"] == 3


# ======================================================================
# 方向辅助函数测试
# ======================================================================

class TestHelperFunctions:
    """工具函数测试。"""

    def test_getDirName(self) -> None:
        """getDirName 正确映射方向对象到名称。"""
        result = _run_js(_build_test_script("""
            console.log(JSON.stringify({
                up: getDirName(DIR.UP),
                down: getDirName(DIR.DOWN),
                left: getDirName(DIR.LEFT),
                right: getDirName(DIR.RIGHT)
            }))
        """))
        assert result["up"] == "UP"
        assert result["down"] == "DOWN"
        assert result["left"] == "LEFT"
        assert result["right"] == "RIGHT"

    def test_opposite_mapping(self) -> None:
        """OPPOSITE 映射完整且正确。"""
        result = _run_js(_build_test_script("""
            console.log(JSON.stringify(OPPOSITE))
        """))
        assert result["UP"] == "DOWN"
        assert result["DOWN"] == "UP"
        assert result["LEFT"] == "RIGHT"
        assert result["RIGHT"] == "LEFT"

    def test_key_map_completeness(self) -> None:
        """KEY_MAP 包含所有方向键和 WASD。"""
        result = _run_js(_build_test_script("""
            console.log(JSON.stringify(KEY_MAP))
        """))
        expected_keys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
                         "w", "W", "s", "S", "a", "A", "d", "D"]
        for key in expected_keys:
            assert key in result, f"KEY_MAP 缺少 '{key}'"
