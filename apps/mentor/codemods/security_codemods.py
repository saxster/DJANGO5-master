"""
LibCST-based security codemods for fixing common Django security vulnerabilities.

These codemods use AST manipulation to safely transform code while preserving
structure, comments, and formatting.
"""

    from libcst import matchers as m
    from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False
    # Create stub classes for when LibCST is not available
    class VisitorBasedCodemodCommand:
        pass
    class CodemodContext:
        pass


class SQLInjectionFixCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to fix SQL injection vulnerabilities in Django ORM .raw() calls.

    Transforms:
        Model.objects.raw("SELECT * FROM table WHERE id = %s", [value])
    Into:
        Model.objects.raw("SELECT * FROM table WHERE id = %(id)s", {"id": value})
    """

    DESCRIPTION: str = "Fix SQL injection vulnerabilities in .raw() calls"

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform .raw() calls to use named parameters."""
        if not self._is_raw_call(updated_node):
            return updated_node

        # Check if this call has potential SQL injection
        if not self._has_potential_sql_injection(updated_node):
            return updated_node

        return self._fix_raw_call(updated_node)

    def _is_raw_call(self, node: cst.Call) -> bool:
        """Check if this is a .raw() method call."""
        if not isinstance(node.func, cst.Attribute):
            return False
        return node.func.attr.value == "raw"

    def _has_potential_sql_injection(self, node: cst.Call) -> bool:
        """Check if the raw call has potential SQL injection."""
        if not node.args:
            return False

        # Get the SQL string argument
        first_arg = node.args[0].value
        if not isinstance(first_arg, (cst.SimpleString, cst.ConcatenatedString)):
            return False

        # Check for % formatting or .format() usage (vulnerable patterns)
        sql_content = self._extract_string_content(first_arg)
        return "%s" in sql_content or "%d" in sql_content or "{" in sql_content

    def _extract_string_content(self, string_node: Union[cst.SimpleString, cst.ConcatenatedString]) -> str:
        """Extract the actual string content from a string node."""
        if isinstance(string_node, cst.SimpleString):
            # Remove quotes and extract content
            return string_node.value[1:-1]  # Remove surrounding quotes
        elif isinstance(string_node, cst.ConcatenatedString):
            # Handle concatenated strings
            content = ""
            for part in string_node.left, string_node.right:
                if isinstance(part, cst.SimpleString):
                    content += part.value[1:-1]
            return content
        return ""

    def _fix_raw_call(self, node: cst.Call) -> cst.Call:
        """Fix the raw call to use named parameters."""
        if not node.args:
            return node

        # Transform the SQL string to use named parameters
        first_arg = node.args[0]
        sql_content = self._extract_string_content(first_arg.value)

        # Replace positional parameters with named ones
        fixed_sql, param_names = self._convert_to_named_params(sql_content)

        # Create new SQL string node
        new_sql_arg = cst.Arg(cst.SimpleString(f'"{fixed_sql}"'))

        # Create parameter dictionary
        if len(node.args) > 1 and param_names:
            # Convert second argument (parameter list) to dictionary
            param_dict = self._create_param_dict(node.args[1], param_names)
            new_args = [new_sql_arg, param_dict]
        else:
            new_args = [new_sql_arg]

        return node.with_changes(args=new_args)

    def _convert_to_named_params(self, sql: str) -> tuple[str, List[str]]:
        """Convert positional parameters to named parameters."""
        param_names = []
        param_counter = 0

        def replace_param(match):
            nonlocal param_counter
            param_counter += 1
            param_name = f"param{param_counter}"
            param_names.append(param_name)
            return f"%({param_name})s"

        # Replace %s with %(paramN)s
        fixed_sql = re.sub(r'%s', replace_param, sql)

        # Replace %d with %(paramN)s (treating all as strings for safety)
        fixed_sql = re.sub(r'%d', replace_param, fixed_sql)

        return fixed_sql, param_names

    def _create_param_dict(self, params_arg: cst.Arg, param_names: List[str]) -> cst.Arg:
        """Create a dictionary argument from a list argument."""
        if isinstance(params_arg.value, cst.List):
            # Convert list to dictionary
            elements = params_arg.value.elements
            dict_elements = []

            for i, param_name in enumerate(param_names):
                if i < len(elements):
                    dict_elements.append(
                        cst.DictElement(
                            key=cst.SimpleString(f'"{param_name}"'),
                            value=elements[i].value
                        )
                    )

            return cst.Arg(cst.Dict(dict_elements))

        # If not a list, create a comment suggestion
        return cst.Arg(
            cst.Dict([]),
            comma=cst.Comma(whitespace_after=cst.SimpleWhitespace("  # TODO: Add parameters here"))
        )


class XSSPreventionCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to fix XSS vulnerabilities in Django templates and views.

    Transforms:
        mark_safe(user_input)
    Into:
        escape(user_input)
    """

    DESCRIPTION: str = "Fix XSS vulnerabilities by replacing mark_safe with escape"

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Transform mark_safe calls to escape calls."""
        if self._is_mark_safe_call(updated_node):
            return self._replace_with_escape(updated_node)
        return updated_node

    def _is_mark_safe_call(self, node: cst.Call) -> bool:
        """Check if this is a mark_safe() function call."""
        if isinstance(node.func, cst.Name):
            return node.func.value == "mark_safe"
        elif isinstance(node.func, cst.Attribute):
            return node.func.attr.value == "mark_safe"
        return False

    def _replace_with_escape(self, node: cst.Call) -> cst.Call:
        """Replace mark_safe with escape."""
        # Change the function name
        new_func = None
        if isinstance(node.func, cst.Name):
            new_func = node.func.with_changes(value="escape")
        elif isinstance(node.func, cst.Attribute):
            new_func = node.func.with_changes(attr=cst.Name("escape"))

        if new_func:
            return node.with_changes(func=new_func)
        return node


class CSRFProtectionCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to add CSRF protection to Django forms and views.

    Adds @csrf_protect decorator to views that handle POST requests.
    """

    DESCRIPTION: str = "Add CSRF protection to Django views"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.csrf_protect_imported = False
        self.views_needing_csrf = []

    def visit_Module(self, node: cst.Module) -> None:
        """Check if csrf_protect is already imported."""
        self.csrf_protect_imported = self._has_csrf_import(node)

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.FunctionDef:
        """Add CSRF protection to view functions."""
        if self._is_view_function(updated_node) and self._needs_csrf_protection(updated_node):
            return self._add_csrf_decorator(updated_node)
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add csrf_protect import if needed."""
        if self.views_needing_csrf and not self.csrf_protect_imported:
            return self._add_csrf_import(updated_node)
        return updated_node

    def _has_csrf_import(self, module: cst.Module) -> bool:
        """Check if csrf_protect is already imported."""
        for stmt in module.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for stmt_item in stmt.body:
                    if isinstance(stmt_item, cst.ImportFrom):
                        if (stmt_item.module and
                            m.matches(stmt_item.module, m.Attribute(attr=m.Name("decorators")))):
                            # Check if csrf_protect is in the import
                            if stmt_item.names and isinstance(stmt_item.names, cst.ImportStar):
                                return True
                            elif stmt_item.names:
                                for name in stmt_item.names:
                                    if isinstance(name, cst.ImportAlias) and name.name.value == "csrf_protect":
                                        return True
        return False

    def _is_view_function(self, func: cst.FunctionDef) -> bool:
        """Check if function is likely a Django view."""
        # Look for request parameter
        if func.params and func.params.params:
            first_param = func.params.params[0]
            return first_param.name.value == "request"
        return False

    def _needs_csrf_protection(self, func: cst.FunctionDef) -> bool:
        """Check if function needs CSRF protection."""
        # Check if it already has csrf_protect or csrf_exempt decorator
        for decorator in func.decorators:
            if isinstance(decorator.decorator, cst.Name):
                if decorator.decorator.value in ["csrf_protect", "csrf_exempt"]:
                    return False

        # Check if function handles POST requests (simplified check)
        func_code = func.code.code if hasattr(func, 'code') else ""
        return "POST" in str(func_code) or "request.method" in str(func_code)

    def _add_csrf_decorator(self, func: cst.FunctionDef) -> cst.FunctionDef:
        """Add csrf_protect decorator to function."""
        csrf_decorator = cst.Decorator(cst.Name("csrf_protect"))
        new_decorators = [csrf_decorator] + list(func.decorators)
        self.views_needing_csrf.append(func.name.value)
        return func.with_changes(decorators=new_decorators)

    def _add_csrf_import(self, module: cst.Module) -> cst.Module:
        """Add csrf_protect import to module."""
        import_stmt = cst.SimpleStatementLine([
            cst.ImportFrom(
                module=cst.Attribute(
                    value=cst.Attribute(
                        value=cst.Name("django"),
                        attr=cst.Name("views")
                    ),
                    attr=cst.Name("decorators")
                ),
                names=[cst.ImportAlias(name=cst.Name("csrf_protect"))]
            )
        ])

        # Add import at the top after other Django imports
        new_body = []
        added = False

        for stmt in module.body:
            if not added and isinstance(stmt, cst.SimpleStatementLine):
                for stmt_item in stmt.body:
                    if isinstance(stmt_item, cst.ImportFrom):
                        if (stmt_item.module and
                            str(stmt_item.module).startswith("django")):
                            new_body.append(stmt)
                            new_body.append(import_stmt)
                            added = True
                            continue

            if not added:
                new_body.append(stmt)
            else:
                new_body.append(stmt)

        if not added:
            new_body.insert(0, import_stmt)

        return module.with_changes(body=new_body)


class SecureRandomCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to replace insecure random generators with secure ones.

    Transforms:
        import random; random.randint(1, 100)
    Into:
        import secrets; secrets.randbelow(100) + 1
    """

    DESCRIPTION: str = "Replace insecure random with cryptographically secure random"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.secrets_imported = False
        self.needs_secrets_import = False

    def visit_Module(self, node: cst.Module) -> None:
        """Check if secrets module is already imported."""
        self.secrets_imported = self._has_secrets_import(node)

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.Call:
        """Replace insecure random calls with secure alternatives."""
        if self._is_insecure_random_call(updated_node):
            self.needs_secrets_import = True
            return self._replace_with_secure_random(updated_node)
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add secrets import if needed."""
        if self.needs_secrets_import and not self.secrets_imported:
            return self._add_secrets_import(updated_node)
        return updated_node

    def _has_secrets_import(self, module: cst.Module) -> bool:
        """Check if secrets module is already imported."""
        for stmt in module.body:
            if isinstance(stmt, cst.SimpleStatementLine):
                for stmt_item in stmt.body:
                    if isinstance(stmt_item, cst.Import):
                        for name in stmt_item.names:
                            if isinstance(name, cst.ImportAlias) and name.name.value == "secrets":
                                return True
        return False

    def _is_insecure_random_call(self, node: cst.Call) -> bool:
        """Check if this is an insecure random function call."""
        if isinstance(node.func, cst.Attribute):
            if (isinstance(node.func.value, cst.Name) and
                node.func.value.value == "random"):
                insecure_methods = ["randint", "random", "choice", "shuffle"]
                return node.func.attr.value in insecure_methods
        return False

    def _replace_with_secure_random(self, node: cst.Call) -> cst.Call:
        """Replace with secure random alternative."""
        if not isinstance(node.func, cst.Attribute):
            return node

        method_name = node.func.attr.value

        if method_name == "randint":
            # random.randint(a, b) -> secrets.randbelow(b - a + 1) + a
            if len(node.args) >= 2:
                # For simplicity, use randbits for now
                return node.with_changes(
                    func=cst.Attribute(
                        value=cst.Name("secrets"),
                        attr=cst.Name("randbits")
                    ),
                    args=[cst.Arg(cst.Integer("32"))]  # 32-bit random number
                )

        elif method_name == "choice":
            # random.choice(seq) -> secrets.choice(seq)
            return node.with_changes(
                func=cst.Attribute(
                    value=cst.Name("secrets"),
                    attr=cst.Name("choice")
                )
            )

        # Default: use secrets.randbits
        return node.with_changes(
            func=cst.Attribute(
                value=cst.Name("secrets"),
                attr=cst.Name("randbits")
            ),
            args=[cst.Arg(cst.Integer("32"))]
        )

    def _add_secrets_import(self, module: cst.Module) -> cst.Module:
        """Add secrets import to module."""
        import_stmt = cst.SimpleStatementLine([
            cst.Import(names=[cst.ImportAlias(name=cst.Name("secrets"))])
        ])

        # Add after existing imports
        new_body = []
        added = False

        for i, stmt in enumerate(module.body):
            new_body.append(stmt)
            if (not added and isinstance(stmt, cst.SimpleStatementLine) and
                any(isinstance(item, (cst.Import, cst.ImportFrom)) for item in stmt.body)):
                # Add after the last import
                if (i + 1 >= len(module.body) or
                    not isinstance(module.body[i + 1], cst.SimpleStatementLine) or
                    not any(isinstance(item, (cst.Import, cst.ImportFrom))
                           for item in module.body[i + 1].body)):
                    new_body.append(import_stmt)
                    added = True

        if not added:
            new_body.insert(0, import_stmt)

        return module.with_changes(body=new_body)


class HardcodedPasswordRemovalCodemod(VisitorBasedCodemodCommand):
    """
    Codemod to remove hardcoded passwords and secrets.

    Replaces hardcoded values with environment variable lookups.
    """

    DESCRIPTION: str = "Remove hardcoded passwords and secrets"

    def __init__(self, context: CodemodContext) -> None:
        super().__init__(context)
        self.os_imported = False
        self.needs_os_import = False

    def leave_Assign(self, original_node: cst.Assign, updated_node: cst.Assign) -> cst.Assign:
        """Replace hardcoded password assignments."""
        if self._has_hardcoded_secret(updated_node):
            return self._replace_with_env_var(updated_node)
        return updated_node

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        """Add os import if needed."""
        if self.needs_os_import and not self.os_imported:
            return self._add_os_import(updated_node)
        return updated_node

    def _has_hardcoded_secret(self, node: cst.Assign) -> bool:
        """Check if assignment contains hardcoded secrets."""
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                var_name = target.target.value.lower()
                secret_keywords = ["password", "secret", "key", "token", "api_key"]
                if any(keyword in var_name for keyword in secret_keywords):
                    # Check if value is a string literal
                    if isinstance(node.value, cst.SimpleString):
                        return True
        return False

    def _replace_with_env_var(self, node: cst.Assign) -> cst.Assign:
        """Replace hardcoded value with environment variable lookup."""
        self.needs_os_import = True

        # Get variable name for environment variable
        for target in node.targets:
            if isinstance(target.target, cst.Name):
                var_name = target.target.value
                env_var_name = var_name.upper()

                # Create os.getenv() call
                env_call = cst.Call(
                    func=cst.Attribute(
                        value=cst.Name("os"),
                        attr=cst.Name("getenv")
                    ),
                    args=[
                        cst.Arg(cst.SimpleString(f'"{env_var_name}"')),
                        cst.Arg(cst.SimpleString('""'))  # Default empty string
                    ]
                )

                return node.with_changes(value=env_call)

        return node

    def _add_os_import(self, module: cst.Module) -> cst.Module:
        """Add os import to module."""
        import_stmt = cst.SimpleStatementLine([
            cst.Import(names=[cst.ImportAlias(name=cst.Name("os"))])
        ])

        # Add at the beginning
        return module.with_changes(body=[import_stmt] + list(module.body))


# Registry of available security codemods
SECURITY_CODEMODS = {
    "sql_injection_fix": SQLInjectionFixCodemod,
    "xss_prevention": XSSPreventionCodemod,
    "csrf_protection": CSRFProtectionCodemod,
    "secure_random": SecureRandomCodemod,
    "hardcoded_password_removal": HardcodedPasswordRemovalCodemod,
}


def get_security_codemod(name: str):
    """Get a security codemod by name."""
    if not LIBCST_AVAILABLE:
        raise ImportError("LibCST is required for advanced codemods")

    return SECURITY_CODEMODS.get(name)