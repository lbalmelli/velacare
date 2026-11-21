import numpy as np

import velacare.evaluation as evaluation


def test_cross_validation_never_sees_held_out_rows(monkeypatch):
    row_ids = np.arange(180, dtype=float)
    X = np.column_stack([row_ids, np.column_stack([row_ids ** power for power in range(2, 31)])])
    y = np.tile(np.array([0, 1], dtype=np.int8), 90)
    X_train, X_test, y_train, y_test = evaluation.split_dataset(X, y, seed=13)
    training_ids = set(X_train[:, 0].tolist())
    held_out_ids = set(X_test[:, 0].tolist())
    assert training_ids.isdisjoint(held_out_ids)

    fit_rows = []
    predict_rows = []

    class SpyPipeline:
        def fit(self, matrix, labels):
            fit_rows.append(set(matrix[:, 0].tolist()))
            assert len(matrix) == len(labels)
            return self

        def predict(self, matrix):
            predict_rows.append(set(matrix[:, 0].tolist()))
            return np.zeros(len(matrix), dtype=np.int8)

    monkeypatch.setattr(evaluation, "pipeline", lambda _seed: SpyPipeline())
    chromosome = np.zeros(30, dtype=np.uint8)
    chromosome[0] = 1

    evaluation.evaluate_cross_validation(chromosome, X_train, y_train, seed=13, folds=3)
    assert fit_rows and predict_rows
    assert all(rows <= training_ids for rows in fit_rows + predict_rows)
    assert all(not rows.intersection(held_out_ids) for rows in fit_rows + predict_rows)

    fit_rows.clear()
    predict_rows.clear()
    evaluation.evaluate_holdout(chromosome, X_train, y_train, X_test, y_test, seed=13)
    assert fit_rows == [training_ids]
    assert predict_rows == [held_out_ids]
