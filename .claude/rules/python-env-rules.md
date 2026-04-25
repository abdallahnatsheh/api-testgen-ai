# Python Environment Rules

## Always use the project venv

If a `venv/` directory exists in the project root, always use it — never use system `python3`, `pip3`, or `pytest` directly.

| Task | Command |
|------|---------|
| Run Python | `venv/bin/python3 <script>` |
| Install packages | `venv/bin/python3 -m pip install <pkg>` |
| Run pytest | `venv/bin/python3 -m pytest <args>` |

Never use `pip install --break-system-packages` or any system-level install.
