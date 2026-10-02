# slot-data-collectors

パチスロ台データを複数のWebデータソースから取得・解析・標準化するPython基盤です。

現在は **PScube の取得経路を実サイトで検証する段階まで進んでいます**。機種一覧XHR、個別台XHR、確率からの回転数推定、グラフ画像からの差枚推定プロトタイプを実装済みです。

2026-09-22 の実サイト検証では、1店舗について機種一覧 **41機種・110台** を全3ページから取得し、サーバーの `count=41` と一致することを確認しました。個別台では BIG / REG / 3種類の確率 / 最大出玉 / グラフ参照先を取得できています。

PScube の `SlotResult` への最終標準化、複数台・複数店舗の本番収集、Supabase書き込み、REITO収集処理は未実装です。確認できていないHTML構造やセレクタは推測で実装しません。

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
  pscube/                  # client.py / parser.py / collector.py / inspect.py / models.py / __init__.py
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
  inspect_pscube.py         # URLを1つ受け取る取得検証CLI
  inspect_pscube_machines.py # 機種一覧JSONの取得・検証CLI
  inspect_pscube_unit.py     # 個別台1台・4日分のJSONと回転数推定
  inspect_pscube_graph.py    # グラフ1枚の差枚推定・注釈画像
tests/
  __init__.py
  conftest.py              # テスト中の実HTTP通信を禁止
  test_models.py
  test_collectors.py
  test_inspection.py
  test_machines.py
  test_unit.py
  test_graph.py
  fixtures/               # 機密情報を除いたHTML fixtureの保存先
.env.example
.gitignore
requirements.txt
README.md
AGENTS.md               # Codex/AI開発エージェント向け作業規約
```

## Collectorの設計

```text
Web → client.fetch(url) → HTML → parser.parse(html)
    → source固有データ → normalize → SlotResult
```

- clientはHTTPのみを担当します。`requests.Session`による通常のCookie維持とセッション注入に対応します。所有するセッションはコンテキストマネージャーで閉じ、注入したセッションは呼び出し元が管理します。
- parserはレスポンス本文だけを解析し、通信しません。PScubeではHTML診断に加え、機種一覧JSON・個別台JSONを専用parserで解析します。
- normalizeはsource固有データを共通`SlotResult`へ変換する場所です。HTML/JSON解析はここに入れません。PScubeの最終マッピングはまだ未実装です。
- collectorはclientとparserを組み合わせます。PScubeでは機種一覧のページング収集まで実装済みです。今後、個別台を複数台へ展開して標準化層へ接続します。
- jobは設定読み込みと検証実行を担当します。`inspect_pscube*` 系CLIで、HTML・機種一覧・個別台・グラフを段階的に検証できます。`collect_pscube` の本番収集接続はまだ行いません。

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
使用する仮想環境は`.venv`に統一します。起動できない`.venv`を削除してから、利用可能なPythonで上記の作成・インストール・テスト手順を実行してください。

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

## PScube検証CLIと詳細仕様

```powershell
python -m jobs.inspect_pscube "URL"
python -m jobs.inspect_pscube_machines "機種一覧URL" --save-json
python -m jobs.inspect_pscube_unit "個別台URL" --save-json
python -m jobs.inspect_pscube_unit --from-json "保存した_unit.json"
python -m jobs.inspect_pscube_graph --unit 0272 --date 20261001 --image "debug/pscube/graphs/20261001_0272.png" --annotate
```

各CLIの`--help`で引数を確認できます。グラフは確認済みの2種類の軸候補から自動選択し、ピンク・紫などの有彩色の連結線を検出します。判定不能時は差枚をNoneとします。任意の軸は`--top-medal / --bottom-medal / --step-medal`の3項目すべてを指定してください。

2026-09-21の0272は+3256枚、2026-10-01の保存画像は+1393枚と推定しました。これらは推定値で、精度保証ではありません。個別台の表示名と確認済み内部キーの両方に対応しています。

詳細は[取得とSession](docs/pscube/overview.md)、[機種一覧](docs/pscube/machine-list.md)、[個別台と回転数](docs/pscube/unit-detail.md)、[グラフ解析](docs/pscube/graph-estimation.md)、[検証記録](docs/pscube/validation.md)を参照してください。

## データソース追加と今後

同じシステムを使う店舗は同じcollectorを共有し、店舗ごとのURLやIDは呼び出し側の設定として扱います。
PScube、REITO、その他のソースは`collectors/<source>/`でHTTP・解析・収集を分離し、共通の`SlotResult`へ変換します。
現時点では汎用基底クラスやプラグイン基盤を導入していません。

1. 許可された実際のPScube HTMLを機密情報除去済みfixtureとして用意する。
2. 店舗・機種・台番号・営業日・game/bb/rb/medalの意味、欠損表記、文字コード、必要な通常セッション操作を確認する。
3. parserとnormalizeをfixtureと期待値で実装・検証し、jobを収集用に接続する。
4. REITOの実HTMLを確認し、同じ責務分離で追加する。

今回の対象外：SupabaseへのINSERT/UPDATE、DB変更、Materialized View更新、GitHub Actions、Playwright/Selenium、並列大量アクセス、みんレポ既存コードの移植、分析ロジック。
