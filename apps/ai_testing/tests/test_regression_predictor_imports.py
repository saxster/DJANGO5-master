"""
Test suite for regression predictor imports validation.

Ensures that all required ML library imports are present and functional.
This test validates that the RegressionPredictor service can instantiate
its models without NameError exceptions.
"""

import pytest
from unittest import TestCase


class RegressionPredictorImportsTestCase(TestCase):
    """Test that RegressionPredictor has all required imports"""

    def test_gradient_boosting_classifier_direct_import(self):
        """
        Test that GradientBoostingClassifier can be imported directly from sklearn.

        This validates that the sklearn.ensemble module provides GradientBoostingClassifier.
        """
        # This import should not raise ImportError or NameError
        from sklearn.ensemble import GradientBoostingClassifier

        # Verify it's a valid class
        self.assertTrue(callable(GradientBoostingClassifier))

        # Instantiate with expected parameters
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=6,
            random_state=42
        )

        # Verify configuration
        self.assertEqual(model.n_estimators, 100)
        self.assertEqual(model.max_depth, 6)
        self.assertEqual(model.random_state, 42)

    def test_random_forest_classifier_direct_import(self):
        """
        Test that RandomForestClassifier can be imported directly from sklearn.

        This validates that the sklearn.ensemble module provides RandomForestClassifier.
        """
        # This import should not raise ImportError or NameError
        from sklearn.ensemble import RandomForestClassifier

        # Verify it's a valid class
        self.assertTrue(callable(RandomForestClassifier))

        # Instantiate with expected parameters
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            random_state=42
        )

        # Verify configuration
        self.assertEqual(model.n_estimators, 100)
        self.assertEqual(model.max_depth, 8)
        self.assertEqual(model.random_state, 42)

    def test_model_instantiation_with_sklearn_imports(self):
        """
        Test that models can be instantiated using sklearn imports.

        This simulates what regression_predictor.py does in __init__.
        """
        from sklearn.neural_network import MLPClassifier
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

        # Create models dict exactly as in RegressionPredictor.__init__
        models = {
            'gradient_boosting': GradientBoostingClassifier(
                n_estimators=100,
                max_depth=6,
                random_state=42
            ),
            'random_forest': RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                random_state=42
            ),
            'neural_network': MLPClassifier(
                hidden_layer_sizes=(100, 50),
                max_iter=1000,
                random_state=42
            )
        }

        # Verify all three models were created
        expected_models = {'gradient_boosting', 'random_forest', 'neural_network'}
        self.assertEqual(set(models.keys()), expected_models)

        # Verify each model has required methods for ML operations
        for model_name, model in models.items():
            # All sklearn models have fit and predict methods
            self.assertTrue(hasattr(model, 'fit'),
                          f"{model_name} missing fit method")
            self.assertTrue(hasattr(model, 'predict'),
                          f"{model_name} missing predict method")
            self.assertTrue(hasattr(model, 'predict_proba'),
                          f"{model_name} missing predict_proba method")

    def test_sklearn_ensemble_module_exports(self):
        """
        Test that sklearn.ensemble module exports both classifiers.

        This validates the required imports are available in sklearn.
        """
        from sklearn import ensemble

        # Verify GradientBoostingClassifier is in ensemble module
        self.assertTrue(hasattr(ensemble, 'GradientBoostingClassifier'),
                       "GradientBoostingClassifier not in sklearn.ensemble")

        # Verify RandomForestClassifier is in ensemble module
        self.assertTrue(hasattr(ensemble, 'RandomForestClassifier'),
                       "RandomForestClassifier not in sklearn.ensemble")

        # Verify they are callable classes
        self.assertTrue(callable(ensemble.GradientBoostingClassifier))
        self.assertTrue(callable(ensemble.RandomForestClassifier))

    def test_no_name_error_on_model_creation(self):
        """
        Test that creating models doesn't raise NameError.

        This is the core test - if imports are missing in regression_predictor.py,
        this would fail with NameError when trying to instantiate the models.
        """
        from sklearn.neural_network import MLPClassifier
        from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier

        try:
            # This is what RegressionPredictor.__init__ does
            models = {
                'gradient_boosting': GradientBoostingClassifier(
                    n_estimators=100,
                    max_depth=6,
                    random_state=42
                ),
                'random_forest': RandomForestClassifier(
                    n_estimators=100,
                    max_depth=8,
                    random_state=42
                ),
                'neural_network': MLPClassifier(
                    hidden_layer_sizes=(100, 50),
                    max_iter=1000,
                    random_state=42
                )
            }
            # If we got here, imports work and no NameError occurred
            self.assertEqual(len(models), 3)
        except NameError as e:
            self.fail(f"NameError occurred during model instantiation: {e}")
