# MECOS Knowledge Layer

**100% free. No API keys. No subscriptions. Runs on your machine.**

---

## What this does

Turns raw text from the internet (and your email) into a **connected knowledge graph**
that MECOS can reason over.

```
Wikipedia / DuckDuckGo
        |
        v
   free_search.py
        |
        v
relationship_extractor.py
        |
        +-- knowledge_core.py
        +-- vector_store.py
        |
        v
learning_pipeline.py
```

---

## Setup (one time)

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

The first semantic search downloads `all-MiniLM-L6-v2` once.

Install the scheduler:

```bash
pip install schedule
```

---

## Usage

```bash
python -m mecos.learning_pipeline learn "Bitcoin"
python -m mecos.learning_pipeline query "bitcoin"
python -m mecos.learning_pipeline semantic "How does the Fed affect crypto?"
python -m mecos.learning_pipeline path "federal reserve" "bitcoin"
python -m mecos.learning_pipeline related "bitcoin" --depth 2
python -m mecos.learning_pipeline stats
```

Email ingestion:

```bash
set MECOS_EMAIL=you@gmail.com
set MECOS_EMAIL_APP_PASSWORD=your-16-char-app-password
python -m mecos.learning_pipeline email
```

---

## Autonomous learning (200 built-in topics)

`auto_learn.py` already includes a built-in list of 200 topics across computing, science,
engineering, finance, social sciences, and practical skills. It runs even if you provide
no topics manually.

Run:

```bash
python mecos/auto_learn.py
```

Fast mode:

```bash
python mecos/auto_learn.py --fast
```

Custom interval (minutes):

```bash
python mecos/auto_learn.py --interval 5
```

Run it in the background:

```bash
# Linux/Mac - keeps running after you close terminal
nohup python auto_learn.py &

# Or with screen
screen -S mecos
python auto_learn.py
# Ctrl+A then D to detach
```

It will keep learning new topics, check email, and update the knowledge graph automatically.

---

## Runtime files

- `mecos_brain.gml`
- `mecos_chroma/`
