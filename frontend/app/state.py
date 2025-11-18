# frontend/app/state.py
# ========================== START: MODIFICATION (Code Addition) ==========================
# DESIGNER'S NOTE:
# This new file holds the shared state of the application.
# Centralizing state management prevents passing variables through many layers
# and makes the data flow clearer and more maintainable.

# Used to store template metadata fetched from the backend, format: {template_key: metadata}.
TEMPLATES_METADATA = {}

# Used to store the formatted choices for subscriber dropdowns, format: ["Remark <email>"].
SUBSCRIBER_CHOICES = []

# ========================== END: MODIFICATION (Code Addition) ============================