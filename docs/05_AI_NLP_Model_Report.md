# AI / NLP Model Development Report
## QueryMate: AI Healthcare Question Answering Chatbot

- **Version:** 1.0
- **Status:** Experiment plan; no model results should be assumed yet.

## 1. Goal
Identify an appropriate method for matching user healthcare questions to relevant reference answers while keeping responses understandable and safety-aware.

## 2. Candidate approaches
### A. TF-IDF + cosine similarity (baseline)
Vectorize the dataset's question field and the user query with TF-IDF. Retrieve the most similar question and return its associated answer only if the similarity score passes a validated threshold.

**Advantages:** fast, transparent, low compute.  
**Limitations:** weaker semantic understanding; may miss paraphrases and synonyms.

### B. Sentence embeddings + vector search
Encode questions into dense vectors and retrieve nearest neighbors by cosine similarity.

**Advantages:** better potential semantic matching.  
**Limitations:** more compute, model dependency, similarity scores still do not guarantee answer correctness.

### C. Retrieval-Augmented Generation (RAG)
Retrieve relevant dataset entries and supply them as context to a language model. The model generates a response grounded in retrieved content.

**Advantages:** potentially more natural answers and synthesis.  
**Limitations:** hallucination risk, extra latency/cost, privacy considerations, and the need to validate grounding.

### D. Fine-tuning (optional)
Consider only if there is a clear need, adequate compute, a license/usage review, and a robust safety evaluation plan. Fine-tuning alone does not guarantee factuality or clinical safety.

## 3. Recommended experiment sequence
1. Audit the data and inspect examples.
2. Build a TF-IDF retrieval baseline.
3. Create a fixed, manually reviewed evaluation set.
4. Measure relevance, top-k retrieval, low-confidence fallback, and latency.
5. Compare a sentence-embedding model if baseline quality is insufficient.
6. Consider RAG only if it improves response quality enough to justify complexity.
7. Test safety independently of general answer relevance.
8. Document the chosen model and known limitations.

## 4. Input/target definition
- Query: user-provided healthcare question.
- Retrieval text: primarily `input`.
- Reference answer: `output`.
- `instruction`: inspect and decide whether it is needed; avoid unnecessary prompt repetition.

## 5. Evaluation metrics
Use metrics appropriate to the method:
- Precision@K / Recall@K for retrieval where labels are available.
- Mean Reciprocal Rank (MRR) where the correct reference is known.
- Human-rated relevance, clarity, completeness, and groundedness.
- Unsafe-response rate on a reviewed safety set.
- Emergency escalation recall on a defined high-risk test set.
- Latency: median and 95th percentile.
- Fallback rate and false fallback rate.
- Optional text-overlap metrics such as ROUGE/BLEU only as secondary indicators; they are not proof of medical correctness.

## 6. Human evaluation rubric
Score each dimension 1–5:
1. Relevance to the question.
2. Clarity/readability.
3. Completeness for general education.
4. Grounding in retrieved evidence.
5. Appropriate uncertainty.
6. Safety.
7. Avoidance of unsupported diagnosis/treatment.

For safety-critical cases, use pass/fail flags in addition to averages. Any dangerous response should be investigated even if the average score is high.

## 7. Threshold calibration
Do not choose an arbitrary cosine similarity threshold and treat it as reliable. Select a threshold using validation examples, including unrelated questions and paraphrases. Report false accepts, false rejections, and safety implications.

## 8. Experimental record template
| Run | Method | Dataset version | Parameters | Evaluation set | Key results | Decision |
|---|---|---|---|---|---|---|
| EXP-01 | TF-IDF baseline | To record | To record | To record | Not run | Pending |
| EXP-02 | Sentence embeddings | To record | To record | To record | Not run | Optional |
| EXP-03 | RAG/LLM | To record | To record | To record | Not run | Optional |

## 9. Model selection rule
Choose the simplest approach that meets the project's measured relevance, safety, latency, and resource requirements. Do not select a model based on a single accuracy or similarity score.

## 10. Reproducibility
Record library/model versions, random seeds where relevant, preprocessing steps, index build procedure, hardware, evaluation set version, and all key parameters.

## 11. Limitations
A model that performs well on a dataset may still fail on real-world questions. General language metrics cannot establish clinical safety. The prototype must not be described as clinically validated.
