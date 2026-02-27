# プロジェクト概要
コネクテッドカーシステムにおける、とある課題を再現するための簡易的な環境です。

コネクテッドカーシステムはスマホアプリ、リバースプロキシサーバ、アプリケーションサーバ、コネクテッドカーの4つのコンポーネントから構成されています。

また、それとは別に、AIエージェントシステムが存在します。これはコネクテッドカーシステムで発生した課題を、ソースコード&設定ファイル&各コンポーネントの実行ログが統合されたファイルを分析することで原因を突き止め、復旧プランを生成する役割を果たします。

# ディレクトリ構成
```
D:.
│  .gitignore
│  docker-compose.yaml
│  README.md
│
├─ai_agent
│      Dockerfile
│      main.py
│      requirements.txt
│
├─app_server
│      Dockerfile
│      main.py
│      requirements.txt
│
├─connected_car
│      Dockerfile
│      simulator.py
│
├─logs
│      app.log
│      monitor.log
│
├─mobile_app
│      Dockerfile
│      launcher.py
│      send_command.py
│
├─nginx
│      Dockerfile
│      nginx.conf
│
└─timeout_monitor
      requirements.txt
      timeout_monitor_recorder.py
      timeout_monitor_snapshot.py
```
`ai_agent`はAIエージェントシステムを指します。`mobile_app`はスマホアプリ、`nginx`はリバースプロキシサーバ、`app_server`はアプリケーションサーバ、`connected_car`はコネクテッドカーを指します。

# 実行手順（起動・ログ収集・実行状態の取得）
このREADMEは、コネクテッドカーシステムの起動方法、実行ログの収集方法、そして`app_server/main.py`の処理状況（メトリクス）をAPIで取得する方法をまとめたものです。

## 前提

- Docker / Docker Compose が利用できること
- リポジトリ直下でコマンドを実行すること
- `./logs` ディレクトリが存在すること（ない場合は作成）

※この手順では、最大で3つのターミナルを使用します。
- ターミナル1：コネクテッドカーシステムの起動・停止用
- ターミナル2：コネクテッドカーシステムのログ収集用
- ターミナル3：メトリクス取得(curl)またはタイムアウト数モニターアプリケーションの実行用

## 1. コネクテッドカーシステム起動とログ収集
ターミナルを2つ開きます。そしてそれぞれディレクトリを移動します。以下例
```
D:\>cd D:\Programming\MyPython\RA_Demo1
```

### ターミナル1（コネクテッドカーシステム起動）
4つのコネクテッドカーシステムコンテナをバックグラウンドで起動します。
```
docker compose --profile app up --build -d
```

### ターミナル2（ログ収集）
起動したコンテナの全ての出力を`./logs/app.log`にリアルタイムで記録します。ターミナル1でコマンド実行した直後にターミナル2で次のコマンドを実行してください。
```
docker compose --profile app logs --follow > ./logs/app.log
```
このコマンドはログを監視し続けるため、このターミナルは開いたままにしてください。

## 2. エラーの再現
`send_command.py`は、時間が経つにつれて大量のリクエストを送信し、システムに負荷をかけてタイムアウトエラーを発生させるように作られています。
- ターミナル2のログを眺めながら、**2分半ほど待機**してください。
- `Client: ... ERROR! Operation timed out.`のようなエラーログが`app.log`に記録されるはずです。トータルで5分程度待機してください。

## ログ収集の停止とコネクテッドカーシステム終了
エラーログが十分に記録されたら、以下の順で停止します。
**1.ターミナル2（ログ監視停止）**
`Ctrl + C`を押してログ監視を停止します。これで`./logs/app.log`への書き込みが完了します。

**2.ターミナル1（コネクテッドカーシステム停止・削除）**
4つのコネクテッドカーシステムコンテナを停止・削除します。
```
docker compose --profile app down
```

## 3. AIエージェントによる分析
AIエージェントは4つのコンポーネントとは独立しています。AIエージェントを起動します（ai_agent コンテナが起動し、main.py が実行されます）。
```
docker compose --profile agent up --build
```
エージェントは自動的に以下を読み込み、分析を開始します。
- 各コンポーネントのソースコード。現在はリバースプロキシサーバとアプリケーションサーバのソースコードのみを読み込むようになっている。
- `./logs/app.log`
処理が完了すると、ターミナルに以下が出力されます。
- エラーの根本原因の分析結果
- 具体的なコード復旧案

## 4. [その他]アプリケーションサーバの処理状況をAPIで取得
`app_server/main.py`での処理状況を確認したい場合は、ターミナル1でコンテナが動作している状態で、ターミナル3を開き次のAPIを叩きます。
**Windows（例：PowerShell / CMD）**
```
curl -s http://localhost:8080/metrics
```
**出力例**
- 時刻
- 滞留リクエスト数
- 累計処理リクエスト数
- 累計到着リクエスト数
- 累計タイムアウト数
```
{"timestamp_epoch":1772199286.840296,"timestamp_iso":"2026-02-27T13:34:46.840299+00:00","uptime_s":300.07,"pending":2923,"done":6168,"timeouts":3932,"errors":3932,"arrived_total":13023,"session_count":240,"reserved_mb":240,"recent_arrivals":179,"recent_timeouts":75,"recent_timeout_ratio":0.419,"per_session_bytes":1048576,"max_sessions":240,"session_ttl":10,"app_queue_timeout_s":60,"log_chunk_kb":1,"httpx_max":2,"sticky_on_timeout_s":10}
```
補足ですが、ターミナル3でコマンド実行する際、ディレクトリはどこでも構いません。

## 5. [その他]アプリケーションサーバのタイムアウト状況のモニタリング
アプリケーションサーバのタイムアウト発生状況を、棒グラフとしてリアルタイムに監視するためのプログラムが `timeout_monitor` ディレクトリに用意されています。

- `timeout_monitor_snapshot.py`  
  グラフをリアルタイム表示し、システム起動から300秒間の推移を**スクショ(PNG)として保存**する
- `timeout_monitor_recorder.py`  
  グラフをリアルタイム表示し、システム起動から300秒間の推移を**動画(MP4)として保存**する

これらのプログラムは **Docker コンテナではなく、ホスト OS 上の Python から直接実行**することを想定しています。

### 5.1 事前準備（timeout_monitor 内に venv を作成）
Python 3.xがインストールされている前提です。  
ここでは、`timeout_monitor`ディレクトリ内に仮想環境 `tm-env` を作成します。

#### (1) ディレクトリ移動
移動例
```cmd
cd D:\Programming\MyPython\RA_Demo1\timeout_monitor
```

#### (2) 仮想環境の作成（初回のみ）

```cmd
python -m venv tm-env
```

これで `timeout_monitor\tm-env` という仮想環境が作成されます。

#### (3) 仮想環境を有効化

コマンドプロンプトの場合：

```cmd
.\tm-env\Scripts\Activate
```

プロンプトの先頭に `(tm-env)` が表示されていれば有効化されています。

#### (4) 依存ライブラリのインストール

```cmd
pip install -r .\requirements.txt
```

以後、この `timeout_monitor` ディレクトリで作業する際は、

- `cd D:\Programming\MyPython\RA_Demo1\timeout_monitor`
- `.\tm-env\Scripts\Activate`

の 2 ステップで仮想環境を有効化してからプログラムを実行してください。  
作業終了後は`deactivate`コマンドを実行することで仮想環境を終了できます。

---

### 5.2 スナップショット版モニタの起動（静止画保存）
ターミナル3を起動しディレクトリを移動します。そして仮想環境を有効にします。
1. ターミナル1でコネクテッドカーシステムを起動した状態にします。
2. ターミナル3で次のコマンドを実行します。
```cmd
python timeout_monitor_snapshot.py
```

3. 2分半ほど待つと、タイムアウト数の推移が棒グラフとして表示されます。
4. ウィンドウを閉じるとプログラムは終了し、同一ディレクトリ内に静止画ファイル(例：`timeout_graph.png`)が保存されます。

---

### 5.3 レコーダ版モニタの起動（動画保存）
同様にターミナル3を起動し仮想環境を有効にします。
1. ターミナル1でコネクテッドカーシステムが起動している状態にします。
2. ターミナル3で次のコマンドを実行します。
```cmd
python timeout_monitor_recorder.py
```

3. グラフウィンドウが表示され、300秒間のタイムアウト数推移が記録されます。
4. 記録完了後(もしくはウィンドウを閉じたタイミング)でプログラムが終了し、同一ディレクトリ内にMP4動画ファイル(例：`RA_plan1.mp4`)が保存されます。

---

### 5.4 モニタと API の接続について
モニタプログラムは、内部でアプリケーションサーバのメトリクスAPIを定期的に呼び出しています。
```python
API_URL = "http://localhost:8080/metrics"
```

といった形で URL が定義されている場合、**手順4で使用したAPIと同じエンドポイント**からメトリクスを取得します。

もしポート番号やパスを変更した場合は、`timeout_monitor_snapshot.py` / `timeout_monitor_recorder.py` 内の `API_URL` も合わせて修正してください。