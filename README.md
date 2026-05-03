# phrasify

`phrasify` は、英語の長文 transcript から「実務でそのまま使える英語表現カード」を抽出する CLI ツールです。
主な読者・利用者は日本語ネイティブのビジネスパーソンです。特に VC、startup、finance、MBA interview、founder / operator conversation などの文脈で、単語ではなく「発話で再利用できる表現の塊」を集めることを目的にしています。

Phrasify is a Japanese-first CLI that turns English transcripts into reusable business expression cards. It is designed for learners who want to turn podcasts, interviews, and startup/VC content into JSONL or CSV learning assets.

DesignSpec は [`phrasify.design-spec.md`](phrasify.design-spec.md) です。旧 lab prototype の必要な機能は `src/phrasify/` 配下の正式モジュールに取り込み済みです。

30 秒で試す

```bash
git clone https://github.com/<your-org>/phrasify.git
cd phrasify
python3 -m venv .venv
.venv/bin/pip install -e .
phrasify extract examples/sample_transcript.md --dry-run
phrasify export examples/sample_output.jsonl --format csv
```

## セットアップ

読み込み・整形・CSV / JSONL export などの基本処理には必須の外部依存はありません。LLM 抽出を実行する場合だけ、使う provider の SDK を入れてください。

```bash
git clone https://github.com/<your-org>/phrasify.git
cd phrasify
python3 -m venv .venv
.venv/bin/pip install -e '.[anthropic]'
# or: .venv/bin/pip install -e '.[openai]'
```

未インストールのまま開発実行する場合は、`PYTHONPATH=src` を付けます。

`ANTHROPIC_API_KEY` または `OPENAI_API_KEY` は `.env` に置きます。

```bash
cp .env.example .env
```

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

`aggregate` は expression を小文字化し、空白と末尾の句読点を正規化して重複判定します。複数ファイルに同じ expression が出た場合は `frequency` と `source_ids` に集約され、最新の record が代表メタデータとして使われます。

## 主なオプション

| option                      | 説明                                       |
| --------------------------- | ------------------------------------------ |
| `--provider`              | `anthropic` / `openai` を選択          |
| `--model`                 | provider の model 名を明示                 |
| `--max-expressions`       | 抽出する最大 expression 数                 |
| `--chunk-max-chars`       | 1 chunk あたりの最大文字数                 |
| `--format`                | `jsonl` / `json` / `csv`             |
| `--notion-handoff`        | Notion MCP handoff JSON を生成             |
| `--notion-database-id`    | handoff payload に database ID を含める    |
| `--notion-data-source-id` | handoff payload に data source ID を含める |

## サンプル

```bash
PYTHONPATH=src python -m phrasify extract examples/sample_transcript.md --dry-run
PYTHONPATH=src python -m phrasify export examples/sample_output.jsonl --format csv
```

## Claude Code / Codex で skill として使う

Phrasify は CLI として直接使えるだけでなく、Claude Code や Codex などの coding agent から呼び出しやすいように `skills/phrasify/SKILL.md` を同梱しています。skill を登録すると、agent は Phrasify の安全な実行手順を読んだうえで、transcript の dry-run、LLM 抽出、CSV export、Notion handoff 生成を進められます。

### Codex ユーザー向け

Codex の user skill として使う場合:

```bash
mkdir -p ~/.codex/skills
cp -R skills/phrasify ~/.codex/skills/
```

その後、Codex のセッションで次のように依頼します。

```text
$phrasify を使って、この transcript から英語表現カードを抽出してください。
入力: /path/to/transcript.md
出力は JSONL と CSV の両方でお願いします。
```

Codex が repo 内で作業している場合は、Phrasify の repository root、または既に `phrasify` が入っている environment を見つけ、まず `phrasify extract ... --dry-run` で loader / chunking を確認してから、本抽出に進む想定です。

### Claude Code ユーザー向け

Claude Code の user skill として使う場合:

```bash
mkdir -p ~/.claude/skills
cp -R skills/phrasify ~/.claude/skills/
```

Claude Code では、以下のように明示的に skill 名を含めると意図が伝わりやすくなります。

```text
$phrasify を使って、/path/to/transcript.md から実務英語表現を抽出してください。
まず dry-run で入力を確認し、問題なければ JSONL を作って、最後に CSV に変換してください。
```

プロジェクトで共有したい場合は、リポジトリ内に `skills/phrasify/` を置いたままにして、README や agent 用の project instructions から参照させる運用が向いています。ユーザー個人の全プロジェクトで使いたい場合だけ、`~/.claude/skills` や `~/.codex/skills` にコピーしてください。

### Skill が agent に伝えること

- `.env` や API key を表示しない
- `extract` は transcript chunk を選択した LLM provider に送る
- `export` と `aggregate` はローカルファイルだけを処理する
- まず dry-run で loader / chunking を確認する
- `outputs/` の生成物は原則 git commit しない
- Notion ID は user が明示した場合だけ使い、コードや docs に固定値を書かない

### よく使う依頼例

```text
$phrasify でこの Markdown から表現カードを抽出して、CSV も作ってください。
```

```text
$phrasify で outputs/example.jsonl を Notion handoff JSON に変換してください。
Notion target ID はまだ入れないでください。
```

```text
$phrasify の抽出結果を確認して、expression_in_source が false のカードを優先レビュー候補としてまとめてください。
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

### 出力 schema 例

```json
{
  "seq": 1,
  "expression": "double down on",
  "original_sentence": "We should double down on founder-led sales.",
  "jp_translation": "創業者主導の営業にさらに注力すべきです。",
  "nuance": "確信を持って追加投資・集中するニュアンス。",
  "usage": "戦略、投資判断、営業・市場選択の文脈で使う。",
  "pattern": "double down on + noun",
  "reusable_examples": [
    "We should double down on enterprise customers before expanding internationally."
  ],
  "tags": ["collocation", "strategy"],
  "source": {
    "file": "examples/sample_transcript.md",
    "chunk_id": "sample_transcript-001"
  },
  "review_status": "New",
  "expression_in_source": true,
  "original_sentence_in_source": true
}
```

### 品質指標

- `expression_in_source`: `expression` が transcript chunk 内に文字列として存在するか
- `original_sentence_in_source`: `original_sentence` が transcript chunk 内に存在するか

LLM は学習しやすい形に正規化することがあるため、`expression_in_source` は false になる場合があります。原文 grounding を重視する場合は、この値を review queue の優先度付けに使います。

## Privacy

`extract` を実行すると、入力 transcript の本文が指定した LLM provider（Anthropic または OpenAI）に送信されます。API key はローカルの environment variable から読み、Phrasify は key を出力ファイルに保存しません。

生成物はデフォルトで `outputs/` に保存されます。`outputs/` は `.gitignore` されているため、`.gitkeep` 以外の生成物は git 管理外です。

Notion 連携は直接書き込みではなく、MCP handoff 用 JSON を生成するだけです。Notion target metadata を入れたい場合は `--notion-database-id` / `--notion-data-source-id`、または `PHRASIFY_NOTION_DATABASE_ID` / `PHRASIFY_NOTION_DATA_SOURCE_ID` を使います。

## FAQ

### Anki に入れられますか？

現時点では CSV export を使って取り込めます。将来的には `--format anki-csv` を追加する想定です。

### transcript はどこに送られますか？

`extract` では、選択した LLM provider に transcript chunk を送ります。`export` と `aggregate` はローカルファイルだけを処理します。

### 日本語以外の学習者にも使えますか？

技術的には使えますが、現状の prompt と README は日本語ネイティブ向けに最適化しています。

## ディレクトリ構成

- `src/phrasify/`: 本体コード
- `src/phrasify/prompts/extract.md`: 抽出プロンプト
- `tests/`: 標準ライブラリ `unittest` によるテスト
- `outputs/`: ローカル生成物（JSONL / CSV / Notion handoff）。`.gitkeep` 以外は git 管理外

## 開発

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

LLM API を叩かない処理は stdlib `unittest` で検証します。provider SDK は必要なものだけ optional dependency として入れます。
