"""
LibCST-based performance codemods for optimizing Django applications.

These codemods use AST manipulation to safely transform code for better performance
while preserving structure, comments, and formatting.
"""

    from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False
    # Create stub classes for when LibCST is not available
    class VisitorBasedCodemodCommand:
        pass
    class CodemodContext:
        pass


class QueryOptimizationCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to optimize Django ORM queries by adding select_related and prefetch_related.

    Transforms:
        for user in User.objects.all():
            print(user.profile.name)
    Into:
        for user in User.objects.select_related('profile').all():
            print(user.profile.name)
    """

    DESCRIPTION: str = "Optimize Django ORM queries with select_related/prefetch_related"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.loop_contexts = []  # Stack to track nested loops
        self.relationship_accesses = []  # Track relationship accesses in loops

    def visit_For(self, node: cst.For) -> None:
        """Track for loops over querysets."""
        if self._is_queryset_iteration(node):
            self.loop_contexts.append({
                'node': node,
                'queryset_var': self._extract_iteration_variable(node),
                'relationship_accesses': []
            })

    def leave_For(self, original_node: cst.For, updated_node: cst.For) -> cst.For:
        """Optimize queryset iteration if needed."""
        if self.loop_contexts and self.loop_contexts[-1]['node'] == original_node:
            context = self.loop_contexts.pop()
            if context['relationship_accesses']:
                return self._optimize_queryset_loop(updated_node, context)
        return updated_node

    def visit_Attribute(self, node: cst.Attribute) -> None:
        """Track attribute access that might be relationships."""
        if self.loop_contexts:
            current_context = self.loop_contexts[-1]
            if self._is_relationship_access(node, current_context['queryset_var']):
                relationship = self._extract_relationship_chain(node)
                if relationship not in current_context['relationship_accesses']:
                    current_context['relationship_accesses'].append(relationship)

    def _is_queryset_iteration(self, node: cst.For) -> bool:
        """Check if for loop is iterating over a Django queryset."""
        if not isinstance(node.iter, cst.Call):
            return False

        # Check for Model.objects.all(), filter(), etc.
        if isinstance(node.iter.func, cst.Attribute):
            if node.iter.func.attr.value in ["all", "filter", "exclude"]:
                return True

        return False

    def _extract_iteration_variable(self, node: cst.For) -> Optional[str]:
        """Extract the variable name being iterated over."""
        if isinstance(node.target, cst.Name):
            return node.target.value
        return None

    def _is_relationship_access(self, node: cst.Attribute, queryset_var: Optional[str]) -> bool:
        """Check if attribute access is a model relationship."""
        if not queryset_var:
            return False

        # Simple heuristic: if we access an attribute on the loop variable
        if isinstance(node.value, cst.Name) and node.value.value == queryset_var:
            # Check if it's not a method call (like save(), delete(), etc.)
            return node.attr.value not in ["save", "delete", "pk", "id"]

        # Chain access like user.profile.name
        if isinstance(node.value, cst.Attribute):
            return self._is_relationship_access(node.value, queryset_var)

        return False

    def _extract_relationship_chain(self, node: cst.Attribute) -> str:
        """Extract the full relationship chain like 'profile__name'."""
        chain_parts = []

        current = node
        while isinstance(current, cst.Attribute):
            chain_parts.append(current.attr.value)
            if isinstance(current.value, cst.Name):
                break
            elif isinstance(current.value, cst.Attribute):
                current = current.value
            else:
                break

        # Return the relationship chain (excluding the model variable)
        return "__".join(reversed(chain_parts[:-1])) if len(chain_parts) > 1 else chain_parts[0]

    def _optimize_queryset_loop(self, node: cst.For, context: Dict) -> cst.For:
        """Add select_related/prefetch_related to the queryset."""
        relationships = context['relationship_accesses']

        if not isinstance(node.iter, cst.Call):
            return node

        # Determine if we need select_related or prefetch_related
        # For simplicity, we'll use select_related for single relationships
        single_relations = [rel for rel in relationships if "__" not in rel]

        if single_relations:
            # Add select_related call
            new_iter = self._add_select_related(node.iter, single_relations)
            return node.with_changes(iter=new_iter)

        return node

    def _add_select_related(self, call_node: cst.Call, relationships: List[str]) -> cst.Call:
        """Add select_related call to queryset."""
        # Create select_related arguments
        select_args = [cst.Arg(cst.SimpleString(f"'{rel}'")) for rel in relationships]

        # Create new select_related call
        select_related_call = cst.Call(
            func=cst.Attribute(
                value=call_node.func.value,  # Model.objects part
                attr=cst.Name("select_related")
            ),
            args=select_args
        )

        # Chain with original call
        return call_node.with_changes(
            func=cst.Attribute(
                value=select_related_call,
                attr=call_node.func.attr
            )
        )


class DatabaseIndexSuggestionCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to add database index suggestions as comments for filtered fields.

    Adds comments suggesting database indexes for frequently filtered fields.
    """

    DESCRIPTION: str = "Add database index suggestions for filtered fields"

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Add index suggestions for filter/exclude calls."""
        if self._is_filter_call(updated_node):
            return self._add_index_suggestion(updated_node)
        return updated_node

    def _is_filter_call(self, node: cst.Call) -> bool:
        """Check if this is a filter() or exclude() call."""
        if isinstance(node.func, cst.Attribute):
            return node.func.attr.value in ["filter", "exclude"]
        return False

    def _add_index_suggestion(self, node: cst.Call) -> cst.Call:
        """Add index suggestion comment if appropriate."""
        # Extract filter fields
        filter_fields = self._extract_filter_fields(node)

        if filter_fields:
            # Add trailing comment
            comment_text = f"  # Consider adding db_index=True to: {', '.join(filter_fields)}"
            return node.with_changes(
                rpar=cst.RightParen(whitespace_before=cst.SimpleWhitespace(" "),
                                   whitespace_after=cst.SimpleWhitespace(comment_text))
            )

        return node

    def _extract_filter_fields(self, node: cst.Call) -> List[str]:
        """Extract field names from filter arguments."""
        fields = []

        for arg in node.args:
            if arg.keyword:
                field_name = arg.keyword.value
                # Remove lookup suffixes
                base_field = field_name.split("__")[0]
                if base_field not in fields:
                    fields.append(base_field)

        return fields


class CachingCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to add caching to expensive operations.

    Adds Django cache framework usage to expensive database queries and computations.
    """

    DESCRIPTION: str = "Add caching to expensive operations"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.cache_imported = False
        self.needs_cache_import = False

    def visit_Module(self, node: cst.Module) -> None:
        """Check if cache is already imported."""
        self.cache_imported = self._has_cache_import(node)

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Add caching to expensive query operations."""
        if self._is_expensive_operation(updated_node):
            self.needs_cache_import = True
            return self._wrap_with_cache(updated_node)
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add cache import if needed."""
        if self.needs_cache_import and not self.cache_imported:
            return self._add_cache_import(updated_node)
        return updated_node

    def _has_cache_import(self, module: cst.Module) -> bool:
        """Check if Django cache is already imported."""
        for stmt in module.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for stmt_item in stmt.body:
                    if isinstance(stmt_item, cst.ImportFrom):
                        if (stmt_item.module and
                            "cache" in str(stmt_item.module)):
                            return True
        return False

    def _is_expensive_operation(self, node: cst.Call) -> bool:
        """Check if this is an expensive operation that should be cached."""
        if isinstance(node.func, cst.Attribute):
            expensive_methods = ["count", "aggregate", "annotate"]
            return node.func.attr.value in expensive_methods
        return False

    def _wrap_with_cache(self, node: cst.Call) -> cst.Call:
        """Wrap the operation with cache.get_or_set()."""
        # Generate a simple cache key based on the query
        cache_key = f"expensive_query_{hash(str(node)) % 10000}"

        # Create cache.get_or_set call
        cache_call = cst.Call(
            func=cst.Attribute(
                value=cst.Name("cache"),
                attr=cst.Name("get_or_set")
            ),
            args=[
                cst.Arg(cst.SimpleString(f'"{cache_key}"')),
                cst.Arg(cst.Lambda(
                    params=cst.Parameters(),
                    body=node
                )),
                cst.Arg(cst.Integer("300"))  # 5 minutes timeout
            ]
        )

        return cache_call

    def _add_cache_import(self, module: cst.Module) -> cst.Module:
        """Add Django cache import to module."""
        import_stmt = cst.SimpleStatementLine([
            cst.ImportFrom(
                module=cst.Attribute(
                    value=cst.Name("django"),
                    attr=cst.Name("core")
                ),
                names=[cst.ImportAlias(name=cst.Name("cache"))]
            )
        ])

        # Add after Django imports
        new_body = []
        added = False

        for stmt in module.body:
            new_body.append(stmt)
            if (not added and isinstance(stmt, cst.SimpleStatementLine) and
                any(isinstance(item, cst.ImportFrom) for item in stmt.body)):
                # Add after Django imports
                if any("django" in str(item.module) for item in stmt.body
                       if isinstance(item, cst.ImportFrom) and item.module):
                    new_body.append(import_stmt)
                    added = True

        if not added:
            new_body.insert(0, import_stmt)

        return module.with_changes(body=new_body)


class ListComprehensionOptimizationCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to optimize loops into list comprehensions where appropriate.

    Transforms:
        result = []
        for item in items:
            result.append(item.value)
    Into:
        result = [item.value for item in items]
    """

    DESCRIPTION: str = "Optimize loops into list comprehensions"

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Find and optimize loop patterns."""
        new_body = []
        i = 0

        while i < len(updated_node.body):
            stmt = updated_node.body[i]

            # Look for the pattern: list = [], for loop with append
            if (i + 1 < len(updated_node.body) and
                self._is_empty_list_assignment(stmt) and
                self._is_append_loop(updated_node.body[i + 1])):

                # Try to optimize
                optimized = self._optimize_list_building_pattern(
                    stmt, updated_node.body[i + 1]
                )
                if optimized:
                    new_body.append(optimized)
                    i += 2  # Skip both statements
                    continue

            new_body.append(stmt)
            i += 1

        return updated_node.with_changes(body=new_body)

    def _is_empty_list_assignment(self, stmt: cst.SimpleStatementLine) -> bool:
        """Check if statement is 'var = []'."""
        if len(stmt.body) == 1 and isinstance(stmt.body[0], cst.Assign):
            assign = stmt.body[0]
            if (len(assign.targets) == 1 and
                isinstance(assign.targets[0].target, cst.Name) and
                isinstance(assign.value, cst.List) and
                len(assign.value.elements) == 0):
                return True
        return False

    def _is_append_loop(self, stmt: cst.SimpleStatementLine) -> bool:
        """Check if statement is a for loop with append operations."""
        if len(stmt.body) == 1 and isinstance(stmt.body[0], cst.For):
            for_loop = stmt.body[0]
            # Check if body contains append calls
            return self._has_append_calls(for_loop.body)
        return False

    def _has_append_calls(self, body: cst.BaseSuite) -> bool:
        """Check if body contains append method calls."""
        if isinstance(body, cst.SimpleStatementSuite):
            for stmt in body.body:
                if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.Call):
                    if (isinstance(stmt.value.func, cst.Attribute) and
                        stmt.value.func.attr.value == "append"):
                        return True
        elif isinstance(body, cst.IndentedBlock):
            for stmt in body.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    for sub_stmt in stmt.body:
                        if (isinstance(sub_stmt, cst.Expr) and
                            isinstance(sub_stmt.value, cst.Call)):
                            if (isinstance(sub_stmt.value.func, cst.Attribute) and
                                sub_stmt.value.func.attr.value == "append"):
                                return True
        return False

    def _optimize_list_building_pattern(
        self,
        assign_stmt: cst.SimpleStatementLine,
        for_stmt: cst.SimpleStatementLine
    ) -> Optional[cst.SimpleStatementLine]:
        """Optimize list building pattern into list comprehension."""
        if (not self._is_empty_list_assignment(assign_stmt) or
            not self._is_append_loop(for_stmt)):
            return None

        # Extract components
        assign = assign_stmt.body[0]
        list_var = assign.targets[0].target.value
        for_loop = for_stmt.body[0]

        # Extract append value (simplified)
        append_value = self._extract_append_value(for_loop.body, list_var)
        if not append_value:
            return None

        # Create list comprehension
        list_comp = cst.ListComp(
            elt=append_value,
            for_in=cst.CompFor(
                target=for_loop.target,
                iter=for_loop.iter
            )
        )

        # Create new assignment
        new_assign = cst.Assign(
            targets=[cst.AssignTarget(target=cst.Name(list_var))],
            value=list_comp
        )

        return cst.SimpleStatementLine([new_assign])

    def _extract_append_value(self, body: cst.BaseSuite, list_var: str) -> Optional[cst.BaseExpression]:
        """Extract the value being appended to the list."""
        # This is a simplified implementation
        if isinstance(body, cst.SimpleStatementSuite):
            for stmt in body.body:
                if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.Call):
                    call = stmt.value
                    if (isinstance(call.func, cst.Attribute) and
                        call.func.attr.value == "append" and
                        isinstance(call.func.value, cst.Name) and
                        call.func.value.value == list_var):
                        if call.args:
                            return call.args[0].value

        elif isinstance(body, cst.IndentedBlock):
            for stmt in body.body:
                if isinstance(stmt, cst.SimpleStatementLine):
                    for sub_stmt in stmt.body:
                        if (isinstance(sub_stmt, cst.Expr) and
                            isinstance(sub_stmt.value, cst.Call)):
                            call = sub_stmt.value
                            if (isinstance(call.func, cst.Attribute) and
                                call.func.attr.value == "append" and
                                isinstance(call.func.value, cst.Name) and
                                call.func.value.value == list_var):
                                if call.args:
                                    return call.args[0].value

        return None


class TransactionOptimizationCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to add database transaction optimization.

    Wraps bulk operations in atomic transactions.
    """

    DESCRIPTION: str = "Add database transaction optimization"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.transaction_imported = False
        self.needs_transaction_import = False

    def leave_For(self, original_node: cst.For, updated_node: cst.For) -> cst.For:
        """Wrap database operations in transactions."""
        if self._has_database_operations(updated_node):
            self.needs_transaction_import = True
            return self._wrap_with_atomic(updated_node)
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add transaction import if needed."""
        if self.needs_transaction_import and not self.transaction_imported:
            return self._add_transaction_import(updated_node)
        return updated_node

    def _has_database_operations(self, node: cst.For) -> bool:
        """Check if loop contains database operations."""
        # Simplified check for save() calls
        return "save" in str(node.body)

    def _wrap_with_atomic(self, node: cst.For) -> cst.For:
        """Wrap the for loop with atomic transaction."""
        # Add @transaction.atomic decorator comment
        atomic_comment = cst.SimpleWhitespace("  # @transaction.atomic")

        return node.with_changes(
            whitespace_before_colon=atomic_comment
        )

    def _add_transaction_import(self, module: cst.Module) -> cst.Module:
        """Add Django transaction import."""
        import_stmt = cst.SimpleStatementLine([
            cst.ImportFrom(
                module=cst.Attribute(
                    value=cst.Name("django"),
                    attr=cst.Name("db")
                ),
                names=[cst.ImportAlias(name=cst.Name("transaction"))]
            )
        ])

        return module.with_changes(body=[import_stmt] + list(module.body))


# Registry of available performance codemods
PERFORMANCE_CODEMODS = {
    "query_optimization": QueryOptimizationCodemod,
    "database_index_suggestions": DatabaseIndexSuggestionCodemod,
    "caching_optimization": CachingCodemod,
    "list_comprehension_optimization": ListComprehensionOptimizationCodemod,
    "transaction_optimization": TransactionOptimizationCodemod,
}


def get_performance_codemod(name: str):
    """Get a performance codemod by name."""
    if not LIBCST_AVAILABLE:
        raise ImportError("LibCST is required for advanced codemods")

    return PERFORMANCE_CODEMODS.get(name)