import boto3
import json

s3 = boto3.client("s3", region_name="us-east-1")
bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
polly = boto3.client("polly", region_name="us-east-1")

BUCKET = "audi-tory-uploads"

# Sample notes to test with
notes = """
Photosynthesis is the process by which plants convert sunlight into energy.
Chlorophyll absorbs light, which drives the conversion of CO2 and water into glucose and oxygen.
This process occurs in the chloroplasts of plant cells.
"""

# Step 1: Transform notes with Bedrock
response = bedrock.invoke_model(
    modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 512,
        "messages": [{
            "role": "user",
            "content": f"Transform these notes into a short, engaging podcast script:\n\n{notes}"
        }]
    })
)
script = json.loads(response["body"].read())["content"][0]["text"]
print("Script generated:\n", script)

# Step 2: Convert script to audio with Polly
audio_response = polly.synthesize_speech(
    Text=script,
    OutputFormat="mp3",
    VoiceId="Joanna"
)
audio_file = "pipeline_output.mp3"
with open(audio_file, "wb") as f:
    f.write(audio_response["AudioStream"].read())

# Step 3: Upload audio to S3
s3.upload_file(audio_file, BUCKET, audio_file)
print("Pipeline complete. Audio uploaded to S3.")