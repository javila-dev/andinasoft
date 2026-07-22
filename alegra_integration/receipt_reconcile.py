"""
Compatibilidad: la reconciliación por reference de journals vive en journal_reconcile.

Los recibos usan el mismo mecanismo (reference RC-…). Este módulo reexporta la API
histórica usada por tests e imports.
"""
from alegra_integration.journal_reconcile import (  # noqa: F401
    claim_existing_journal,
    claim_existing_receipt_journal,
    find_journal_by_exact_reference,
    list_journals_by_reference,
    mark_document_from_journal,
    mark_receipt_document_from_journal,
    reconcile_journal_document,
    reconcile_receipt_document,
    reference_from_payload,
    should_attempt_journal_reconcile,
    should_attempt_receipt_reconcile,
)
