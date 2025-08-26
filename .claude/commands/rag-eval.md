# Command: RAG Evaluation Run
Evaluate retrieval + answer selection on a given dataset of questions.

## Inputs
- `--dataset`: Path to JSONL file of questions. Each entry:  
  ```json
  {"question": "...", "expected_answer": "...", "labels": ["optional"]}
