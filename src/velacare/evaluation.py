"""Leakage-safe candidate evaluation and final hold-out assessment."""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def split_dataset(X: np.ndarray, y: np.ndarray, seed: int):
    """Create a stratified 80/20 split; only the 80% training side feeds CV."""
    return train_test_split(
        X,
        y,
        test_size=0.2,
        stratify=y,
        random_state=seed,
    )


def classifier(seed: int) -> LogisticRegression:
    return LogisticRegression(
        solver="liblinear",
        class_weight="balanced",
        C=1.0,
        max_iter=500,
        random_state=seed,
    )


def pipeline(seed: int):
    # Scaling is fit independently inside each training fold / final training set.
    return make_pipeline(StandardScaler(), classifier(seed))


def _metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    # Matrix order is actual/predicted [malignant, benign].
    matrix = confusion_matrix(y_true, y_pred, labels=[1, 0])
    tp, fn = (int(value) for value in matrix[0])
    fp, tn = (int(value) for value in matrix[1])
    malignant_sensitivity = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "malignant_sensitivity": float(malignant_sensitivity),
        "specificity": float(specificity),
        "f1_malignant": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_labels": ["malignant", "benign"],
    }


def evaluate_cross_validation(
    chromosome: np.ndarray,
    X_train: np.ndarray,
    y_train: np.ndarray,
    *,
    seed: int,
    folds: int = 3,
) -> dict:
    """Evaluate out-of-fold predictions using only the training partition."""
    indices = np.flatnonzero(chromosome)
    if indices.size == 0:
        raise ValueError("A candidate must select at least one feature.")
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed)
    predictions = np.empty_like(y_train)
    for train_indices, validation_indices in splitter.split(X_train, y_train):
        model = pipeline(seed)
        model.fit(X_train[train_indices][:, indices], y_train[train_indices])
        predictions[validation_indices] = model.predict(X_train[validation_indices][:, indices])
    return _metrics(y_train, predictions)


def evaluate_holdout(
    chromosome: np.ndarray,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    *,
    seed: int,
) -> dict:
    """Fit the chosen feature subset once and score the untouched test split."""
    indices = np.flatnonzero(chromosome)
    if indices.size == 0:
        raise ValueError("A candidate must select at least one feature.")
    model = pipeline(seed)
    model.fit(X_train[:, indices], y_train)
    return _metrics(y_test, model.predict(X_test[:, indices]))


def fitness_from_cv(metrics: dict, feature_count: int, total_features: int = 30) -> tuple[float, dict]:
    """Sensitivity-focused quality score with a small linear complexity cost.

    fitness = 0.60 * malignant sensitivity + 0.40 * balanced accuracy
              - 0.02 * selected_features / total_features
    """
    quality = 0.60 * metrics["malignant_sensitivity"] + 0.40 * metrics["balanced_accuracy"]
    complexity_penalty = 0.02 * feature_count / total_features
    return float(quality - complexity_penalty), {
        "quality_component": float(quality),
        "malignant_sensitivity_component": float(0.60 * metrics["malignant_sensitivity"]),
        "balanced_accuracy_component": float(0.40 * metrics["balanced_accuracy"]),
        "complexity_penalty": float(complexity_penalty),
    }
