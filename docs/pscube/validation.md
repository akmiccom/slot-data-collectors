# PScube検証記録

## 2026-10-02: 縦軸ラベル限定認識の通信なし検証

現行の自動選択は全7ラベルを必須にします。以下の過去記録にある「A/Dは自動選択不能」「ラベルなしのB/C/E自動選択」は旧仕様です。元画像・既存CSVは変更せず、Webアクセスと外部差枚による選択は行っていません。

| Profile | 台・営業日 | 自動選択 | estimated_medal |
| --- | --- | --- | ---: |
| A | 0272 / 2026-09-21 | 原画像なし、実画像検証未実施 | — |
| B | 0101 / 2026-10-01 | B / high | -1278 |
| C | 0100 / 2026-10-01 | C / high | 135 |
| D | 0125 / 2026-10-01 | D / high | 1861 |
| E | 0105 / 2026-10-01 | E / high | -1610 |

B/C/D/Eの保存原画像で全7ラベルを認識しました。Dは2500/2000/1500/1000/500/0/-500からAと区別しました。この4画像はテンプレート作成にも使用したため適合確認です。追加で作成に未使用のB・0272 / 2026-10-01を再解析し、全ラベル認識・B・+1393枚を維持しました。独立画像による大規模精度検証ではありません。

Pillow生成ラベル付きグラフではA〜Eを選択し、A/Dを区別します。Aの実字体は未検証です。既存A・+3256枚の明示profile回帰を維持します。一部ラベル欠損、ノイズ、読み取り不能、同点の数値候補競合、非等間隔、単一Aラベル混入、0強調線矛盾、数学的に整合した未知軸ではlow/Noneを検証します。従来の幾何回帰は明示profileで保持します。

## 0272 / 2026-09-21

ユーザー確認済み実画像: 800×730、plot=(79,20,780,676)、grid=[20,129,238,348,457,567,676]、Profile A（+5000〜-1000、1000刻み）、ピンク系線。
zero_y=567、step_px=109.3333、終点=(779,211)、推定+3256枚。みんレポ+3250、アナスロ+3245。

今回、当日の元画像はローカルに見つからなかったため、確認済み幾何とピンク線をPillowで再現し、自動選択による+3256枚の回帰テストを追加しました。元画像の再解析とは区別します。

## 0272 / 2026-10-01

yasudaya.pscube.jp / a744207、ネオアイムジャグラーEX。ユーザーがProfile B（+1500〜-1500、500刻み）、紫〜青紫系線を確認。旧固定profileでは0ラインと強調線が矛盾し、差枚Noneとなりました。

今回、保存済みの原画像を通信せず再解析: 800×730、plot=(79,20,780,676)、grid=[20,129,238,348,457,567,676]、Profile Bを自動選択、zero_y=348、step_px=109.3333、終点=(779,43.5)、推定+1393枚、confidence=high。
目視の約+1400枚と整合しますが、目視値は正解値やテスト期待値として使用していません。今回ユーザーから比較値として、みんレポ+1390枚、アナスロ+1386枚が提示されました。

BIG25/REG26、分母252.4/242.7/123.8からestimated_game=6311、candidates=[]。最大出玉1769は差枚ではありません。

## テストと今後の評価

外部画像はGitへ追加しません。Pillow生成でA/ピンク、B/紫・青、正負差枚、異なるサイズ、ノイズ、欠損、複数線、軸選択不能、明示profileを検証します。
highはスケール前提付きの幾何検出評価です。未確認レンジを常に識別できるという意味ではありません。

多数の同一台・同一日比較でMAE、誤差中央値、最大誤差、±25/50/100/200枚以内率を評価する作業は未実施です。

## 提示済み2件の比較

| 日付・台 | PScube | みんレポ | アナスロ | 絶対誤差（みんレポ/アナスロ） |
| --- | ---: | ---: | ---: | --- |
| 2026-09-21 / 0272 | 3256 | 3250 | 3245 | 6 / 11 |
| 2026-10-01 / 0272 | 1393 | 1390 | 1386 | 3 / 7 |

ユーザー提示値との比較で、みんレポ基準MAE=4.5枚、アナスロ基準MAE=9.0枚です。2件だけで精度保証はできません。比較サイトの自動取得は行いません。

## Profile C / 0100 / 2026-10-01

別店舗の実画像についてユーザーが上3000・下0・500刻み、グリッド7本、最下段index=6が0ラインであることを確認しました。紫系の折れ線です。ユーザー提示の終点概算x=779/y=646と約+137枚は目視・幾何の参考値で、正解差枚として使用していません。

保存済み原画像`debug/pscube/validation/e624dc5f6e6b/images/20261001_0100.png`を通信せず再解析しました。

- 画像: 800×730、plot=(74,20,780,676)
- grid Y: [20,129,238,348,457,567,676]
- Profile Cを自動選択、zero_y=676、step_px=109.3333
- 折れ線終点: (779,646.5)、estimated_medal=+135枚、confidence=high

Pillowで生成した紫系線・最下段強調のfixtureでもCの選択を確認しました。期待差枚は生成した終点・グリッド間隔から算出し、実例の約+137枚を固定していません。台番号・日付を変えても同じ選択になります。強調なし・複数強調・候補外の0位置はlow/None、明示profileと矛盾する強調線もNoneを維持します。A/Bの既存回帰テストも維持しています。

ローカルCSVのminrepo_medal/anaslo_medalは空欄です。外部値との比較は未完了で、この例をMAE等の集計へ追加していません。元CSVは変更していません。highはprofile前提付きの幾何評価で、差枚精度を保証しません。

## 複数台検証CLI

### Profile D/E追加後の注意

AとDはグリッド本数と0位置が一致するため、自動選択ではlow/Noneになります。複数台CLIも同じ自動選択を使用するため、この画像はgraph_low_confidenceになります。軸を確認した単画像CLIで3つの軸値を明示すれば再解析できます。成功済みCSVを自動で書き換える処理は追加していません。

```powershell
python -m jobs.validate_pscube_units `
  --hall-url "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v03-001.php?cd_ps=2" `
  --machine-name "ネオアイムジャグラーＥＸ" `
  --date 20261001 --units 0272,0273,0274 `
  --output "debug/pscube/validation/20261001_neoiam.csv" --annotate
```

`--units`（カンマ区切り）・`--limit`（正の整数、m03順の先頭N台）・`--all-units`のいずれか1つが必須です。未指定はusage errorとなり、デフォルト全台取得はありません。台番号はm03の対象機種に所属する文字列だけを受理し、先頭ゼロを保持します。機種名は完全一致で1件だけを選びます。16台の番号をコードへ固定しません。

通常ページ→m03の全ページ→機種選択→各台の通常ページ/m06→指定日のGraph→既存estimate_graph→CSVの順です。1つのSession、REQUEST_TIMEOUT/REQUEST_INTERVAL、リトライ0で逐次実行し、並列取得は禁止です。グラフの再取得にm06を重複実行しません。

`--output`の親ディレクトリを作成します。未指定時は`debug/pscube/validation/<店舗host・path・機種名のハッシュ>/YYYYMMDD_validation.csv`です。画像は同じハッシュ配下の`images/YYYYMMDD_台番号.png`、`--annotate`時だけ`annotated/`へ保存します。店舗間の衝突を避けるためハッシュで分離しています。debugはGit対象外です。

CSVはUTF-8 BOM付きです。各台処理後、同じディレクトリの一時ファイルから置換して保存します。既存CSVのstatus=successはスキップし、`--force`時だけ再取得します。未成功行は再試行し、手入力のminrepo_medal/anaslo_medalを保持し、再処理行の計算済み誤差は空へ戻します。同じCSVへ異なる店舗・日付・機種を混在させません。重複台・不正な列構造はエラーになります。

1台の通常失敗は記録して次台へ続けます。403/429では失敗行を保存し、その後の取得を停止します。m03で失敗した場合は全体を停止します。終了コードは全対象成功0、台単位の未成功または403/429停止2、設定・m03・CSV保存失敗1です。stdoutのJSONはprocessed/skipped/success/failure/not_processed/stopped/outputを表示します。

### CSV列

- 識別: hall_host、hall_path（店舗区別用の追加列）、business_date、machine_name、unit_no
- 個別台: bb、rb、bb_probability、rb_probability、combined_probability、estimated_game、estimated_game_candidates、game_estimation_spread、max_payout
- グラフ: estimated_medal、graph_confidence、graph_profile_top、graph_profile_bottom、graph_profile_step、graph_warnings
- 状態: status、error_type
- 手入力: minrepo_medal、anaslo_medal
- 再計算: error_vs_minrepo、error_vs_anaslo、absolute_error_vs_minrepo、absolute_error_vs_anaslo

欠損は空欄、candidates/warningsはJSON配列文字列です。statusはsuccess、no_daily_data、no_graph、graph_low_confidence、unit_fetch_failed、graph_fetch_failed、parse_failed、graph_processing_failedです。例外本文・Cookie・キー・Graph URLはCSVやログへ出力しません。台番号をExcelへ取り込む場合、unit_no列を文字列として指定してください。Excelの自動数値変換はCSVの先頭ゼロを落とす場合があります。

### 手入力比較と再集計

minrepo_medal/anaslo_medalへ同一店舗・同一台・同一日の整数差枚を入力して保存します。欠損は空欄のままにします。Excel保存時も列名・unit_noの文字列を維持してください。

```powershell
python -m jobs.evaluate_pscube_validation "debug/pscube/validation/20261001_neoiam.csv"
```

同じCSVを更新し、`estimated_medal - 比較値`とその絶対値を計算します。推定値または比較値が欠損の組は除外し、不正数値ではCSVを変更せず失敗します。
みんレポ・アナスロ別にsample_count、mean_error、MAE、median_absolute_error、max_absolute_error、within_10/25/50/100/200_countとrateをJSONで表示します。rateは0〜100の百分率、標本0件では指標とrateはnullです。

まず3台で検証してから10台へ広げます。normalize、保存DB、本番collector、OCR・推定ロジック変更は今回の対象外です。

## 2026-10-02の実サイト3台検証

対象日は2026-10-01。通常Sessionと既定の逐次通信でm03から対象機種16台を確認し、指定した0272/0273/0274だけを取得しました。success=3、failure=0、403/429なし。3台ともProfile B、confidence=highです。

| 台番号 | estimated_game | estimated_medal |
| --- | ---: | ---: |
| 0272 | 6311 | 1393 |
| 0273 | 3552 | 87 |
| 0274 | 2993 | -373 |

CSVはローカルの`debug/pscube/validation/20261001_neoiam.csv`へ保存し、3枚の原画像と注釈画像も保存しました。0272には提示済み比較値1390/1386を入力してevaluateを実行し、誤差+3/+7を確認しました。0273/0274の比較値は未入力です。これらの推定結果だけでは枚数精度を保証しません。

10台検証へ進める状態です。同じCSVへ`--limit 10`を指定すれば成功済み3台をスキップし、残りだけを逐次取得します。

## Profile D/EとBの実画像再解析

ユーザーがD（2500,2000,1500,1000,500,0,-500）、E（1000,500,0,-500,-1000,-1500,-2000）の軸を確認しました。いずれも500刻み・7本です。Dの0位置は5、Eは2。101は既存B（1500〜-1500、500刻み、0位置3）の回帰確認例です。

2026-10-01の保存済み原画像`debug/pscube/validation/e624dc5f6e6b/images/`を通信せず再解析しました。台番号は元データの先頭ゼロ付き文字列のまま保持しています。

| 台 | profile・選択 | 推定差枚 | みんレポ参考値 | アナスロ参考値 | 誤差（みんレポ/アナスロ） |
| --- | --- | ---: | ---: | ---: | --- |
| 0125 | D・明示指定 | 1861 | 1860 | 1855 | +1 / +6 |
| 0105 | E・自動 | -1610 | -1610 | -1610 | 0 / 0 |
| 0101 | B・自動 | -1278 | -1270 | -1268 | -8 / -10 |

3件ともconfidence=high。終点Yは順に160、590、627.5です。DはAと0位置が共通なので自動ではlow/None、確認済み軸を指定して計算しました。ユーザーの約+1850/-1600/-1270や外部参考値は、profile選択・終点補正・テスト期待値の根拠には使用していません。

下枠と破線0ラインを区別したBの実画像回帰を確認し、Cの0100も自動選択で+135枚を維持しました。Aは明示指定による+3256枚のPillow回帰を維持します。外部値はユーザー提示値で、自動取得していません。元画像・CSVは変更せず、Gitへ追加していません。少数例の一致から精度を保証しません。
