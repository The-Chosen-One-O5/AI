#!/usr/bin/env python3
"""
Fix remaining syntax errors from the port
"""

import re

print("Reading main.py...")
with open('main.py', 'r') as f:
    content = f.read()

# Fix malformed function signatures
# Pattern: async def func_name(event)  # ...rest of signature):
pattern = r'async def (\w+)\(event\)\s+#[^:]+:'
replacement = r'async def \1(event):'

matches = re.findall(pattern, content)
print(f"Found {len(matches)} malformed function signatures: {matches}")

content = re.sub(pattern, replacement, content)
print("✓ Function signatures fixed")

# Write output
with open('main.py', 'w') as f:
    f.write(content)

print("✓ File written")
print("\nChecking for syntax errors...")

import subprocess
result = subprocess.run(['python3', '-m', 'py_compile', 'main.py'], capture_output=True, text=True)
if result.returncode == 0:
    print("✅ No syntax errors!")
else:
    print("⚠ Remaining errors:")
    print(result.stderr[:1000])
