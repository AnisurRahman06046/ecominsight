"""
Query Logger for MCP System
Tracks all queries, responses, and failures for analysis and fine-tuning
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class QueryLogger:
    """Log all queries for analysis and model fine-tuning."""

    def __init__(self, log_dir: str = "query_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)

        # Separate log files
        self.all_queries_file = self.log_dir / "all_queries.jsonl"
        self.failed_queries_file = self.log_dir / "failed_queries.jsonl"
        self.success_queries_file = self.log_dir / "success_queries.jsonl"

    def log_query(
        self,
        question: str,
        shop_id: int,
        answer: str,
        tool_used: str,
        intent: str,
        confidence: float,
        success: bool,
        response_time: float,
        error: Optional[str] = None,
        data: Optional[Any] = None,
        user_feedback: Optional[str] = None
    ):
        """
        Log a query with all metadata.

        Args:
            question: User's question
            shop_id: Shop ID
            answer: Generated answer
            tool_used: Tool that was used
            intent: Classified intent
            confidence: Intent confidence score
            success: Whether query succeeded
            response_time: Time taken to process
            error: Error message if failed
            data: Result data
            user_feedback: Optional user feedback (thumbs up/down)
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "question": question,
            "shop_id": shop_id,
            "answer": answer,
            "tool_used": tool_used,
            "intent": intent,
            "confidence": confidence,
            "success": success,
            "response_time": response_time,
            "error": error,
            "has_data": data is not None,
            "user_feedback": user_feedback
        }

        # Log to all queries
        self._append_to_file(self.all_queries_file, log_entry)

        # Log to success/failure specific files
        if success:
            self._append_to_file(self.success_queries_file, log_entry)
        else:
            self._append_to_file(self.failed_queries_file, log_entry)

        logger.info(f"Query logged: {question[:50]}... | Success: {success}")

    def _append_to_file(self, file_path: Path, entry: Dict[str, Any]):
        """Append entry to JSONL file."""
        try:
            with open(file_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")

    def get_failed_queries(self, limit: int = 100) -> list:
        """Get recent failed queries for analysis."""
        try:
            with open(self.failed_queries_file, 'r') as f:
                queries = [json.loads(line) for line in f]
                return queries[-limit:]  # Return last N
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read failed queries: {e}")
            return []

    def get_low_confidence_queries(self, threshold: float = 0.5, limit: int = 100) -> list:
        """Get queries with low confidence scores for review."""
        try:
            low_confidence = []
            with open(self.all_queries_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get('confidence', 1.0) < threshold:
                        low_confidence.append(entry)
            return low_confidence[-limit:]
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f"Failed to read low confidence queries: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Get query statistics for monitoring."""
        try:
            total_queries = 0
            failed_queries = 0
            intent_distribution = {}
            tool_distribution = {}
            avg_confidence = []
            avg_response_time = []

            with open(self.all_queries_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    total_queries += 1

                    if not entry.get('success', False):
                        failed_queries += 1

                    intent = entry.get('intent', 'unknown')
                    intent_distribution[intent] = intent_distribution.get(intent, 0) + 1

                    tool = entry.get('tool_used', 'unknown')
                    tool_distribution[tool] = tool_distribution.get(tool, 0) + 1

                    if entry.get('confidence'):
                        avg_confidence.append(entry['confidence'])

                    if entry.get('response_time'):
                        avg_response_time.append(entry['response_time'])

            return {
                "total_queries": total_queries,
                "failed_queries": failed_queries,
                "success_rate": (total_queries - failed_queries) / total_queries * 100 if total_queries > 0 else 0,
                "intent_distribution": intent_distribution,
                "tool_distribution": tool_distribution,
                "avg_confidence": sum(avg_confidence) / len(avg_confidence) if avg_confidence else 0,
                "avg_response_time": sum(avg_response_time) / len(avg_response_time) if avg_response_time else 0
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def export_for_finetuning(self, output_file: str = "finetuning_data.jsonl"):
        """
        Export queries in format suitable for fine-tuning.

        Format for FLAN-T5:
        {"input": "question with context", "output": "expected answer"}
        """
        try:
            output_path = self.log_dir / output_file

            with open(self.all_queries_file, 'r') as f_in, open(output_path, 'w') as f_out:
                for line in f_in:
                    entry = json.loads(line)

                    # Only export successful queries with good confidence
                    if entry.get('success') and entry.get('confidence', 0) > 0.7:
                        finetuning_entry = {
                            "input": f"Answer this e-commerce analytics question: {entry['question']}",
                            "output": entry['answer'],
                            "intent": entry.get('intent'),
                            "tool": entry.get('tool_used')
                        }
                        f_out.write(json.dumps(finetuning_entry) + '\n')

            logger.info(f"Fine-tuning data exported to {output_path}")
            return str(output_path)
        except Exception as e:
            logger.error(f"Failed to export fine-tuning data: {e}")
            return None


# Global instance
query_logger = QueryLogger()