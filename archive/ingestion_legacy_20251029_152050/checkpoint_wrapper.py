"""Wrapper functions for integrating checkpointing into passes."""
from pathlib import Path
from typing import Callable, Any
from pipeline_state import PipelineState
import traceback

def with_checkpoint(pass_name: str):
    """
    Decorator to add checkpointing to pass functions.

    Usage:
        @with_checkpoint("pass_a")
        def run_pass_a(document_path: Path) -> Dict:
            # ... pass logic ...
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(document_path: Path, *args, **kwargs) -> Any:
            state_manager = PipelineState()
            doc_id = state_manager._document_id_from_path(document_path)

            # Check if already completed
            if state_manager.is_pass_completed(doc_id, pass_name):
                print(f"⏭️  Skipping {pass_name} (already completed)")
                return {"skipped": True, "reason": "already_completed"}

            # Mark started
            state_manager.mark_pass_started(doc_id, pass_name)

            try:
                # Execute pass
                result = func(document_path, *args, **kwargs)

                # Mark completed
                state_manager.mark_pass_completed(
                    doc_id,
                    pass_name,
                    metadata={"result_keys": list(result.keys()) if isinstance(result, dict) else None}
                )

                return result

            except Exception as e:
                # Mark failed
                error_msg = f"{type(e).__name__}: {str(e)}"
                state_manager.mark_pass_failed(doc_id, pass_name, error_msg)

                print(f"❌ {pass_name} failed: {error_msg}")
                traceback.print_exc()

                raise

        return wrapper
    return decorator
