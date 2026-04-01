import json
import base64
import tempfile
import os
from pipeline import run_pipeline, run_pipeline_from_pdf

VALID_VOICES = {'Matthew', 'Joanna', 'Ruth', 'Stephen'}
MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 50_000


def handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))

        style = body.get("style", "concepts")
        length = body.get("length", "short")
        voice = body.get("voice", "Matthew")
        pdf_b64 = body.get("pdf")
        notes = body.get("notes")

        if voice not in VALID_VOICES:
            return _response(400, {"error": f"Invalid voice. Choose from: {sorted(VALID_VOICES)}"})

        if pdf_b64:
            try:
                pdf_bytes = base64.b64decode(pdf_b64)
            except Exception:
                return _response(400, {"error": "Invalid base64 PDF data."})
            if len(pdf_bytes) > MAX_PDF_BYTES:
                return _response(400, {"error": "PDF must be under 5MB."})
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_bytes)
                tmp_path = tmp.name
            try:
                url = run_pipeline_from_pdf(tmp_path, style, length, voice, max_chars=MAX_TEXT_CHARS)
            finally:
                os.remove(tmp_path)
        elif notes:
            if len(notes) > MAX_TEXT_CHARS:
                return _response(400, {"error": f"Notes must be under {MAX_TEXT_CHARS} characters."})
            url = run_pipeline(notes, style, length, voice)
        else:
            return _response(400, {"error": "Provide either 'pdf' (base64) or 'notes' (text)."})

        return _response(200, {"url": url})

    except ValueError as e:
        return _response(400, {"error": str(e)})
    except Exception as e:
        print(f"Internal error: {e}")
        return _response(500, {"error": "An error occurred. Please try again."})


def _response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
