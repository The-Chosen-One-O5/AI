#!/usr/bin/env python3
"""
Test script to verify job_queue safety checks are in place.
This script checks that all job_queue accesses have proper null checks.
"""

import re
import sys

def check_job_queue_safety(filename):
    """Check if all job_queue accesses have proper null checks."""
    with open(filename, 'r') as f:
        content = f.read()
    
    # Find all lines with job_queue method calls
    job_queue_pattern = r'(context\.job_queue|job_queue)\.(get_jobs_by_name|run_once|run_daily|run_repeating)'
    
    matches = list(re.finditer(job_queue_pattern, content))
    
    print(f"Found {len(matches)} job_queue method calls")
    print("-" * 80)
    
    issues = []
    
    for match in matches:
        line_num = content[:match.start()].count('\n') + 1
        
        # Get context (previous 10 lines)
        lines_before = content[:match.start()].split('\n')
        context_lines = lines_before[-10:] if len(lines_before) >= 10 else lines_before
        
        # Check if there's a null check in the previous lines
        has_null_check = False
        for line in context_lines:
            if 'if not context.job_queue' in line or 'if context.job_queue' in line or 'if job_queue' in line:
                has_null_check = True
                break
        
        # Get the actual line
        all_lines = content.split('\n')
        actual_line = all_lines[line_num - 1] if line_num <= len(all_lines) else ""
        
        status = "✓ SAFE" if has_null_check else "⚠ NEEDS CHECK"
        
        print(f"Line {line_num}: {status}")
        print(f"  Code: {actual_line.strip()}")
        
        if not has_null_check:
            issues.append((line_num, actual_line.strip()))
        
        print()
    
    print("-" * 80)
    
    if issues:
        print(f"\n⚠️  WARNING: Found {len(issues)} job_queue accesses without null checks:")
        for line_num, code in issues:
            print(f"  Line {line_num}: {code}")
        return False
    else:
        print("\n✅ All job_queue accesses have proper null checks!")
        return True

if __name__ == "__main__":
    filename = "main.py"
    success = check_job_queue_safety(filename)
    sys.exit(0 if success else 1)
