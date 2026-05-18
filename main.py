from openai import OpenAI

from app.sandbox import load_env, create_sandbox, setup_sandbox
from app.tools import tools, execute_tool
from app.tools_schemas import tools_schemas
from app.agent import coding_agent
from app.ui import ui


def main():
    load_env()

    print("🚀 Starting sandboxes...")
    code_sbx = create_sandbox(cache_file="code_sbx.cache")
    web_sbx = create_sandbox(cache_file="web_sbx.cache", template="dlai-nextjs-developer")

    print("🔧 Setting up sandboxes...")
    setup_sandbox(code_sbx)
    setup_sandbox(web_sbx)

    client = OpenAI()
    host = f"https://{web_sbx.get_host(3000)}"

    def agent(query, messages, usage, **kwargs):
        return coding_agent(
            client=client,
            code_sbx=code_sbx,
            web_sbx=web_sbx,
            query=query,
            tools=tools,
            tools_schemas=tools_schemas,
            messages=messages,
            usage=usage,
            **kwargs,
        )

    print(f"🌐 Web sandbox live at: {host}")
    print("🎨 Launching Gradio UI...")

    demo = ui(
        coding_agent=agent,
        host=host,
        code_sbx=code_sbx,
    )
    demo.launch()


if __name__ == "__main__":
    main()
