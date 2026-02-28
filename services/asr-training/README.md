# asr-training

Fine-tunes Whisper on corrected transcript data and re-drafts pending clips with the improved model. Uses HuggingFace Seq2SeqTrainer and WhisperForConditionalGeneration.

## Setup

From the repo root:

```bash
make install
```

Requires: PyTorch, transformers, datasets, soundfile. Device: auto (cuda > mps > cpu), or explicit `--device mps|cuda|cpu`.

## Usage

```bash
./ambara train -d data/training/20250101_some-run -o models/whisper-mg-v1 --base-model openai/whisper-small --epochs 10
./ambara re-draft -m models/whisper-mg-v1 -d data/output/20250101_some-run -l some-run
```

Examples:

```bash
./ambara train -d data/training/20250101_church -o models/mg-v2 --epochs 15 --batch-size 8 --device cuda
./ambara train -d data/training/run1 -o models/out --push-to-hub user/whisper-mg
./ambara re-draft -m user/whisper-mg -d data/output/20250101_church --run <uuid>
```

## Architecture

- `train.py`: `fine_tune()` loads base model and processor, builds Seq2SeqTrainer, trains, saves to `output_dir/model`; `push_to_hub()` for HuggingFace
- `redraft.py`: `redraft_pending()` loads model, fetches pending clips from Supabase, transcribes locally, updates `draft_transcription`
- `config.py`: `TrainingConfig` (epochs, batch_size, lr, eval_steps, etc.)
- `dataset.py`: `load_training_data()` — HuggingFace audiofolder format (train/test dirs with `metadata.csv`)
- `collator.py`: `WhisperDataCollator`; `metrics.py`: WER computation for eval

## Data Flow

Input (train): exported training dir with `train/` and `test/` (WAV + metadata.csv). Input (re-draft): run label/UUID, local clips dir. Output: fine-tuned model dir, or updated `draft_transcription` in Supabase. External: HuggingFace (model download; optional push), Supabase (re-draft).

## How to Modify

- Add training options: extend `TrainingConfig` and `Seq2SeqTrainingArguments` in `train.py`; add CLI flags in `cli.py`
- Change base model or language: `config.py` (`base_model`, `language`), or pass via CLI
- Support another ASR model: implement a similar `fine_tune` flow and a `redraft_pending` path that uses the new model
- Re-draft filters: adjust `_fetch_pending_clips` in `redraft.py` (e.g. by status, clip attributes)
