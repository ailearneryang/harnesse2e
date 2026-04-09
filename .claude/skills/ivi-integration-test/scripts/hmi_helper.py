"""
HMI Helper — 车机 HMI 交互自动化工具
封装 UIAutomator2 / adb input 命令，提供面向测试场景的 HMI 操作 API
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from adb_runner import ADBRunner


@dataclass
class UIElement:
    """UIAutomator dump 中解析出的元素信息。"""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    bounds: str = ""          # 格式: [left,top][right,bottom]
    clickable: bool = False
    enabled: bool = True


@dataclass
class HMITestResult:
    """单条 HMI 测试结果。"""
    tc_id: str
    name: str
    passed: bool
    duration_ms: float
    error: str = ""
    screenshot_path: str = ""
    steps: list[str] = field(default_factory=list)


class HMIHelper:
    """
    HMI 交互测试工具。

    基于 `adb shell input` 和 `uiautomator dump` 实现不依赖额外框架的 HMI 自动化。
    如台架已安装 uiautomator2 server，可通过 _ua2_tap 方法使用高级 API。
    """

    # 常用 KeyEvent 代码
    KEY_HOME = 3
    KEY_BACK = 4
    KEY_MENU = 82
    KEY_POWER = 26
    KEY_VOLUME_UP = 24
    KEY_VOLUME_DOWN = 25
    KEY_ENTER = 66
    KEY_DPAD_UP = 19
    KEY_DPAD_DOWN = 20
    KEY_DPAD_LEFT = 21
    KEY_DPAD_RIGHT = 22
    KEY_DPAD_CENTER = 23

    def __init__(self, runner: ADBRunner, screenshot_dir: str = "/tmp/ivi_screenshots"):
        self.runner = runner
        self.screenshot_dir = screenshot_dir
        self._results: list[HMITestResult] = []

    # ------------------------------------------------------------------
    # 基础输入
    # ------------------------------------------------------------------

    def tap(self, x: int, y: int, wait_ms: int = 500) -> None:
        """点击屏幕坐标。"""
        self.runner.shell(f"input tap {x} {y}")
        time.sleep(wait_ms / 1000)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        """滑动手势。"""
        self.runner.shell(f"input swipe {x1} {y1} {x2} {y2} {duration_ms}")
        time.sleep(0.3)

    def key_event(self, keycode: int) -> None:
        self.runner.shell(f"input keyevent {keycode}")
        time.sleep(0.2)

    def input_text(self, text: str) -> None:
        """向当前焦点输入文本（特殊字符需 URL 编码）。"""
        safe = text.replace(" ", "%s").replace("'", "\\'")
        self.runner.shell(f"input text '{safe}'")
        time.sleep(0.3)

    def long_press(self, x: int, y: int, duration_ms: int = 1000) -> None:
        self.runner.shell(f"input swipe {x} {y} {x} {y} {duration_ms}")
        time.sleep(0.5)

    # ------------------------------------------------------------------
    # UI 元素查找
    # ------------------------------------------------------------------

    def dump_ui(self, local_xml: str = "/tmp/ivi_ui_dump.xml") -> str:
        """导出当前屏幕 UIAutomator hierarchy XML，返回本地路径。"""
        remote = "/sdcard/_ivi_ui_dump.xml"
        self.runner.shell("uiautomator dump --compressed " + remote)
        self.runner.pull(remote, local_xml)
        self.runner.shell(f"rm {remote}")
        return local_xml

    def find_element_by_id(self, resource_id: str, xml_path: Optional[str] = None) -> Optional[UIElement]:
        """从 UI dump 中按 resource-id 查找元素。"""
        return self._parse_element(f'resource-id="{resource_id}"', xml_path)

    def find_element_by_text(self, text: str, xml_path: Optional[str] = None) -> Optional[UIElement]:
        """从 UI dump 中按 text 查找元素。"""
        return self._parse_element(f'text="{text}"', xml_path)

    def wait_for_element(self, resource_id: str, timeout_s: float = 10.0) -> Optional[UIElement]:
        """等待元素出现，返回元素或 None（超时）。"""
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            elem = self.find_element_by_id(resource_id)
            if elem:
                return elem
            time.sleep(0.5)
        return None

    def tap_element(self, resource_id: str, timeout_s: float = 5.0) -> bool:
        """等待并点击指定 resource-id 的元素，返回是否成功。"""
        elem = self.wait_for_element(resource_id, timeout_s)
        if not elem or not elem.clickable:
            return False
        cx, cy = self._center_of(elem.bounds)
        self.tap(cx, cy)
        return True

    # ------------------------------------------------------------------
    # 车机场景快捷方法
    # ------------------------------------------------------------------

    def go_home(self) -> None:
        """回到 Launcher 主界面。"""
        self.key_event(self.KEY_HOME)
        time.sleep(0.8)

    def go_back(self) -> None:
        self.key_event(self.KEY_BACK)
        time.sleep(0.4)

    def open_settings(self) -> bool:
        """启动系统设置。"""
        out, rc = self.runner.shell(
            "am start -n com.android.settings/.Settings"
        )
        time.sleep(1.5)
        return rc == 0

    def check_screen_on(self) -> bool:
        """检查屏幕是否亮起（未锁屏）。"""
        out, _ = self.runner.shell("dumpsys power | grep 'mWakefulness'")
        return "Awake" in out

    def get_current_activity(self) -> str:
        """获取当前前台 Activity。"""
        out, _ = self.runner.shell(
            "dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'"
        )
        return out.strip()

    # ------------------------------------------------------------------
    # 测试场景执行框架
    # ------------------------------------------------------------------

    def run_test_case(self, tc_id: str, name: str, steps: list[dict]) -> HMITestResult:
        """
        执行一条结构化测试用例。

        steps 格式示例:
          [
            {"action": "tap_element", "resource_id": "com.example:id/btn_nav", "wait": 1.0},
            {"action": "assert_text", "resource_id": "com.example:id/title", "expected": "导航"},
            {"action": "screenshot", "tag": "nav_opened"},
          ]
        """
        start = time.time()
        result = HMITestResult(tc_id=tc_id, name=name, passed=False, duration_ms=0)
        try:
            for step in steps:
                action = step["action"]
                step_desc = f"{action}({step.get('resource_id', step.get('tag', ''))})"
                result.steps.append(step_desc)

                if action == "tap_element":
                    ok = self.tap_element(step["resource_id"], step.get("wait", 5.0))
                    if not ok:
                        raise AssertionError(f"元素未找到或不可点击: {step['resource_id']}")

                elif action == "tap":
                    self.tap(step["x"], step["y"], step.get("wait_ms", 500))

                elif action == "swipe":
                    self.swipe(step["x1"], step["y1"], step["x2"], step["y2"], step.get("duration_ms", 300))

                elif action == "input_text":
                    self.input_text(step["text"])

                elif action == "key_event":
                    self.key_event(step["keycode"])

                elif action == "wait":
                    time.sleep(step.get("seconds", 1.0))

                elif action == "assert_text":
                    elem = self.wait_for_element(step["resource_id"], step.get("wait", 5.0))
                    if elem is None:
                        raise AssertionError(f"断言失败：元素未出现 {step['resource_id']}")
                    if elem.text != step["expected"]:
                        raise AssertionError(
                            f"文本断言失败: 期望 '{step['expected']}', 实际 '{elem.text}'"
                        )

                elif action == "assert_activity":
                    actual = self.get_current_activity()
                    if step["expected"] not in actual:
                        raise AssertionError(
                            f"Activity 断言失败: 期望包含 '{step['expected']}', 实际 '{actual}'"
                        )

                elif action == "screenshot":
                    tag = step.get("tag", tc_id)
                    path = f"{self.screenshot_dir}/{tc_id}_{tag}.png"
                    result.screenshot_path = self.runner.screenshot(path)

                elif action == "go_home":
                    self.go_home()

                elif action == "go_back":
                    self.go_back()

            result.passed = True

        except AssertionError as e:
            result.error = str(e)
        except Exception as e:
            result.error = f"执行异常: {e}"
        finally:
            result.duration_ms = round((time.time() - start) * 1000, 1)
            if not result.screenshot_path:
                path = f"{self.screenshot_dir}/{tc_id}_final.png"
                try:
                    result.screenshot_path = self.runner.screenshot(path)
                except Exception:
                    pass
            self._results.append(result)

        return result

    @property
    def results(self) -> list[HMITestResult]:
        return list(self._results)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _parse_element(self, attr_match: str, xml_path: Optional[str]) -> Optional[UIElement]:
        """从 XML dump 中解析元素属性（简单文本匹配，不依赖 lxml）。"""
        import re
        if xml_path is None:
            xml_path = self.dump_ui()
        try:
            with open(xml_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            return None

        pattern = rf'<node[^>]*{re.escape(attr_match)}[^>]*/>'
        match = re.search(pattern, content)
        if not match:
            return None

        node = match.group(0)
        def _attr(name: str) -> str:
            m = re.search(rf'{name}="([^"]*)"', node)
            return m.group(1) if m else ""

        return UIElement(
            resource_id=_attr("resource-id"),
            text=_attr("text"),
            content_desc=_attr("content-desc"),
            bounds=_attr("bounds"),
            clickable=_attr("clickable") == "true",
            enabled=_attr("enabled") != "false",
        )

    @staticmethod
    def _center_of(bounds: str) -> tuple[int, int]:
        """解析 bounds 字符串 '[x1,y1][x2,y2]' 返回中心坐标。"""
        import re
        nums = list(map(int, re.findall(r"\d+", bounds)))
        if len(nums) == 4:
            return (nums[0] + nums[2]) // 2, (nums[1] + nums[3]) // 2
        return 0, 0
