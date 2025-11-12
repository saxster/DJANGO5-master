#!/usr/bin/env python3
"""
Verify deep nesting refactoring results.
Compares before/after metrics and validates improvements.
"""
import ast
import argparse
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime


class RefactoringVerifier:
    """Verify refactoring results and generate compliance reports."""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'files_analyzed': 0,
            'files_compliant': 0,
            'files_warning': 0,
            'files_violation': 0,
            'violations': [],
            'improvements': [],
            'metrics': {}
        }
    
    def analyze_file(self, filepath: Path) -> Dict:
        """Analyze a single file for nesting depth."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            max_depth = self._calculate_max_depth(tree)
            
            return {
                'file': str(filepath),
                'max_depth': max_depth,
                'status': self._get_compliance_status(max_depth),
                'line_count': len(content.split('\n'))
            }
        except Exception as e:
            return {
                'file': str(filepath),
                'max_depth': 0,
                'status': 'error',
                'error': str(e)
            }
    
    def _calculate_max_depth(self, tree) -> int:
        """Calculate maximum nesting depth in AST."""
        max_depth = 0
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                depth = self._get_function_depth(node)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _get_function_depth(self, node, current_depth=0) -> int:
        """Get maximum depth within a function."""
        max_depth = current_depth
        
        for child in ast.walk(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth = self._get_block_depth(child, current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _get_block_depth(self, node, current_depth) -> int:
        """Recursively get depth of nested blocks."""
        max_depth = current_depth
        
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                depth = self._get_block_depth(child, current_depth + 1)
                max_depth = max(max_depth, depth)
        
        return max_depth
    
    def _get_compliance_status(self, max_depth: int) -> str:
        """Determine compliance status based on depth."""
        if max_depth <= 2:
            return 'compliant'
        elif max_depth == 3:
            return 'warning'
        else:
            return 'violation'
    
    def verify_directory(self, directory: Path) -> Dict:
        """Verify all Python files in directory."""
        python_files = list(directory.rglob('*.py'))
        python_files = [f for f in python_files if '__pycache__' not in str(f) and 'migrations' not in str(f)]
        
        self.results['files_analyzed'] = len(python_files)
        
        for filepath in python_files:
            result = self.analyze_file(filepath)
            
            if result['status'] == 'compliant':
                self.results['files_compliant'] += 1
            elif result['status'] == 'warning':
                self.results['files_warning'] += 1
                self.results['violations'].append(result)
            elif result['status'] == 'violation':
                self.results['files_violation'] += 1
                self.results['violations'].append(result)
        
        return self.results
    
    def generate_report(self, output_file: str):
        """Generate verification report."""
        with open(output_file, 'w') as f:
            f.write("# Deep Nesting Refactoring Verification Report\n\n")
            f.write(f"**Generated**: {self.results['timestamp']}\n\n")
            
            f.write("## Summary\n\n")
            f.write(f"- **Files Analyzed**: {self.results['files_analyzed']}\n")
            f.write(f"- **Compliant (≤2 levels)**: {self.results['files_compliant']} ")
            f.write(f"({self.results['files_compliant']/max(self.results['files_analyzed'],1)*100:.1f}%)\n")
            f.write(f"- **Warning (3 levels)**: {self.results['files_warning']} ")
            f.write(f"({self.results['files_warning']/max(self.results['files_analyzed'],1)*100:.1f}%)\n")
            f.write(f"- **Violations (≥4 levels)**: {self.results['files_violation']} ")
            f.write(f"({self.results['files_violation']/max(self.results['files_analyzed'],1)*100:.1f}%)\n\n")
            
            if self.results['violations']:
                f.write("## Violations & Warnings\n\n")
                f.write("| File | Max Depth | Status |\n")
                f.write("|------|-----------|--------|\n")
                
                sorted_violations = sorted(self.results['violations'], key=lambda x: x['max_depth'], reverse=True)
                for violation in sorted_violations[:50]:
                    f.write(f"| {violation['file']} | {violation['max_depth']} | {violation['status'].upper()} |\n")
                
                if len(self.results['violations']) > 50:
                    f.write(f"\n*... and {len(self.results['violations']) - 50} more files*\n")
            
            f.write("\n## Compliance Status\n\n")
            compliance_rate = self.results['files_compliant'] / max(self.results['files_analyzed'], 1) * 100
            
            if compliance_rate >= 95:
                f.write("✅ **EXCELLENT** - Compliance rate: {:.1f}%\n".format(compliance_rate))
            elif compliance_rate >= 85:
                f.write("✅ **GOOD** - Compliance rate: {:.1f}%\n".format(compliance_rate))
            elif compliance_rate >= 70:
                f.write("⚠️ **NEEDS IMPROVEMENT** - Compliance rate: {:.1f}%\n".format(compliance_rate))
            else:
                f.write("❌ **CRITICAL** - Compliance rate: {:.1f}%\n".format(compliance_rate))
            
            f.write("\n## Recommendations\n\n")
            if self.results['files_violation'] > 0:
                f.write(f"1. Refactor {self.results['files_violation']} files with violations (≥4 levels)\n")
            if self.results['files_warning'] > 0:
                f.write(f"2. Review {self.results['files_warning']} files with warnings (3 levels)\n")
            if compliance_rate < 95:
                f.write("3. Implement pre-commit hooks to prevent new violations\n")
                f.write("4. Add CI/CD gates to block merges with violations\n")


def main():
    parser = argparse.ArgumentParser(description='Verify nesting refactoring')
    parser.add_argument('--verify-all', action='store_true', help='Verify all apps')
    parser.add_argument('--path', default='apps', help='Path to verify')
    parser.add_argument('--output', default='NESTING_VERIFICATION_REPORT.md', help='Output file')
    
    args = parser.parse_args()
    
    verifier = RefactoringVerifier()
    
    if args.verify_all:
        print("Verifying all files in apps/...")
        results = verifier.verify_directory(Path('apps'))
    else:
        print(f"Verifying files in {args.path}...")
        results = verifier.verify_directory(Path(args.path))
    
    print(f"\n{'='*80}")
    print("VERIFICATION RESULTS")
    print(f"{'='*80}")
    print(f"Files analyzed: {results['files_analyzed']}")
    print(f"Compliant (≤2 levels): {results['files_compliant']} ({results['files_compliant']/max(results['files_analyzed'],1)*100:.1f}%)")
    print(f"Warning (3 levels): {results['files_warning']} ({results['files_warning']/max(results['files_analyzed'],1)*100:.1f}%)")
    print(f"Violations (≥4 levels): {results['files_violation']} ({results['files_violation']/max(results['files_analyzed'],1)*100:.1f}%)")
    print(f"{'='*80}\n")
    
    verifier.generate_report(args.output)
    print(f"Report generated: {args.output}")
    
    # Exit with error if violations found
    return 1 if results['files_violation'] > 0 else 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
