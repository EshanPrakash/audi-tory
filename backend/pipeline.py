from dotenv import load_dotenv
import os
import json
import time
import boto3

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
polly = boto3.client("polly", region_name=AWS_REGION)

STYLE_INSTRUCTIONS = {
    "podcast": (
        "Transform these notes into a natural, conversational podcast script. "
        "Write as if one person is casually explaining the topic to a friend. "
        "Expand on ideas, add flow between points, and make it engaging."
    ),
    "readback": (
        "Read back these notes clearly and faithfully. "
        "Do not add extra commentary or expand beyond what is written. "
        "Preserve the original meaning and order of the notes."
    ),
    "concepts": (
        "Identify the core concepts in these notes and explain each one in depth. "
        "Start with 'These notes cover the following core concepts:' and then go through each concept by name, "
        "followed by a thorough explanation of what it is, how it works, and why it matters. "
        "Do not cover anything outside of the core concepts, but for each concept go as deep as needed."
    ),
}

LENGTH_INSTRUCTIONS = {
    "short": "Write approximately 200 words. Cover only the most essential points.",
    "medium": (
        "Write approximately 800 words. "
        "Do not just restate the notes — actively expand on them. "
        "Add context, real-world examples, and analogies to reach the word count."
    ),
    "long": (
        "Write approximately 1800 words. "
        "Go deep. Elaborate extensively on every point, add examples, counterpoints, historical context, and analogies. "
        "Use the notes as a starting point, not a ceiling — the output should be significantly longer than the input."
    ),
}

CONCEPTS_LENGTH_INSTRUCTIONS = {
    "short": "Always start by listing all the concepts upfront as instructed. Then for each concept, write one to two sentences — just the essential definition, nothing more.",
    "medium": "Always start by listing all the concepts upfront as instructed. Then for each concept, write a detailed paragraph covering what it is, how it works, and why it matters.",
    "long": "Always start by listing all the concepts upfront as instructed. Then for each concept, go as deep as the concept demands — multiple paragraphs if the concept warrants it.",
}

MAX_TOKENS_MAP = {
    "short": 400,
    "medium": 1200,
    "long": 2500,
}


def extract_text_from_pdf(pdf_path: str) -> str:
    import pypdf
    with open(pdf_path, "rb") as f:
        reader = pypdf.PdfReader(f)
        pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ValueError("No extractable text found in PDF.")
    return text


def generate_script(notes: str, style: str, length: str) -> str:
    if style not in STYLE_INSTRUCTIONS:
        raise ValueError(f"Invalid style '{style}'. Choose from: {list(STYLE_INSTRUCTIONS)}")
    if length not in LENGTH_INSTRUCTIONS:
        raise ValueError(f"Invalid length '{length}'. Choose from: {list(LENGTH_INSTRUCTIONS)}")

    if style == "readback":
        length_instruction = ""
    elif style == "concepts":
        length_instruction = CONCEPTS_LENGTH_INSTRUCTIONS[length]
    else:
        length_instruction = LENGTH_INSTRUCTIONS[length]

    prompt = f"""{STYLE_INSTRUCTIONS[style]} {length_instruction}

STRICT RULES:
- Output ONLY the words to be spoken, nothing else.
- No section labels, headers, or stage directions (no "INTRO:", "HOST:", "OUTRO:", "[pause]", etc.).
- No meta-commentary, no descriptions of tone, no formatting — just pure spoken sentences.
- Do not start with "Welcome" or "Hello everyone" — just dive into the content.

Notes:
{notes}"""

    max_tokens = MAX_TOKENS_MAP["medium"] if style == "readback" else MAX_TOKENS_MAP[length]

    try:
        response = bedrock.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}]
            })
        )
        return json.loads(response["body"].read())["content"][0]["text"]
    except bedrock.exceptions.ModelNotReadyException as e:
        raise RuntimeError(f"Bedrock model not ready: {e}")
    except bedrock.exceptions.ThrottlingException as e:
        raise RuntimeError(f"Bedrock request throttled: {e}")
    except bedrock.exceptions.ModelErrorException as e:
        raise RuntimeError(f"Bedrock model error: {e}")
    except Exception as e:
        raise RuntimeError(f"Bedrock call failed: {e}")


def synthesize_audio(script: str, voice: str) -> str:
    """starts an async Polly task, polls until done, returns the S3 key of the MP3"""
    task = polly.start_speech_synthesis_task(
        Text=script,
        OutputFormat="mp3",
        VoiceId=voice,
        Engine="neural",
        OutputS3BucketName=BUCKET,
        OutputS3KeyPrefix="pipeline_output",
    )
    task_id = task["SynthesisTask"]["TaskId"]
    print(f"Polly task started: {task_id}")

    max_polls = 40
    for poll in range(max_polls):
        result = polly.get_speech_synthesis_task(TaskId=task_id)["SynthesisTask"]
        status = result["TaskStatus"]
        print(f"Polly status: {status}")
        if status == "completed":
            output_uri = result["OutputUri"]
            s3_key = output_uri.split(f"{BUCKET}/")[1]
            return s3_key
        if status == "failed":
            raise RuntimeError("Polly task failed")
        if poll == max_polls - 1:
            raise RuntimeError("Polly task timed out after 2 minutes")
        time.sleep(3)


def get_download_url(s3_key: str, expires_in: int = 3600) -> str:
    """returns a presigned S3 URL, valid for 1 hour by default"""
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": s3_key},
        ExpiresIn=expires_in,
    )


def run_pipeline(notes: str, style: str, length: str, voice: str, max_chars: int = None) -> str:
    """full pipeline: notes -> script -> audio -> presigned download URL"""
    if max_chars and len(notes) > max_chars:
        raise ValueError(f"Notes exceed {max_chars} character limit.")
    print("Generating script...")
    script = generate_script(notes, style, length)
    print(f"Script generated ({len(script)} chars)")

    print("Synthesizing audio...")
    s3_key = synthesize_audio(script, voice)
    print(f"Audio stored at s3://{BUCKET}/{s3_key}")

    url = get_download_url(s3_key)
    return url


def run_pipeline_from_pdf(pdf_path: str, style: str, length: str, voice: str, max_chars: int = None) -> str:
    """same as run_pipeline but starts from a PDF file"""
    print(f"Extracting text from {pdf_path}...")
    notes = extract_text_from_pdf(pdf_path)
    print(f"Extracted {len(notes)} chars from PDF")
    if max_chars and len(notes) > max_chars:
        raise ValueError(f"PDF contains too much text (>{max_chars} chars). Use a shorter document.")
    return run_pipeline(notes, style, length, voice)
