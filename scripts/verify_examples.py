#!/usr/bin/env python3
"""
Verification script for Example Roadmaps feature.

This script tests:
1. Data file validity (JSON structure)
2. Import success for all new modules
3. Data loading functionality
4. Example roadmap structure validation
"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_json_files():
    """Test that all JSON files are valid."""
    print("Testing JSON file validity...")
    examples_dir = Path(__file__).parent.parent / "examples" / "roadmaps"

    files = ["metadata.json", "react_beginner_zh_tw.json",
             "python_data_science_en.json", "web_fullstack_beginner_zh_tw.json"]

    for filename in files:
        filepath = examples_dir / filename
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                json.load(f)
            print(f"  ✓ {filename} is valid JSON")
        except Exception as e:
            print(f"  ✗ {filename} is INVALID: {e}")
            return False

    return True


def test_imports():
    """Test that all new modules can be imported."""
    print("\nTesting imports...")

    try:
        from coursegen.ui.utils.example_loader import (
            load_metadata, load_example_roadmap, get_example_metadata
        )
        print("  ✓ example_loader imports successful")
    except Exception as e:
        print(f"  ✗ example_loader import failed: {e}")
        return False

    try:
        from coursegen.ui.components.example_browser import render_example_browser
        print("  ✓ example_browser imports successful")
    except Exception as e:
        print(f"  ✗ example_browser import failed: {e}")
        return False

    try:
        from coursegen.ui.components.example_banner import render_example_banner
        print("  ✓ example_banner imports successful")
    except Exception as e:
        print(f"  ✗ example_banner import failed: {e}")
        return False

    return True


def test_data_loading():
    """Test data loading functions."""
    print("\nTesting data loading...")

    try:
        from coursegen.ui.utils.example_loader import (
            load_metadata, load_example_roadmap
        )

        # Load metadata
        metadata = load_metadata()
        examples = metadata.get("examples", [])
        print(f"  ✓ Loaded {len(examples)} examples from metadata")

        if len(examples) == 0:
            print("  ✗ No examples found in metadata")
            return False

        # Load each example
        for ex in examples:
            roadmap = load_example_roadmap(ex["id"])
            if roadmap is None:
                print(f"  ✗ Failed to load example: {ex['id']}")
                return False
            print(f"  ✓ Loaded example: {ex['display_name']}")

        return True

    except Exception as e:
        print(f"  ✗ Data loading failed: {e}")
        return False


def test_roadmap_structure():
    """Test that roadmap structures are valid."""
    print("\nTesting roadmap structure...")

    try:
        from coursegen.ui.utils.example_loader import (
            load_metadata, load_example_roadmap
        )

        metadata = load_metadata()
        examples = metadata.get("examples", [])

        for ex in examples:
            roadmap = load_example_roadmap(ex["id"])

            # Check required fields
            if "topic" not in roadmap:
                print(f"  ✗ {ex['id']}: Missing 'topic' field")
                return False

            if "nodes" not in roadmap:
                print(f"  ✗ {ex['id']}: Missing 'nodes' field")
                return False

            nodes = roadmap["nodes"]

            # Check node structure
            for node in nodes:
                required = ["id", "label", "description", "dependencies"]
                for field in required:
                    if field not in node:
                        print(f"  ✗ {ex['id']}: Node {node.get('id', '?')} missing '{field}'")
                        return False

            # Check dependencies are valid
            node_ids = {node["id"] for node in nodes}
            for node in nodes:
                for dep in node["dependencies"]:
                    if dep not in node_ids:
                        print(f"  ✗ {ex['id']}: Invalid dependency '{dep}' in node {node['id']}")
                        return False

            print(f"  ✓ {ex['display_name']}: {len(nodes)} nodes, valid structure")

        return True

    except Exception as e:
        print(f"  ✗ Structure validation failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Example Roadmaps Feature Verification")
    print("=" * 60)

    tests = [
        ("JSON File Validity", test_json_files),
        ("Module Imports", test_imports),
        ("Data Loading", test_data_loading),
        ("Roadmap Structure", test_roadmap_structure),
    ]

    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)

    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
        if not result:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n✅ All tests passed! The Example Roadmaps feature is ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
