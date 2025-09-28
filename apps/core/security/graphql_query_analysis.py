"""
GraphQL Query Analysis and Security Engine

Advanced security analysis system for GraphQL queries that provides:
- Query complexity analysis and limiting
- Depth limiting and recursion detection
- Query whitelisting and blacklisting
- Introspection control
- Query cost analysis
- Malicious pattern detection
- Performance impact assessment
"""

import re
import json
import time
import hashlib
import logging
from typing import Dict, Any, Optional, List, Set, Tuple
from dataclasses import dataclass
from django.conf import settings
from django.core.cache import cache
from graphql import parse, DocumentNode, visit, Visitor
from graphql.language.ast import (
    OperationDefinitionNode, FieldNode, FragmentDefinitionNode,
    InlineFragmentNode, SelectionSetNode
)
from graphql.error import GraphQLSyntaxError


query_analysis_logger = logging.getLogger('graphql_query_analysis')
security_logger = logging.getLogger('security')


@dataclass
class QueryAnalysisResult:
    """Result of GraphQL query security analysis."""
    is_valid: bool
    complexity_score: int
    depth_score: int
    cost_estimate: float
    security_issues: List[Dict[str, Any]]
    performance_warnings: List[str]
    analysis_time_ms: float
    query_fingerprint: str
    recommendations: List[str]


@dataclass
class SecurityIssue:
    """Represents a security issue found in a GraphQL query."""
    severity: str  # 'low', 'medium', 'high', 'critical'
    issue_type: str
    description: str
    location: Optional[str]
    recommendation: str


class GraphQLQuerySecurityAnalyzer:
    """
    Comprehensive GraphQL query security analyzer.

    Analyzes queries for security vulnerabilities, performance issues,
    and compliance with security policies.
    """

    def __init__(self):
        self.config = self._load_security_config()
        self.malicious_patterns = self._load_malicious_patterns()
        self.query_whitelist = self._load_query_whitelist()
        self.query_blacklist = self._load_query_blacklist()

    def analyze_query(self, query: str, variables: Dict[str, Any] = None,
                     operation_name: str = None, correlation_id: str = None) -> QueryAnalysisResult:
        """
        Perform comprehensive security analysis of a GraphQL query.

        Args:
            query: The GraphQL query string
            variables: Query variables
            operation_name: Specific operation name
            correlation_id: Request correlation ID

        Returns:
            QueryAnalysisResult with analysis findings
        """
        start_time = time.time()

        try:
            # Parse the query
            document = parse(query)
            query_fingerprint = self._generate_query_fingerprint(query, variables)

            # Initialize analysis result
            result = QueryAnalysisResult(
                is_valid=True,
                complexity_score=0,
                depth_score=0,
                cost_estimate=0.0,
                security_issues=[],
                performance_warnings=[],
                analysis_time_ms=0.0,
                query_fingerprint=query_fingerprint,
                recommendations=[]
            )

            # Perform various security analyses
            self._analyze_query_structure(document, result)
            self._analyze_complexity(document, result)
            self._analyze_depth(document, result)
            self._analyze_malicious_patterns(query, result)
            self._analyze_introspection_usage(document, result)
            self._analyze_query_whitelist_blacklist(query, result)
            self._analyze_cost_estimation(document, variables, result)
            self._analyze_performance_impact(document, result)

            # Generate recommendations
            self._generate_recommendations(result)

            # Calculate analysis time
            result.analysis_time_ms = (time.time() - start_time) * 1000

            # Log analysis results
            self._log_analysis_result(result, correlation_id)

            return result

        except GraphQLSyntaxError as e:
            # Handle syntax errors
            result = QueryAnalysisResult(
                is_valid=False,
                complexity_score=0,
                depth_score=0,
                cost_estimate=0.0,
                security_issues=[{
                    'severity': 'high',
                    'issue_type': 'syntax_error',
                    'description': f'GraphQL syntax error: {str(e)}',
                    'location': getattr(e, 'locations', None),
                    'recommendation': 'Fix syntax errors in the GraphQL query'
                }],
                performance_warnings=[],
                analysis_time_ms=(time.time() - start_time) * 1000,
                query_fingerprint='',
                recommendations=['Fix syntax errors before resubmitting']
            )

            query_analysis_logger.warning(
                f"GraphQL syntax error during analysis: {str(e)}, "
                f"Correlation ID: {correlation_id}"
            )

            return result

        except (TypeError, ValidationError, ValueError) as e:
            # Handle unexpected errors
            query_analysis_logger.error(
                f"Unexpected error during query analysis: {str(e)}, "
                f"Correlation ID: {correlation_id}",
                exc_info=True
            )

            # Return safe default result
            result = QueryAnalysisResult(
                is_valid=False,
                complexity_score=float('inf'),
                depth_score=float('inf'),
                cost_estimate=float('inf'),
                security_issues=[{
                    'severity': 'critical',
                    'issue_type': 'analysis_error',
                    'description': 'Failed to analyze query for security issues',
                    'location': None,
                    'recommendation': 'Contact system administrator'
                }],
                performance_warnings=[],
                analysis_time_ms=(time.time() - start_time) * 1000,
                query_fingerprint='',
                recommendations=['Query could not be analyzed safely']
            )

            return result

    def _load_security_config(self) -> Dict[str, Any]:
        """Load security configuration from settings."""
        return getattr(settings, 'GRAPHQL_QUERY_SECURITY_CONFIG', {
            'max_query_depth': 10,
            'max_query_complexity': 1000,
            'max_cost_estimate': 1000.0,
            'enable_introspection_control': True,
            'allow_introspection_in_production': False,
            'enable_query_whitelisting': False,
            'enable_malicious_pattern_detection': True,
            'enable_performance_analysis': True,
            'cache_analysis_results': True,
            'analysis_cache_ttl': 300,  # 5 minutes
            'complexity_weights': {
                'scalar': 1,
                'object': 2,
                'list': 5,
                'connection': 10
            },
            'cost_factors': {
                'base_cost': 1.0,
                'depth_multiplier': 1.5,
                'connection_multiplier': 10.0,
                'argument_multiplier': 1.2
            }
        })

    def _load_malicious_patterns(self) -> List[Dict[str, Any]]:
        """Load malicious query patterns for detection."""
        return getattr(settings, 'GRAPHQL_MALICIOUS_PATTERNS', [
            {
                'name': 'deep_nesting_attack',
                'pattern': r'(\{[^}]*){10,}',  # Deep nesting
                'severity': 'high',
                'description': 'Excessively deep query nesting detected'
            },
            {
                'name': 'large_query_attack',
                'pattern': r'.{10000,}',  # Very large queries
                'severity': 'medium',
                'description': 'Unusually large query detected'
            },
            {
                'name': 'introspection_fishing',
                'pattern': r'__schema.*__type.*fields.*type.*name',
                'severity': 'medium',
                'description': 'Potential schema introspection fishing attempt'
            },
            {
                'name': 'recursive_fragment',
                'pattern': r'fragment\s+\w+.*\.\.\.\w+.*fragment\s+\w+',
                'severity': 'high',
                'description': 'Potentially recursive fragment detected'
            },
            {
                'name': 'alias_overload',
                'pattern': r'(\w+\s*:\s*\w+.*){50,}',  # Many aliases
                'severity': 'medium',
                'description': 'Excessive use of field aliases detected'
            }
        ])

    def _load_query_whitelist(self) -> Set[str]:
        """Load whitelisted query fingerprints."""
        whitelist = getattr(settings, 'GRAPHQL_QUERY_WHITELIST', [])
        return set(whitelist)

    def _load_query_blacklist(self) -> Set[str]:
        """Load blacklisted query fingerprints."""
        blacklist = getattr(settings, 'GRAPHQL_QUERY_BLACKLIST', [])
        return set(blacklist)

    def _generate_query_fingerprint(self, query: str, variables: Dict[str, Any] = None) -> str:
        """Generate a unique fingerprint for the query."""
        # Normalize query by removing whitespace and comments
        normalized = re.sub(r'\s+', ' ', query.strip())
        normalized = re.sub(r'#.*?\n', '', normalized)

        # Include variables in fingerprint
        if variables:
            query_data = {'query': normalized, 'variables': variables}
        else:
            query_data = {'query': normalized}

        query_json = json.dumps(query_data, sort_keys=True)
        return hashlib.sha256(query_json.encode('utf-8')).hexdigest()

    def _analyze_query_structure(self, document: DocumentNode, result: QueryAnalysisResult):
        """Analyze basic query structure for issues."""
        operations = [node for node in document.definitions if isinstance(node, OperationDefinitionNode)]

        if len(operations) == 0:
            result.security_issues.append({
                'severity': 'high',
                'issue_type': 'no_operations',
                'description': 'No valid operations found in query',
                'location': None,
                'recommendation': 'Ensure query contains valid GraphQL operations'
            })
            result.is_valid = False

        if len(operations) > 1:
            result.security_issues.append({
                'severity': 'medium',
                'issue_type': 'multiple_operations',
                'description': 'Multiple operations in single query',
                'location': None,
                'recommendation': 'Use single operation per query for better security'
            })

    def _analyze_complexity(self, document: DocumentNode, result: QueryAnalysisResult):
        """Analyze query complexity."""
        complexity_analyzer = ComplexityAnalyzer(self.config['complexity_weights'])
        visit(document, complexity_analyzer)

        result.complexity_score = complexity_analyzer.get_complexity()

        if result.complexity_score > self.config['max_query_complexity']:
            result.security_issues.append({
                'severity': 'high',
                'issue_type': 'excessive_complexity',
                'description': f'Query complexity {result.complexity_score} exceeds limit {self.config["max_query_complexity"]}',
                'location': None,
                'recommendation': 'Reduce query complexity by limiting nested fields'
            })
            result.is_valid = False

    def _analyze_depth(self, document: DocumentNode, result: QueryAnalysisResult):
        """Analyze query depth."""
        depth_analyzer = DepthAnalyzer()
        visit(document, depth_analyzer)

        result.depth_score = depth_analyzer.get_max_depth()

        if result.depth_score > self.config['max_query_depth']:
            result.security_issues.append({
                'severity': 'high',
                'issue_type': 'excessive_depth',
                'description': f'Query depth {result.depth_score} exceeds limit {self.config["max_query_depth"]}',
                'location': None,
                'recommendation': 'Reduce query nesting depth'
            })
            result.is_valid = False

    def _analyze_malicious_patterns(self, query: str, result: QueryAnalysisResult):
        """Analyze query for malicious patterns."""
        if not self.config['enable_malicious_pattern_detection']:
            return

        for pattern_config in self.malicious_patterns:
            pattern = pattern_config['pattern']
            if re.search(pattern, query, re.IGNORECASE | re.DOTALL):
                result.security_issues.append({
                    'severity': pattern_config['severity'],
                    'issue_type': pattern_config['name'],
                    'description': pattern_config['description'],
                    'location': None,
                    'recommendation': f'Avoid {pattern_config["name"]} patterns in queries'
                })

                if pattern_config['severity'] in ['high', 'critical']:
                    result.is_valid = False

    def _analyze_introspection_usage(self, document: DocumentNode, result: QueryAnalysisResult):
        """Analyze introspection usage."""
        if not self.config['enable_introspection_control']:
            return

        introspection_analyzer = IntrospectionAnalyzer()
        visit(document, introspection_analyzer)

        if introspection_analyzer.has_introspection():
            # Check if introspection is allowed
            is_production = not getattr(settings, 'DEBUG', False)
            allow_introspection = self.config['allow_introspection_in_production']

            if is_production and not allow_introspection:
                result.security_issues.append({
                    'severity': 'medium',
                    'issue_type': 'introspection_disabled',
                    'description': 'Introspection queries are disabled in production',
                    'location': None,
                    'recommendation': 'Use documented API instead of introspection'
                })
                result.is_valid = False
            else:
                result.performance_warnings.append('Introspection queries can be expensive')

    def _analyze_query_whitelist_blacklist(self, query: str, result: QueryAnalysisResult):
        """Check query against whitelist and blacklist."""
        if self.config['enable_query_whitelisting'] and self.query_whitelist:
            if result.query_fingerprint not in self.query_whitelist:
                result.security_issues.append({
                    'severity': 'high',
                    'issue_type': 'query_not_whitelisted',
                    'description': 'Query is not in the approved whitelist',
                    'location': None,
                    'recommendation': 'Use only pre-approved queries'
                })
                result.is_valid = False

        if result.query_fingerprint in self.query_blacklist:
            result.security_issues.append({
                'severity': 'critical',
                'issue_type': 'query_blacklisted',
                'description': 'Query matches a blacklisted pattern',
                'location': None,
                'recommendation': 'This query is explicitly forbidden'
            })
            result.is_valid = False

    def _analyze_cost_estimation(self, document: DocumentNode, variables: Dict[str, Any], result: QueryAnalysisResult):
        """Estimate query execution cost."""
        cost_analyzer = CostAnalyzer(self.config['cost_factors'])
        visit(document, cost_analyzer)

        result.cost_estimate = cost_analyzer.get_cost_estimate(variables or {})

        if result.cost_estimate > self.config['max_cost_estimate']:
            result.security_issues.append({
                'severity': 'high',
                'issue_type': 'excessive_cost',
                'description': f'Estimated query cost {result.cost_estimate:.2f} exceeds limit {self.config["max_cost_estimate"]}',
                'location': None,
                'recommendation': 'Reduce query scope or use pagination'
            })
            result.is_valid = False

    def _analyze_performance_impact(self, document: DocumentNode, result: QueryAnalysisResult):
        """Analyze potential performance impact."""
        if not self.config['enable_performance_analysis']:
            return

        performance_analyzer = PerformanceAnalyzer()
        visit(document, performance_analyzer)

        warnings = performance_analyzer.get_warnings()
        result.performance_warnings.extend(warnings)

    def _generate_recommendations(self, result: QueryAnalysisResult):
        """Generate recommendations based on analysis."""
        if result.complexity_score > self.config['max_query_complexity'] * 0.8:
            result.recommendations.append('Consider breaking down complex queries into smaller parts')

        if result.depth_score > self.config['max_query_depth'] * 0.8:
            result.recommendations.append('Use pagination or fragment spreading to reduce nesting')

        if len(result.security_issues) > 0:
            result.recommendations.append('Review and fix security issues before production use')

        if len(result.performance_warnings) > 0:
            result.recommendations.append('Optimize query for better performance')

    def _log_analysis_result(self, result: QueryAnalysisResult, correlation_id: str):
        """Log query analysis results."""
        log_data = {
            'correlation_id': correlation_id,
            'query_fingerprint': result.query_fingerprint,
            'is_valid': result.is_valid,
            'complexity_score': result.complexity_score,
            'depth_score': result.depth_score,
            'cost_estimate': result.cost_estimate,
            'security_issues_count': len(result.security_issues),
            'performance_warnings_count': len(result.performance_warnings),
            'analysis_time_ms': result.analysis_time_ms
        }

        if result.is_valid:
            query_analysis_logger.info('GraphQL query analysis passed', extra=log_data)
        else:
            security_logger.warning('GraphQL query analysis failed', extra=log_data)

            # Log high-severity issues separately
            for issue in result.security_issues:
                if issue['severity'] in ['high', 'critical']:
                    security_logger.error(
                        f"Critical GraphQL security issue: {issue['issue_type']} - {issue['description']}",
                        extra={**log_data, 'security_issue': issue}
                    )


class ComplexityAnalyzer(Visitor):
    """Visitor to analyze GraphQL query complexity."""

    def __init__(self, complexity_weights: Dict[str, int]):
        self.complexity = 0
        self.weights = complexity_weights

    def enter_field(self, node: FieldNode, *_):
        """Calculate complexity when entering a field."""
        # Base complexity for each field
        self.complexity += self.weights.get('scalar', 1)

        # Additional complexity for fields with arguments
        if node.arguments:
            self.complexity += len(node.arguments) * self.weights.get('object', 2)

    def get_complexity(self) -> int:
        """Get calculated complexity score."""
        return self.complexity


class DepthAnalyzer(Visitor):
    """Visitor to analyze GraphQL query depth."""

    def __init__(self):
        self.max_depth = 0
        self.current_depth = 0

    def enter_selection_set(self, node: SelectionSetNode, *_):
        """Track depth when entering selection sets."""
        self.current_depth += 1
        self.max_depth = max(self.max_depth, self.current_depth)

    def leave_selection_set(self, node: SelectionSetNode, *_):
        """Track depth when leaving selection sets."""
        self.current_depth -= 1

    def get_max_depth(self) -> int:
        """Get maximum depth found."""
        return self.max_depth


class IntrospectionAnalyzer(Visitor):
    """Visitor to detect introspection queries."""

    def __init__(self):
        self.has_introspection_fields = False

    def enter_field(self, node: FieldNode, *_):
        """Check for introspection fields."""
        field_name = node.name.value
        if field_name.startswith('__'):
            self.has_introspection_fields = True

    def has_introspection(self) -> bool:
        """Check if query contains introspection fields."""
        return self.has_introspection_fields


class CostAnalyzer(Visitor):
    """Visitor to estimate query execution cost."""

    def __init__(self, cost_factors: Dict[str, float]):
        self.cost = 0.0
        self.factors = cost_factors
        self.depth = 0

    def enter_field(self, node: FieldNode, *_):
        """Calculate cost when entering fields."""
        base_cost = self.factors.get('base_cost', 1.0)
        depth_multiplier = self.factors.get('depth_multiplier', 1.5)

        # Base cost with depth multiplier
        field_cost = base_cost * (depth_multiplier ** self.depth)

        # Additional cost for arguments
        if node.arguments:
            arg_multiplier = self.factors.get('argument_multiplier', 1.2)
            field_cost *= (arg_multiplier ** len(node.arguments))

        self.cost += field_cost

    def enter_selection_set(self, node: SelectionSetNode, *_):
        """Track depth for cost calculation."""
        self.depth += 1

    def leave_selection_set(self, node: SelectionSetNode, *_):
        """Track depth for cost calculation."""
        self.depth -= 1

    def get_cost_estimate(self, variables: Dict[str, Any]) -> float:
        """Get estimated execution cost."""
        # Adjust cost based on variables (e.g., pagination limits)
        variable_multiplier = 1.0

        # Check for pagination variables that might increase cost
        for var_name, var_value in variables.items():
            if var_name.lower() in ['first', 'last', 'limit'] and isinstance(var_value, (int, float)):
                if var_value > 100:  # Large pagination
                    variable_multiplier *= 2.0

        return self.cost * variable_multiplier


class PerformanceAnalyzer(Visitor):
    """Visitor to analyze potential performance issues."""

    def __init__(self):
        self.warnings = []
        self.field_count = 0
        self.connection_count = 0

    def enter_field(self, node: FieldNode, *_):
        """Analyze fields for performance issues."""
        self.field_count += 1
        field_name = node.name.value

        # Check for connection fields (pagination)
        if field_name.endswith('Connection') or 'edges' in field_name.lower():
            self.connection_count += 1

        # Check for potentially expensive fields
        expensive_patterns = ['search', 'all', 'list', 'find']
        if any(pattern in field_name.lower() for pattern in expensive_patterns):
            if not node.arguments:
                self.warnings.append(f'Field "{field_name}" may be expensive without filtering arguments')

    def get_warnings(self) -> List[str]:
        """Get performance warnings."""
        if self.field_count > 50:
            self.warnings.append(f'Query requests {self.field_count} fields, consider reducing scope')

        if self.connection_count > 5:
            self.warnings.append(f'Query contains {self.connection_count} connections, may impact performance')

        return self.warnings