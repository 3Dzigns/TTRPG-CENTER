from src_common.vector_store.memory import MemoryVectorStore


def test_memory_backend_topk():
    store = MemoryVectorStore(env="test")
    store.delete_all()

    documents = [
        {
            "chunk_id": f"chunk-{idx}",
            "content": f"Spell {idx} allows quick casting",
            "metadata": {"source_hash": f"hash-{idx}", "source_file": f"spell-{idx}.json"},
        }
        for idx in range(5)
    ]

    store.upsert_documents(documents)

    results = store.query(vector=None, top_k=3, filters={"query_text": "Spell"})

    assert len(results) == 3
    assert all(result["content"].startswith("Spell") for result in results)
    store.delete_all()
