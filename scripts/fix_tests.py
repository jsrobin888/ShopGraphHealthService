#!/usr/bin/env python3
"""
Script to fix test methods to match the current API.
"""

import re

def fix_test_file():
    with open('tests/test_health_calculation_engine.py', 'r') as f:
        content = f.read()
    
    # Fix calculate_health_score calls to remove base_promotion parameter
    content = re.sub(
        r'engine\.calculate_health_score\(\s*base_promotion,\s*\[([^\]]+)\]\)',
        r'engine.calculate_health_score([\1])',
        content
    )
    
    # Fix calculate_health_score calls with single event
    content = re.sub(
        r'engine\.calculate_health_score\(\s*base_promotion,\s*\[([^]]+)\]\)',
        r'engine.calculate_health_score([\1])',
        content
    )
    
    # Remove confidence and reason from return values
    content = re.sub(
        r'new_score,\s*confidence,\s*reason\s*=\s*engine\.calculate_health_score',
        r'new_score = engine.calculate_health_score',
        content
    )
    
    content = re.sub(
        r'new_score,\s*_,\s*_\s*=\s*engine\.calculate_health_score',
        r'new_score = engine.calculate_health_score',
        content
    )
    
    # Remove assertions for confidence and reason
    content = re.sub(
        r'\s*assert confidence > 0\.0\n\s*assert "[^"]+" in reason',
        '',
        content
    )
    
    content = re.sub(
        r'\s*assert confidence > 0\.0',
        '',
        content
    )
    
    content = re.sub(
        r'\s*assert "[^"]+" in reason',
        '',
        content
    )
    
    # Fix AI processor tests to be async
    content = re.sub(
        r'def test_process_community_tip_([^(]+)\(self, processor([^)]*)\):',
        r'async def test_process_community_tip_\1(self, processor\2):',
        content
    )
    
    content = re.sub(
        r'result = processor\.process_community_tip\(([^)]+)\)',
        r'result = await processor.process_community_tip(\1)',
        content
    )
    
    # Fix dict() calls to model_dump()
    content = re.sub(
        r'\.dict\(\)',
        '.model_dump()',
        content
    )
    
    with open('tests/test_health_calculation_engine.py', 'w') as f:
        f.write(content)

if __name__ == '__main__':
    fix_test_file() 