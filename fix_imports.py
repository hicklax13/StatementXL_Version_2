import anthropic
import os

client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")  # Uses environment variable instead of hardcoded key
)

# Read the files that need fixing
files_to_fix = [
    'backend/api/routes/auth.py',
    'backend/auth/__init__.py', 
    'backend/auth/utils.py',
    'tests/unit/test_auth.py'
]

for filepath in files_to_fix:
    print(f"\n{'='*50}")
    print(f"Fixing: {filepath}")
    print('='*50)
    
    # Read the file
    try:
        with open(filepath, 'r') as f:
            original_code = f.read()
    except FileNotFoundError:
        print(f"⚠️  File not found, skipping...")
        continue
    
    # Ask Claude to fix the imports
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": f"""Fix the imports in this Python file. Change any imports of hash_password or verify_password from backend.auth.utils to backend.core.security.

Original file:
{original_code}

Return ONLY the complete fixed code, no explanations."""
        }]
    )
    
    fixed_code = message.content[0].text
    
    # Write the fixed code back
    with open(filepath, 'w') as f:
        f.write(fixed_code)
    
    print(f"✅ Fixed!")

print("\n🎉 All files updated!")