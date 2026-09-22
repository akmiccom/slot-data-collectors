# slot-data-collectors

パチスロ台データを複数のWebデータソースから取得・解析・標準化するPython基盤です。

現在は初期構築段階で、PScubeのHTTP取得と共通モデルを実装しています。

PScubeの機種一覧JSON取得・解析を実装しています。個別台HTMLの解析・SlotResultへの標準化とREITOの収集処理は未実装で、呼び出すと明示的に例外になります。

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
tests/
  __init__.py
  conftest.py              # テスト中の実HTTP通信を禁止
  test_models.py
  test_collectors.py
  test_inspection.py
  test_machines.py
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
- jobは設定読み込みと実行を担当します。`collect_pscube`はネットワークアクセスせず、未実装をログに記録して終了コード1で終了します。不正な設定は終了コード2です。取得検証には別の`inspect_pscube`を使用します。

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

## PScube取得検証

仮想環境を有効化し、リポジトリ直下で実行します。

```sh
python -m jobs.inspect_pscube "URL"
python -m jobs.inspect_pscube "URL" --save-html
python -m jobs.inspect_pscube --help
```

有効化しない場合はWindowsで`.\.venv\Scripts\python.exe`、検証用環境なら
`.\.venv-check\Scripts\python.exe`を`python`の代わりに使用できます。

このコマンドはPScubeのアクセス挙動を調査する検証ツールであり、アクセス制御回避や認証突破を目的としません。
`requests.Session`で指定URLへ通常のGETを行い、HTTPリダイレクトだけを追従します。
承認ボタン操作、form送信、meta refreshの追従、JavaScript実行、ブラウザ自動化は行いません。
環境変数のtimeout・通信間隔を使用し、検証CLIのリトライは0回です。
HTTPリダイレクト中の各通信はrequestsの通常動作に従い、`REQUEST_INTERVAL`は`fetch`呼び出し間の間隔です。

標準出力のJSONにrequested/final URL、HTTP status、Content-Type、本文サイズ（受信・展開後のバイト数）、
リダイレクトの有無、セッションおよびリダイレクト応答で確認したCookie名一覧、HTML診断を表示します。
安全のためURLはoriginのみを残し、パス・query・fragment・ユーザー情報を`[redacted]`に置き換えます。
同一host内の遷移先パスはこの出力からは特定できませんが、リダイレクトの有無は履歴から判定します。
ヘッダーはSet-Cookieを除外し、Content-Typeのメディア型以外の値は伏せて名前のみ確認できます。
Cookie値は通常のセッション内だけで扱い、FetchResult・ログ・レポートへコピーしません。
HTML本文は`FetchResult.html`で利用でき、オブジェクトのreprには含めません。

診断はtitle、meta refresh、form数、リンク数（href付きaタグ）、script数、iframe数、submit数、
password input、checkbox、承認/同意/確認/利用規約/agreement/consentの有無を抽出します。
submit数にはinputのsubmit/imageとtype省略またはsubmitのbuttonを含みます。
キーワードはscript/styleを除くテキストの部分一致で、承認画面を確定するものではありません。
通常ページにも「確認」などがあれば検出されます。

INFOログは標準エラーへ出力し、requested/final host・status・サイズを記録します。
HTTP 4xx/5xxでも診断・任意保存を行い終了コード1、400未満は0、設定・通信・保存失敗は1です。
既存の`PscubeClient.fetch()`は従来通りHTTPエラーを例外にし、検証用の`fetch_result()`だけがエラー応答も返します。

`--save-html`指定時だけ、リポジトリ直下の`debug/pscube/`へUTC timestampとhost名のファイル名で保存します。
例：`20260922_001500_123456_pscube_jp.html`。同時刻のファイルが既にある場合は連番を付け、上書きしません。保存はデコード後のHTMLをUTF-8で行います。
`debug/`はGit管理対象外です。HTML自体にはhidden inputやtoken等が含まれる可能性があり、
自動で完全に機密情報を除去するものではありません。ローカル調査用として扱い、共有やfixture化する前に内容を確認・除去してください。
titleも本文由来なので、JSONレポートを共有する前に確認してください。

実URLで次に確認する項目：HTTP statusと最終host、リダイレクト有無、Cookie名、
title・承認語句・meta refresh・formの有無、保存HTMLの文字化けやデータ表示の有無。
承認画面が出た場合はそこで観察に留め、このツールで操作しません。

## PScube機種一覧XHR取得

ユーザーが実通信で確認した仕様：GET `nc-m03-001.php`、Content-Typeは
`application/json`。パラメータは`cd_ps=2`、`bai=0`、`YMD_biz=`、`page=1`、`loaded=`。
トップレベルに`YMD_biz / PS / Ki / count / page / pageMax`があり、
`Ki`が機種一覧、各機種の`list.cd_dai`が先頭ゼロ付き台番号一覧です。

```powershell
python -m jobs.inspect_pscube_machines "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v03-001.php?cd_ps=2"
python -m jobs.inspect_pscube_machines "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v03-001.php?cd_ps=2" --save-json
python -m jobs.inspect_pscube_machines --help
```

有効化していない場合は`python`を`.\.venv-check\Scripts\python.exe`等に置き換えてください。
通常ページをGETしてから、同じSessionでXHRをpage=1からpageMaxまで逐次取得します。
各呼び出し間は`REQUEST_INTERVAL`、timeoutは`REQUEST_TIMEOUT`を使用します。
手動Cookie注入や認証回避は行いません。HTTPエラー、JSONでない応答、必須フィールド不正で停止します。
出力はhost、営業日、サーバーのcount/pageMax、取得機種件数、各機種名・台数・台番号件数です。
countの意味と実際の機種件数が一致するかは未検証のため、独立した値として表示します。

`client.fetch_json()`はJSON decodeまで行い`JsonFetchResult`を返します。
`parser.parse_machine_page()`は通信せず`PscubeMachinePage`へ変換し、
`collector.collect_machines()`は`list[PscubeMachine]`を返します。
CLIは同じ`iter_machine_pages()`を使いページ情報も表示します。
`collectors/pscube/models.py`の対応：

| 元JSON | Python |
| --- | --- |
| YMD_biz | business_date |
| nmk_kisyu | machine_name |
| cd_ps | cd_ps |
| bai | rate |
| ct_dai | unit_count |
| list.cd_kisyu | machine_code |
| list.cd_dai | unit_numbers（文字列のまま保持） |
| mph | machine_path（取得しません） |

実装上の受け入れ規則（実レスポンス全パターンの確認済み仕様ではありません）：
日付はYYYYMMDD / YYYY-MM-DD / YYYY/MM/DDを許容し、空はNone。
機種名とlist.cd_dai、トップレベルのKi/count/page/pageMaxは必須です。
その他のモデル項目は欠損をNoneとし、未知フィールド（PS/fg_new/mcd_kisyu/nm_ka/DIVA等）は変換しません。
数値項目は数値文字列も許容しますが、台番号を数値から補完することはしません。
空一覧はcount=0、page=1、pageMax=0または1を許容します。
要求と異なるpageや、途中で変わる営業日/count/pageMaxはエラーとします。

`--save-json`は各取得ページを`debug/pscube/`へUTC時刻・ランダム識別子・host・ページ番号で保存します。
ヘッダーやCookieは保存しません。JSON本文は未加工のため、共有前に内容を確認してください。
失敗時に、それまで成功したページの保存ファイルが残る場合があります。
テスト用JSONは確認された構造を模した架空データです。実サイトにはテストからアクセスしません。
個別台データ取得・mph先・DBマッピングは未実装です。

## データソース追加と今後

同じシステムを使う店舗は同じcollectorを共有し、店舗ごとのURLやIDは呼び出し側の設定として扱います。
PScube、REITO、その他のソースは`collectors/<source>/`でHTTP・解析・収集を分離し、共通の`SlotResult`へ変換します。
現時点では汎用基底クラスやプラグイン基盤を導入していません。

1. 許可された実際のPScube HTMLを機密情報除去済みfixtureとして用意する。
2. 店舗・機種・台番号・営業日・game/bb/rb/medalの意味、欠損表記、文字コード、必要な通常セッション操作を確認する。
3. parserとnormalizeをfixtureと期待値で実装・検証し、jobを収集用に接続する。
4. REITOの実HTMLを確認し、同じ責務分離で追加する。

今回の対象外：SupabaseへのINSERT/UPDATE、DB変更、Materialized View更新、GitHub Actions、Playwright/Selenium、並列大量アクセス、みんレポ既存コードの移植、分析ロジック。
