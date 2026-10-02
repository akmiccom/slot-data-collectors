# PScube取得検証

仮想環境を有効化し、リポジトリ直下で実行します。

```sh
python -m jobs.inspect_pscube "URL"
python -m jobs.inspect_pscube "URL" --save-html
python -m jobs.inspect_pscube --help
```

有効化しない場合はWindowsで`.\.venv\Scripts\python.exe`を`python`の代わりに使用できます。

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
