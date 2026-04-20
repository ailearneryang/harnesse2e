import asyncio
import os
import sys
import types
import unittest
from unittest import mock

os.environ.setdefault("FEISHU_APP_ID", "test-app-id")
os.environ.setdefault("FEISHU_APP_SECRET", "test-app-secret")


def _install_fake_lark():
    if "lark_oapi" in sys.modules:
        return

    class _Builder:
        def app_id(self, *_args, **_kwargs):
            return self

        def app_secret(self, *_args, **_kwargs):
            return self

        def log_level(self, *_args, **_kwargs):
            return self

        def request_body(self, *_args, **_kwargs):
            return self

        def receive_id_type(self, *_args, **_kwargs):
            return self

        def receive_id(self, *_args, **_kwargs):
            return self

        def msg_type(self, *_args, **_kwargs):
            return self

        def content(self, *_args, **_kwargs):
            return self

        def message_id(self, *_args, **_kwargs):
            return self

        def event_handler(self, *_args, **_kwargs):
            return self

        def register_p2_im_message_receive_v1(self, *_args, **_kwargs):
            return self

        def build(self):
            return self

    class _Client:
        @staticmethod
        def builder():
            return _Builder()

    class _WsClient:
        def __init__(self, *_args, **_kwargs):
            pass

        def start(self):
            return None

    fake_lark = types.ModuleType("lark_oapi")
    fake_lark.Client = _Client
    fake_lark.LogLevel = types.SimpleNamespace(INFO="INFO")
    fake_lark.ws = types.SimpleNamespace(Client=_WsClient)
    fake_lark.EventDispatcherHandler = types.SimpleNamespace(builder=lambda *_args, **_kwargs: _Builder())

    model_mod = types.ModuleType("lark_oapi.api.im.v1.model")
    for name in (
        "P2ImMessageReceiveV1",
        "CreateMessageRequest",
        "CreateMessageRequestBody",
        "GetMessageRequest",
        "PatchMessageRequest",
        "PatchMessageRequestBody",
        "ReplyMessageRequest",
        "ReplyMessageRequestBody",
    ):
        setattr(model_mod, name, type(name, (), {"builder": staticmethod(lambda: _Builder())}))

    sys.modules["lark_oapi"] = fake_lark
    sys.modules["lark_oapi.api"] = types.ModuleType("lark_oapi.api")
    sys.modules["lark_oapi.api.im"] = types.ModuleType("lark_oapi.api.im")
    sys.modules["lark_oapi.api.im.v1"] = types.ModuleType("lark_oapi.api.im.v1")
    sys.modules["lark_oapi.api.im.v1.model"] = model_mod
    sys.modules["lark_oapi.event"] = types.ModuleType("lark_oapi.event")
    sys.modules["lark_oapi.event.callback"] = types.ModuleType("lark_oapi.event.callback")
    sys.modules["lark_oapi.event.callback.model"] = types.ModuleType("lark_oapi.event.callback.model")
    card_mod = types.ModuleType("lark_oapi.event.callback.model.p2_card_action_trigger")
    for name in ("P2CardActionTrigger", "P2CardActionTriggerResponse", "CallBackToast"):
        setattr(card_mod, name, type(name, (), {}))
    sys.modules["lark_oapi.event.callback.model.p2_card_action_trigger"] = card_mod


_install_fake_lark()

import feishu_client
import main


class MainStopTests(unittest.IsolatedAsyncioTestCase):
    def test_build_card_button_element_uses_event_path_by_default(self):
        button = feishu_client.build_card_button_element(
            {"text": "继续", "value": {"action": "pipeline_feedback", "task_id": "task-1"}},
            "btn_0",
        )

        self.assertEqual(button["value"]["action"], "pipeline_feedback")
        self.assertNotIn("behaviors", button)

    def test_build_card_button_element_allows_explicit_callback_behavior(self):
        button = feishu_client.build_card_button_element(
            {
                "text": "继续",
                "value": {"action": "pipeline_feedback", "task_id": "task-1"},
                "use_callback": True,
            },
            "btn_0",
        )

        self.assertEqual(
            button["behaviors"],
            [{"type": "callback", "value": {"action": "pipeline_feedback", "task_id": "task-1"}}],
        )

    async def test_handle_stop_command_returns_no_active_run_message(self):
        with mock.patch.object(main, "stop_run", mock.AsyncMock(return_value=False)):
            reply = await main._handle_stop_command("user-1")

        self.assertIn("没有正在运行", reply)

    async def test_handle_stop_command_requests_stop_for_active_run(self):
        active_run = mock.Mock(stop_requested=False)

        with mock.patch.object(
            main._active_runs,
            "get_run",
            return_value=active_run,
        ), mock.patch.object(
            main,
            "stop_run",
            mock.AsyncMock(return_value=True),
        ) as stop_run_mock:
            reply = await main._handle_stop_command("user-1")

        stop_run_mock.assert_awaited_once()
        self.assertIn("已发送停止请求", reply)

    async def test_handle_pipeline_feedback_action_resumes_task_and_updates_card(self):
        with mock.patch.object(
            main,
            "_post_harness_json",
            mock.AsyncMock(return_value={
                "current_stage": "testing",
                "context": {
                    "testing": {
                        "human_prompt_title": "Manual action required",
                        "human_prompt_content": "待确认项如下：\n- A：补齐接口定义\n- B：确认验收标准",
                    }
                },
            }),
        ) as post_mock, mock.patch.object(main, "feishu") as mock_feishu:
            mock_feishu.update_card_elements = mock.AsyncMock()

            await main._handle_pipeline_feedback_action(
                "user-1",
                "oc_chat_1",
                {"task_id": "task-1", "stage": "testing", "prompt_title": "当前确认项", "prompt_content": "请确认是否继续推进", "feedback": "请继续", "prioritize": True},
                {"supplemental_input": "补充细节"},
                "msg-1",
            )

        post_mock.assert_awaited_once_with(
            "/api/tasks/task-1/resume",
            {
                "prioritize": True,
                "feedback": "请继续\n补充说明：补充细节",
                "actor": "user-1",
                "source": "feishu-card",
            },
        )
        mock_feishu.update_card_elements.assert_awaited_once()
        update_args = mock_feishu.update_card_elements.await_args.args
        self.assertEqual(update_args[0], "msg-1")
        self.assertEqual(update_args[1][0]["tag"], "markdown")
        self.assertIn("已提交人工反馈并恢复流水线", update_args[1][0]["content"])
        joined_content = "\n".join(element.get("content", "") for element in update_args[1] if isinstance(element, dict) and "content" in element)
        self.assertIn("**待确认项**", joined_content)
        self.assertIn("Manual action required", joined_content)
        self.assertIn("- A：补齐接口定义", joined_content)
        self.assertIn("- B：确认验收标准", joined_content)
        self.assertIn("**用户选择结果**", joined_content)
        self.assertIn("请继续", joined_content)
        self.assertIn("**处理人**: `user-1`", joined_content)
        # Card schema V2 不再支持 note 标签，终端展示改为 markdown
        self.assertEqual(update_args[1][-1]["tag"], "markdown")
        self.assertIn("已处理", update_args[1][-1]["content"])

    async def test_handle_pipeline_approval_action_resolves_approval_and_updates_card(self):
        with mock.patch.object(
            main,
            "_post_harness_json",
            mock.AsyncMock(return_value={"status": "approved"}),
        ) as post_mock, mock.patch.object(main, "feishu") as mock_feishu:
            mock_feishu.update_card_elements = mock.AsyncMock()

            await main._handle_pipeline_approval_action(
                "user-1",
                "oc_chat_1",
                {"task_id": "task-2", "approval_id": "approval-1", "stage": "design", "prompt_title": "设计审批", "prompt_content": "请确认当前方案是否允许继续", "resolution": "approved"},
                {"supplemental_input": "可以继续"},
                "msg-2",
            )

        post_mock.assert_awaited_once_with(
            "/api/approvals/task-2/approval-1/resolve",
            {
                "resolution": "approved",
                "note": "可以继续",
                "actor": "user-1",
                "source": "feishu-card",
            },
        )
        mock_feishu.update_card_elements.assert_awaited_once()
        update_args = mock_feishu.update_card_elements.await_args.args
        self.assertEqual(update_args[0], "msg-2")
        joined_content = "\n".join(element.get("content", "") for element in update_args[1] if isinstance(element, dict) and "content" in element)
        self.assertIn("**待确认项**", joined_content)
        self.assertIn("设计审批", joined_content)
        self.assertIn("请确认当前方案是否允许继续", joined_content)
        self.assertIn("**用户选择结果**", joined_content)
        self.assertIn("批准继续", joined_content)
        self.assertIn("**补充说明**", joined_content)
        self.assertIn("可以继续", joined_content)
        self.assertIn("**处理人**: `user-1`", joined_content)
        # Card schema V2 不再支持 note 标签，终端展示改为 markdown
        self.assertEqual(update_args[1][-1]["tag"], "markdown")
        self.assertIn("原按钮不再可点击", update_args[1][-1]["content"])


if __name__ == "__main__":
    unittest.main()
