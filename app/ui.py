import os
import json
import base64
from io import BytesIO
from typing import Callable

import gradio as gr
from gradio import ChatMessage
from PIL import Image
import tiktoken
from gradio_browser import Browser
from gradio_aicontext import AIContext
from e2b_code_interpreter import Sandbox

from .agent import clean_messages_for_llm
from .prompts import SYSTEM_PROMPT_CODE_DATA, SYSTEM_PROMPT_WEB_DEV


def count_tokens(message: dict) -> int:
    encoding = tiktoken.encoding_for_model("gpt-4")
    return len(encoding.encode(json.dumps(clean_messages_for_llm([message]))))


def parse_openai_message(part: dict) -> list[ChatMessage]:
    messages = []

    if "role" in part:
        if part["role"] == "user":
            messages.append(ChatMessage(role="user", content=part["content"]))
        elif part["role"] == "assistant" and part["content"]:
            text = part["content"]
            if isinstance(text, list):
                text = text[0]["text"]
            messages.append(ChatMessage(role="assistant", content=text))

    elif "type" in part:
        if part["type"] == "reasoning":
            messages.append(ChatMessage(
                role="assistant",
                content="Analyzing the problem...",
                metadata={"title": "🧠 Reasoning", "status": "done"},
            ))
        elif part["type"] == "function_call":
            content = ""
            if part["name"] == "execute_code":
                arguments = json.loads(part["arguments"])
                content = arguments.get("code", "")
            else:
                content = f"```json\n{json.dumps(part['arguments'], indent=2)}\n```"
            messages.append(ChatMessage(
                role="assistant",
                content=content,
                metadata={"title": f"🛠️ Using {part['name']}", "id": part["call_id"], "status": "done"},
            ))
        elif part["type"] == "function_call_output":
            result = json.loads(part["output"])
            messages.append(ChatMessage(
                role="assistant",
                content=f"```json\n{json.dumps(result, indent=2)}\n```",
                metadata={"title": "✅ Tool completed"},
            ))

    if "_metadata" in part:
        for image_b64 in part["_metadata"].get("images", []):
            messages.append(ChatMessage(
                role=part.get("role", "assistant"),
                content=gr.Image(value=Image.open(BytesIO(base64.b64decode(image_b64)))),
            ))

    return messages


def ui(
    coding_agent: Callable,
    host: str,
    code_sbx: Sandbox,
):
    cd_state = {"data": [], "usage": 0}
    wd_state = {"data": [], "usage": 0}

    def make_chat_fn(state, system_prompt):
        def chat(message: str, history: list):
            gradio_messages = history.copy()
            msgs = state["data"]
            usage = state["usage"]
            for part, msgs, usage in coding_agent(
                messages=state["data"],
                usage=state["usage"],
                query=message,
                system=system_prompt,
            ):
                gradio_messages.extend(parse_openai_message(part))
                yield gradio_messages.copy(), msgs
            state["data"] = msgs
            state["usage"] = usage
        return chat

    def make_reset_fn(state):
        def reset():
            state["data"] = []
            state["usage"] = 0
            return [], []
        return reset

    def handle_upload(file):
        if file is None:
            return "No file selected."
        filename = os.path.basename(file)
        with open(file, "rb") as f:
            content = f.read()
        code_sbx.files.write(f"/home/user/{filename}", content)
        return f"✅ {filename} → /home/user/{filename}"

    css = """
.gradio-container { margin: 0; padding: 8px; }
.h-full { height: 100% !important; }
.flex { display: flex; }
.min-h-0 { min-height: 0; }
#context-cd, #context-wd {
    height: calc(100vh - 200px);
    max-height: calc(100vh - 200px);
    overflow: hidden;
}
"""

    with gr.Blocks(fill_width=True, fill_height=True, css=css) as demo:
        gr.Markdown("# 🤖 AI Coding Platform")

        with gr.Tabs():

            # ── Tab 1: Code & Data ──────────────────────────────────────
            with gr.Tab("💻 Code & Data"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=4, min_width=300):
                        chatbot_cd = gr.Chatbot(
                            type="messages",
                            show_copy_button=True,
                            scale=1,
                            elem_classes="flex-grow",
                            label="Chat",
                        )
                        upload_btn = gr.UploadButton(
                            "📎 Upload File",
                            file_count="single",
                            scale=0,
                        )
                        upload_status = gr.Textbox(
                            scale=0,
                            interactive=False,
                            show_label=False,
                            placeholder="Upload status...",
                        )
                        msg_cd = gr.Textbox(
                            placeholder="Ask me to write code or analyse your data...",
                            lines=2,
                            label="Message",
                            max_lines=4,
                            scale=0,
                        )
                        send_cd = gr.Button("Send", variant="primary", scale=0)

                    with gr.Column(scale=1, min_width=176, elem_id="context-cd"):
                        aicontext_cd = AIContext(
                            value=[],
                            count_tokens_fn=count_tokens,
                            elem_classes="h-full flex min-h-0",
                        )

                chat_cd = make_chat_fn(cd_state, SYSTEM_PROMPT_CODE_DATA)
                reset_cd = make_reset_fn(cd_state)

                upload_btn.upload(handle_upload, inputs=[upload_btn], outputs=[upload_status])
                chatbot_cd.clear(fn=reset_cd, outputs=[chatbot_cd, aicontext_cd])
                for trigger in [msg_cd.submit, send_cd.click]:
                    trigger(
                        chat_cd,
                        inputs=[msg_cd, chatbot_cd],
                        outputs=[chatbot_cd, aicontext_cd],
                    ).then(lambda: "", outputs=[msg_cd])

            # ── Tab 2: Web Dev ──────────────────────────────────────────
            with gr.Tab("🌐 Web Dev"):
                with gr.Row(equal_height=True):
                    with gr.Column(scale=3, min_width=300):
                        chatbot_wd = gr.Chatbot(
                            type="messages",
                            show_copy_button=True,
                            scale=1,
                            elem_classes="flex-grow",
                            label="Chat",
                        )
                        msg_wd = gr.Textbox(
                            placeholder="Ask me to build or update the web app...",
                            lines=2,
                            label="Message",
                            max_lines=4,
                            scale=0,
                        )
                        send_wd = gr.Button("Send", variant="primary", scale=0)

                    with gr.Column(scale=5, min_width=500):
                        Browser(value=host, min_height=700)

                    with gr.Column(scale=1, min_width=176, elem_id="context-wd"):
                        aicontext_wd = AIContext(
                            value=[],
                            count_tokens_fn=count_tokens,
                            elem_classes="h-full flex min-h-0",
                        )

                chat_wd = make_chat_fn(wd_state, SYSTEM_PROMPT_WEB_DEV)
                reset_wd = make_reset_fn(wd_state)

                chatbot_wd.clear(fn=reset_wd, outputs=[chatbot_wd, aicontext_wd])
                for trigger in [msg_wd.submit, send_wd.click]:
                    trigger(
                        chat_wd,
                        inputs=[msg_wd, chatbot_wd],
                        outputs=[chatbot_wd, aicontext_wd],
                    ).then(lambda: "", outputs=[msg_wd])

    return demo
