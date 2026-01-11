import os
import glob
from agents import Agent, function_tool, Runner
import asyncio
import openai
from openai.types.responses import ResponseTextDeltaEvent

# --- 設定 ---
# 修正対象のルートディレクトリ（docker-composeでマウントした場所）
PROJECT_ROOT = "/app/source"

# --- ツール定義 (分析用) ---
ALLOWED_FILES = [
    "cloud_api/main.py",
    "nginx/nginx.conf",
    "docker-compose.yaml"
]

@function_tool
def read_log_file(log_name: str) -> str:
    """ログファイル(app.log, monitor.log)を読み取ります。"""
    log_path = os.path.join(PROJECT_ROOT, "logs", log_name)
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            # 分析精度向上のため、直近400行を読み込む
            return "".join(lines[-400:])
    except Exception as e:
        return f"ログ読み込みエラー: {e}"

@function_tool
def read_file(relative_path: str) -> str:
    """指定されたパスのソースコードを読み取ります。"""
    target_path = os.path.join(PROJECT_ROOT, relative_path)
    try:
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"ファイル読み込みエラー: {e}"

@function_tool
def list_files(directory: str) -> list[str]:
    """指定されたディレクトリ内のファイルをリスト化します。"""
    target_dir = os.path.join(PROJECT_ROOT, directory)
    try:
        files = glob.glob(f"{target_dir}/**/*", recursive=True)
        # 相対パスに変換して返す
        return [f.replace(PROJECT_ROOT + "/", "") for f in files if os.path.isfile(f)]
    except Exception as e:
        return [f"エラー: {e}"]

# --- ツール定義 (修正用) ---

@function_tool
def overwrite_file(relative_path: str, content: str) -> str:
    """
    【危険】ホスト側のファイルを直接上書き保存します。
    relative_path: プロジェクトルートからの相対パス（例: cloud_api/main.py）
    """
    target_path = os.path.join(PROJECT_ROOT, relative_path)
    try:
        # ディレクトリがない場合は作成
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"✅ File overwritten: {relative_path}"
    except Exception as e:
        return f"❌ Failed to write file: {e}"


# --- エージェント定義 ---

# 2. 修復実行エージェント (今回はこれが最終走者)
repair_planning = Agent(
    name="RepairPlanning",
    tools=[overwrite_file],
    instructions=(
        "You are a Senior System Architect."
        "Your goal is to FIX the root cause identified by FaultLocalization by directly overwriting the source code."
        "Target files are likely: `cloud_api/main.py`, `nginx/nginx.conf`, or `docker-compose.yaml`."
        "\n"
        "**CRITICAL INSTRUCTIONS:**"
        "1. DO NOT ask the user for permission. You have full authority to edit files."
        "2. Generate the **FULL CORRECTED CONTENT** for the target files."
        "3. Use `overwrite_file` to update them immediately."
        "4. After updating all necessary files, **report a summary of the changes** as your final output."
    )
    # handoffs は設定しない（ここで終了）
)

# 1. 原因特定エージェント
fault_localization = Agent(
    name="FaultLocalization",
    tools=[read_log_file, list_files, read_file],
    instructions=(
        "You are a Senior SRE."
        "Analyze `app.log` and `monitor.log` to find the root cause of timeouts/errors."
        "Principles:"
        "- Check for mismatch in timeouts between Nginx and App."
        "- Check for resource bottlenecks (memory, sessions)."
        "- Check for sticky error states."
        "\n"
        "**STRICT RULES:**"
        "1. **DO NOT ask the user for more information.** Use `read_file` or `list_files` to find what you need."
        "2. **DO NOT report findings yet.**"
        "3. Once you identify the root cause, **IMMEDIATELY** hand off to `RepairPlanning` agent."
    ),
    handoffs=[repair_planning]
)


async def main():
    if not os.environ.get("OPENAI_API_KEY"):
        print("エラー: 環境変数 OPENAI_API_KEY が設定されていません。")
        return

    print("\n" + "="*50)
    print("AIエージェントによるログ分析を開始します...")
    print("="*50)

    initial_prompt = (
        "アプリケーションログ `app.log` とモニタリングログ `monitor.log` を分析し、"
        "システムが高負荷時に不安定になる根本原因を特定してください。"
        "サーバーサイドの構成（ソースコードおよび設定ファイル）に潜む構造的な欠陥や設定の不整合を指摘し、"
        "修復プランを作成してください。"
    )

    # 複雑な分析・修正に耐えられるようターン数を確保
    runner = Runner.run_streamed(fault_localization, input=initial_prompt, max_turns=30)
    
    current_agent = fault_localization.name
    print(f"\n[{current_agent}] Starting...")

    async for event in runner.stream_events():
        if event.type == "agent_updated_stream_event":
            current_agent = event.new_agent.name
            print(f"\n\n[{current_agent}] Handing over...")
        elif event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)

    print("\n\n[Final Output]")
    print(runner.final_output)

if __name__ == "__main__":
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    asyncio.run(main())