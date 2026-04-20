import os
import sys
import asyncio
from typing import Optional

# Add feishu-claude-code to sys.path so we can import its modules
harness_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
feishu_path = os.path.join(harness_dir, "feishu-claude-code")
if feishu_path not in sys.path:
    sys.path.insert(0, feishu_path)

def _load_notifier_context():
    try:
        import dotenv
        dotenv.load_dotenv(os.path.join(feishu_path, ".env"))
    except Exception as exc:
        print(f"Warning: Failed to load Feishu .env file: {exc}")

    try:
        from bot_config import FEISHU_APP_ID, FEISHU_APP_SECRET, ADMIN_OPEN_ID
        import lark_oapi as lark
        from feishu_client import FeishuClient
    except Exception as exc:
        print(f"Warning: Could not load feishu modules or config: {exc}")
        return None, None, None, None, None

    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("Feishu notifier is disabled due to missing config (FEISHU_APP_ID, FEISHU_APP_SECRET).")
        return None, None, None, None, None

    client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
    fc = FeishuClient(client, FEISHU_APP_ID, FEISHU_APP_SECRET)
    return FEISHU_APP_ID, FEISHU_APP_SECRET, ADMIN_OPEN_ID, client, fc


def _run_async_send(send_coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import threading

        def run_in_thread():
            asyncio.run(send_coro())

        threading.Thread(target=run_in_thread, daemon=True).start()
    else:
        loop.run_until_complete(send_coro())

def _resolve_recipient(source_metadata: Optional[dict], admin_open_id: Optional[str]) -> Optional[str]:
    metadata = source_metadata or {}
    return metadata.get("chat_id") or admin_open_id


def notify_stage_completed(title: str, content: str, stage: str, task_id: str, artifact_paths: list = None, source_metadata: Optional[dict] = None):
    """
    Called by the engine when a task stage completes successfully.
    Sends an informational rich text card to the admin user via Feishu.
    """
    _app_id, _app_secret, admin_open_id, _client, fc = _load_notifier_context()
    recipient = _resolve_recipient(source_metadata, admin_open_id)
    if not fc or not recipient:
        return

    extra_info = ""
    # 提取 intake 阶段需要确认的点并在飞书展示
    if artifact_paths:
        extra_info += "\n\n**📦 阶段产物 (Artifacts)**"
        for p in artifact_paths:
            if p.endswith(".md"):
                # 如果是 Markdown 文件，记录它的文件名
                filename = os.path.basename(p)
                extra_info += f"\n- {filename} (已生成)"
                
                # 特别针对 intake/requirements/planning 等文档，尝试提取 "需确认的点" 或 "待确认"
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        text = f.read()
                        
                    # 尝试寻找相关标题
                    import re
                    match = re.search(r'(#{2,4}\s*(需确认的点|待确认的问题|问题与澄清|Issues to Clarify|待沟通事宜|待确认项)[\s\S]*?)(?=\n#{1,4}\s|\Z)', text, re.IGNORECASE)
                    if match:
                        questions = match.group(1).strip()
                        extra_info += f"\n\n**❓ 发现待确认事项 ({filename})**\n> " + questions.replace('\n', '\n> ')
                except Exception:
                    pass
    msg = (f"**✅ 阶段完成通知 (Stage Completed)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**状态摘要**: {title}\n\n"
           f"{content}"
           f"{extra_info}")

    async def _send():
        try:
            await fc.send_card_to_user(open_id=recipient, content=msg, loading=False)
            print(f"Successfully sent feishu completion notification to {recipient}")
        except Exception as e:
            print(f"Failed to send Feishu completion notification: {e}")

    _run_async_send(_send)

def notify_user_for_feedback(title: str, content: str, stage: str, task_id: str, options: list = None, source_metadata: Optional[dict] = None):
    """
    Called by the engine when a task fails and needs human intervention.
    Sends a rich text card to the admin user via Feishu.
    """
    _app_id, _app_secret, admin_open_id, _client, fc = _load_notifier_context()
    recipient = _resolve_recipient(source_metadata, admin_open_id)
    if not fc or not recipient:
        return

    msg = (f"**🚨 ⚠️ 流水线处于挂起状态 (Human Needed)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**异常/确认摘要**: {title}\n\n"
           f"{content}\n\n"
           f"---\n"
           f"💡 *操作指南*：请选择下方选项，您可以同时填写补充说明一起提交。\n")

    # 构建动态选项或兜底按钮
    buttons = []
    if options and isinstance(options, list) and len(options) > 0:
        all_opts = [str(opt) for opt in options]
        for opt in options:
            buttons.append({
                "text": str(opt),
                "value": {
                    "action": "pipeline_feedback",
                    "task_id": task_id,
                    "stage": stage,
                    "prompt_title": title,
                    "prompt_content": content,
                    "feedback": str(opt),
                    "clicked_text": str(opt),
                    "all_options": all_opts,
                    "prioritize": True,
                    "cid": recipient,
                }
            })
    else:
        all_opts_default = ["✅ 没问题，直接放行", "🔧 尝试使用 debug 模式修复", "🛑 终止并等待人工处理"]
        buttons = [
            {"text": "✅ 没问题，直接放行", "value": {"action": "pipeline_feedback", "task_id": task_id, "stage": stage, "prompt_title": title, "prompt_content": content, "feedback": "授权通过，无额外修改意见", "clicked_text": "✅ 没问题，直接放行", "all_options": all_opts_default, "prioritize": True, "cid": recipient}},
            {"text": "🔧 尝试使用 debug 模式修复", "value": {"action": "pipeline_feedback", "task_id": task_id, "stage": stage, "prompt_title": title, "prompt_content": content, "feedback": "请查阅日志并尝试自动修复", "clicked_text": "🔧 尝试使用 debug 模式修复", "all_options": all_opts_default, "prioritize": True, "cid": recipient}},
            {"text": "🛑 终止并等待人工处理", "value": {"action": "pipeline_feedback", "task_id": task_id, "stage": stage, "prompt_title": title, "prompt_content": content, "feedback": "人工决定暂不继续自动执行，请停止并等待进一步处理", "clicked_text": "🛑 终止并等待人工处理", "all_options": all_opts_default, "prioritize": False, "cid": recipient}}
        ]

    # 添加独立的发送文本说明按钮
    buttons.append({
        "text": "📤 仅发送说明",
        "value": {
            "action": "pipeline_feedback",
            "task_id": task_id,
            "stage": stage,
            "prompt_title": title,
            "prompt_content": content,
            "feedback": "仅提供附件或补充说明，请继续执行",
            "clicked_text": "📤 仅发送说明",
            "all_options": all_opts if options and isinstance(options, list) and len(options) > 0 else all_opts_default,
            "prioritize": True,
            "cid": recipient,
        }
    })

    async def _send():
        try:
            msg_id = await fc.send_card_to_user(open_id=recipient, content=msg, loading=False)
            if msg_id:
                await fc.update_card_with_buttons(msg_id, msg, buttons, use_input=True)
            print(f"Successfully sent feishu notification with options to {recipient}")
        except Exception as e:
            print(f"Failed to send Feishu notification: {e}")

    _run_async_send(_send)


def notify_approval_required(title: str, content: str, stage: str, task_id: str, approval_id: str, source_metadata: Optional[dict] = None):
    _app_id, _app_secret, admin_open_id, _client, fc = _load_notifier_context()
    recipient = _resolve_recipient(source_metadata, admin_open_id)
    if not fc or not recipient:
        return

    msg = (f"**🛂 流水线等待审批 (Approval Required)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**审批摘要**: {title}\n\n"
           f"{content}\n\n"
           f"---\n"
           f"💡 *操作指南*：请选择批准或拒绝，您也可以填写补充说明。")

    buttons = [
        {"text": "✅ 批准继续", "value": {"action": "pipeline_approval", "task_id": task_id, "approval_id": approval_id, "stage": stage, "prompt_title": title, "prompt_content": content, "resolution": "approved", "clicked_text": "✅ 批准继续", "all_options": ["✅ 批准继续", "🛑 拒绝继续"], "cid": recipient}},
        {"text": "🛑 拒绝继续", "value": {"action": "pipeline_approval", "task_id": task_id, "approval_id": approval_id, "stage": stage, "prompt_title": title, "prompt_content": content, "resolution": "rejected", "clicked_text": "🛑 拒绝继续", "all_options": ["✅ 批准继续", "🛑 拒绝继续"], "cid": recipient}},
        {"text": "📤 仅发送说明", "value": {"action": "pipeline_approval", "task_id": task_id, "approval_id": approval_id, "stage": stage, "prompt_title": title, "prompt_content": content, "resolution": "comment_only", "clicked_text": "📤 仅发送说明", "all_options": ["✅ 批准继续", "🛑 拒绝继续"], "cid": recipient}},
    ]

    async def _send():
        try:
            msg_id = await fc.send_card_to_user(open_id=recipient, content=msg, loading=False)
            if msg_id:
                await fc.update_card_with_buttons(msg_id, msg, buttons, use_input=True)
            print(f"Successfully sent feishu approval request to {recipient}")
        except Exception as e:
            print(f"Failed to send Feishu approval notification: {e}")

    _run_async_send(_send)
