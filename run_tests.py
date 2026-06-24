import sys
from tests.test_parser import (
    test_security_helpers,
    test_csv_parser,
    test_contact_extractor,
    test_jd_deconstructor_fallback,
    test_workspace_isolation
)

def run_all_tests():
    print("=================================================================")
    print("         AI RECRUITER SYSTEM - BACKEND DIAGNOSTICS")
    print("=================================================================")
    
    tests = [
        ("JWT Auth & Cryptography Security Test", test_security_helpers),
        ("CSV Profiles Spreadsheet Ingestion Parser Test", test_csv_parser),
        ("Contact & Name Regular Expression Extractor Test", test_contact_extractor),
        ("Job Description Intent Deconstructor Fallback Test", test_jd_deconstructor_fallback),
        ("Recruiter Workspace Isolation & Access Control Test", test_workspace_isolation)
    ]
    
    failed = 0
    passed = 0
    
    for name, test_func in tests:
        print(f"Running: {name} ...", end=" ", flush=True)
        try:
            test_func()
            print("[\033[92mSUCCESS\033[0m]")
            passed += 1
        except Exception as e:
            print(f"[\033[91mFAILED\033[0m]")
            print(f" -> Error details: {e}")
            failed += 1
            
    print("=================================================================")
    print(f"Diagnostics complete. Passed: {passed}, Failed: {failed}")
    print("=================================================================")
    
    if failed > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_all_tests()
