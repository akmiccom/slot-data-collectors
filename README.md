# slot-data-collectors

パチスロ台データを複数のWebデータソースから取得・解析・標準化するPython基盤です。

現在は初期構築段階で、PScubeのHTTP取得と共通モデルを実装しています。

PScubeの解析・標準化とREITOの収集処理は未実装で、呼び出すと明示的に例外になります。

本番HTMLの構造やセレクタは推測していません。

## 役割分担

| リポジトリ・サービス | 責務 |
| --- | --- |
| slot-data-collectors | Webからの取得・解析・標準化 |
| Supabase | データ保存・統合（将来の接続先） |
| Slot-Data-Analysis | データ分析 |
| Slot-Data-Analysis-web | Web画面・可視化 |
| Slot-Data-Analysis-DB | DB schema / migration / view / RPC管理 |

このリポジトリには分析・ランキング計算やDB書き込みを含めません。

## 構成

```text
collectors/
  __init__.py
  pscube/                  # client.py / parser.py / collector.py / __init__.py
  reitoweb/                # 同じ構成の未実装の骨格
common/
  __init__.py
  models.py                # dataclass SlotResultと値の検証
  normalize.py             # source固有データ → SlotResult（現時点では未実装）
  exceptions.py            # 取得・解析・標準化の例外
  logging_config.py        # JSON形式ログとURLのマスキング
jobs/
  __init__.py
  collect_pscube.py         # 通信しない設定・実装状態の確認用エントリーポイント
tests/
  __init__.py
  conftest.py              # テスト中の実HTTP通信を禁止
  test_models.py
  test_collectors.py
  fixtures/               # 機密情報を除いたHTML fixtureの保存先
.env.example
.gitignore
requirements.txt
README.md
```

## Collectorの設計

```text
Web → client.fetch(url) → HTML → parser.parse(html)
    → source固有データ → normalize → SlotResult
```

- clientはHTTPのみを担当します。`requests.Session`による通常のCookie維持とセッション注入に対応します。所有するセッションはコンテキストマネージャーで閉じ、注入したセッションは呼び出し元が管理します。
- parserはHTML文字列だけを解析し、通信しません。BeautifulSoupは実HTMLに基づく実装時に使用します。
- normalizeはフィールド名・欠損値・日付・数値を標準形式へ変換する場所です。HTML解析は行いません。PScubeのフィールド契約確定後に実装します。
- collectorは上記を組み合わせ、`list[SlotResult]`を返す設計です。現状のPScubeはHTML取得後、parserの未実装例外で停止します。
- jobは設定読み込みと実行を担当します。現時点ではネットワークアクセスせず、未実装をログに記録して終了コード1で終了します。不正な設定は終了コード2です。

`SlotResult`は台番号・営業日・sourceを必須とし、店舗ID・機種ID・名称・各集計値・URLは`None`を許容します。台番号は正の整数、game/bb/rbは0以上、medalは負数も許容します。boolや数値文字列は自動変換せず拒否します。営業日は`date`、取得時刻はタイムゾーン付き`datetime`で、既定はUTCです。sourceは固定列挙にせず、追加したソース名も保持します。

## 開発環境

Python 3.10以上を使用します。以下はリポジトリ直下で実行してください。
既存の`.venv`が動作する場合は作り直す必要はありません。

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m jobs.collect_pscube --help
.\.venv\Scripts\python.exe -m jobs.collect_pscube
```

`.env`が既にある場合、コピーは省略してください。仮想環境を有効化する場合は
`.\.venv\Scripts\Activate.ps1`を実行し、以降は`python -m pytest`などを利用できます。
有効化しなくても上記の実行ファイル指定で動作します。

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
.venv/bin/python -m pytest
.venv/bin/python -m jobs.collect_pscube --help
```

既存の仮想環境が`No Python at ...`で起動しない場合は、作成元のPythonが利用できていません。
利用可能なPythonから別名の仮想環境（例：`.venv-check`）を作成し、同じインストール・テスト手順を実行してください。

## 環境変数と通信設定

jobはリポジトリ直下の`.env`を読み込みます。OSの環境変数を優先し、未設定・空欄は既定値を使います。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| REQUEST_TIMEOUT | 15 | requestsのタイムアウト秒数（正の有限値） |
| REQUEST_INTERVAL | 1 | 前回リクエスト終了から次回開始までの最低間隔秒数（0以上の有限値） |

Python APIを直接使う場合は`PscubeClient(timeout=..., request_interval=...)`に渡してください。
User-Agentを設定し、逐次取得します。並列利用を想定していません。
リトライは既定で0回、`max_retries`で最大3回まで指定でき、接続エラー・タイムアウトだけを指数的な待機を挟んで再試行します。
HTTPエラー（401/403/429などを含む）は再試行しません。タイムアウトはジョブ全体の期限ではありません。

## テスト・ログ・機密情報

`python -m pytest`でモデル・HTTPモック・未実装境界・ログを検証します。実サイトへのアクセスはありません。
fixtureのHTMLは`tests/fixtures/`配下に置いてGit管理できます。一時HTML・debug・logs・`.env`・仮想環境は除外し、`.env.example`だけを共有します。

ログはloggingを使用し、source / URL / 成功・失敗 / 件数をJSON形式で記録します。
URLはoriginだけを残し、ユーザー情報・パス・クエリ・fragmentを削除します。
失敗時の件数は不明として`null`を記録します。例外本文・HTML・Cookie・ヘッダー・APIキー・DB接続文字列は記録しません。
`SlotResult.source_url`には元URLが入る想定のため、将来の保存・出力時には認証情報が含まれていないか確認が必要です。
fixtureにもCookie・トークン・個人情報や非公開データを含めないでください。

対象サイトの利用条件とアクセス可能な範囲を確認し、適切な間隔で取得します。
ログイン回避・認証突破・CAPTCHA回避・アクセス制御回避は実装しません。

## データソース追加と今後

同じシステムを使う店舗は同じcollectorを共有し、店舗ごとのURLやIDは呼び出し側の設定として扱います。
PScube、REITO、その他のソースは`collectors/<source>/`でHTTP・解析・収集を分離し、共通の`SlotResult`へ変換します。
現時点では汎用基底クラスやプラグイン基盤を導入していません。

1. 許可された実際のPScube HTMLを機密情報除去済みfixtureとして用意する。
2. 店舗・機種・台番号・営業日・game/bb/rb/medalの意味、欠損表記、文字コード、必要な通常セッション操作を確認する。
3. parserとnormalizeをfixtureと期待値で実装・検証し、jobを収集用に接続する。
4. REITOの実HTMLを確認し、同じ責務分離で追加する。

今回の対象外：SupabaseへのINSERT/UPDATE、DB変更、Materialized View更新、GitHub Actions、Playwright/Selenium、並列大量アクセス、みんレポ既存コードの移植、分析ロジック。
