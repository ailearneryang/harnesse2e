import os
import sys
import asyncio
import json

# Add feishu-claude-code to sys.path so we can import its modules
harness_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
feishu_path = os.path.join(harness_dir, "feishu-claude-code")
if feishu_path not in sys.path:
    sys.path.insert(0, feishu_path)

try:
    import dotenv
    dotenv.load_dotenv(os.path.join(feishu_path, ".env"))
except Exception:
    pass

try:
    from bot_config import FEISHU_APP_ID, FEISHU_APP_SECRET, ADMIN_OPEN_ID
    import lark_oapi as lark
    from feishu_client import FeishuClient
except Exception as e:
    print(f"Warning: Could not load feishu modules or config: {e}")
    FEISHU_APP_ID = None

def notify_stage_completed(title: str, content: str, stage: str, task_id: str):
    """
    Called by the engine when a task stage completes successfully.
    Sends an informational rich text card to the admin user via Feishu.
    """
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET or not ADMIN_OPEN_ID:
        return

    client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
    fc = FeishuClient(client, FEISHU_APP_ID, FEISHU_APP_SECRET)

    msg = (f"**✅ 阶段完成通知 (Stage Completed)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**状态摘要**: {title}\n\n"
           f"{content}")

    async def _send():
        try:
            await fc.send_card_to_user(open_id=ADMIN_OPEN_ID, content=msg, loading=False)
            print(f"Successfully sent feishu completion notification to {ADMIN_OPEN_ID}")
        except Exception as e:
            print(f"Failed to send Feishu completion notification: {e}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        import threading
        def run_in_thread():
            asyncio.run(_send())
        threading.Thread(target=run_in_thread).start()
    else:
        loop.run_until_complete(_send())

def notify_user_for_feedback(title: str, content: str, stage: str, task_id: str):
    """
    Called by the engine when a task stage completes successfully.
    Sends an informational rich text card to the admin user via Feishu.
    """
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET or not ADMIN_OPEN_ID:
        return

    client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
    fc = FeishuClient(client, FEISHU_APP_ID, FEISHU_APP_SECRET)

    msg = (f"**✅ 阶段完成通知 (Stage Completed)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**状态摘要**: {title}\n\n"
           f"{content}")

    async def _send():
        try:
            await fc.send_card_to_user(open_id=ADMIN_OPEN_ID, content=msg, loading=False)
            print(f"Successfully sent feishu completion notification to {ADMIN_OPEN_ID}")
        except Exception as e:
            print(f"Failed to send Feishu completion notification: {e}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        import threading
        def run_in_thread():
            asyncio.run(_send())
        threading.Thread(target=run_in_thread).start()
    else:
        loop.run_until_complete(_send())
    """
    Called by the engine when a task fails and needs human intervention.
    Sends a rich text card to the admin user via Feishu.
    """
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET or not ADMIN_OPEN_ID:
        print("Feishu notifier is disabled due to missing config (FEISHU_APP_ID, FEISHU_APP_SECRET, ADMIN_OPEN_ID).")
        return

    client = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
    fc = FeishuClient(client, FEISHU_APP_ID, FEISHU_APP_SECRET)

    msg = (f"**🚨 ⚠️ 流水线处于挂起状态 (Human Needed)**\n\n"
           f"**Task ID**: {task_id}\n"
           f"**Stage**: {stage}\n\n"
           f"**异常/确认摘要**: {title}\n\n"
           f"{content}\n\n"
           f"---\n"
           f"💡 *操作指南*：您可以直接在这里回复我，比如：\n"
           f"> 帮我看下错误日志里写了{stage}什么问题，修复该问题然后恢复流水线！\n"
           f"> (通过 CLI 会自动调用 /api/control/resume)")

    async def _send():
        try:
            await fc.send_card_to_user(open_id=ADMIN_OPEN_ID, content=msg, loading=False)
            print(f"Successfully sent feishu notification to {ADMIN_OPEN_ID}")
        except Exception as e:
            print(f"Failed to send Feishu notification: {e}")

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    if loop.is_running():
        # if already running, we might need a thread or nest_asyncio. 
        # But this is a synchronous pipeline_runner thread.
        import threading
        def run_in_thread():
            asyncio.run(_send())
        threading.Thread(target=run_in_thread).start()
    else:
        loop.run_until_complete(_send())
