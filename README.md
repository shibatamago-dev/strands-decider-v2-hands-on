# Strands Decider v2 E2B ハンズオン

AWS Strandsチームの判断専用モデル **Strands Decider v2 E2B** を、Gemini Decision 1 のハンズオンで使ったのと同じ54問で動かした検証の、再現コードと結果です。

検証記事: [Strands Decider v2をColab無料T4で試した：答えを出さず確率だけ返す判断モデル](https://zenn.dev/shibatamago_dev/articles/strands-decider-v2-hands-on)（Zenn、2026-11-29 14:30以降に公開予定）
元の54問: [gemini-decision-1-hands-on](https://github.com/shibatamago-dev/gemini-decision-1-hands-on)（54問中53問正解だった Gemini Decision 1 の再現リポジトリ）
比較対象: [nexus-decision-4b-hands-on](https://github.com/shibatamago-dev/nexus-decision-4b-hands-on)（ボスが同じ54問で検証した判断モデル、47/54）

## 結果

- **43/54 正解（79.6%）**。nexus-decision-4b は 47/54、Gemini Decision 1 は 53/54 でした。
- カバレッジ（誤差5%以下で自動判断できる割合）は **28/54（51.9%）**。nexus は 43/54（79.6%）。
- テキスト（設計書）8/8、画像 35/46。
- 詳しい内訳と実行条件は [RESULTS.md](RESULTS.md) にあります。

## どう動かしたか

- Google Colab 無料 T4 で `strands-decider serve` を常駐させ、`/v1/systemone` に54問を投げました。`ask` は1問ごとにモデルを再ロードするため、繰り返し使うなら `serve` が前提です。
- モデルは `StrandsAgents/strands-decider-E2B-gemma4-v2-2611`（Gemma 4 E2B ベースのマージ済みフルモデル、bf16 10.3GB、Apache-2.0）。
- 公式の設計書には「Gemma 4 のモデルは vision encoder を落としておりテキストのみ」とありますが、実際に動かしたサーバーの `/health` は `"images": true` を返し、画像つきの質問にも答えられました（プローブ 4/4 正解）。この挙動の違いは RESULTS.md に記録してあります。
- v1 E2B は同じ Colab 環境で LoRA の読み込みに失敗したため（torchao 0.10.0 に対して 0.16.0 以上を要求）、v1 の実測はありません。公式ベンチマークの比較だけ RESULTS.md に載せています。

## 使い方

前提: [gemini-decision-1-hands-on](https://github.com/shibatamago-dev/gemini-decision-1-hands-on) を隣のフォルダに置いてください（54問の定義・正解・画像・設計書はそちらから読みます）。

```bash
# 1. Colab（T4 GPU）でインストール
pip install -q "strands-decider[cuda]"
# 2. サーバ起動（バックグラウンド）
strands-decider serve StrandsAgents/strands-decider-E2B-gemma4-v2-2611 --port 8000
# 3. 別セル／ターミナルで実行
python3 run_strands_54.py --probe-only  # 疎通確認: 画像1件・4問
python3 run_strands_54.py              # 全54問（結果は strands_54_results.json に保存）
python3 run_strands_54.py --text-only  # design_doc（テキスト8問）だけ実行
```

T4 が取れないときは中止してください。CPU ランタイムでは 10.3GB のモデルが載らず OOM になります（12.67GB RAM で確認）。

## ファイル

| ファイル | 内容 |
| --- | --- |
| `run_strands_54.py` | 54問の実行スクリプト（元の `standalone_run.py` を import して質問・正解・判定を共有） |
| `RESULTS.md` | 検証結果ドキュメント |
| `LICENSE` | MIT License |

## 注意

- 54問のうち画像46問は、Strands v2 も nexus も判断学習がテキストのみで、画像はどちらの専門外でもあります。結果はテキスト／画像の内訳つきで読んでください。
- 54問では1問の重みが約1.9ポイントあり統計的に粗いため、この差をモデルの優劣として断定はできません。
- 実行結果の生 JSON（`strands_54_results.json`）は、Colab ランタイムのリサイクルで失われました。RESULTS.md の数値は、保存済みノートブックのセル出力から転記したものです。復旧には54問の再実行が必要です。
- 日本語の問題は試していません。学習データの約96%が英語のため、日本語では別途測る必要があります。
