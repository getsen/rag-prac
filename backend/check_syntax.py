#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/senthilkumar/git/rag-prac/backend')
try:
    import py_compile
    py_compile.compile('app/chunk/chunk.py', doraise=True)
    print("✓ Syntax OK")
except py_compile.PyCompileError as e:
    print(f"✗ Syntax Error: {e}")
    sys.exit(1)
