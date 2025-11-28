import asyncio
from agentic_pipeline import run_pipeline
from data_manager import initialize_data_directory

if __name__ == "__main__":
    initialize_data_directory()
    claim_text_input = input("\nEnter the claim you want to verify: ")
    asyncio.run(run_pipeline(claim_text_input))