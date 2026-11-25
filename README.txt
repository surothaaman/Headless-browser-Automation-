Provider XX - masked terminal payment entry patch

WHAT CHANGES
- At program start, after the scenario JSON/customer data is loaded but BEFORE Chromium is launched, the runner prompts for payment details in the terminal.
- Every payment prompt uses getpass, so typed characters are not echoed.
- Payment details are validated in memory, encrypted with the existing RSA-OAEP-256 + A256GCM JWE public-key flow, and uploaded to the local FastAPI CSE endpoint.
- No payment JSON file is required and no card details are written to disk, environment variables, logs, or screenshots.
- During the payment page, the runner retrieves the one-time record. The API authenticates/decrypts JWE using the configured private key. A successful authenticated decrypt verifies that the matching private key can decrypt the public-key-encrypted payload.
- Playwright fills the payment controls and reads each field back in memory to verify the value entered. It logs PASS/FAIL only, never the values.
- The payment inputs are cleared from the browser fields after verification/Forward. The final order submission is not clicked.

FILES TO REPLACE / ADD
- tests/test_browser_launch.py (replace)
- app/config.py (replace)
- app/api/sensitive_data.py (replace)
- app/security/encrypt_order.py (replace)
- app/security/jwe_handler.py (replace)
- app/security/sensitive_client.py (replace)
- app/security/terminal_payment.py (new)
- tests/test_terminal_payment.py (new)

REQUIREMENTS
- Keep your existing app/security/sensitive_store.py and app/main.py.
- Keep the existing matching keys/server_public.pem and keys/server_private.pem. Do not overwrite or share private keys.
- Project-root .env must contain CSE_ACCESS_TOKEN and CSE_API_URL=http://127.0.0.1:8000.
- The API and runner load the same project-root .env. Never commit .env or keys.
- Start API without --reload so the in-memory one-time record is not lost on file changes:
    uvicorn app.main:app --host 127.0.0.1 --port 8000
- In another terminal, run:
    python -m tests.test_browser_launch --json ".\scenario-04-ez-enroll(2).json"
- The runner prompts for simulator-approved TEST payment details before opening Chromium. All prompts are masked. Do not enter personal/bank card details. If the simulator has not supplied test credentials, obtain them from its administrator; do not invent credentials.

TESTS
- python -m py_compile tests/test_browser_launch.py app/config.py app/api/sensitive_data.py app/security/encrypt_order.py app/security/jwe_handler.py app/security/sensitive_client.py app/security/terminal_payment.py
- python -m pytest -q tests/test_terminal_payment.py
- Live JWE/API and authenticated simulator testing must be completed in the user's environment where jwcrypto, the actual key pair, API process, and simulator login are available.

SECURITY LIMITATIONS
- getpass masks terminal input but cannot guarantee memory zeroization in Python.
- The API currently uses an in-memory one-time store; restarting the API invalidates outstanding records.
- Do not enable screenshots during payment entry.
