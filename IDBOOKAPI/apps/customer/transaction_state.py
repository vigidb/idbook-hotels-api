def normalize_wallet_transaction_state(status_value, success_value=None):
    """
    Canonical rule:
    - status == Completed  => is_transaction_success = True
    - any other status     => is_transaction_success = False
    """
    is_completed = str(status_value or "").strip().lower() == "completed"
    return "Completed" if is_completed else status_value, bool(is_completed)
