#!/usr/bin/env python3
"""
Fine-tune FLAN-T5-base for e-commerce query responses
Uses logged query data from query_logs/finetuning_data.jsonl
"""

import json
import os
from pathlib import Path
from datasets import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq
)

# Configuration
MODEL_NAME = "google/flan-t5-base"
TRAINING_DATA_FILE = "query_logs/finetuning_data.jsonl"
OUTPUT_DIR = "./finetuned_flan_t5"
FINAL_MODEL_DIR = "./finetuned_flan_t5/final"

def load_finetuning_data(file_path):
    """Load JSONL data"""
    if not Path(file_path).exists():
        raise FileNotFoundError(f"Training data not found: {file_path}")

    data = {"input": [], "output": []}
    with open(file_path, 'r') as f:
        for line in f:
            entry = json.loads(line)
            data["input"].append(entry["input"])
            data["output"].append(entry["output"])

    print(f"✓ Loaded {len(data['input'])} training examples")
    return Dataset.from_dict(data)

def preprocess_function(examples, tokenizer, max_input_length=512, max_output_length=200):
    """Tokenize inputs and outputs"""
    model_inputs = tokenizer(
        examples["input"],
        max_length=max_input_length,
        truncation=True,
        padding="max_length"
    )

    labels = tokenizer(
        examples["output"],
        max_length=max_output_length,
        truncation=True,
        padding="max_length"
    )

    model_inputs["labels"] = labels["input_ids"]
    return model_inputs

def main():
    print("="*70)
    print("FLAN-T5 FINE-TUNING FOR ECOMINSIGHT")
    print("="*70)

    # Check if training data exists
    if not Path(TRAINING_DATA_FILE).exists():
        print(f"\n❌ Training data not found: {TRAINING_DATA_FILE}")
        print(f"\nPlease run: python -c 'from app.services.query_logger import query_logger; query_logger.export_for_finetuning()'")
        return

    # Load model and tokenizer
    print(f"\n1. Loading model and tokenizer: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME)
    print("✓ Model and tokenizer loaded")

    # Load and prepare data
    print(f"\n2. Loading training data from: {TRAINING_DATA_FILE}")
    dataset = load_finetuning_data(TRAINING_DATA_FILE)

    # Check dataset size
    if len(dataset) < 50:
        print(f"\n⚠️  WARNING: Only {len(dataset)} training examples found.")
        print(f"   Recommended: 500+ examples for best results")
        print(f"   Minimum: 100 examples")
        print(f"\n   Continue anyway? (y/n): ", end="")
        response = input().strip().lower()
        if response != 'y':
            print("Aborted.")
            return

    # Split into train/val (90/10)
    print(f"\n3. Splitting data into train/validation sets")
    split_dataset = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = split_dataset["train"]
    val_dataset = split_dataset["test"]

    print(f"✓ Training examples: {len(train_dataset)}")
    print(f"✓ Validation examples: {len(val_dataset)}")

    # Tokenize
    print(f"\n4. Tokenizing data...")
    train_dataset = train_dataset.map(
        lambda x: preprocess_function(x, tokenizer),
        batched=True,
        remove_columns=["input", "output"]
    )
    val_dataset = val_dataset.map(
        lambda x: preprocess_function(x, tokenizer),
        batched=True,
        remove_columns=["input", "output"]
    )
    print("✓ Data tokenized")

    # Training arguments
    print(f"\n5. Setting up training configuration")
    training_args = Seq2SeqTrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",  # Changed from evaluation_strategy
        learning_rate=3e-4,
        per_device_train_batch_size=4,
        per_device_eval_batch_size=4,
        num_train_epochs=5,
        weight_decay=0.01,
        save_total_limit=3,
        predict_with_generate=True,
        fp16=False,  # Set to True if using GPU with fp16 support
        logging_steps=50,
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
    )
    print("✓ Training configuration set")

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        model=model
    )

    # Trainer
    print(f"\n6. Initializing trainer")
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        data_collator=data_collator,
    )
    print("✓ Trainer initialized")

    # Train
    print(f"\n7. Starting fine-tuning (this may take a while)...")
    print("="*70)
    trainer.train()
    print("="*70)
    print("✓ Fine-tuning completed!")

    # Save final model
    print(f"\n8. Saving fine-tuned model to: {FINAL_MODEL_DIR}")
    trainer.save_model(FINAL_MODEL_DIR)
    tokenizer.save_pretrained(FINAL_MODEL_DIR)
    print("✓ Model saved")

    print("\n" + "="*70)
    print("FINE-TUNING COMPLETE!")
    print("="*70)
    print(f"\nFine-tuned model saved to: {FINAL_MODEL_DIR}")
    print(f"\nTo use the fine-tuned model:")
    print(f"1. Update app/services/hf_response_generator.py")
    print(f"2. Change model path to: {FINAL_MODEL_DIR}")
    print(f"3. Restart the server")
    print(f"\nOr run test script: python test_finetuned_model.py")

if __name__ == "__main__":
    main()