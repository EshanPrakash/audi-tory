# audi-tory

Notes-to-audio web app built on React and AWS. PDF or plain text in, MP3 out in ~20–30 seconds.

**Live App**: https://audi-tory.vercel.app

## Table of Contents
- [Usage](#usage)
- [Quick Start (Local)](#quick-start-local)
- [App Overview](#app-overview)
- [Backend Pipeline](#backend-pipeline)

---

## Usage

Visit **https://audi-tory.vercel.app** and:

1. Upload a PDF or paste your notes as plain text
2. Choose a **style**, **length**, and **voice**
3. Hit **Generate Audio** — takes ~20–30 seconds
4. Play or save the MP3

### Styles

| Style | What it does |
|-------|--------------|
| `Core Concepts` | Identifies the key concepts in your notes and explains each one in depth |
| `Podcast` | Rewrites your notes as a natural, conversational audio script |
| `Readback` | Reads your notes back clearly and faithfully, no expansion |

### Lengths

| Length | Target | Best for |
|--------|--------|----------|
| `Short` | ~200 words | Quick review, sparse notes |
| `Medium` | ~800 words | Standard study session |
| `Long` | ~1800 words | Deep dive, dense notes |

### Voices

| Voice | |
|-------|-|
| Matthew | Masculine |
| Stephen | Masculine |
| Joanna | Feminine |
| Ruth | Feminine |

---

## Quick Start (Local)

To run this locally:

### Backend

```bash
git clone https://github.com/EshanPrakash/audi-tory.git
cd audi-tory/backend
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
AWS_REGION=us-east-1
S3_BUCKET=your-s3-bucket
BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
LOCAL_OUTPUT_PATH=/path/to/output.mp3
```

Run the pipeline locally with sample notes:

```bash
python test_pipeline.py
python test_pipeline.py --notes black_holes --style podcast --length medium
python test_pipeline.py --pdf /path/to/notes.pdf --style concepts --length short
python test_pipeline.py --voice Joanna
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env`:

```
VITE_API_URL=https://your-api-gateway-url/prod/process
```

Visit http://localhost:5173.

To deploy the backend (Lambda + API Gateway):

```bash
cd backend
./deploy.sh
```

---

## App Overview

### What You Can Do

audi-tory takes your notes and turns them into a generated audio file:

- **PDF or plain text**: upload a PDF or paste notes directly — both go through the same pipeline
- **Three output styles**: Core Concepts breaks your notes into explained topics, Podcast rewrites them conversationally, Readback reads them faithfully as-is
- **Three lengths**: Short (~200 words) for quick review, Medium (~800 words) for standard study, Long (~1800 words) for deep coverage
- **Four neural voices**: Matthew and Stephen (masculine), Joanna and Ruth (feminine)

### Performance

- **Processing time**: ~20–30 seconds end to end (Bedrock + Polly async)
- **Audio expiry**: presigned S3 URL valid for 1 hour after generation
- **Input limits**: 5MB max for PDFs, 50,000 characters max for plain text
- **Concurrency**: serverless — scales automatically with demand

### Features

- Fully serverless — no backend server to maintain
- Rate limiting: 2 req/sec, burst of 5
- Auto-deletes generated audio from S3 after 24 hours

---


## Backend Pipeline

The core pipeline lives in `backend/pipeline.py` and runs as four steps:

1. **`extract_text_from_pdf`** — extracts raw text from an uploaded PDF using pypdf
2. **`generate_script`** — sends the text to Claude Haiku via Bedrock with a style/length prompt, returns a clean spoken-word script
3. **`synthesize_audio`** — submits the script to Polly as an async neural TTS task, polls until complete, stores MP3 in S3
4. **`get_download_url`** — generates a presigned S3 URL valid for 1 hour

Plain text input skips step 1 and goes directly to step 2.

---

## License

MIT License - see LICENSE file.
