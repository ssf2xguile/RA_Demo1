import os
import glob
from agents import Agent, function_tool, Runner, Handoff
import asyncio
import openai

# --- ツール定義 ---

@function_tool
def read_application_log() -> str:
    """
    ./logs/app.log に保存されたアプリケーションのログファイルを読み取ります。
    このエージェントを実行する前に、必ずアプリケーションを実行してログを生成しておく必要があります。
    """
    log_path = "/app/logs/app.log"
    try:
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            # ログが非常に大きい可能性を考慮し、最後の100行を読み込む
            lines = f.readlines()
            return "".join(lines[-100:])
    except FileNotFoundError:
        return f"エラー: ログファイルが {log_path} に見つかりませんでした。先にアプリケーションを実行してログファイルを生成してください。"
    except Exception as e:
        return f"ログファイルの読み込み中にエラーが発生しました: {e}"

@function_tool
def read_file(file_path: str) -> str:
    """指定されたパスのソースコードファイルの内容を読み取ります。"""
    try:
        # セキュリティのため、/app/source ディレクトリ内のファイルのみを対象とする
        base_path = os.path.abspath("/app/source")
        target_path = os.path.abspath(file_path)
        if not target_path.startswith(base_path):
            return "エラー: アクセスが許可されていないディレクトリです。/app/source 内のファイルのみ読み取れます。"

        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        return f"ファイルの読み込み中にエラーが発生しました: {e}"

@function_tool
def list_files(directory: str) -> list[str]:
    """指定されたディレクトリ内のソースコードファイルとディレクトリのリストを再帰的に返します。"""
    try:
        # セキュリティのため、/app/source ディレクトリ内のファイルのみを対象とする
        base_path = os.path.abspath("/app/source")
        target_path = os.path.abspath(directory)
        if not target_path.startswith(base_path):
            return ["エラー: アクセスが許可されていないディレクトリです。/app/source 内のみリスト化できます。"]

        return glob.glob(f"{target_path}/**/*.py", recursive=True)
    except Exception as e:
        return [f"ファイルのリスト化中にエラーが発生しました: {e}"]


# --- エージェント定義 ---

# 2. 修復案提案エージェント (SolutionPlanner)
# 原因特定エージェントから分析結果を受け取り、具体的な解決策を提示します。
solution_planner = Agent(
    name="SolutionPlanner",
    instructions=(
        "You are an expert in devising concrete, actionable repair plans for identified issues. "
        "Based on the failure analysis report from the ProblemIdentifier, "
        "provide a specific code modification proposal, detailing which part of which file to modify and how. "
        "Also, suggest long-term architectural improvements if necessary."
    )
)

# 1. 原因特定エージェント (ProblemIdentifier)
# ログファイルとソースコードを分析し、問題の根本原因を特定します。
problem_identifier = Agent(
    name="ProblemIdentifier",
    tools=[read_application_log, list_files, read_file],
    instructions=(
        "You are a system failure investigator. Your expertise is analyzing the log file at `/app/logs/app.log` "
        "and the associated source code in `/app/source` to determine the root cause of a failure. "
        "First, use `read_application_log` to read the logs and find errors or abnormal patterns (e.g., timeouts, error messages). "
        "Next, use `list_files` and `read_file` to investigate the relevant source code and determine why the error occurred. "
        "Your task is to identify the root cause. Analyze the identified cause in detail and hand off the results to the SolutionPlanner."
    ),
    handoffs=[solution_planner]
)


# --- オーケストレーション ---
async def main():
    # OpenAI APIキーの確認
    if not os.environ.get("OPENAI_API_KEY"):
        print("エラー: 環境変数 OPENAI_API_KEY が設定されていません。")
        return

    print("\n" + "="*50)
    print("AIエージェントによるログ分析を開始します...")
    print("="*50)

    # 開始プロンプト
    initial_prompt = (
        "アプリケーションログ `app.log` を分析し、エラーの根本原因を特定してください。"
        "特定後、その原因を解決するための修復計画を作成してください。"
    )

    final_result = None
    try:
        # 原因特定エージェントからオーケストレーションを開始
        final_result = await Runner.run(problem_identifier, input=initial_prompt)
    except Exception as e:
        print(f"エージェントの実行中に予期せぬエラーが発生しました: {e}")

    if final_result and final_result.final_output:
        print("\n--- ✅ 分析と修復案の提案が完了しました ---")
        print(final_result.final_output)
    else:
        print("\n--- ❌ エラー分析または修復案の生成に失敗しました。---")

    print("\n" + "="*50)
    print("分析プロセスを終了します。")
    print("="*50)


if __name__ == "__main__":
    # agentsライブラリがasyncioを使用するため、非同期関数として実行
    asyncio.run(main())
