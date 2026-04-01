# local test runner for the pipeline
# usage:
#   python test_pipeline.py
#   python test_pipeline.py --notes black_holes --style podcast --length medium
#   python test_pipeline.py --pdf /path/to/notes.pdf --style concepts --length short
#   python test_pipeline.py --pdf /path/to/notes.pdf --voice Joanna

import argparse
from pipeline import run_pipeline, run_pipeline_from_pdf

SAMPLE_NOTES = {
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


def main():
    parser = argparse.ArgumentParser(description="Test the audi-tory pipeline locally.")
    parser.add_argument("--pdf", help="Path to a PDF file to process")
    parser.add_argument(
        "--notes",
        choices=list(SAMPLE_NOTES),
        default="photosynthesis",
        help="Sample notes to use if no PDF provided (default: photosynthesis)",
    )
    parser.add_argument("--style", choices=["podcast", "readback", "concepts"], default="concepts")
    parser.add_argument("--length", choices=["short", "medium", "long"], default="short")
    parser.add_argument("--voice", default="Matthew", help="Polly neural voice (default: Matthew)")
    args = parser.parse_args()

    if args.pdf:
        url = run_pipeline_from_pdf(args.pdf, args.style, args.length, args.voice)
    else:
        notes = SAMPLE_NOTES[args.notes]
        url = run_pipeline(notes, args.style, args.length, args.voice)

    print(f"\nDone! Download URL (valid 1 hour):\n{url}")


if __name__ == "__main__":
    main()
