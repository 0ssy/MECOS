"""
MECOS LLM Trainer
Autonomous fine-tuning pipeline for the MECOS LLM.
Learns from the 'llm_experiences.jsonl' generated during operation.
"""

import json
import torch
from transformers import TrainingArguments, Trainer, AutoModelForCausalLM, AutoTokenizer
from datasets import Dataset
from loguru import logger
from config import settings
from pathlib import Path

class MECOSTrainer:
    def __init__(self, model_name: str = "mistralai/Mistral-7B-v0.1"):
        self.model_name = model_name
        self.output_dir = settings.BASE_DIR / "mecos_llm_checkpoints"
        self.output_dir.mkdir(exist_ok=True)

    def prepare_dataset(self):
        """Load experiences and format them for fine-tuning."""
        exp_file = settings.DATA_DIR / "llm_experiences.jsonl"
        if not exp_file.exists():
            logger.warning("No experiences found for training.")
            return None
        
        data = []
        with open(exp_file, "r") as f:
            for line in f:
                exp = json.loads(line)
                # Format: [USER] prompt [INTERNAL MONOLOGUE] monologue [FINAL RESPONSE] response
                text = f"[USER] {exp['prompt']} [INTERNAL MONOLOGUE] {exp['monologue']} [FINAL RESPONSE] {exp['response']}"
                data.append({"text": text})
        
        return Dataset.from_list(data)

    def train(self):
        """Run the fine-tuning process."""
        dataset = self.prepare_dataset()
        if not dataset or len(dataset) < 10:
            logger.info("Not enough data to start training. Need at least 10 experiences.")
            return

        logger.info(f"Starting MECOS LLM self-training on {len(dataset)} experiences...")
        
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto"
        )

        def tokenize_function(examples):
            return tokenizer(examples["text"], padding="max_length", truncation=True, max_length=512)

        tokenized_datasets = dataset.map(tokenize_function, batched=True)

        training_args = TrainingArguments(
            output_dir=str(self.output_dir),
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            num_train_epochs=3,
            learning_rate=2e-5,
            weight_decay=0.01,
            logging_dir=str(settings.LOGS_DIR),
            save_strategy="epoch",
            push_to_hub=False
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=tokenized_datasets,
        )

        trainer.train()
        logger.info("MECOS LLM self-training complete. New model checkpoint saved.")
        
        # Update config to use the new checkpoint
        # settings.DEFAULT_MODEL = str(self.output_dir / "latest")
        return True

if __name__ == "__main__":
    trainer = MECOSTrainer()
    trainer.train()
