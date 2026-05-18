import json
import re
from typing import Callable, Generator, Literal, Optional

from openai import OpenAI
from e2b_code_interpreter import Sandbox
from IPython.display import Image, display
import base64

from .logger import logger, log_tool_call
from .prompts import SYSTEM_PROMPT_COMPRESS_MESSAGES, SYSTEM_PROMPT_CODE_DATA
from .tools import execute_tool

TOKEN_LIMIT = 60_000
COMPRESS_THRESHOLD = 0.7
STATE_SNAPSHOT_PATTERN = re.compile(
    r"<state_snapshot>(.*?)</state_snapshot>", re.DOTALL
)


def clean_messages_for_llm(messages: list[dict]) -> list[dict]:
    return [{k: v for k, v in msg.items() if not k.startswith("_")} for msg in messages]


def compress_messages(client: OpenAI, messages: list[dict]) -> list[dict]:
    response = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "developer", "content": SYSTEM_PROMPT_COMPRESS_MESSAGES},
            *messages,
            {"role": "user", "content": "First, reason in your scratchpad. Then, generate the <state_snapshot>."},
        ],
    )
    text = response.output_text
    context = "\n".join(STATE_SNAPSHOT_PATTERN.findall(text))
    return [
        {"role": "user", "content": f"This is snapshot of the conversation so far:\n{context}"},
        {"role": "assistant", "content": "Got it. Thanks for the additional context!"},
    ]


def format_messages(messages: list[dict]) -> str:
    content = ""
    for message in messages:
        if "role" in message:
            if message["role"] == "user":
                content += f"[user]: {message['content']}\n"
            elif message["role"] == "assistant":
                content += f"[assistant]: {message['content']}\n"
        elif "type" in message:
            if message["type"] == "function_call":
                content += f"[assistant] Calls {message['name']}\n"
            elif message["type"] == "function_call_output":
                content += f"[function_result]: {message['output']}\n"
    return content


def get_compress_message_index(messages: list[dict]) -> int:
    chars = [len(json.dumps(m)) for m in messages]
    total_chars = sum(chars)
    target_chars = total_chars * COMPRESS_THRESHOLD
    curr_chars = 0
    for index, char in enumerate(chars):
        curr_chars += char
        if curr_chars >= target_chars:
            return index
    return len(messages)


def get_first_user_message_index(messages: list[dict]) -> int:
    for index, message in enumerate(messages):
        if message.get("role") == "user":
            return index
    return 0


def maybe_compress_messages(
    client: OpenAI, messages: list[dict], usage: int
) -> list[dict]:
    if usage <= TOKEN_LIMIT * COMPRESS_THRESHOLD:
        return messages
    compress_index = get_compress_message_index(messages)
    if compress_index >= len(messages):
        return messages
    compress_index += get_first_user_message_index(messages[compress_index:])
    if compress_index <= 0:
        return messages
    last_message = messages[compress_index - 1]
    if last_message.get("type") == "function_call":
        compress_index += 1
    to_compress = messages[:compress_index]
    to_keep = messages[compress_index:]
    if to_compress:
        logger.info(f"[agent] 📦 compressing messages [0...{compress_index}]...")
        return [*compress_messages(client, to_compress), *to_keep]
    return messages


def coding_agent(
    client: OpenAI,
    code_sbx: Sandbox,
    web_sbx: Sandbox,
    query: str,
    tools: dict[str, Callable],
    tools_schemas: list[dict],
    max_steps: int = 100,
    system: Optional[str] = None,
    messages: Optional[list[dict]] = None,
    usage: Optional[int] = 0,
    model: Literal["gpt-4.1-mini", "gpt-4.1"] = "gpt-4.1-mini",
    **model_kwargs,
) -> Generator:
    if system is None:
        system = SYSTEM_PROMPT_CODE_DATA
    if messages is None:
        messages = []

    user_message = {"role": "user", "content": query}
    messages.append(user_message)
    yield user_message, messages, usage

    steps = 0
    while steps < max_steps:
        messages = maybe_compress_messages(client, clean_messages_for_llm(messages), usage)
        response = client.responses.create(
            model=model,
            input=[
                {"role": "developer", "content": system},
                *clean_messages_for_llm(messages),
            ],
            tools=tools_schemas,
            **model_kwargs,
        )
        usage = response.usage.total_tokens
        has_function_call = False

        for part in response.output:
            messages.append(part.to_dict())
            yield part.to_dict(), messages, usage

            if part.type == "function_call":
                has_function_call = True
                result, metadata = execute_tool(
                    part.name,
                    part.arguments,
                    tools,
                    code_sbx=code_sbx,
                    web_sbx=web_sbx,
                )
                result_msg = {
                    "type": "function_call_output",
                    "call_id": part.call_id,
                    "output": json.dumps(result),
                    "_metadata": metadata,
                }
                messages.append(result_msg)
                yield result_msg, messages, usage

        steps += 1
        if not has_function_call:
            break

    return messages, usage


def log(generator_func, *args, **kwargs):
    gen = generator_func(*args, **kwargs)
    step = 0
    pending_tool_calls = {}

    try:
        while True:
            part_dict, messages, usage = next(gen)
            part_type = part_dict.get("type")

            if part_type == "reasoning":
                if step == 0:
                    logger.info(f"✨: [agent-#{step}] Thinking...")
                    step += 1
                logger.info(" ...")
            elif part_type == "message":
                content = part_dict.get("content")
                if content and content[0].get("text"):
                    logger.info(f"✨: {content[0]['text']}")
            elif part_type == "function_call":
                call_id = part_dict.get("call_id")
                pending_tool_calls[call_id] = (part_dict.get("name"), part_dict.get("arguments"))
            elif part_type == "function_call_output":
                call_id = part_dict.get("call_id")
                if call_id in pending_tool_calls:
                    name, arguments = pending_tool_calls.pop(call_id)
                    result = json.loads(part_dict.get("output", "{}"))
                    log_tool_call(name, arguments, result)
                metadata = part_dict.get("_metadata")
                if metadata and metadata.get("images"):
                    for image in metadata["images"]:
                        display(Image(data=base64.b64decode(image)))

    except StopIteration as e:
        messages, final_usage = e.value
        logger.info(f"[agent] 🔢 tokens: {final_usage} total")
        return messages, final_usage
