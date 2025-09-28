"""
Django introspection system for comprehensive analysis of Django components.

This introspector provides deep analysis of:
- Model introspection: Fields, relationships, managers, Meta options
- URL pattern analysis: Named groups, converters, included patterns
- View analysis: CBV/FBV detection, mixins, permissions
- Form/Serializer mapping: Field validation, model relationships
- Admin configuration: Registered models, custom actions
- Signal connections: Sender/receiver mapping
"""

import importlib
import inspect
import re
from dataclasses import dataclass

from django.apps import apps
from django.contrib import admin
from django.db import models
from django.forms import Form, ModelForm
from django.urls import URLResolver, URLPattern
from django.views import View
from django.views.generic import TemplateView
from rest_framework.viewsets import ViewSet

from django.db import transaction
from apps.mentor.models import IndexedFile, DjangoURL, DjangoModel


@dataclass
class ModelInfo:
    """Container for Django model information."""
    name: str
    app_label: str
    fields: Dict[str, Any]
    relationships: List[Dict[str, Any]]
    managers: List[str]
    meta_options: Dict[str, Any]
    methods: List[str]
    properties: List[str]
    db_table: str
    file_path: str
    line_number: int


@dataclass
class ViewInfo:
    """Container for Django view information."""
    name: str
    type: str  # 'function', 'class', 'generic'
    base_classes: List[str]
    mixins: List[str]
    permissions: List[str]
    decorators: List[str]
    template_name: Optional[str]
    model: Optional[str]
    serializer_class: Optional[str]
    file_path: str
    line_number: int


@dataclass
class URLInfo:
    """Container for URL pattern information."""
    pattern: str
    name: Optional[str]
    view_name: str
    view_type: str
    namespace: Optional[str]
    app_name: Optional[str]
    methods: List[str]
    parameters: List[str]
    converters: Dict[str, str]
    file_path: str
    line_number: int


@dataclass
class FormInfo:
    """Container for Django form information."""
    name: str
    type: str  # 'form', 'model_form'
    model: Optional[str]
    fields: List[str]
    widgets: Dict[str, str]
    validators: Dict[str, List[str]]
    file_path: str
    line_number: int


@dataclass
class AdminInfo:
    """Container for Django admin configuration."""
    model_name: str
    admin_class: str
    list_display: List[str]
    list_filter: List[str]
    search_fields: List[str]
    actions: List[str]
    inlines: List[str]
    readonly_fields: List[str]
    file_path: str
    line_number: int


class DjangoIntrospector:
    """Comprehensive Django application introspector."""

    def __init__(self):
        self.models_info: List[ModelInfo] = []
        self.views_info: List[ViewInfo] = []
        self.urls_info: List[URLInfo] = []
        self.forms_info: List[FormInfo] = []
        self.admin_info: List[AdminInfo] = []
        self.signals_info: List[Dict[str, Any]] = []

    def introspect_django_app(self, app_name: str) -> Dict[str, int]:
        """Introspect a specific Django app."""
        try:
            app_config = apps.get_app_config(app_name)

            # Introspect models
            self._introspect_models(app_config)

            # Introspect views
            self._introspect_views(app_config)

            # Introspect URLs
            self._introspect_urls(app_config)

            # Introspect forms
            self._introspect_forms(app_config)

            # Introspect admin
            self._introspect_admin(app_config)

            # Introspect signals
            self._introspect_signals(app_config)

            return {
                'models': len(self.models_info),
                'views': len(self.views_info),
                'urls': len(self.urls_info),
                'forms': len(self.forms_info),
                'admin': len(self.admin_info),
                'signals': len(self.signals_info),
            }

        except (ValueError, TypeError) as e:
            print(f"Error introspecting app {app_name}: {e}")
            return {'error': 1}

    def introspect_all_apps(self) -> Dict[str, Any]:
        """Introspect all Django apps."""
        results = {}

        for app_config in apps.get_app_configs():
            if not app_config.name.startswith('django.'):
                app_results = self.introspect_django_app(app_config.name)
                results[app_config.name] = app_results

        return results

    def _introspect_models(self, app_config):
        """Introspect Django models in the app."""
        for model_class in app_config.get_models():
            try:
                model_info = self._analyze_model(model_class)
                self.models_info.append(model_info)
            except (ValueError, TypeError) as e:
                print(f"Error analyzing model {model_class.__name__}: {e}")

    def _analyze_model(self, model_class) -> ModelInfo:
        """Analyze a Django model class."""
        # Basic info
        name = model_class.__name__
        app_label = model_class._meta.app_label

        # Fields analysis
        fields = {}
        relationships = []

        for field in model_class._meta.get_fields():
            field_info = self._analyze_field(field)
            fields[field.name] = field_info

            # Check for relationships
            if hasattr(field, 'related_model') and field.related_model:
                relationship = {
                    'field_name': field.name,
                    'type': field.__class__.__name__,
                    'related_model': f"{field.related_model._meta.app_label}.{field.related_model.__name__}",
                    'related_name': getattr(field, 'related_name', None),
                    'on_delete': getattr(field, 'on_delete', None).__name__ if hasattr(field, 'on_delete') else None,
                }
                relationships.append(relationship)

        # Managers
        managers = [name for name, manager in model_class._meta.managers_map.items()]

        # Meta options
        meta_options = self._extract_meta_options(model_class._meta)

        # Methods and properties
        methods = []
        properties = []

        for attr_name in dir(model_class):
            if not attr_name.startswith('_'):
                attr = getattr(model_class, attr_name)
                if callable(attr) and not isinstance(attr, type):
                    methods.append(attr_name)
                elif isinstance(attr, property):
                    properties.append(attr_name)

        # File location
        file_path = inspect.getfile(model_class)
        line_number = self._get_class_line_number(model_class)

        return ModelInfo(
            name=name,
            app_label=app_label,
            fields=fields,
            relationships=relationships,
            managers=managers,
            meta_options=meta_options,
            methods=methods,
            properties=properties,
            db_table=model_class._meta.db_table,
            file_path=file_path,
            line_number=line_number
        )

    def _analyze_field(self, field) -> Dict[str, Any]:
        """Analyze a Django model field."""
        field_info = {
            'type': field.__class__.__name__,
            'null': getattr(field, 'null', False),
            'blank': getattr(field, 'blank', False),
            'unique': getattr(field, 'unique', False),
            'db_index': getattr(field, 'db_index', False),
            'primary_key': getattr(field, 'primary_key', False),
            'max_length': getattr(field, 'max_length', None),
            'default': self._serialize_default(getattr(field, 'default', models.NOT_PROVIDED)),
            'choices': getattr(field, 'choices', None),
            'help_text': getattr(field, 'help_text', ''),
            'verbose_name': getattr(field, 'verbose_name', ''),
        }

        # Field-specific attributes
        if hasattr(field, 'upload_to'):
            field_info['upload_to'] = str(field.upload_to)

        if hasattr(field, 'decimal_places'):
            field_info['decimal_places'] = field.decimal_places
            field_info['max_digits'] = field.max_digits

        return field_info

    def _extract_meta_options(self, meta) -> Dict[str, Any]:
        """Extract Meta class options."""
        options = {}

        meta_attrs = [
            'verbose_name', 'verbose_name_plural', 'ordering', 'get_latest_by',
            'abstract', 'proxy', 'managed', 'unique_together', 'index_together',
            'constraints', 'indexes', 'permissions', 'default_permissions',
            'select_on_save', 'default_related_name'
        ]

        for attr in meta_attrs:
            if hasattr(meta, attr):
                value = getattr(meta, attr)
                if value is not None:
                    options[attr] = self._serialize_meta_value(value)

        return options

    def _serialize_default(self, default):
        """Serialize field default value."""
        if default is models.NOT_PROVIDED:
            return None
        elif callable(default):
            return f"<callable: {default.__name__}>"
        else:
            return str(default)

    def _serialize_meta_value(self, value):
        """Serialize Meta option value."""
        if isinstance(value, (list, tuple)):
            return list(value)
        elif callable(value):
            return f"<callable: {value.__name__}>"
        else:
            return str(value)

    def _get_class_line_number(self, cls) -> int:
        """Get line number where class is defined."""
        try:
            return inspect.getsourcelines(cls)[1]
        except:
            return 1

    def _introspect_views(self, app_config):
        """Introspect Django views in the app."""
        views_module = f"{app_config.name}.views"

        try:
            module = importlib.import_module(views_module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                # Check if it's a view
                if self._is_view(attr):
                    view_info = self._analyze_view(attr, attr_name, module)
                    self.views_info.append(view_info)

        except ImportError:
            # No views module
            pass
        except (ValueError, TypeError) as e:
            print(f"Error introspecting views in {app_config.name}: {e}")

    def _is_view(self, obj) -> bool:
        """Check if object is a Django view."""
        if inspect.isfunction(obj):
            # Function-based view
            return hasattr(obj, '__annotations__') or 'request' in str(inspect.signature(obj))
        elif inspect.isclass(obj):
            # Class-based view
            return issubclass(obj, View) or hasattr(obj, 'as_view')
        return False

    def _analyze_view(self, view, name: str, module) -> ViewInfo:
        """Analyze a Django view."""
        if inspect.isfunction(view):
            return self._analyze_function_view(view, name, module)
        elif inspect.isclass(view):
            return self._analyze_class_view(view, name, module)

    def _analyze_function_view(self, view_func, name: str, module) -> ViewInfo:
        """Analyze function-based view."""
        # Extract decorators from source
        decorators = self._extract_decorators_from_source(view_func)

        # Extract permissions
        permissions = self._extract_permissions_from_decorators(decorators)

        return ViewInfo(
            name=name,
            type='function',
            base_classes=[],
            mixins=[],
            permissions=permissions,
            decorators=decorators,
            template_name=None,
            model=None,
            serializer_class=None,
            file_path=inspect.getfile(module),
            line_number=self._get_function_line_number(view_func)
        )

    def _analyze_class_view(self, view_class, name: str, module) -> ViewInfo:
        """Analyze class-based view."""
        # Base classes and mixins
        base_classes = [base.__name__ for base in view_class.__bases__]
        mixins = [base.__name__ for base in view_class.__bases__ if 'Mixin' in base.__name__]

        # Template name
        template_name = getattr(view_class, 'template_name', None)

        # Model
        model = getattr(view_class, 'model', None)
        model_name = f"{model._meta.app_label}.{model.__name__}" if model else None

        # Serializer class (for DRF views)
        serializer_class = getattr(view_class, 'serializer_class', None)
        serializer_name = serializer_class.__name__ if serializer_class else None

        # Permissions
        permission_classes = getattr(view_class, 'permission_classes', [])
        permissions = [perm.__name__ for perm in permission_classes if hasattr(perm, '__name__')]

        # Determine view type
        view_type = 'class'
        if issubclass(view_class, TemplateView):
            view_type = 'generic'
        elif issubclass(view_class, ViewSet):
            view_type = 'viewset'

        return ViewInfo(
            name=name,
            type=view_type,
            base_classes=base_classes,
            mixins=mixins,
            permissions=permissions,
            decorators=[],
            template_name=template_name,
            model=model_name,
            serializer_class=serializer_name,
            file_path=inspect.getfile(module),
            line_number=self._get_class_line_number(view_class)
        )

    def _extract_decorators_from_source(self, func) -> List[str]:
        """Extract decorators from function source code."""
        try:
            source_lines = inspect.getsourcelines(func)[0]
            decorators = []

            for line in source_lines:
                line = line.strip()
                if line.startswith('@'):
                    decorator = line[1:].split('(')[0]  # Remove parameters
                    decorators.append(decorator)
                elif line.startswith('def '):
                    break

            return decorators
        except:
            return []

    def _extract_permissions_from_decorators(self, decorators: List[str]) -> List[str]:
        """Extract permissions from decorators."""
        permission_decorators = [
            'login_required', 'permission_required', 'user_passes_test',
            'staff_member_required', 'superuser_required'
        ]

        return [dec for dec in decorators if any(perm in dec for perm in permission_decorators)]

    def _get_function_line_number(self, func) -> int:
        """Get line number where function is defined."""
        try:
            return inspect.getsourcelines(func)[1]
        except:
            return 1

    def _introspect_urls(self, app_config):
        """Introspect URL patterns in the app."""
        urls_module = f"{app_config.name}.urls"

        try:
            module = importlib.import_module(urls_module)

            if hasattr(module, 'urlpatterns'):
                self._analyze_urlpatterns(
                    module.urlpatterns,
                    inspect.getfile(module),
                    app_config.name
                )

        except ImportError:
            # No urls module
            pass
        except (ValueError, TypeError) as e:
            print(f"Error introspecting URLs in {app_config.name}: {e}")

    def _analyze_urlpatterns(self, urlpatterns: List, file_path: str, app_name: str):
        """Analyze URL patterns recursively."""
        for i, pattern in enumerate(urlpatterns):
            try:
                if isinstance(pattern, URLPattern):
                    url_info = self._analyze_url_pattern(pattern, file_path, app_name, i + 1)
                    self.urls_info.append(url_info)
                elif isinstance(pattern, URLResolver):
                    # Recursively analyze included URLs
                    if hasattr(pattern, 'url_patterns'):
                        self._analyze_urlpatterns(
                            pattern.url_patterns,
                            file_path,
                            pattern.app_name or app_name
                        )
            except (ValueError, TypeError) as e:
                print(f"Error analyzing URL pattern {i}: {e}")

    def _analyze_url_pattern(self, pattern: URLPattern, file_path: str, app_name: str, line_num: int) -> URLInfo:
        """Analyze a single URL pattern."""
        # Pattern string
        pattern_str = pattern.pattern._regex.pattern if hasattr(pattern.pattern, '_regex') else str(pattern.pattern)

        # View name
        view_name = self._extract_view_name(pattern.callback)

        # View type
        view_type = self._determine_view_type(pattern.callback)

        # HTTP methods
        methods = self._extract_http_methods(pattern.callback)

        # Parameters and converters
        parameters, converters = self._extract_url_parameters(pattern_str)

        return URLInfo(
            pattern=pattern_str,
            name=pattern.name,
            view_name=view_name,
            view_type=view_type,
            namespace=None,  # TODO: Extract namespace
            app_name=app_name,
            methods=methods,
            parameters=parameters,
            converters=converters,
            file_path=file_path,
            line_number=line_num
        )

    def _extract_view_name(self, callback) -> str:
        """Extract view name from callback."""
        if hasattr(callback, 'view_class'):
            return callback.view_class.__name__
        elif hasattr(callback, '__name__'):
            return callback.__name__
        else:
            return str(callback)

    def _determine_view_type(self, callback) -> str:
        """Determine view type."""
        if hasattr(callback, 'view_class'):
            return 'class'
        elif callable(callback):
            return 'function'
        else:
            return 'unknown'

    def _extract_http_methods(self, callback) -> List[str]:
        """Extract allowed HTTP methods."""
        if hasattr(callback, 'view_class'):
            # Class-based view
            view_class = callback.view_class
            if hasattr(view_class, 'http_method_names'):
                return list(view_class.http_method_names)

        # Default methods
        return ['GET', 'POST']

    def _extract_url_parameters(self, pattern_str: str) -> Tuple[List[str], Dict[str, str]]:
        """Extract parameters and converters from URL pattern."""
        parameters = []
        converters = {}

        # Find named groups
        named_groups = re.findall(r'\(\?P<(\w+)>', pattern_str)
        parameters.extend(named_groups)

        # Find converter patterns (Django 2.0+)
        converter_pattern = r'<(\w+):(\w+)>'
        converter_matches = re.findall(converter_pattern, pattern_str)

        for converter, param in converter_matches:
            parameters.append(param)
            converters[param] = converter

        return parameters, converters

    def _introspect_forms(self, app_config):
        """Introspect Django forms in the app."""
        forms_module = f"{app_config.name}.forms"

        try:
            module = importlib.import_module(forms_module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if self._is_form(attr):
                    form_info = self._analyze_form(attr, attr_name, module)
                    self.forms_info.append(form_info)

        except ImportError:
            pass
        except (ValueError, TypeError) as e:
            print(f"Error introspecting forms in {app_config.name}: {e}")

    def _is_form(self, obj) -> bool:
        """Check if object is a Django form."""
        if inspect.isclass(obj):
            return issubclass(obj, Form) and obj is not Form
        return False

    def _analyze_form(self, form_class, name: str, module) -> FormInfo:
        """Analyze a Django form."""
        # Form type
        form_type = 'model_form' if issubclass(form_class, ModelForm) else 'form'

        # Model (for ModelForm)
        model = None
        if hasattr(form_class, '_meta') and hasattr(form_class._meta, 'model'):
            model_class = form_class._meta.model
            model = f"{model_class._meta.app_label}.{model_class.__name__}"

        # Fields
        fields = []
        if hasattr(form_class, '_meta') and hasattr(form_class._meta, 'fields'):
            if form_class._meta.fields == '__all__':
                # Get all model fields
                if form_class._meta.model:
                    fields = [f.name for f in form_class._meta.model._meta.get_fields()]
            else:
                fields = list(form_class._meta.fields or [])

        # Declared fields
        declared_fields = []
        for attr_name in dir(form_class):
            attr = getattr(form_class, attr_name)
            if hasattr(attr, '__class__') and 'Field' in attr.__class__.__name__:
                declared_fields.append(attr_name)

        fields.extend(declared_fields)

        return FormInfo(
            name=name,
            type=form_type,
            model=model,
            fields=fields,
            widgets={},  # TODO: Extract widgets
            validators={},  # TODO: Extract validators
            file_path=inspect.getfile(module),
            line_number=self._get_class_line_number(form_class)
        )

    def _introspect_admin(self, app_config):
        """Introspect Django admin configuration."""
        admin_module = f"{app_config.name}.admin"

        try:
            module = importlib.import_module(admin_module)

            # Get registered models
            for model, admin_class in admin.site._registry.items():
                if model._meta.app_label == app_config.name:
                    admin_info = self._analyze_admin(model, admin_class, module)
                    self.admin_info.append(admin_info)

        except ImportError:
            pass
        except (ValueError, TypeError) as e:
            print(f"Error introspecting admin in {app_config.name}: {e}")

    def _analyze_admin(self, model, admin_class, module) -> AdminInfo:
        """Analyze Django admin configuration."""
        return AdminInfo(
            model_name=f"{model._meta.app_label}.{model.__name__}",
            admin_class=admin_class.__class__.__name__,
            list_display=list(getattr(admin_class, 'list_display', [])),
            list_filter=list(getattr(admin_class, 'list_filter', [])),
            search_fields=list(getattr(admin_class, 'search_fields', [])),
            actions=[action.__name__ for action in getattr(admin_class, 'actions', []) if callable(action)],
            inlines=[inline.__name__ for inline in getattr(admin_class, 'inlines', [])],
            readonly_fields=list(getattr(admin_class, 'readonly_fields', [])),
            file_path=inspect.getfile(module),
            line_number=self._get_class_line_number(admin_class.__class__)
        )

    def _introspect_signals(self, app_config):
        """Introspect Django signals."""
        # This is more complex as signals can be defined anywhere
        # For now, we'll look for signals.py module
        signals_module = f"{app_config.name}.signals"

        try:
            module = importlib.import_module(signals_module)

            # Look for signal connections (this is a simplified approach)
            for attr_name in dir(module):
                attr = getattr(module, attr_name)

                if hasattr(attr, '__name__') and 'receiver' in str(attr):
                    signal_info = {
                        'name': attr_name,
                        'file_path': inspect.getfile(module),
                        'line_number': self._get_function_line_number(attr) if callable(attr) else 1
                    }
                    self.signals_info.append(signal_info)

        except ImportError:
            pass
        except (ValueError, TypeError) as e:
            print(f"Error introspecting signals in {app_config.name}: {e}")

    def save_to_database(self) -> Dict[str, int]:
        """Save introspected data to database."""
        stats = {'models_saved': 0, 'urls_saved': 0, 'errors': 0}

        try:
            with transaction.atomic():
                # Save models
                for model_info in self.models_info:
                    try:
                        # Get or create indexed file
                        indexed_file, _ = IndexedFile.objects.get_or_create(
                            path=model_info.file_path,
                            defaults={
                                'sha': 'unknown',
                                'mtime': 0,
                                'size': 0,
                                'language': 'python'
                            }
                        )

                        # Save model
                        DjangoModel.objects.update_or_create(
                            app_label=model_info.app_label,
                            model_name=model_info.name,
                            defaults={
                                'fields': model_info.fields,
                                'db_table': model_info.db_table,
                                'meta_options': model_info.meta_options,
                                'file': indexed_file,
                                'line_number': model_info.line_number,
                            }
                        )
                        stats['models_saved'] += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving model {model_info.name}: {e}")
                        stats['errors'] += 1

                # Save URLs
                for url_info in self.urls_info:
                    try:
                        # Get or create indexed file
                        indexed_file, _ = IndexedFile.objects.get_or_create(
                            path=url_info.file_path,
                            defaults={
                                'sha': 'unknown',
                                'mtime': 0,
                                'size': 0,
                                'language': 'python'
                            }
                        )

                        # Save URL
                        DjangoURL.objects.update_or_create(
                            route=url_info.pattern,
                            view_name=url_info.view_name,
                            defaults={
                                'name': url_info.name,
                                'methods': url_info.methods,
                                'permissions': [],  # TODO: Extract permissions
                                'app_label': url_info.app_name,
                                'file': indexed_file,
                                'line_number': url_info.line_number,
                            }
                        )
                        stats['urls_saved'] += 1

                    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                        print(f"Error saving URL {url_info.pattern}: {e}")
                        stats['errors'] += 1

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            print(f"Database transaction error: {e}")
            stats['errors'] += 1

        return stats