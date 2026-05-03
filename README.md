# phrasify

`phrasify` は、英語の長文 transcript から「実務でそのまま使える英語表現カード」を抽出する CLI ツールです。

主な読者・利用者は日本語ネイティブのビジネスパーソンです。特に VC、startup、finance、MBA interview、founder / operator conversation などの文脈で、単語ではなく「発話で再利用できる表現の塊」を集めることを目的にしています。

DesignSpec は [`phrasify.design-spec.md`](phrasify.design-spec.md) です。旧 lab prototype の必要な機能は `src/phrasify/` 配下の正式モジュールに取り込み済みです。

## セットアップ

読み込み・整形・CSV / JSONL export などの基本処理には必須の外部依存はありません。LLM 抽出を実行する場合だけ、使う provider の SDK を入れてください。

```bash
cd /Users/toshiakiyabe/exp/tools/phrasify
python3 -m venv .venv
.venv/bin/pip install -e '.[anthropic]'
# or: .venv/bin/pip install -e '.[openai]'
```

未インストールのまま開発実行する場合は、`PYTHONPATH=src` を付けます。

`ANTHROPIC_API_KEY` または `OPENAI_API_KEY` は以下のいずれかに置きます。

- `/Users/toshiakiyabe/exp/tools/phrasify/.env`
- `/Users/toshiakiyabe/exp/tools/.env`
- `/Users/toshiakiyabe/exp/.env.local`
- `/Users/toshiakiyabe/exp/lab/.env`（移行期間中の互換 fallback）

## 使い方

loader / chunker だけ確認する dry-run:

```bash
PYTHONPATH=src python -m phrasify extract /path/to/transcript.md --dry-run
```

英語表現カードを JSONL で抽出:

```bash
PYTHONPATH=src python -m phrasify extract /path/to/transcript.md \
  --provider anthropic \
  --max-expressions 30
```

Notion MCP handoff 用 JSON も同時に作る:

```bash
PYTHONPATH=src python -m phrasify extract /path/to/transcript.md --notion-handoff
```

既存の JSONL 出力を CSV に変換:

```bash
PYTHONPATH=src python -m phrasify export outputs/example_20260503.jsonl --format csv
```

複数 JSONL を横断集約し、正規化した expression で dedup:

```bash
PYTHONPATH=src python -m phrasify aggregate
```

## 入力形式

- `.md`
- `.txt`
- `.srt`
- `.vtt`

## 出力

デフォルトでは以下の JSONL を作ります。

- `outputs/<transcript>_<YYYYMMDD>.jsonl`

必要に応じて CSV や Notion handoff JSON も生成できます。

## ディレクトリ構成

- `src/phrasify/`: 本体コード
- `src/phrasify/prompts/extract.md`: 抽出プロンプト
- `tests/`: 標準ライブラリ `unittest` によるテスト
- `outputs/`: ローカル生成物（JSONL / CSV / Notion handoff）。`.gitkeep` 以外は git 管理外
