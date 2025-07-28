#!/usr/bin/env python3
"""
Script to fix AI processor tests.
"""

import re

def fix_ai_tests():
    with open('tests/test_health_calculation_engine.py', 'r') as f:
        content = f.read()
    
    # Fix all AI processor test calls
    content = re.sub(
        r'result = await processor\.process_community_tip\(([^)]+)\)',
        r'result = await processor.process_community_tip(\1.tipText, \1.userReputation or 50)',
        content
    )
    
    # Fix assertions to use dictionary access
    content = re.sub(
        r'result\.structured_data\.effectiveness',
        r'result["structured_data"]["effectiveness"]',
        content
    )
    
    content = re.sub(
        r'result\.structured_data\.confidence',
        r'result["structured_data"]["confidence"]',
        content
    )
    
    content = re.sub(
        r'result\.health_impact',
        r'result["health_impact"]',
        content
    )
    
    content = re.sub(
        r'result\.conditions',
        r'result["conditions"]',
        content
    )
    
    content = re.sub(
        r'result\.exclusions',
        r'result["exclusions"]',
        content
    )
    
    # Fix the config test for floating point precision
    content = re.sub(
        r'assert config\.total_weight == 1\.0',
        r'assert abs(config.total_weight - 1.0) < 0.0001',
        content
    )
    
    with open('tests/test_health_calculation_engine.py', 'w') as f:
        f.write(content)

if __name__ == '__main__':
    fix_ai_tests() 