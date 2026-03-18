from dotenv import load_dotenv
import os
import boto3
import json

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
polly = boto3.client("polly", region_name=AWS_REGION)

# Sample notes to test with
notes = """
Photosynthesis is the process by which plants convert sunlight into energy.
Chlorophyll absorbs light, which drives the conversion of CO2 and water into glucose and oxygen.
This process occurs in the chloroplasts of plant cells.
"""

# Step 1: Transform notes with Bedrock
response = bedrock.invoke_model(
    modelId=MODEL_ID,
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{
            "role": "user",
            "content": f"""Transform these notes into a short, engaging podcast script.

STRICT RULES:
- Output ONLY the words to be spoken, nothing else.
- No section labels, headers, or stage directions (no "INTRO:", "HOST:", "OUTRO:", "[pause]", etc.).
- No meta-commentary, no descriptions of tone, no formatting — just pure spoken sentences.
- Write in a natural, conversational tone as if one person is casually explaining the topic to a friend.
- Do not start with "Welcome" or "Hello everyone" — just dive into the content.

Notes:
{notes}"""
        }]
    })
)
script = json.loads(response["body"].read())["content"][0]["text"]
print("Script generated:\n", script)

# Step 2: Convert script to audio with Polly
audio_response = polly.synthesize_speech(
    Text=script,
    OutputFormat="mp3",
    VoiceId="Joanna",
    Engine="neural"
)
audio_file = "pipeline_output.mp3"
with open(audio_file, "wb") as f:
    f.write(audio_response["AudioStream"].read())

# Step 3: Upload audio to S3
s3.upload_file(audio_file, BUCKET, audio_file)
print("Pipeline complete. Audio uploaded to S3.")
