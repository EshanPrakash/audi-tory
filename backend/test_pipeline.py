from dotenv import load_dotenv
import os
import boto3
import json
import time

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
BUCKET = os.getenv("S3_BUCKET")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID")
LOCAL_OUTPUT_PATH = os.getenv("LOCAL_OUTPUT_PATH")

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
polly = boto3.client("polly", region_name=AWS_REGION)

# --- Sample notes ---
sample_notes = {
    "photosynthesis": """
Photosynthesis is the process by which plants convert sunlight into energy.
Chlorophyll is the pigment inside plant cells that absorbs light — mostly red and blue wavelengths, reflecting green, which is why plants look green.
This absorbed light energy drives a two-stage process: the light-dependent reactions and the Calvin cycle.
In the light-dependent reactions, water molecules are split, releasing oxygen as a byproduct — this is where all atmospheric oxygen comes from.
The energy captured is stored as ATP and NADPH, which then power the Calvin cycle.
In the Calvin cycle, CO2 from the air is fixed into glucose using that stored energy.
This all happens inside chloroplasts, organelles found in plant cells.
Photosynthesis is the foundation of almost all food chains on Earth — it's the original source of energy for nearly every living thing.
""",
    "black_holes": """
Black holes form when massive stars — typically more than 20 times the mass of the Sun — exhaust their nuclear fuel and collapse under their own gravity.
The core collapses so densely that it creates a singularity, a point where known physics breaks down.
Surrounding the singularity is the event horizon — the boundary beyond which escape velocity exceeds the speed of light, making it a point of no return.
Nothing, not even light, can escape once it crosses the event horizon.
Black holes are detected indirectly: through gravitational effects on nearby stars, X-ray emissions from accretion disks, and gravitational waves from mergers.
Hawking radiation is a theoretical process where quantum effects near the event horizon cause black holes to slowly emit energy and lose mass over vast timescales.
Supermassive black holes, millions to billions of solar masses, sit at the centers of most large galaxies, including the Milky Way (Sagittarius A*).
The first image of a black hole's shadow was captured in 2019 by the Event Horizon Telescope, targeting M87*.
""",
    "stoicism": """
Stoicism is a philosophy founded in Athens around 300 BC by Zeno of Citium, later developed by Epictetus, Seneca, and Roman Emperor Marcus Aurelius.
The central practice is the dichotomy of control: clearly distinguishing what is up to you (your thoughts, values, actions) from what is not (external outcomes, other people, circumstances).
You focus only on the former and accept the latter with equanimity.
Virtue — wisdom, courage, justice, temperance — is the only true good. Everything else (wealth, health, reputation) is a "preferred indifferent": nice to have, but not necessary for a good life.
Negative visualization (premeditatio malorum) is a key exercise: regularly imagining loss or hardship to build resilience and appreciation for what you have.
Stoics practice living according to nature, meaning living in accordance with reason and our social nature as human beings.
Marcus Aurelius wrote Meditations as a private journal of Stoic practice — it remains one of the most widely read works of philosophy.
Epictetus, born a slave, emphasized that no one can take away your inner freedom — how you respond to anything is always your choice.
""",
}

# --- Prompt configuration ---
style_instructions = {
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

length_instructions = {
    "short": (
        "Write approximately 200 words. Cover only the most essential points."
    ),
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

max_tokens_map = {
    "short": 400,
    "medium": 1200,
    "long": 2500,
}

# --- Pipeline configuration (change these to test different combinations) ---
notes = sample_notes["photosynthesis"]
style = "concepts"   # "podcast" | "readback" | "concepts"
length = "long"      # "short" | "medium" | "long"
voice = "Matthew"     # any Polly neural voice, e.g. "Matthew", "Joanna", "Ruth"

# Step 1: Transform notes with Bedrock
concepts_length_instructions = {
    "short": "Always start by listing all the concepts upfront as instructed. Then for each concept, write one to two sentences — just the essential definition, nothing more.",
    "medium": "Always start by listing all the concepts upfront as instructed. Then for each concept, write a detailed paragraph covering what it is, how it works, and why it matters.",
    "long": "Always start by listing all the concepts upfront as instructed. Then for each concept, go as deep as the concept demands — multiple paragraphs if the concept warrants it.",
}

if style == "readback":
    length_instruction = ""
elif style == "concepts":
    length_instruction = concepts_length_instructions[length]
else:
    length_instruction = length_instructions[length]
prompt = f"""{style_instructions[style]} {length_instruction}

STRICT RULES:
- Output ONLY the words to be spoken, nothing else.
- No section labels, headers, or stage directions (no "INTRO:", "HOST:", "OUTRO:", "[pause]", etc.).
- No meta-commentary, no descriptions of tone, no formatting — just pure spoken sentences.
- Do not start with "Welcome" or "Hello everyone" — just dive into the content.

Notes:
{notes}"""

max_tokens = max_tokens_map["medium"] if style == "readback" else max_tokens_map[length]
response = bedrock.invoke_model(
    modelId=MODEL_ID,
    body=json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": prompt
        }]
    })
)
script = json.loads(response["body"].read())["content"][0]["text"]
print("Script generated:\n", script)

# Step 2 & 3: Convert script to audio with Polly and store directly in S3
local_output = LOCAL_OUTPUT_PATH
s3_key_prefix = "pipeline_output"
task = polly.start_speech_synthesis_task(
    Text=script,
    OutputFormat="mp3",
    VoiceId=voice,
    Engine="neural",
    OutputS3BucketName=BUCKET,
    OutputS3KeyPrefix=s3_key_prefix,
)
task_id = task["SynthesisTask"]["TaskId"]
print(f"Polly task started: {task_id}")

max_polls = 40
for poll in range(max_polls):
    status = polly.get_speech_synthesis_task(TaskId=task_id)["SynthesisTask"]["TaskStatus"]
    print(f"Status: {status}")
    if status == "completed":
        output_uri = polly.get_speech_synthesis_task(TaskId=task_id)["SynthesisTask"]["OutputUri"]
        s3_key = output_uri.split(f"{BUCKET}/")[1]
        break
    if status == "failed":
        raise RuntimeError("Polly task failed")
    if poll == max_polls - 1:
        raise RuntimeError("Polly task timed out after 2 minutes")
    time.sleep(3)

# Download the output from S3 to local file
if os.path.exists(local_output):
    os.remove(local_output)
s3.download_file(BUCKET, s3_key, local_output)
print(f"Pipeline complete. Audio saved to {local_output} ({os.path.getsize(local_output)} bytes)")
