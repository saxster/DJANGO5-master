# ML Model Storage

This directory stores trained fraud detection models.

## Model Files

Models are stored as joblib-serialized `.pkl` files with versioning:
- `fraud_model_v1.pkl` - Version 1
- `fraud_model_v2.pkl` - Version 2
- etc.

## Version Management

- Keep last 3 model versions
- Version increments on successful training
- Older versions automatically cleaned up

## Model Metrics

Performance metrics stored in `apps.noc.models.MLModelMetrics`:
- Precision, Recall, F1 Score
- Training sample count
- Training date
- Active status

## Usage

```python
from apps.noc.security_intelligence.ml.local_ml_engine import LocalMLEngine

# Predict fraud probability
features = {...}  # 12-feature dict
probability = LocalMLEngine.predict_fraud_probability(features)
```

## Training

Models trained weekly via Celery task:
- Task: `apps.noc.tasks.ml_training_tasks.TrainFraudModelTask`
- Schedule: Sunday 2 AM
- Queue: ml_queue
- Minimum samples: 500 labeled records

## Security

- Models are not committed to git (.gitignore)
- Only trained on production data
- Validated against thresholds before activation
