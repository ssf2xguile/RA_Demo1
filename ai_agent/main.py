import os
import glob
from agents import Agent, function_tool, Runner, Handoff
import asyncio
import openai
from openai.types.responses import ResponseTextDeltaEvent

# --- ツール定義 ---
ALLOWED_SERVER_DIRS = [
    "/app/source/cloud_api",
    "/app/source/nginx",
    "/app/source/docker-compose.yaml"
]

@function_tool
def read_log_file(log_name: str) -> str:
    """
    ./logs/ ディレクトリにあるログファイルを読み取ります。
    引数 log_name には 'app.log' または 'monitor.log' を指定してください。
    """
    if log_name not in ["app.log", "monitor.log"]:
        return "エラー: 指定できるログファイルは 'app.log' または 'monitor.log' のみです。"

    log_path = f"/app/logs/{log_name}"
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            # 最後の200行を読み込む
            lines = f.readlines()
            return "".join(lines[-200:])
    except FileNotFoundError:
        return f"エラー: ログファイルが {log_path} に見つかりませんでした。先にアプリケーションを実行してログファイルを生成してください。"
    except Exception as e:
        return f"ログファイルの読み込み中にエラーが発生しました: {e}"

@function_tool
def read_file(file_path: str) -> str:
    try:
        base_path = os.path.abspath("/app/source")
        target_path = os.path.abspath(file_path)
        
        is_allowed = any(target_path.startswith(os.path.abspath(d)) for d in ALLOWED_SERVER_DIRS)
        
        if not target_path.startswith(base_path):
             return "エラー: アクセスが許可されていないディレクトリです。/app/source 内のファイルのみ読み取れます。"
        
        if not is_allowed:
            return "エラー: あなたはサーバーサイドエンジニアです。スマホアプリや車両のコードにアクセスする権限はありません。"

        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"ファイルの読み込み中にエラーが発生しました: {e}"

@function_tool
def list_files(directory: str) -> list[str]:
    """
    指定されたディレクトリ内のサーバーサイド関連ファイル（cloud_api, nginx）のみをリスト化して返します。
    """
    try:
        base_path = os.path.abspath("/app/source")
        target_path = os.path.abspath(directory)
        if not target_path.startswith(base_path):
            return ["エラー: アクセスが許可されていないディレクトリです。/app/source 内のみリスト化できます。"]

        file_patterns = ["*.py", "*.conf", "*.yml", "*.yaml"]
        files = []

        found_files = []
        for pattern in file_patterns:
            found_files.extend(glob.glob(f"{target_path}/**/{pattern}", recursive=True))
            
        filtered_files = []
        for f in found_files:
            abs_f = os.path.abspath(f)
            if any(abs_f.startswith(os.path.abspath(d)) for d in ALLOWED_SERVER_DIRS):
                filtered_files.append(f)
        
        if not filtered_files:
             return ["指定されたディレクトリ内に、アクセス可能なサーバーサイドのソースコードは見つかりませんでした。cloud_api または nginx ディレクトリを確認してください。"]

        return filtered_files
    except Exception as e:
        return [f"ファイルのリスト化中にエラーが発生しました: {e}"]

@function_tool
def apply_patch_to_staging(diff_text: str) -> str:
    """
    Apply a unified diff patch to the staging source directory.
    This function does NOT touch /app/source directly.
    """
    import subprocess
    import os
    staging_path = "/app/staging/source"

    # Ensure the staging directory exists
    os.makedirs(staging_path, exist_ok=True)

    # Write diff to a temporary file
    patch_path = "/tmp/patch.diff"
    with open(patch_path, "w", encoding="utf-8") as f:
        f.write(diff_text)

    # Apply the patch using `patch` command
    try:
        subprocess.run(
            ["patch", "-p1", "-d", staging_path, "-i", patch_path],
            check=True,
            text=True
        )
        return "✅ Patch applied successfully to staging environment."
    except subprocess.CalledProcessError as e:
        return f"❌ Failed to apply patch: {e}"

@function_tool
def compose_up_staging() -> str:
    """Bring up the staging Docker Compose environment."""
    import subprocess
    compose_file = "/app/compose.staging/docker-compose.yml"
    try:
        subprocess.run(["docker", "compose", "-f", compose_file, "up", "-d", "--build"], check=True)
        return "✅ Staging environment started successfully."
    except subprocess.CalledProcessError as e:
        return f"❌ Failed to start staging environment: {e}"

@function_tool
def compose_down_staging() -> str:
    """Tear down the staging Docker Compose environment."""
    import subprocess
    compose_file = "/app/compose.staging/docker-compose.yml"
    try:
        subprocess.run(["docker", "compose", "-f", compose_file, "down", "-v"], check=True)
        return "🧹 Staging environment cleaned up successfully."
    except subprocess.CalledProcessError as e:
        return f"⚠️ Failed to tear down staging environment: {e}"


# 2. 修復案提案エージェント (RepairPlanning)
repair_planning = Agent(
    name="RepairPlanning",
    instructions=(
        "You are an expert in devising concrete, actionable repair plans for identified issues. "
        "Based on the failure analysis report from the FaultLocalization, "
        "provide a specific code modification proposal, detailing which part of which file to modify and how. "
        "In doing so, you may add functions and change values, but you must not delete existing code. "
        "Also, strictly follow the constraints written in the code comments."
    )
)

# 1. 原因特定エージェント (FaultLocalization)
fault_localization = Agent(
    name="FaultLocalization",
    tools=[read_log_file, list_files, read_file],
    instructions=(
        "You are a Senior System Architect responsible for diagnosing complex failures in distributed systems. "
        "Your goal is to identify the root cause of the failure by analyzing the interaction between components (Nginx, App Server). "
        "\n"
        "**Investigation Principles:**\n"
        "1. **Holistic View:** Do not view errors in isolation. Analyze how a request flows through the entire system (Proxy -> App) and identify where the bottleneck occurs.\n"
        "2. **Configuration Consistency:** Verify if the operational parameters (timeouts, limits, buffers) are consistent across different layers. "
        "3. **State Analysis:** Investigate how the system manages state (e.g., sessions, connections) under error conditions. "
        "\n"
        "Analyze the provided logs and source code based on these principles. "
        "Identify the logic or configuration that causes the instability and hand off the results to the RepairPlanningAgent."
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

    streaming = Runner.run_streamed(fault_localization, input=initial_prompt)
    async for event in streaming.stream_events():
        # 1. エージェントが切り替わった場合
        if event.type == "agent_updated_stream_event":
            current_agent = event.new_agent.name
            print(f"\n\n[{current_agent}]")

        # 2. テキスト生成（中間出力）の場合
        elif event.type == "raw_response_event":
            if isinstance(event.data, ResponseTextDeltaEvent):
                print(event.data.delta, end="", flush=True)


if __name__ == "__main__":
    asyncio.run(main())