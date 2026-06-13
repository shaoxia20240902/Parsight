from typing import Any, Dict, List


class UnderstandingNotReadyError(Exception):
    def __init__(self, pending_tables: List[str], pending_sheets: List[Dict[str, Any]]):
        self.pending_tables = pending_tables
        self.pending_sheets = pending_sheets
        super().__init__(f"六维理解未就绪: {', '.join(pending_tables)}")
